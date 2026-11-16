import http.cookiejar,json,os,pathlib,socket,sqlite3,subprocess,sys,tempfile,time,unittest,urllib.request,urllib.error
from email.utils import formatdate
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]));from finance import ledger
from decimal import Decimal
ROOT=pathlib.Path(__file__).resolve().parents[1]
class InvestmentStatusTests(unittest.TestCase):
 def test_plans_and_investment_endpoint(self):
  with tempfile.TemporaryDirectory() as d:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();base='http://127.0.0.1:'+str(port)
   env={**os.environ,'DOIT_HOST':'127.0.0.1','PORT':str(port),'DATABASE_URL':d+'/test.db','DOIT_TEST_SQLITE':'1','DOIT_SECURE_COOKIE':'0','DOIT_ADMIN_EMAIL':'','DOIT_ADMIN_BOOTSTRAP_PASSWORD':''}
   p=subprocess.Popen([sys.executable,'server.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    for _ in range(80):
     try:
      with urllib.request.urlopen(base+'/api/health',timeout=1):break
     except Exception:time.sleep(.1)
    with urllib.request.urlopen(base+'/api/plans') as r:plans=json.load(r)['plans']
    self.assertEqual([(x['name'],x['min_xof'],x['max_xof'],x['rate']) for x in plans],[('Starter',25000,31000,40),('Silver',50000,75000,45),('Gold',100000,150000,50),('Premium',200000,300000,55)])
    for p_,expected in zip(plans,[35000,72500,150000,310000]):self.assertEqual(Decimal(p_['min_xof'])*(1+Decimal(p_['rate'])/100),expected)
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def post(path,body,csrf=None):
     headers={'Content-Type':'application/json'}
     if csrf:headers['X-CSRF-Token']=csrf
     req=urllib.request.Request(base+path,data=json.dumps(body).encode(),headers=headers)
     try:
      with op.open(req) as r:return r.status,json.load(r)
     except urllib.error.HTTPError as e:return e.code,json.load(e)
    self.assertEqual(post('/api/register',{'first_name':'Test','last_name':'Test','phone':'12345678','email':'test@example.test','password':'test-password-123'})[0],201)
    with op.open(base+'/api/me') as r:csrf=json.load(r)['user']['csrf']
    with op.open(base+'/api/dashboard') as r:before=json.load(r)
    rates={x:'1' for x in ['USD','EUR','XOF','GBP','NGN','GHS','CAD','CNY','JPY']};rates['XOF']='600'
    with sqlite3.connect(env['DATABASE_URL']) as c:c.execute('INSERT OR REPLACE INTO fx_cache VALUES(1,?,?,?)',(json.dumps(rates),formatdate(usegmt=True),int(time.time())))
    self.assertEqual(post('/api/invest',{'plan':'Starter','usd':'50','request_key':'invest-one'},csrf)[0],400)
    with op.open(base+'/api/me') as r:uid=json.load(r)['user']['id']
    ledger.book_verified_deposit(env['DATABASE_URL'],uid,5000,'test-only')
    body={'plan':'Starter','usd':'50','request_key':'invest-one'}
    code,created=post('/api/invest',body,csrf);self.assertEqual(code,201);self.assertTrue(created['created'])
    self.assertFalse(post('/api/invest',body,csrf)[1]['created'])
    with op.open(base+'/api/dashboard') as r:after=json.load(r)
    self.assertEqual(after['invested_usd'],50);self.assertEqual(after['available_usd'],0)
    with op.open(base+'/api/investments') as r:items=json.load(r)['investments']
    self.assertEqual(len(items),1);self.assertEqual(items[0]['plan'],'Starter');self.assertEqual(items[0]['profit_theoretical_cents'],2000)
   finally:p.terminate();p.wait(timeout=5)
if __name__=='__main__':unittest.main()
