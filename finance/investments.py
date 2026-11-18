"""Investment workflow: accounting only, no claim of verified custody.

The USD/XOF quote is captured at activation. Returns are theoretical until funded;
settlement requires a ledger profit reserve and never creates money automatically.
"""
import hashlib, json, re, time
from email.utils import parsedate_to_datetime
from decimal import Decimal, ROUND_HALF_EVEN
from finance import ledger,web_queue
DURATION=30*86400
COMMISSIONS=[1500,700,500,300,200]
PLANS={'Starter':(25000,31000,4000),'Silver':(50000,75000,4500),'Gold':(100000,150000,5000),'Premium':(200000,300000,5500)}

def init(path):
 ledger.migrate(path)
 with ledger.open_db(path) as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS investment_terms(investment_id TEXT PRIMARY KEY REFERENCES fin_investments(id),user_id INTEGER NOT NULL,request_key TEXT NOT NULL,plan TEXT NOT NULL,rate_xof_per_usd TEXT NOT NULL,rate_source TEXT NOT NULL,rate_time TEXT NOT NULL,created_at TEXT NOT NULL, UNIQUE(user_id,request_key));
  CREATE TRIGGER IF NOT EXISTS investment_terms_no_update BEFORE UPDATE ON investment_terms BEGIN SELECT RAISE(ABORT,'immutable investment terms'); END;
  CREATE TRIGGER IF NOT EXISTS investment_terms_no_delete BEFORE DELETE ON investment_terms BEGIN SELECT RAISE(ABORT,'immutable investment terms'); END;''')

def create(path,uid,plan,usd,key,quote,at=None):
 ledger.user_id(uid);ledger.valid_key(key);amount=web_queue.parse_cents(usd)
 if not isinstance(plan,str) or plan not in PLANS:raise ValueError('Plan invalide')
 if not isinstance(quote,dict) or quote.get('stale'):raise ValueError('Taux de change indisponible ou périmé')
 try:
  fx=Decimal(str(quote['rate']));source=quote['source'];stamp=quote['source_time']
  if not fx.is_finite() or fx<=0 or not isinstance(source,str) or not 1<=len(source)<=100 or not isinstance(stamp,str) or not 1<=len(stamp)<=100:raise ValueError()
  published=parsedate_to_datetime(stamp)
  if published.tzinfo is None:raise ValueError()
  age=time.time()-published.timestamp()
  if age< -300 or age>48*3600:raise ValueError()
 except Exception:raise ValueError('Taux de change invalide')
 lower,upper,rate=PLANS[plan];xof=Decimal(amount)*fx/100
 if not Decimal(lower)<=xof<=Decimal(upper):raise ValueError('Montant hors de la plage du plan au taux indiqué')
 epoch=int(time.time()) if at is None else at
 if isinstance(epoch,bool) or not isinstance(epoch,int) or epoch<0:raise ValueError('Date invalide')
 iid='i-'+hashlib.sha256((str(uid)+':'+key).encode()).hexdigest()[:40]
 def action(c):
  previous=c.execute('SELECT i.*,t.plan FROM fin_investments i JOIN investment_terms t ON t.investment_id=i.id WHERE t.user_id=? AND t.request_key=?',(uid,key)).fetchone()
  if previous:
   if previous['amount']!=amount or previous['plan']!=plan:raise ValueError('Identifiant de demande déjà utilisé')
   return {'id':previous['id'],'created':False}
  parent=c.execute('SELECT referred_by FROM users WHERE id=?',(uid,)).fetchone()
  if not parent:raise ValueError('Compte inexistant')
  ancestors=[];seen={uid};current=parent['referred_by']
  while current is not None and len(ancestors)<5:
   if current in seen:raise ValueError('Cycle de parrainage détecté')
   seen.add(current);record=c.execute('SELECT referred_by FROM users WHERE id=?',(current,)).fetchone()
   if not record:raise ValueError('Parrain inexistant')
   ancestors.append(current);current=record['referred_by']
  ledger.system(c);ledger.setup_user(c,uid)
  ledger.post(c,'invest:'+iid,'invest',[(f'user:{uid}:available',-amount),(f'user:{uid}:invested',amount)])
  now=ledger.timestamp();c.execute('INSERT INTO fin_investments VALUES(?,?,?,?,?,?,?,?)',(iid,uid,amount,rate,DURATION,epoch,'active',now))
  c.execute('INSERT INTO investment_terms VALUES(?,?,?,?,?,?,?,?)',(iid,uid,key,plan,str(fx),source,stamp,now))
  for level,parent_id in enumerate(ancestors,1):
   ledger.setup_user(c,parent_id);c.execute('INSERT INTO fin_investment_uplines VALUES(?,?,?,?)',(iid,level,parent_id,COMMISSIONS[level-1]))
  return {'id':iid,'created':True}
 return ledger.atomic(path,action)

def list_for_user(path,uid,at=None):
 ledger.user_id(uid);epoch=int(time.time()) if at is None else at
 with ledger.open_db(path) as c:
  rows=c.execute('''SELECT i.*,t.plan,t.rate_xof_per_usd,t.rate_time,t.rate_source FROM fin_investments i JOIN investment_terms t ON t.investment_id=i.id WHERE i.user_id=? ORDER BY i.starts_at DESC,i.id DESC''',(uid,)).fetchall()
  result=[]
  for r in rows:
   elapsed=max(0,min(r['duration_seconds'],epoch-r['starts_at']));days=elapsed//86400;profit=ledger.amount_at_bps(r['amount'],r['rate_bps'])
   capital=int((Decimal(r['amount'])*elapsed/r['duration_seconds']).quantize(Decimal(1),rounding=ROUND_HALF_EVEN))
   accrual=int((Decimal(profit)*elapsed/r['duration_seconds']).quantize(Decimal(1),rounding=ROUND_HALF_EVEN))
   status='settled' if r['status']=='settled' else ('matured_awaiting_funding' if days>=30 else 'active')
   result.append({'id':r['id'],'plan':r['plan'],'amount_cents':r['amount'],'rate_bps':r['rate_bps'],'start':r['starts_at'],'maturity':r['starts_at']+r['duration_seconds'],'days':days,'capital_accrued_cents':capital,'profit_theoretical_cents':profit,'profit_accrued_cents':accrual,'total_accrued_cents':capital+accrual,'status':status,'rate_xof_per_usd':r['rate_xof_per_usd'],'rate_time':r['rate_time'],'rate_source':r['rate_source']})
  return result

def settle_due(path,at=None,limit=100):
 epoch=int(time.time()) if at is None else at
 with ledger.open_db(path) as c:ids=[x[0] for x in c.execute("SELECT id FROM fin_investments WHERE status='active' AND starts_at+duration_seconds<=? ORDER BY RANDOM() LIMIT ?",(epoch,limit))]
 completed=waiting=0
 for iid in ids:
  try:
   if ledger.settle_investment(path,iid,epoch):completed+=1
  except ValueError as exc:
   if str(exc)=='fonds insuffisants':waiting+=1
   else:raise
 return {'completed':completed,'awaiting_funding':waiting}

def funded_commissions(path,uid):
 ledger.user_id(uid)
 with ledger.open_db(path) as c:
  return c.execute('''SELECT COALESCE(SUM(p.amount),0) FROM fin_postings p
    JOIN fin_transactions t ON t.id=p.transaction_id
    JOIN fin_investments i ON t.idem_key=('mature-profit:'||i.id)
    WHERE t.kind='mature_profit' AND i.user_id<>? AND p.account=? AND p.amount>0''',(uid,f'user:{uid}:available')).fetchone()[0]
