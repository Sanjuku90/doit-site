import unittest, tempfile, pathlib, threading, urllib.request, urllib.error, json, http.cookiejar, sys, os, io
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1])); import server
class AppTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();server.DB=pathlib.Path(cls.temp.name)/'test.sqlite';server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.temp.cleanup()
 def opener(self):return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 def req(self,op,path,body=None,csrf=None):
  headers={};data=None
  if body is not None:data=json.dumps(body).encode();headers['Content-Type']='application/json'
  if csrf:headers['X-CSRF-Token']=csrf
  try:
   with op.open(urllib.request.Request(self.base+path,data=data,headers=headers)) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_flow(self):
  a=self.opener();b=self.opener()
  self.assertEqual(self.req(a,'/api/dashboard')[0],401)
  user={'first_name':'Awa','last_name':'Diallo','phone':'+2211234567','email':'awa@example.com','password':'valid-password-123'}
  self.assertEqual(self.req(a,'/api/register',user)[0],201)
  code,me=self.req(a,'/api/me');self.assertEqual(code,200);self.assertEqual(me['user']['first_name'],'Awa');csrf=me['user']['csrf']
  code,d=self.req(a,'/api/dashboard');self.assertEqual(d['bonus_xof'],5000);self.assertEqual(d['available_usd'],0);self.assertIsNone(d['bonus_usd'])
  self.assertEqual(self.req(a,'/api/withdraw',{},csrf)[0],503)
  self.assertEqual(self.req(a,'/api/preferences',{'currency':'EUR'})[0],403)
  self.assertEqual(self.req(a,'/api/preferences',{'currency':'EUR'},csrf)[0],200)
  self.assertEqual(self.req(a,'/api/me')[1]['user']['display_currency'],'EUR')
  user.update({'email':'user2@example.com','referral':me['user']['referral_code']})
  self.assertEqual(self.req(b,'/api/register',user)[0],201)
  self.assertEqual(len(self.req(a,'/api/referrals')[1]['members']),1)
  self.assertEqual(self.req(a,'/api/logout',{},csrf)[0],200);self.assertEqual(self.req(a,'/api/me')[0],401)
  self.assertEqual(self.req(a,'/api/login',{'email':'awa@example.com','password':'incorrectpassword'})[0],401)
  self.assertEqual(self.req(a,'/api/login',{'email':'awa@example.com','password':'valid-password-123'})[0],200)
 def test_calculations_and_immutability(self):
  self.assertEqual([(p['min_xof'],p['rate']) for p in server.PLANS],[(25000,40),(50000,45),(100000,50),(200000,55)])
  with server.db() as c:
   c.execute("INSERT INTO users(first_name,last_name,phone,email,password_hash,referral_code,created_at) VALUES('Test','User','12345','test@example.com','hash','testcode','now')")
   c.execute("INSERT INTO ledger(user_id,kind,created_at,description) VALUES(last_insert_rowid(),'test','now','original')")
   with self.assertRaises(server.sqlite3.IntegrityError):c.execute('UPDATE ledger SET description="changed"')
 def test_exchange_rates_and_fallback(self):
  fixture={'result':'success','base_code':'USD','time_last_update_utc':'Thu, 12 Nov 2026 00:00:00 +0000','rates':{'USD':1,'EUR':0.9,'XOF':600,'GBP':0.8,'NGN':1500,'GHS':12,'CAD':1.4,'CNY':7,'JPY':150}}
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,n):return json.dumps(fixture).encode()
  server.FX_LAST_ATTEMPT=0;server.FX_LAST_FAILED=False
  with patch('server.urllib.request.urlopen',return_value=Response()):
   x=server.conversion('100','USD','XOF');self.assertEqual(x['result'],'60000.00');self.assertFalse(x['stale'])
   self.assertEqual(server.conversion('300','XOF','USD')['result'],'0.50')
  with server.db() as c:c.execute('UPDATE fx_cache SET fetched_at=0')
  server.FX_LAST_ATTEMPT=0
  with patch('server.urllib.request.urlopen',side_effect=OSError('no network')):
   x=server.conversion('2','USD','EUR');self.assertEqual(x['result'],'1.80');self.assertTrue(x['stale'])
   self.assertTrue(server.conversion('2','USD','EUR')['stale'])
  for amount in ['-1','NaN','Infinity','1000000001']:
   with self.assertRaises(ValueError):server.conversion(amount,'USD','XOF')
  with self.assertRaises(ValueError):server.conversion('1','USDT','USD')
 def test_five_level_network(self):
  op=self.opener();user={'first_name':'Root','last_name':'Network','phone':'123456789','email':'root-network@example.com','password':'very-safe-password'}
  self.assertEqual(self.req(op,'/api/register',user)[0],201)
  uid=self.req(op,'/api/me')[1]['user']['id'];parent=uid
  with server.db() as c:
   for i in range(1,7):
    cur=c.execute('INSERT INTO users(first_name,last_name,phone,email,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?)',('Level'+str(i),'User','12345',f'level{i}@example.com','hash','ref'+str(i),parent,server.now()));parent=cur.lastrowid
  members=self.req(op,'/api/referrals')[1]['members'];self.assertEqual([x['depth'] for x in members],[1,2,3,4,5]);self.assertEqual(len(members),5)
 def test_secure_cookie_and_health_failure(self):
  old_secure=server.SECURE
  try:
   server.SECURE=True
   op=self.opener()
   data=json.dumps({'first_name':'Secure','last_name':'Test','phone':'12345678','email':'secure@example.com','password':'secure-password-123'}).encode()
   req=urllib.request.Request(self.base+'/api/register',data=data,headers={'Content-Type':'application/json'})
   with op.open(req) as r:
    cookie=r.headers.get('Set-Cookie');self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
  finally:server.SECURE=old_secure
  from unittest.mock import patch
  with patch('server.db',side_effect=server.sqlite3.OperationalError('unavailable')):
   self.assertEqual(self.req(self.opener(),'/api/health')[0],503)
 def test_static_and_api(self):
  with urllib.request.urlopen(self.base+'/') as r:self.assertIn(b'DO IT',r.read())
  self.assertEqual(self.req(self.opener(),'/api/plans')[0],200)
if __name__=='__main__':unittest.main()
