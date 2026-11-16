"""Local, not web-connected administrative review queue.

Approval NEVER verifies or credits deposits, and NEVER executes withdrawals.
Host access must be restricted to trusted operators. This module is not a production
admin interface and does not provide authentication, KYC or blockchain verification.
"""
import re
import postgres_compat as sqlite3
from finance import ledger

HEX=re.compile(r'^[0-9a-f]{64}$')
def text(value,maximum=200):
 if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):raise ValueError('texte invalide')
 return value.strip()

def migrate(path):
 ledger.migrate(path)
 with ledger.open_db(path) as c:
  c.executescript('''
  CREATE TABLE IF NOT EXISTS review_requests(
   id TEXT PRIMARY KEY,kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal')),
   user_id INTEGER NOT NULL,amount_usd_cents INTEGER NOT NULL CHECK(amount_usd_cents>0),
   deposit_txid TEXT UNIQUE,withdrawal_id TEXT UNIQUE,
   state TEXT NOT NULL CHECK(state IN ('pending','approved_verification_required','approved_payment_pending','rejected')),
   created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
   CHECK((kind='deposit' AND deposit_txid IS NOT NULL AND withdrawal_id IS NULL) OR
         (kind='withdrawal' AND deposit_txid IS NULL AND withdrawal_id IS NOT NULL))
  );
  CREATE TABLE IF NOT EXISTS review_events(id INTEGER PRIMARY KEY,request_id TEXT NOT NULL REFERENCES review_requests(id),actor TEXT NOT NULL,action TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
  CREATE TRIGGER IF NOT EXISTS review_events_no_update BEFORE UPDATE ON review_events BEGIN SELECT RAISE(ABORT,'audit immutable'); END;
  CREATE TRIGGER IF NOT EXISTS review_events_no_delete BEFORE DELETE ON review_events BEGIN SELECT RAISE(ABORT,'audit immutable'); END;
  ''')

def submit_deposit(path,request_id,user_id,amount_usd_cents,txid):
 ledger.valid_key(request_id);ledger.user_id(user_id);ledger.cents(amount_usd_cents)
 if not isinstance(txid,str) or not HEX.fullmatch(txid.lower()):raise ValueError('TXID TRON invalide')
 txid=txid.lower()
 def action(c):
  old=c.execute('SELECT * FROM review_requests WHERE id=?',(request_id,)).fetchone()
  if old:
   if (old['kind'],old['user_id'],old['amount_usd_cents'],old['deposit_txid'])!=('deposit',user_id,amount_usd_cents,txid):raise ValueError('identifiant déjà utilisé')
   return False
  now=ledger.timestamp();c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'deposit',user_id,amount_usd_cents,txid,None,'pending',now,now))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,'system','created','demande non vérifiée',now));return True
 return ledger.atomic(path,action)

def submit_reserved_withdrawal(path,request_id,withdrawal_id):
 ledger.valid_key(request_id);ledger.valid_key(withdrawal_id)
 def action(c):
  wd=c.execute('SELECT * FROM fin_withdrawals WHERE id=?',(withdrawal_id,)).fetchone()
  if not wd or wd['status']!='reserved':raise ValueError('retrait non réservé ou inexistant')
  old=c.execute('SELECT * FROM review_requests WHERE id=?',(request_id,)).fetchone()
  if old:
   if old['withdrawal_id']!=withdrawal_id:raise ValueError('identifiant déjà utilisé')
   return False
  now=ledger.timestamp();c.execute('INSERT INTO review_requests VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'withdrawal',wd['user_id'],wd['amount'],None,withdrawal_id,'pending',now,now))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,'system','created','retrait réservé',now));return True
 return ledger.atomic(path,action)

def decide(path,request_id,decision,actor,reason):
 ledger.valid_key(request_id);text(actor,80);reason=text(reason,500)
 if decision not in ('approve','reject'):raise ValueError('décision invalide')
 def action(c):
  row=c.execute('SELECT * FROM review_requests WHERE id=?',(request_id,)).fetchone()
  if not row:raise ValueError('demande introuvable')
  if row['state']!='pending':raise ValueError('demande déjà traitée')
  if row['kind']=='deposit':
   new='approved_verification_required' if decision=='approve' else 'rejected'
  elif decision=='approve':
   wd=c.execute('SELECT status FROM fin_withdrawals WHERE id=?',(row['withdrawal_id'],)).fetchone()
   if not wd or wd['status']!='reserved':raise ValueError('réservation introuvable')
   new='approved_payment_pending'
  else:
   wd=c.execute('SELECT * FROM fin_withdrawals WHERE id=?',(row['withdrawal_id'],)).fetchone()
   if not wd or wd['status']!='reserved':raise ValueError('réservation introuvable')
   uid=wd['user_id'];amount=wd['amount']
   ledger.post(c,'withdraw-reject:'+row['withdrawal_id'],'withdraw_reject',[(f'user:{uid}:reserved',-amount),(f'user:{uid}:available',amount)])
   c.execute('UPDATE fin_withdrawals SET status=?,updated_at=? WHERE id=?',('rejected',ledger.timestamp(),row['withdrawal_id']))
   new='rejected'
  now=ledger.timestamp()
  c.execute('UPDATE review_requests SET state=?,updated_at=? WHERE id=? AND state=\'pending\'',(new,now,request_id))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,actor,decision,reason,now))
  return new
 return ledger.atomic(path,action)

def list_requests(path,state=None):
 with ledger.open_db(path) as c:
  if state:return [dict(r) for r in c.execute('SELECT * FROM review_requests WHERE state=? ORDER BY created_at,id LIMIT 1000',(state,))]
  return [dict(r) for r in c.execute('SELECT * FROM review_requests ORDER BY created_at,id LIMIT 1000')]

def events(path,request_id):
 ledger.valid_key(request_id)
 with ledger.open_db(path) as c:return [dict(r) for r in c.execute('SELECT actor,action,reason,created_at FROM review_events WHERE request_id=? ORDER BY id',(request_id,))]
