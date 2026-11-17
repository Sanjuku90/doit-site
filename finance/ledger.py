"""Internal USD-cent journal. Not connected to the public web app or any blockchain.

Posting keys and transaction digest make retries idempotent. All operations require
an explicit authorized caller; never expose these functions directly to web requests.
Each posting set is balanced and persisted under a PostgreSQL advisory lock. A signed value is
an accounting position, not evidence of cash or a customer withdrawal entitlement.
"""
import hashlib, json, re
import postgres_compat as sqlite3
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_EVEN

MAX_CENTS=10**13
ACCOUNT_RE=re.compile(r'^[a-z][a-z0-9:_-]{1,100}$')
KEY_RE=re.compile(r'^[A-Za-z0-9:_.-]{1,128}$')

def cents(value):
 if isinstance(value,bool) or not isinstance(value,int) or not 0<value<=MAX_CENTS: raise ValueError('montant en centimes invalide')
 return value

def timestamp():return datetime.now(timezone.utc).isoformat()
def open_db(path):
 c=sqlite3.connect(path,timeout=10);return c

def migrate(path):
 with open_db(path) as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS fin_accounts(code TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK(kind IN ('controlled','external')), created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS fin_transactions(id INTEGER PRIMARY KEY, idem_key TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, digest TEXT NOT NULL, created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS fin_postings(id INTEGER PRIMARY KEY, transaction_id INTEGER NOT NULL REFERENCES fin_transactions(id), account TEXT NOT NULL REFERENCES fin_accounts(code), amount INTEGER NOT NULL CHECK(amount<>0));
  CREATE INDEX IF NOT EXISTS fin_postings_account ON fin_postings(account);
  CREATE TRIGGER IF NOT EXISTS fin_postings_no_update BEFORE UPDATE ON fin_postings BEGIN SELECT RAISE(ABORT,'immutable posting'); END;
  CREATE TRIGGER IF NOT EXISTS fin_postings_no_delete BEFORE DELETE ON fin_postings BEGIN SELECT RAISE(ABORT,'immutable posting'); END;
  CREATE TRIGGER IF NOT EXISTS fin_tx_no_update BEFORE UPDATE ON fin_transactions BEGIN SELECT RAISE(ABORT,'immutable transaction'); END;
  CREATE TRIGGER IF NOT EXISTS fin_tx_no_delete BEFORE DELETE ON fin_transactions BEGIN SELECT RAISE(ABORT,'immutable transaction'); END;
  CREATE TABLE IF NOT EXISTS fin_withdrawals(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),status TEXT NOT NULL CHECK(status IN ('reserved','rejected','paid')),created_at TEXT NOT NULL,updated_at TEXT NOT NULL, payout_txid TEXT UNIQUE);
  CREATE TABLE IF NOT EXISTS fin_investments(id TEXT PRIMARY KEY,user_id INTEGER NOT NULL,amount INTEGER NOT NULL CHECK(amount>0),rate_bps INTEGER NOT NULL CHECK(rate_bps BETWEEN 0 AND 10000),duration_seconds INTEGER NOT NULL CHECK(duration_seconds>0),starts_at INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('active','settled')),created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS fin_investment_uplines(investment_id TEXT NOT NULL REFERENCES fin_investments(id),level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),user_id INTEGER NOT NULL,commission_bps INTEGER NOT NULL CHECK(commission_bps BETWEEN 0 AND 10000),PRIMARY KEY(investment_id,level),UNIQUE(investment_id,user_id));
  ''')

def valid_key(k):
 if not isinstance(k,str) or not KEY_RE.fullmatch(k):raise ValueError('identifiant invalide')
 return k

def user_id(uid):
 if isinstance(uid,bool) or not isinstance(uid,int) or uid<=0:raise ValueError('utilisateur invalide')
 return uid

def account(c,code,kind='controlled'):
 if not ACCOUNT_RE.fullmatch(code):raise ValueError('compte invalide')
 c.execute('INSERT OR IGNORE INTO fin_accounts(code,kind,created_at) VALUES(?,?,?)',(code,kind,timestamp()))
 row=c.execute('SELECT kind FROM fin_accounts WHERE code=?',(code,)).fetchone()
 if row['kind']!=kind:raise ValueError('type de compte différent')

def balance(c,code):return c.execute('SELECT COALESCE(SUM(amount),0) FROM fin_postings WHERE account=?',(code,)).fetchone()[0]

def post(c,key,kind,lines):
 valid_key(key);valid_key(kind)
 if len(lines)<2 or any(not isinstance(n,int) or isinstance(n,bool) or not n or abs(n)>MAX_CENTS for _,n in lines):raise ValueError('écritures invalides')
 if sum(n for _,n in lines)!=0:raise ValueError('écritures déséquilibrées')
 if len(set(a for a,_ in lines))!=len(lines):raise ValueError('comptes répétés')
 digest=hashlib.sha256(json.dumps([kind,sorted(lines)],separators=(',',':')).encode()).hexdigest()
 prior=c.execute('SELECT id,digest FROM fin_transactions WHERE idem_key=?',(key,)).fetchone()
 if prior:
  if prior['digest']!=digest:raise ValueError('clé déjà utilisée pour une autre opération')
  return prior['id'],False
 for name,amount in lines:
  row=c.execute('SELECT kind FROM fin_accounts WHERE code=?',(name,)).fetchone()
  if not row:raise ValueError('compte introuvable')
  if row['kind']=='controlled' and balance(c,name)+amount<0:raise ValueError('fonds insuffisants')
 tid=c.execute('INSERT INTO fin_transactions(idem_key,kind,digest,created_at) VALUES(?,?,?,?)',(key,kind,digest,timestamp())).lastrowid
 c.executemany('INSERT INTO fin_postings(transaction_id,account,amount) VALUES(?,?,?)',[(tid,a,n) for a,n in lines])
 return tid,True

LEDGER_LOCK_KEY=727001  # verrou consultatif PostgreSQL : sérialise les écritures du registre (remplace BEGIN IMMEDIATE)
def atomic(path,action):
 c=open_db(path)
 try:
  c.execute('SELECT pg_advisory_xact_lock(?)',(LEDGER_LOCK_KEY,));result=action(c);c.commit();return result
 except Exception:
  c.rollback();raise
 finally:c.close()

def setup_user(c,uid):
 user_id(uid)
 for kind in ('available','invested','reserved'):account(c,f'user:{uid}:{kind}')
def system(c):
 account(c,'external:custody','external');account(c,'external:operator','external');account(c,'external:payout','external');account(c,'platform:profit_reserve')

# PRIVILEGED integration boundary: caller must independently verify deposit/reconciliation.
# These methods do not query TRON, identify USDT, verify confirmations, KYC or custody.
def book_verified_deposit(path,user,amount,event_key):
 user_id(user);cents(amount);valid_key(event_key)
 def action(c):
  system(c);setup_user(c,user)
  return post(c,'deposit:'+event_key,'deposit',[('external:custody',-amount),(f'user:{user}:available',amount)])
 return atomic(path,action)

def book_verified_operator_funding(path,amount,funding_key):
 cents(amount);valid_key(funding_key)
 def action(c):
  system(c)
  return post(c,'funding:'+funding_key,'funding',[('external:operator',-amount),('platform:profit_reserve',amount)])
 return atomic(path,action)

def reserve_withdrawal(path,user,amount,withdrawal_id):
 user_id(user);cents(amount);valid_key(withdrawal_id)
 def action(c):
  system(c);setup_user(c,user)
  row=c.execute('SELECT user_id,amount FROM fin_withdrawals WHERE id=?',(withdrawal_id,)).fetchone()
  if row:
   if row['user_id']!=user or row['amount']!=amount:raise ValueError('demande déjà utilisée')
   return False
  post(c,'withdraw-reserve:'+withdrawal_id,'withdraw_reserve',[(f'user:{user}:available',-amount),(f'user:{user}:reserved',amount)])
  now=timestamp();c.execute('INSERT INTO fin_withdrawals VALUES(?,?,?,?,?,?,NULL)',(withdrawal_id,user,amount,'reserved',now,now));return True
 return atomic(path,action)

def reject_withdrawal(path,withdrawal_id):
 valid_key(withdrawal_id)
 def action(c):
  row=c.execute('SELECT * FROM fin_withdrawals WHERE id=?',(withdrawal_id,)).fetchone()
  if not row:raise ValueError('demande introuvable')
  if row['status']=='rejected':return False
  if row['status']!='reserved':raise ValueError('demande non remboursable')
  uid=row['user_id'];amount=row['amount']
  post(c,'withdraw-reject:'+withdrawal_id,'withdraw_reject',[(f'user:{uid}:reserved',-amount),(f'user:{uid}:available',amount)])
  c.execute('UPDATE fin_withdrawals SET status=?,updated_at=? WHERE id=?',('rejected',timestamp(),withdrawal_id));return True
 return atomic(path,action)

# Caller must independently verify actual payout before invoking; no TRON implementation here.
def book_verified_payout(path,withdrawal_id,txid):
 valid_key(withdrawal_id);valid_key(txid)
 def action(c):
  row=c.execute('SELECT * FROM fin_withdrawals WHERE id=?',(withdrawal_id,)).fetchone()
  if not row:raise ValueError('demande introuvable')
  if row['status']=='paid':
   if row['payout_txid']!=txid:raise ValueError('TXID différent')
   return False
  if row['status']!='reserved':raise ValueError('demande non payable')
  system(c);uid=row['user_id'];amount=row['amount']
  post(c,'withdraw-paid:'+withdrawal_id,'withdraw_paid',[(f'user:{uid}:reserved',-amount),('external:payout',amount)])
  c.execute('UPDATE fin_withdrawals SET status=?,updated_at=?,payout_txid=? WHERE id=?',('paid',timestamp(),txid,withdrawal_id));return True
 return atomic(path,action)

def start_investment(path,user,amount,rate_bps,duration_seconds,starts_at,investment_id,uplines):
 user_id(user);cents(amount);valid_key(investment_id)
 if any(isinstance(x,bool) or not isinstance(x,int) for x in (rate_bps,duration_seconds,starts_at)) or not 0<=rate_bps<=10000 or not 1<=duration_seconds<=10*365*86400 or starts_at<0:raise ValueError('paramètres invalides')
 if not isinstance(uplines,list) or len(uplines)>5:raise ValueError('parrainage invalide')
 seen=set()
 for u,bps in uplines:
  user_id(u)
  if u==user or u in seen or isinstance(bps,bool) or not isinstance(bps,int) or not 0<=bps<=10000:raise ValueError('parrainage invalide')
  seen.add(u)
 if sum(b for _,b in uplines)>10000:raise ValueError('commissions excessives')
 def action(c):
  existing=c.execute('SELECT * FROM fin_investments WHERE id=?',(investment_id,)).fetchone()
  if existing:
   existing_u=[(r['user_id'],r['commission_bps']) for r in c.execute('SELECT user_id,commission_bps FROM fin_investment_uplines WHERE investment_id=? ORDER BY level',(investment_id,))]
   if (existing['user_id'],existing['amount'],existing['rate_bps'],existing['duration_seconds'],existing['starts_at'],existing_u)!=(user,amount,rate_bps,duration_seconds,starts_at,uplines):raise ValueError('investissement déjà utilisé')
   return False
  system(c);setup_user(c,user)
  post(c,'invest:'+investment_id,'invest',[(f'user:{user}:available',-amount),(f'user:{user}:invested',amount)])
  c.execute('INSERT INTO fin_investments VALUES(?,?,?,?,?,?,?,?)',(investment_id,user,amount,rate_bps,duration_seconds,starts_at,'active',timestamp()))
  for level,(u,bps) in enumerate(uplines,1):
   setup_user(c,u);c.execute('INSERT INTO fin_investment_uplines VALUES(?,?,?,?)',(investment_id,level,u,bps))
  return True
 return atomic(path,action)

def amount_at_bps(amount,bps):return int((Decimal(amount)*Decimal(bps)/Decimal(10000)).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN))

def settle_investment(path,investment_id,at):
 valid_key(investment_id)
 if isinstance(at,bool) or not isinstance(at,int):raise ValueError('date invalide')
 def action(c):
  inv=c.execute('SELECT * FROM fin_investments WHERE id=?',(investment_id,)).fetchone()
  if not inv:raise ValueError('investissement introuvable')
  if inv['status']=='settled':return False
  if at<inv['starts_at']+inv['duration_seconds']:raise ValueError('investissement non arrivé à échéance')
  uplines=c.execute('SELECT user_id,commission_bps FROM fin_investment_uplines WHERE investment_id=? ORDER BY level',(investment_id,)).fetchall()
  profit=amount_at_bps(inv['amount'],inv['rate_bps'])
  commissions=[(r['user_id'],amount_at_bps(profit,r['commission_bps'])) for r in uplines]
  total=profit+sum(n for _,n in commissions)
  if total>MAX_CENTS:raise ValueError('montant excessif')
  uid=inv['user_id']
  post(c,'mature-capital:'+investment_id,'mature_capital',[(f'user:{uid}:invested',-inv['amount']),(f'user:{uid}:available',inv['amount'])])
  if total:
   lines=[('platform:profit_reserve',-total)]
   if profit:lines.append((f'user:{uid}:available',profit))
   lines.extend((f'user:{u}:available',n) for u,n in commissions if n)
   post(c,'mature-profit:'+investment_id,'mature_profit',lines)
  c.execute("UPDATE fin_investments SET status='settled' WHERE id=?",(investment_id,));return True
 return atomic(path,action)

def snapshot(path,user):
 user_id(user)
 with open_db(path) as c:
  return {k:balance(c,f'user:{user}:{k}') for k in ('available','invested','reserved')}
