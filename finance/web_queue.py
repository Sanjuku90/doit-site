"""TEST ONLY. Web intake for the manual review queue. Never transfers real funds."""
import hashlib, re, secrets
from decimal import Decimal, InvalidOperation
from finance import ledger,review_queue
ADDRESS='TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS'

def init(path):
 review_queue.migrate(path)
 with ledger.open_db(path) as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS review_web_metadata(request_id TEXT PRIMARY KEY REFERENCES review_requests(id),destination TEXT,declared_usdt TEXT);
  CREATE TRIGGER IF NOT EXISTS review_web_meta_no_update BEFORE UPDATE ON review_web_metadata BEGIN SELECT RAISE(ABORT,'immutable'); END;
  CREATE TRIGGER IF NOT EXISTS review_web_meta_no_delete BEFORE DELETE ON review_web_metadata BEGIN SELECT RAISE(ABORT,'immutable'); END;''')

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

def deposit(path,uid,usd,usdt,txid):
 ledger.user_id(uid);amount=parse_cents(usd)
 if not isinstance(usdt,str) or not re.fullmatch(r'\d{1,12}(?:\.\d{1,6})?',usdt) or Decimal(usdt)<=0:raise ValueError('Montant USDT invalide')
 if not isinstance(txid,str) or not review_queue.HEX.fullmatch(txid.lower()):raise ValueError('TXID invalide (64 caractères hexadécimaux requis)')
 request_id='d-'+secrets.token_hex(16);txid=txid.lower()
 def action(c):
  t=ledger.timestamp();c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'deposit',uid,amount,txid,None,'pending',t,t))
  c.execute('INSERT INTO review_web_metadata VALUES(?,?,?)',(request_id,ADDRESS,usdt))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,'user:'+str(uid),'created','Déclaration utilisateur non vérifiée',t));return request_id
 return ledger.atomic(path,action)

def withdraw(path,uid,usd,destination):
 ledger.user_id(uid);amount=parse_cents(usd)
 if not tron_address(destination):raise ValueError('Adresse TRON invalide')
 rid='r-'+secrets.token_hex(16);wid='w-'+secrets.token_hex(16)
 def action(c):
  ledger.system(c);ledger.setup_user(c,uid)
  ledger.post(c,'withdraw-reserve:'+wid,'withdraw_reserve',[(f'user:{uid}:available',-amount),(f'user:{uid}:reserved',amount)])
  t=ledger.timestamp();c.execute('INSERT INTO fin_withdrawals VALUES(?,?,?,?,?,?,NULL)',(wid,uid,amount,'reserved',t,t))
  c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(rid,'withdrawal',uid,amount,None,wid,'pending',t,t))
  c.execute('INSERT INTO review_web_metadata VALUES(?,?,?)',(rid,destination,None))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(rid,'user:'+str(uid),'created','Demande réservée',t));return rid
 return ledger.atomic(path,action)

def list_user(path,uid):
 ledger.user_id(uid)
 with ledger.open_db(path) as c:return [dict(x) for x in c.execute('''SELECT r.id,r.kind,r.amount_usd_cents,r.deposit_txid,
 CASE WHEN s.request_id IS NOT NULL AND r.kind='deposit' THEN 'credited_test' WHEN s.request_id IS NOT NULL THEN 'paid_test' ELSE r.state END AS state,
 r.created_at,r.updated_at,m.destination,m.declared_usdt,s.usd_cents AS credited_usd_cents,s.txid AS settlement_txid
 FROM review_requests r LEFT JOIN review_web_metadata m ON m.request_id=r.id LEFT JOIN manual_settlements s ON s.request_id=r.id
 WHERE r.user_id=? ORDER BY r.created_at DESC LIMIT 100''',(uid,))]

def list_admin(path):
 with ledger.open_db(path) as c:return [dict(x) for x in c.execute('''SELECT r.id,r.kind,r.user_id,r.amount_usd_cents,r.deposit_txid,
 CASE WHEN s.request_id IS NOT NULL AND r.kind='deposit' THEN 'credited_test' WHEN s.request_id IS NOT NULL THEN 'paid_test' ELSE r.state END AS state,
 r.created_at,m.destination,m.declared_usdt,s.usd_cents AS credited_usd_cents,s.txid AS settlement_txid
 FROM review_requests r LEFT JOIN review_web_metadata m ON m.request_id=r.id LEFT JOIN manual_settlements s ON s.request_id=r.id
 ORDER BY r.created_at DESC LIMIT 100''')]
