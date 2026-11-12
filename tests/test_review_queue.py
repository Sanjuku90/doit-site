import concurrent.futures,pathlib,sqlite3,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));from finance import ledger as l,review_queue as q
class ReviewTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.db=str(pathlib.Path(self.tmp.name)/'app.db');q.migrate(self.db)
 def tearDown(self):self.tmp.cleanup()
 def test_deposit_approval_never_credits(self):
  tx='a'*64;self.assertTrue(q.submit_deposit(self.db,'d1',1,5000,tx));self.assertFalse(q.submit_deposit(self.db,'d1',1,5000,tx))
  with self.assertRaises(sqlite3.IntegrityError):q.submit_deposit(self.db,'d2',2,5000,tx.upper())
  self.assertEqual(q.decide(self.db,'d1','approve','admin','dossier examiné'),'approved_verification_required');self.assertEqual(l.snapshot(self.db,1)['available'],0)
  with self.assertRaises(ValueError):q.decide(self.db,'d1','reject','admin','trop tard')
  self.assertEqual(len(q.events(self.db,'d1')),2)
 def test_withdraw_rejection_releases_reserve(self):
  l.book_verified_deposit(self.db,1,10000,'mock-deposit');l.reserve_withdrawal(self.db,1,5000,'w1');q.submit_reserved_withdrawal(self.db,'r1','w1')
  self.assertEqual(q.decide(self.db,'r1','reject','admin','non conforme'),'rejected');self.assertEqual(l.snapshot(self.db,1),{'available':10000,'invested':0,'reserved':0})
  with self.assertRaises(ValueError):q.decide(self.db,'r1','reject','admin','double')
  with l.open_db(self.db) as c:
   self.assertEqual(c.execute('SELECT status FROM fin_withdrawals WHERE id=?',('w1',)).fetchone()[0],'rejected')
   with self.assertRaises(sqlite3.IntegrityError):c.execute('DELETE FROM review_events')
 def test_withdraw_approval_is_not_payment(self):
  l.book_verified_deposit(self.db,1,10000,'mock');l.reserve_withdrawal(self.db,1,4000,'w');q.submit_reserved_withdrawal(self.db,'r','w')
  self.assertEqual(q.decide(self.db,'r','approve','admin','conforme'),'approved_payment_pending');self.assertEqual(l.snapshot(self.db,1)['reserved'],4000)
  with l.open_db(self.db) as c:self.assertEqual(c.execute('SELECT status FROM fin_withdrawals WHERE id=?',('w',)).fetchone()[0],'reserved')
 def test_competing_decisions(self):
  q.submit_deposit(self.db,'r',1,100,'b'*64)
  def task(d):
   try:return q.decide(self.db,'r',d,'admin','examen')
   except ValueError:return 'already'
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:result=list(p.map(task,['approve','reject']))
  self.assertEqual(result.count('already'),1);self.assertEqual(len(q.events(self.db,'r')),2)
 def test_validation(self):
  with self.assertRaises(ValueError):q.submit_deposit(self.db,'x',1,100,'invalid')
  with self.assertRaises(ValueError):q.submit_reserved_withdrawal(self.db,'x','missing')
  q.submit_deposit(self.db,'x',1,100,'c'*64)
  with self.assertRaises(ValueError):q.decide(self.db,'x','reject','admin','')
if __name__=='__main__':unittest.main()
