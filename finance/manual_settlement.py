"""Manual settlement ledger. Admin-entered values and TXIDs are audit records, not blockchain proof.
The administrator must independently verify deposits and execute payouts outside the application.
"""
import re
from decimal import Decimal, ROUND_HALF_EVEN
from finance import ledger,review_queue

def init(path):
 review_queue.migrate(path)
 with ledger.open_db(path) as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS manual_settlements(
  request_id TEXT PRIMARY KEY REFERENCES review_requests(id),kind TEXT NOT NULL CHECK(kind IN ('deposit','withdrawal')),
  txid TEXT NOT NULL, usd_cents INTEGER NOT NULL CHECK(usd_cents>0),usdt TEXT,rate TEXT,source TEXT,actor TEXT NOT NULL,created_at TEXT NOT NULL, UNIQUE(kind,txid));
  CREATE TRIGGER IF NOT EXISTS manual_settlements_immutable_update BEFORE UPDATE ON manual_settlements BEGIN SELECT RAISE(ABORT,'immutable settlement'); END;
  CREATE TRIGGER IF NOT EXISTS manual_settlements_immutable_delete BEFORE DELETE ON manual_settlements BEGIN SELECT RAISE(ABORT,'immutable settlement'); END;''')

def verified_amount(usdt,rate):
 if not isinstance(usdt,str) or not re.fullmatch(r'\d{1,9}(?:\.\d{1,6})?',usdt):raise ValueError('Montant USDT invalide')
 if not isinstance(rate,str) or not re.fullmatch(r'\d{1,4}(?:\.\d{1,8})?',rate):raise ValueError('Taux invalide')
 u,r=Decimal(usdt),Decimal(rate)
 if not (u>0 and Decimal('0.000001')<=r<=Decimal('1000')):raise ValueError('Montant ou taux invalide')
 cents=int((u*r*100).quantize(Decimal(1),rounding=ROUND_HALF_EVEN));ledger.cents(cents);return cents

def credit_deposit(path,request_id,actor,reason,usdt,usd_per_usdt,source):
 ledger.valid_key(request_id);actor=review_queue.text(actor,80);reason=review_queue.text(reason,500);source=review_queue.text(source,200)
 amount=verified_amount(usdt,usd_per_usdt)
 def work(c):
  row=c.execute('SELECT * FROM review_requests WHERE id=?',(request_id,)).fetchone()
  if not row or row['kind']!='deposit':raise ValueError('Dépôt introuvable')
  if row['state']!='approved_verification_required':raise ValueError('Approbation administrative préalable requise')
  existing=c.execute('SELECT * FROM manual_settlements WHERE request_id=?',(request_id,)).fetchone()
  if existing:
   if existing['usd_cents']!=amount or existing['usdt']!=usdt or existing['rate']!=usd_per_usdt:raise ValueError('Dépôt déjà crédité avec d’autres valeurs')
   return False
  uid=row['user_id'];ledger.system(c);ledger.setup_user(c,uid)
  ledger.post(c,'deposit:'+row['deposit_txid'],'deposit',[('external:custody',-amount),(f'user:{uid}:available',amount)])
  t=ledger.timestamp();c.execute('INSERT INTO manual_settlements VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'deposit',row['deposit_txid'],amount,usdt,usd_per_usdt,source,actor,t))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,actor,'credit_manual',reason,t));return True
 return ledger.atomic(path,work)

def complete_withdrawal(path,request_id,actor,reason,txid):
 ledger.valid_key(request_id);actor=review_queue.text(actor,80);reason=review_queue.text(reason,500)
 if not isinstance(txid,str) or not re.fullmatch(r'[0-9a-fA-F]{64}',txid):raise ValueError('TXID de paiement invalide')
 txid=txid.lower()
 def work(c):
  row=c.execute('SELECT * FROM review_requests WHERE id=?',(request_id,)).fetchone()
  if not row or row['kind']!='withdrawal' or row['state']!='approved_payment_pending':raise ValueError('Retrait approuvé requis')
  done=c.execute('SELECT * FROM manual_settlements WHERE request_id=?',(request_id,)).fetchone()
  if done:
   if done['txid']!=txid:raise ValueError('Retrait déjà finalisé avec un autre TXID')
   return False
  wd=c.execute('SELECT * FROM fin_withdrawals WHERE id=?',(row['withdrawal_id'],)).fetchone()
  if not wd or wd['status']!='reserved':raise ValueError('Réservation introuvable')
  has_table=c.execute("SELECT to_regclass('public.withdrawal_fee_snapshot')").fetchone()[0]
  fee_info=c.execute('SELECT * FROM withdrawal_fee_snapshot WHERE request_id=?',(request_id,)).fetchone() if has_table else None
  if fee_info:
   fee,net=fee_info['fee_cents'],fee_info['net_cents']
   if fee+net!=wd['amount'] or fee<0 or net<=0:raise ValueError('Frais incohérents')
  else:
   has_meta=c.execute("SELECT to_regclass('public.review_web_metadata')").fetchone()[0]
   if has_meta and c.execute('SELECT 1 FROM review_web_metadata WHERE request_id=?',(request_id,)).fetchone():
    raise ValueError('Ancien retrait : frais à réconcilier manuellement')
   fee,net=0,wd['amount']
  ledger.system(c);lines=[(f'user:{wd["user_id"]}:reserved',-wd['amount']),('external:payout',net)]
  if fee:
   ledger.account(c,'platform:withdrawal_fees')
   lines.append(('platform:withdrawal_fees',fee))
  ledger.post(c,'withdraw-paid:'+wd['id'],'withdraw_paid',lines)
  t=ledger.timestamp();c.execute('UPDATE fin_withdrawals SET status=?,updated_at=?,payout_txid=? WHERE id=?',('paid',t,txid,wd['id']))
  c.execute('INSERT INTO manual_settlements VALUES(?,?,?,?,?,?,?,?,?)',(request_id,'withdrawal',txid,wd['amount'],None,None,None,actor,t))
  c.execute('INSERT INTO review_events(request_id,actor,action,reason,created_at) VALUES(?,?,?,?,?)',(request_id,actor,'payment_manual',reason,t));return True
 return ledger.atomic(path,work)
