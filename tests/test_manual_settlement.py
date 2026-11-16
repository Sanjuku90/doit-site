import tempfile,pathlib,sys,unittest,concurrent.futures,sqlite3
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from finance import ledger as l,review_queue as q,manual_settlement as s,web_queue
class Tests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.db=str(pathlib.Path(self.t.name)/'app.db');s.init(self.db)
 def tearDown(self):self.t.cleanup()
 def test_credit_only_approved_and_idempotent(self):
  q.submit_deposit(self.db,'d1',1,10000,'a'*64)
  with self.assertRaises(ValueError):s.credit_deposit(self.db,'d1','admin','vérifié','100','0.99','source manuelle')
  q.decide(self.db,'d1','approve','admin','contrôle')
  self.assertTrue(s.credit_deposit(self.db,'d1','admin','vérifié','100','0.99','source manuelle'));self.assertEqual(l.snapshot(self.db,1)['available'],9900)
  self.assertFalse(s.credit_deposit(self.db,'d1','admin','retry','100','0.99','source manuelle'))
  with self.assertRaises(ValueError):s.credit_deposit(self.db,'d1','admin','vérifié','101','0.99','source manuelle')
  with l.open_db(self.db) as c:self.assertEqual(c.execute('SELECT SUM(amount) FROM fin_postings').fetchone()[0],0)
 def test_withdraw_is_not_paid_by_approval_and_no_duplicate_txid(self):
  l.book_verified_deposit(self.db,1,10000,'mock');l.reserve_withdrawal(self.db,1,4000,'w1');q.submit_reserved_withdrawal(self.db,'r1','w1')
  with self.assertRaises(ValueError):s.complete_withdrawal(self.db,'r1','admin','confirmation','b'*64)
  q.decide(self.db,'r1','approve','admin','revue');self.assertEqual(l.snapshot(self.db,1)['reserved'],4000)
  self.assertTrue(s.complete_withdrawal(self.db,'r1','admin','envoyé','b'*64));self.assertEqual(l.snapshot(self.db,1)['reserved'],0)
  self.assertFalse(s.complete_withdrawal(self.db,'r1','admin','retry','b'*64))
  l.reserve_withdrawal(self.db,1,1000,'w2');q.submit_reserved_withdrawal(self.db,'r2','w2');q.decide(self.db,'r2','approve','admin','revue')
  with self.assertRaises(sqlite3.IntegrityError):s.complete_withdrawal(self.db,'r2','admin','envoyé','b'*64)
  self.assertEqual(l.snapshot(self.db,1)['reserved'],1000)
 def test_parallel_credit(self):
  q.submit_deposit(self.db,'d1',1,1000,'c'*64);q.decide(self.db,'d1','approve','admin','revue')
  def f(i):return s.credit_deposit(self.db,'d1','admin','vérifié','10','1','test')
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:r=list(p.map(f,range(2)))
  self.assertEqual(sorted(r),[False,True]);self.assertEqual(l.snapshot(self.db,1)['available'],1000)
 def test_legacy_withdrawal_without_fee_snapshot_table(self):
  web_queue.init(self.db)
  l.book_verified_deposit(self.db,1,5000,'deposit')
  l.reserve_withdrawal(self.db,1,2000,'withdrawal')
  q.submit_reserved_withdrawal(self.db,'request','withdrawal')
  q.decide(self.db,'request','approve','admin','revue')
  with l.open_db(self.db) as c:c.execute('DROP TABLE withdrawal_fee_snapshot')
  self.assertTrue(s.complete_withdrawal(self.db,'request','admin','envoyé','d'*64))
if __name__=='__main__':unittest.main()
