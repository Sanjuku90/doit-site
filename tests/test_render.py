import http.cookiejar, json, os, pathlib, socket, subprocess, sys, tempfile, time, unittest, urllib.error, urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[1]
class RenderTests(unittest.TestCase):
 def test_render_start_and_persistence(self):
  with tempfile.TemporaryDirectory() as d:
   sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
   db_path=pathlib.Path(d)/'persist'/'app.sqlite3';db_path.parent.mkdir()
   env={**os.environ,'DOIT_HOST':'0.0.0.0','PORT':str(port),'DATABASE_URL':str(db_path),'DOIT_TEST_SQLITE':'1','DOIT_SECURE_COOKIE':'0','DOIT_ADMIN_EMAIL':''}
   url='http://127.0.0.1:'+str(port)
   def request(op,path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(url+path,data=data,headers={'Content-Type':'application/json'} if data else {})
    try:
     with op.open(req,timeout=3) as r:return r.status,json.load(r)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
   def start():
    p=subprocess.Popen([sys.executable,'server.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for _ in range(80):
     try:
      with urllib.request.urlopen(url+'/api/health',timeout=.5) as r:
       if r.status==200:return p
     except Exception: time.sleep(.1)
    p.kill();p.wait();self.fail('server did not start')
   p=start()
   try:
    op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    user={'first_name':'Test','last_name':'Persistence','email':'render-test@example.com','phone':'123456789','password':'une-phrase-secrete-123'}
    self.assertEqual(request(op,'/api/register',user)[0],201)
    self.assertEqual(request(op,'/api/admin')[0],403)
    self.assertEqual(request(op,'/api/dashboard')[1]['available_usd'],0)
    self.assertTrue(pathlib.Path(env['DATABASE_URL']).exists())
    p.terminate();p.wait(timeout=5);p=start()
    self.assertEqual(request(op,'/api/me')[1]['user']['email'],user['email'])
    self.assertEqual(request(op,'/api/dashboard')[1]['bonus_xof'],5000)
   finally:p.terminate();p.wait(timeout=5)
 def test_render_config(self):
  text=(ROOT/'render.yaml').read_text()
  for item in ('runtime: python','pip install -r requirements.txt','key: DATABASE_URL','sync: false','healthCheckPath: /api/health','value: 0.0.0.0','value: "1"'):
   self.assertIn(item,text)
  self.assertNotIn('key: DOIT_DB',text)
  self.assertNotIn('mountPath: /var/data',text)
 def test_render_keepalive_workflow(self):
  workflow=(ROOT/'.github'/'workflows'/'render-keepalive.yml').read_text()
  self.assertIn("cron: '*/10 * * * *'",workflow)
  self.assertIn('vars.RENDER_URL',workflow)
  self.assertIn('/api/health',workflow)

if __name__=='__main__':unittest.main()
