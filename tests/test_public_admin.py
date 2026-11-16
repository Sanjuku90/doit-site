import http.cookiejar, json, os, pathlib, socket, subprocess, sys, tempfile, time, unittest, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
class PublicAdminTests(unittest.TestCase):
 def test_anonymous_admin_and_two_percent(self):
  with tempfile.TemporaryDirectory() as d:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close();base='http://127.0.0.1:'+str(port)
   env={**os.environ,'DOIT_HOST':'127.0.0.1','PORT':str(port),'DATABASE_URL':d+'/site.db','DOIT_TEST_SQLITE':'1','DOIT_MANUAL_TEST':'1','DOIT_WITHDRAW_FEE_PERCENT':'2','DOIT_ADMIN_EMAIL':'admin@example.test','DOIT_ADMIN_BOOTSTRAP_PASSWORD':'admin-password-12345'}
   p=subprocess.Popen([sys.executable,'server.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   try:
    for _ in range(60):
     try:
      with urllib.request.urlopen(base+'/api/health',timeout=1) as r:break
     except Exception:time.sleep(.1)
    with urllib.request.urlopen(base+'/admin',timeout=2) as r:self.assertEqual(r.status,200);self.assertIn('text/html',r.headers['Content-Type'])
    with urllib.request.urlopen(base+'/api/manual/config',timeout=2) as r:self.assertEqual(json.load(r)['fee_bps'],200)
    req=urllib.request.Request(base+'/api/manual/admin/list',data=b'{}',headers={'Content-Type':'application/json'})
    try:urllib.request.urlopen(req,timeout=2);self.fail('anonymous admin access must be denied')
    except urllib.error.HTTPError as e:self.assertEqual(e.code,401)
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def post(path,data,csrf=None,opener=op):
     head={'Content-Type':'application/json'}
     if csrf:head['X-CSRF-Token']=csrf
     req=urllib.request.Request(base+path,data=json.dumps(data).encode(),headers=head)
     with opener.open(req,timeout=3) as r:return json.load(r)
    post('/api/register',{'first_name':'Awa','last_name':'Test','phone':'1234567','email':'sample@example.test','password':'test-password-123'})
    adminop=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    post('/api/login',{'email':'admin@example.test','password':'admin-password-12345'},opener=adminop)
    with adminop.open(base+'/api/me') as r:csrf=json.load(r)['user']['csrf']
    userop=op
    with userop.open(base+'/api/me') as r:usercsrf=json.load(r)['user']['csrf']
    reqid=post('/api/manual/deposit',{'usd':'100','usdt':'100','txid':'f'*64},usercsrf,opener=userop)['id']
    result=post('/api/manual/admin/list',{},csrf,opener=adminop)
    self.assertEqual(result['requests'][0]['id'],reqid)
    post('/api/manual/admin/decide',{'id':reqid,'decision':'approve','reason':'manual check'},csrf,opener=adminop)
    result=post('/api/manual/admin/credit',{'id':reqid,'reason':'manual check','usdt':'100','rate':'1','source':'manual'},csrf,opener=adminop)
    self.assertTrue(result['changed'])
    with userop.open(base+'/api/dashboard') as r:self.assertEqual(json.load(r)['available_usd'],100)
    quote=post('/api/manual/withdraw-quote',{'usd':'50'},usercsrf,opener=userop)
    self.assertEqual((quote['fee_bps'],quote['fee_cents'],quote['net_cents']),(200,100,4900))
   finally:p.terminate();p.wait(timeout=5)
if __name__=='__main__':unittest.main()
