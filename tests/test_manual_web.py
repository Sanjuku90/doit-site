import http.cookiejar,json,pathlib,sys,tempfile,threading,unittest,urllib.request,urllib.error
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));import server
from finance import ledger
class ManualWebTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=pathlib.Path(cls.tmp.name)/'test.db';server.MANUAL_TEST=True;server.WITHDRAW_FEE_PERCENT='2.5';server.ADMIN_EMAIL='admin@example.com';server.ADMIN_SECRET='s'*40;server.ADMIN_PASSWORD='secret-password-1234';server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.t=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.t.start();cls.url='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup();server.MANUAL_TEST=False;server.ADMIN_EMAIL='';server.ADMIN_SECRET='';server.ADMIN_PASSWORD=''
 def req(self,op,path,data=None,csrf=None):
  headers={};body=None
  if data is not None:body=json.dumps(data).encode();headers['Content-Type']='application/json'
  if csrf:headers['X-CSRF-Token']=csrf
  try:
   with op.open(urllib.request.Request(self.url+path,data=body,headers=headers)) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def register(self,email):
  op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));body={'first_name':'Test','last_name':'User','phone':'123456789','email':email,'password':'secret-password-1234'}
  self.assertEqual(self.req(op,'/api/register',body)[0],201);me=self.req(op,'/api/me')[1]['user'];return op,me
 def test_complete_test_flow(self):
  user,um=self.register('user@example.test');admin=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));self.assertEqual(self.req(admin,'/api/login',{'email':'admin@example.com','password':'secret-password-1234'})[0],200);am=self.req(admin,'/api/me')[1]['user'];other,om=self.register('other@example.test')
  self.assertEqual(self.req(other,'/api/register',{'first_name':'Test','last_name':'Test','phone':'1234567','email':'admin@example.com','password':'very-long-password-123'})[0],409)
  self.assertTrue(self.req(user,'/api/manual/config')[1]['enabled']);self.assertEqual(self.req(user,'/api/manual/config')[1]['deposit_address'],'TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS')
  dep={'usd':'100.00','usdt':'100.123456','txid':'a'*64}
  self.assertEqual(self.req(user,'/api/manual/deposit',dep)[0],403)
  status,created=self.req(user,'/api/manual/deposit',dep,um['csrf']);self.assertEqual(status,201);rid=created['id']
  self.assertEqual(self.req(user,'/api/manual/deposit',dep,um['csrf'])[0],400)
  self.assertEqual(self.req(other,'/api/manual/requests')[1]['requests'],[])
  self.assertEqual(self.req(other,'/api/manual/admin/list',{})[0],403)
  self.assertEqual(self.req(admin,'/api/manual/admin/list',{})[0],403)
  listing=self.req(admin,'/api/manual/admin/list',{'secret':'s'*40},am['csrf'])[1]['requests'];self.assertEqual(listing[0]['id'],rid)
  decision={'id':rid,'decision':'approve','reason':'revue de test','secret':'s'*40}
  self.assertEqual(self.req(admin,'/api/manual/admin/decide',decision,am['csrf'])[1]['state'],'approved_verification_required')
  self.assertEqual(ledger.snapshot(server.DB,um['id'])['available'],0)
  self.assertEqual(self.req(admin,'/api/manual/admin/decide',decision,am['csrf'])[0],400)
  self.assertEqual(self.req(user,'/api/manual/requests')[1]['requests'][0]['state'],'approved_verification_required')
  wd={'usd':'50.00','address':'TAB1oeEKDS5NATwFAaUrTioDU9djX7anyS','accepted_fee_bps':250,'accepted_fee_cents':125}
  quote=self.req(user,'/api/manual/withdraw-quote',{'usd':'50.00'},um['csrf'])[1];self.assertEqual(quote,{'gross_cents':5000,'fee_bps':250,'fee_cents':125,'net_cents':4875})
  self.assertEqual(self.req(user,'/api/manual/withdraw-quote',{'usd':'9.99'},um['csrf'])[0],400)
  self.assertEqual(self.req(user,'/api/manual/withdraw',{**wd,'accepted_fee_cents':0},um['csrf'])[0],400)
  self.assertEqual(self.req(user,'/api/manual/withdraw',wd,um['csrf'])[0],400)
  credit={'id':rid,'secret':'s'*40,'reason':'montant de test vérifié','usdt':'100.00','rate':'1.00','source':'source de test'}
  self.assertEqual(self.req(other,'/api/manual/admin/credit',{**credit,'id':'introuvable'})[0],403)
  self.assertEqual(self.req(admin,'/api/manual/admin/credit',credit,am['csrf'])[1]['changed'],True)
  self.assertEqual(self.req(admin,'/api/manual/admin/credit',credit,am['csrf'])[1]['changed'],False)
  self.assertEqual(self.req(user,'/api/dashboard')[1]['available_usd'],100)
  self.assertEqual(self.req(user,'/api/manual/requests')[1]['requests'][0]['state'],'credited_test')
  status,w=self.req(user,'/api/manual/withdraw',wd,um['csrf']);self.assertEqual(status,201);self.assertEqual(ledger.snapshot(server.DB,um['id'])['reserved'],5000)
  decision={'id':w['id'],'decision':'reject','reason':'rejet test','secret':'s'*40}
  self.assertEqual(self.req(admin,'/api/manual/admin/decide',decision,am['csrf'])[1]['state'],'rejected');self.assertEqual(ledger.snapshot(server.DB,um['id'])['available'],10000);self.assertEqual(ledger.snapshot(server.DB,um['id'])['reserved'],0)
  status,w2=self.req(user,'/api/manual/withdraw',wd,um['csrf']);decision.update({'id':w2['id'],'decision':'approve'})
  self.assertEqual(self.req(admin,'/api/manual/admin/decide',decision,am['csrf'])[1]['state'],'approved_payment_pending');self.assertEqual(ledger.snapshot(server.DB,um['id'])['reserved'],5000)
  with ledger.open_db(server.DB) as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM fin_withdrawals WHERE status='paid'").fetchone()[0],0)
  complete={'id':w2['id'],'secret':'s'*40,'reason':'déclaration de paiement de test','txid':'b'*64}
  self.assertEqual(self.req(admin,'/api/manual/admin/complete',complete,am['csrf'])[1]['changed'],True)
  self.assertEqual(self.req(admin,'/api/manual/admin/complete',complete,am['csrf'])[1]['changed'],False)
  self.assertEqual(ledger.snapshot(server.DB,um['id'])['reserved'],0)
  with ledger.open_db(server.DB) as c:self.assertEqual(ledger.balance(c,'platform:withdrawal_fees'),125);self.assertEqual(ledger.balance(c,'external:payout'),4875)
  result=self.req(user,'/api/manual/requests')[1]['requests'][0];self.assertEqual(result['state'],'paid_test');self.assertEqual((result['fee_bps'],result['fee_cents'],result['net_cents']),(250,125,4875))
if __name__=='__main__':unittest.main()
