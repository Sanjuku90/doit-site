import concurrent.futures, pathlib, sqlite3, sys, tempfile, unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from finance import ledger as l
class FinanceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.db=str(pathlib.Path(self.tmp.name)/'finance.sqlite');l.migrate(self.db)
 def tearDown(self):self.tmp.cleanup()
 def snap(self,u):return l.snapshot(self.db,u)
 def test_deposit_idempotence_and_duplicate_reference(self):
  l.book_verified_deposit(self.db,1,10000,'chain-event-0');self.assertFalse(l.book_verified_deposit(self.db,1,10000,'chain-event-0')[1]);self.assertEqual(self.snap(1)['available'],10000)
  with self.assertRaises(ValueError):l.book_verified_deposit(self.db,2,10000,'chain-event-0')
  with self.assertRaises(ValueError):l.book_verified_deposit(self.db,1,20000,'chain-event-0')
 def test_withdrawal_reject_and_paid_idempotence(self):
  l.book_verified_deposit(self.db,1,10000,'dep1');l.reserve_withdrawal(self.db,1,4000,'withdraw-1');self.assertEqual(self.snap(1),{'available':6000,'invested':0,'reserved':4000})
  l.reject_withdrawal(self.db,'withdraw-1');self.assertFalse(l.reject_withdrawal(self.db,'withdraw-1'));self.assertEqual(self.snap(1)['available'],10000)
  with self.assertRaises(ValueError):l.book_verified_payout(self.db,'withdraw-1','tx1')
  l.reserve_withdrawal(self.db,1,3000,'withdraw-2');self.assertTrue(l.book_verified_payout(self.db,'withdraw-2','tx2'));self.assertFalse(l.book_verified_payout(self.db,'withdraw-2','tx2'))
  with self.assertRaises(ValueError):l.book_verified_payout(self.db,'withdraw-2','different')
  l.reserve_withdrawal(self.db,1,1000,'withdraw-3')
  with self.assertRaises(sqlite3.IntegrityError):l.book_verified_payout(self.db,'withdraw-3','tx2')
  self.assertEqual(self.snap(1),{'available':6000,'invested':0,'reserved':1000})
 def test_concurrent_reservation(self):
  l.book_verified_deposit(self.db,1,10000,'dep1')
  def reserve(i):
   try:l.reserve_withdrawal(self.db,1,7000,'request-'+str(i));return True
   except ValueError:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(reserve,range(2)))
  self.assertEqual(sorted(result),[False,True]);self.assertEqual(self.snap(1),{'available':3000,'invested':0,'reserved':7000})
 def test_maturity_is_funded_and_commissions_on_profits(self):
  l.book_verified_deposit(self.db,1,10000,'dep1');l.start_investment(self.db,1,10000,4000,30,100,'investment-1',[(2,1500),(3,700),(4,500),(5,300),(6,200)])
  with self.assertRaises(ValueError):l.settle_investment(self.db,'investment-1',129)
  with self.assertRaises(ValueError):l.settle_investment(self.db,'investment-1',130)
  self.assertEqual(self.snap(1),{'available':0,'invested':10000,'reserved':0})
  l.book_verified_operator_funding(self.db,5280,'funding-1');self.assertTrue(l.settle_investment(self.db,'investment-1',130));self.assertFalse(l.settle_investment(self.db,'investment-1',130))
  self.assertEqual(self.snap(1)['available'],14000)
  for u,expected in [(2,600),(3,280),(4,200),(5,120),(6,80)]:self.assertEqual(self.snap(u)['available'],expected)
  with l.open_db(self.db) as c:
   self.assertEqual(c.execute('SELECT SUM(amount) FROM fin_postings').fetchone()[0],0)
   with self.assertRaises(sqlite3.IntegrityError):c.execute('UPDATE fin_postings SET amount=0')
   self.assertEqual(l.balance(c,'platform:profit_reserve'),0)
 def test_inputs_and_investment_idempotence(self):
  for v in [True,0,-1,1.5,10**15]:
   with self.assertRaises(ValueError):l.book_verified_deposit(self.db,1,v,'x')
  l.book_verified_deposit(self.db,1,10000,'dep');args=(self.db,1,10000,4000,30,100,'invest-1',[(2,1500)])
  self.assertTrue(l.start_investment(*args));self.assertFalse(l.start_investment(*args))
  with self.assertRaises(ValueError):l.start_investment(self.db,1,10000,4500,30,100,'invest-1',[(2,1500)])
  with self.assertRaises(ValueError):l.start_investment(self.db,1,10000,4000,30,100,'other',[(1,1500)])
if __name__=='__main__':unittest.main()
