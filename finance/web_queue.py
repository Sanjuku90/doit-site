"""Web intake for administrator-reviewed deposit and withdrawal requests. No automatic transfers."""
import hashlib, re, secrets
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from finance import ledger,review_queue
ADDRESS='TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS'

def init(path):
 review_queue.migrate(path)
 with ledger.open_db(path) as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS review_web_metadata(request_id TEXT PRIMARY KEY REFERENCES review_requests(id),destination TEXT,declared_usdt TEXT,declared_currency TEXT,declared_amount TEXT);
  CREATE TRIGGER IF NOT EXISTS review_web_meta_no_update BEFORE UPDATE ON review_web_metadata BEGIN SELECT RAISE(ABORT,'immutable'); END;
  CREATE TRIGGER IF NOT EXISTS review_web_meta_no_delete BEFORE DELETE ON review_web_metadata BEGIN SELECT RAISE(ABORT,'immutable'); END;
  CREATE TABLE IF NOT EXISTS withdrawal_fee_snapshot(request_id TEXT PRIMARY KEY REFERENCES review_requests(id),rate_bps INTEGER NOT NULL,fee_cents INTEGER NOT NULL,net_cents INTEGER NOT NULL);
  CREATE TRIGGER IF NOT EXISTS fee_snapshot_no_update BEFORE UPDATE ON withdrawal_fee_snapshot BEGIN SELECT RAISE(ABORT,'immutable'); END;
  CREATE TRIGGER IF NOT EXISTS fee_snapshot_no_delete BEFORE DELETE ON withdrawal_fee_snapshot BEGIN SELECT RAISE(ABORT,'immutable'); END;''')
  cols={r['name'] for r in c.execute('PRAGMA table_info(review_web_metadata)')}
  if 'declared_currency' not in cols:c.execute('ALTER TABLE review_web_metadata ADD COLUMN declared_currency TEXT')
  if 'declared_amount' not in cols:c.execute('ALTER TABLE review_web_metadata ADD COLUMN declared_amount TEXT')

def tron_address(s):
 alphabet='123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
 if not isinstance(s,str) or len(s)!=34:return False
 try:
  n=0
  for c in s:n=n*58+alphabet.index(c)
  b=n.to_bytes((n.bit_length()+7)//8,'big');b=b'\0'*(len(s)-len(s.lstrip('1')))+b
  return len(b)==25 and b[0]==65 and hashlib.sha256(hashlib.sha256(b[:-4]).digest()).digest()[:4]==b[-4:]
 except ValueError:return False

def parse_cents(s):
 if not isinstance(s,str) or not re.fullmatch(r'\d{1,10}(?:\.\d{1,2})?',s):raise ValueError('Montant USD invalide')
 x=int(Decimal(s)*100);ledger.cents(x);return x

def deposit(path,uid,usd,usdt,txid,currency=None,declared_amount=None):
 ledger.user_id(uid);amount=parse_cents(usd)
 if not isinstance(usdt,str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,6})?',usdt) or Decimal(usdt)<=0:raise ValueError('Montant USDT invalide')
 if not isinstance(txid,str) or not review_queue.HEX.fullmatch(txid.lower()):raise ValueError('TXID invalide (64 caractères hexadécimaux requis)')
 request_id='d-'+secrets.token_hex(16);txid=txid.lower()
 def action(c):
  t=ledger.timestamp();c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'deposit',uid,amount,txid,None,'pending',t,t))
  c.execute('INSERT INTO review_web_metadata(request_id,destination,declared_usdt,declared_currency,declared_amount) VALUES(?,?,?,?,?)',(request_id,ADDRESS,usdt,currency,declared_amount or usd))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,'user:'+str(uid),'created','Déclaration utilisateur non vérifiée',t));return request_id
 return ledger.atomic(path,action)

def fee_bps_from_percent(value):
 if not isinstance(value,str) or not re.fullmatch(r'(?:\d{1,2})(?:\.\d{1,2})?',value):raise ValueError('Frais non configurés ou invalides')
 pct=Decimal(value)
 if pct<0 or pct>=100:raise ValueError('Frais invalides')
 return int(pct*100)

def quote(usd,fee_percent):
 amount=parse_cents(usd)
 if amount<1000:raise ValueError('Retrait minimum : 10 USD')
 bps=fee_bps_from_percent(fee_percent)
 fee=int((Decimal(amount)*bps/10000).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN))
 net=amount-fee
 if net<=0:raise ValueError('Montant net insuffisant')
 return {'gross_cents':amount,'fee_bps':bps,'fee_cents':fee,'net_cents':net}

def withdraw(path,uid,usd,destination,fee_percent,accepted_bps,accepted_fee_cents):
 ledger.user_id(uid);amount=parse_cents(usd)
 if not tron_address(destination):raise ValueError('Adresse TRON invalide')
 q=quote(usd,fee_percent)
 if isinstance(accepted_bps,bool) or isinstance(accepted_fee_cents,bool) or accepted_bps!=q['fee_bps'] or accepted_fee_cents!=q['fee_cents']:raise ValueError('Frais modifiés : veuillez vérifier à nouveau')
 rid='r-'+secrets.token_hex(16);wid='w-'+secrets.token_hex(16)
 def action(c):
  ledger.system(c);ledger.setup_user(c,uid)
  ledger.post(c,'withdraw-reserve:'+wid,'withdraw_reserve',[(f'user:{uid}:available',-amount),(f'user:{uid}:reserved',amount)])
  t=ledger.timestamp();c.execute('INSERT INTO fin_withdrawals VALUES(?,?,?,?,?,?,NULL)',(wid,uid,amount,'reserved',t,t))
  c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(rid,'withdrawal',uid,amount,None,wid,'pending',t,t))
  c.execute('INSERT INTO review_web_metadata(request_id,destination,declared_usdt,declared_currency,declared_amount) VALUES(?,?,?,?,?)',(rid,destination,None,None,None))
  c.execute('INSERT INTO withdrawal_fee_snapshot VALUES(?,?,?,?)',(rid,q['fee_bps'],q['fee_cents'],q['net_cents']))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(rid,'user:'+str(uid),'created','Demande réservée',t));return rid
 return ledger.atomic(path,action)

def list_user(path,uid):
 ledger.user_id(uid)
 with ledger.open_db(path) as c:return [dict(x) for x in c.execute('''SELECT r.id,r.kind,r.amount_usd_cents,r.deposit_txid,
 CASE WHEN s.request_id IS NOT NULL AND r.kind='deposit' THEN 'credited_test' WHEN s.request_id IS NOT NULL THEN 'paid_test' ELSE r.state END AS state,
 r.created_at,r.updated_at,m.destination,m.declared_usdt,m.declared_currency,m.declared_amount,s.usd_cents AS credited_usd_cents,s.txid AS settlement_txid,f.rate_bps AS fee_bps,f.fee_cents,f.net_cents
 FROM review_requests r LEFT JOIN review_web_metadata m ON m.request_id=r.id LEFT JOIN manual_settlements s ON s.request_id=r.id
 LEFT JOIN withdrawal_fee_snapshot f ON f.request_id=r.id
 WHERE r.user_id=? ORDER BY r.created_at DESC LIMIT 100''',(uid,))]

def list_admin(path):
 with ledger.open_db(path) as c:return [dict(x) for x in c.execute('''SELECT r.id,r.kind,r.user_id,r.amount_usd_cents,r.deposit_txid,
 CASE WHEN s.request_id IS NOT NULL AND r.kind='deposit' THEN 'credited_test' WHEN s.request_id IS NOT NULL THEN 'paid_test' ELSE r.state END AS state,
 r.created_at,m.destination,m.declared_usdt,m.declared_currency,m.declared_amount,s.usd_cents AS credited_usd_cents,s.txid AS settlement_txid,f.rate_bps AS fee_bps,f.fee_cents,f.net_cents
 FROM review_requests r LEFT JOIN review_web_metadata m ON m.request_id=r.id LEFT JOIN manual_settlements s ON s.request_id=r.id
 LEFT JOIN withdrawal_fee_snapshot f ON f.request_id=r.id
 ORDER BY r.created_at DESC LIMIT 100''')]
