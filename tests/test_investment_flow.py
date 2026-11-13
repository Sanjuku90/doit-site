import pathlib,sys,tempfile,unittest,sqlite3,concurrent.futures
from email.utils import formatdate
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import server
from finance import ledger,investments
class InvestmentFlowTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.old=server.DB;server.DB=pathlib.Path(self.t.name)/'db';self.db=server.DB;server.init()
  with server.db() as c:
   for i in range(1,8):c.execute('INSERT INTO users(id,first_name,last_name,phone,email,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(i,'Test','User','123456',f'test{i}@example.test','hash',f'ref{i}',i-1 if i>1 else None,server.now()))
  self.q={'rate':'600','source':'test','source_time':formatdate(usegmt=True),'stale':False}
 def tearDown(self):server.DB=self.old;self.t.cleanup()
 def test_boundaries_bonus_and_idempotence(self):
  with self.assertRaises(ValueError):investments.create(self.db,7,'Starter','41.66','first',self.q,0)
  with self.assertRaises(ValueError):investments.create(self.db,7,'Starter','41.67','first',self.q,0)
  ledger.book_verified_deposit(self.db,7,10000,'fake-credit')
  with self.assertRaises(ValueError):investments.create(self.db,7,'Starter','51.67','maxbad',self.q,0)
  with self.assertRaises(ValueError):investments.create(self.db,7,'Starter','41.67','stale',{**self.q,'stale':True},0)
  self.assertTrue(investments.create(self.db,7,'Starter','50.00','request1',self.q,0)['created']);self.assertFalse(investments.create(self.db,7,'Starter','50.00','request1',self.q,0)['created'])
  with self.assertRaises(ValueError):investments.create(self.db,7,'Silver','50.00','request1',self.q,0)
  self.assertEqual(ledger.snapshot(self.db,7),{'available':5000,'invested':5000,'reserved':0})
  with ledger.open_db(self.db) as c:self.assertEqual([x[0] for x in c.execute('SELECT user_id FROM fin_investment_uplines ORDER BY level')],[6,5,4,3,2])
 def test_cumulation_and_settlement_requires_reserve(self):
  ledger.book_verified_deposit(self.db,7,5000,'fake');r=investments.create(self.db,7,'Starter','50.00','request2',self.q,100)
  x=investments.list_for_user(self.db,7,100+12*86400)[0];self.assertEqual((x['days'],x['capital_accrued_cents'],x['profit_accrued_cents'],x['total_accrued_cents']),(12,2000,800,2800))
  self.assertEqual(investments.settle_due(self.db,100+30*86400),{'completed':0,'awaiting_funding':1});self.assertEqual(investments.list_for_user(self.db,7,100+30*86400)[0]['status'],'matured_awaiting_funding');self.assertEqual(ledger.snapshot(self.db,7)['available'],0)
  ledger.book_verified_operator_funding(self.db,2640,'fake-reserve');self.assertEqual(investments.settle_due(self.db,100+30*86400)['completed'],1);self.assertEqual(ledger.snapshot(self.db,7)['available'],7000);self.assertEqual(investments.list_for_user(self.db,7,100+30*86400)[0]['status'],'settled')
  for u,expected in [(6,300),(5,140),(4,100),(3,60),(2,40)]:self.assertEqual(ledger.snapshot(self.db,u)['available'],expected);self.assertEqual(investments.funded_commissions(self.db,u),expected)
  self.assertEqual(investments.funded_commissions(self.db,7),0)
  self.assertEqual(investments.settle_due(self.db,100+31*86400)['completed'],0)
 def test_competing_investments_and_retry(self):
  ledger.book_verified_deposit(self.db,7,5000,'fake')
  def go(k):
   try:return investments.create(self.db,7,'Starter','50.00',k,self.q,0)['created']
   except ValueError:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as p:res=list(p.map(go,['first','second']))
  self.assertEqual(sorted(res),[False,True]);self.assertEqual(ledger.snapshot(self.db,7)['invested'],5000)
if __name__=='__main__':unittest.main()
