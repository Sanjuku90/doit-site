import http.cookiejar, json, pathlib, tempfile, threading, urllib.request, urllib.error, unittest, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1])); import server

class V13FeatureTests(unittest.TestCase):
 def test_profile_support_notifications_admin_export_and_suspend(self):
  old=(server.DB,server.ADMIN_EMAIL,server.ADMIN_PASSWORD)
  with tempfile.TemporaryDirectory() as d:
   try:
    server.DB=pathlib.Path(d)/'v13.sqlite';server.ADMIN_EMAIL='admin-v13@example.test';server.ADMIN_PASSWORD='admin-password-v13';server.init()
    srv=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=srv.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{srv.server_port}'
    def opener():return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def req(op,path,body=None,csrf=None):
     headers={};data=None
     if body is not None:data=json.dumps(body).encode();headers['Content-Type']='application/json'
     if csrf:headers['X-CSRF-Token']=csrf
     try:
      with op.open(urllib.request.Request(base+path,data=data,headers=headers)) as r:return r.status,json.load(r)
     except urllib.error.HTTPError as e:return e.code,json.load(e)
    user=opener();admin=opener()
    self.assertEqual(req(user,'/api/register',{'first_name':'Awa','last_name':'Test','phone':'12345678','email':'awa-v13@example.test','password':'password-v13-12345'})[0],201)
    u=req(user,'/api/me')[1]['user'];csrf=u['csrf'];uid=u['id']
    self.assertEqual(req(user,'/api/profile',{'first_name':'Awa','last_name':'Diallo','phone':'12345678','avatar_url':'https://example.test/avatar.png'},csrf)[0],200)
    self.assertEqual(req(user,'/api/me')[1]['user']['avatar_url'],'https://example.test/avatar.png')
    self.assertEqual(req(user,'/api/support',{'message':'Besoin d’aide'},csrf)[0],201)
    self.assertEqual(len(req(user,'/api/support')[1]['messages']),1)
    self.assertEqual(req(admin,'/api/login',{'email':'admin-v13@example.test','password':'admin-password-v13'})[0],200)
    ac=req(admin,'/api/me')[1]['user']['csrf']
    self.assertEqual(req(admin,'/api/admin/dashboard')[0],200)
    self.assertEqual(len(req(admin,'/api/admin/users?q=awa')[1]['users']),1)
    self.assertEqual(len(req(admin,'/api/admin/support')[1]['messages']),1)
    self.assertEqual(req(admin,'/api/admin/support/reply',{'user_id':uid,'message':'Nous vous répondons.'},ac)[0],201)
    self.assertEqual(len(req(user,'/api/notifications')[1]['notifications']),2)
    self.assertEqual(req(user,'/api/calendar')[0],200)
    with admin.open(base+'/api/admin/export') as r:self.assertEqual(r.headers['Content-Type'].split(';')[0],'text/csv')
    self.assertEqual(req(admin,'/api/admin/users/status',{'user_id':uid,'active':False},ac)[0],200)
    self.assertEqual(req(user,'/api/me')[0],401)
    login=opener();self.assertEqual(req(login,'/api/login',{'email':'awa-v13@example.test','password':'password-v13-12345'})[0],401)
   finally:
    if 'srv' in locals():srv.shutdown();srv.server_close()
    server.DB,server.ADMIN_EMAIL,server.ADMIN_PASSWORD=old
