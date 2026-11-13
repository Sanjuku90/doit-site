import concurrent.futures,http.cookiejar,json,pathlib,sys,tempfile,threading,unittest,urllib.request,urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import server
from finance import ledger,web_queue
class RobustnessTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=pathlib.Path(cls.tmp.name)/'test.db';server.init();server.MANUAL_TEST=True;server.WITHDRAW_FEE_PERCENT='2.5';server.ADMIN_EMAIL='admin@tests.invalid';server.ADMIN_SECRET='u'*40;server.RATE.clear();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.t=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.t.start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup();server.MANUAL_TEST=False;server.ADMIN_EMAIL='';server.ADMIN_SECRET='';server.RATE.clear()
 def request(self,op,path,data=None,csrf=None):
  headers={};body=None
  if data is not None:body=json.dumps(data).encode();headers['Content-Type']='application/json'
  if csrf:headers['X-CSRF-Token']=csrf
  try:
   with op.open(urllib.request.Request(self.url+path,data=body,headers=headers),timeout=3) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def new_user(self,email):
  op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
  data={'first_name':'Utilisateur','last_name':'Test','email':email,'phone':'12345678','password':'mot-de-passe-12345'}
  self.assertEqual(self.request(op,'/api/register',data)[0],201)
  return op,self.request(op,'/api/me')[1]['user']
 def test_concurrent_deposit_and_invalid_inputs(self):
  op,me=self.new_user('concurrency@tests.invalid');payload={'usd':'5.00','usdt':'5.000000','txid':'f'*64}
  def send(_):return self.request(op,'/api/manual/deposit',payload,me['csrf'])[0]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(send,range(2)))
  self.assertEqual(sorted(codes),[201,400]);self.assertEqual(len(self.request(op,'/api/manual/requests')[1]['requests']),1)
  for v in ['NaN','-1','0','10.123','Infinity']:
   status,_=self.request(op,'/api/manual/deposit',{'usd':v,'usdt':'1','txid':'a'*64},me['csrf']);self.assertEqual(status,400)
 def test_reserved_double_request_and_dashboard(self):
  op,me=self.new_user('withdraw@tests.invalid');ledger.book_verified_deposit(server.DB,me['id'],10000,'simulated')
  payload={'usd':'70.00','address':web_queue.ADDRESS,'accepted_fee_bps':250,'accepted_fee_cents':175}
  def send(_):return self.request(op,'/api/manual/withdraw',payload,me['csrf'])[0]
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(send,range(2)))
  self.assertEqual(sorted(codes),[201,400]);d=self.request(op,'/api/dashboard')[1];self.assertEqual(d['available_usd'],30);self.assertEqual(d['reserved_usd'],70)
 def test_private_records_and_disabled_mode(self):
  a,am=self.new_user('a@tests.invalid');b,bm=self.new_user('b@tests.invalid')
  payload={'usd':'10','usdt':'10','txid':'b'*64};self.assertEqual(self.request(a,'/api/manual/deposit',payload,am['csrf'])[0],201)
  self.assertEqual(self.request(b,'/api/manual/requests')[1]['requests'],[])
  for path in ['/api/deposit','/api/withdraw']:
   self.assertEqual(self.request(a,path,{},am['csrf'])[0],503)
  server.MANUAL_TEST=False
  try:
   self.assertEqual(self.request(a,'/api/manual/requests')[0],503);self.assertEqual(self.request(a,'/api/manual/deposit',payload,am['csrf'])[0],503)
  finally:server.MANUAL_TEST=True
 def test_declared_address_checksum(self):
  self.assertTrue(web_queue.tron_address(web_queue.ADDRESS));self.assertFalse(web_queue.tron_address(web_queue.ADDRESS[:-1]+'T'));self.assertFalse(web_queue.tron_address('invalid'))
if __name__=='__main__':unittest.main()
