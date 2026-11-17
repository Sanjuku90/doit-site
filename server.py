#!/usr/bin/env python3
"""DO IT foundation: persistent accounts, restricted test bonus and read-only finance.
Money movement is intentionally disabled until verified integrations are implemented.
"""
import os, sys, json, re, secrets, hashlib, hmac, time, threading, logging
import postgres_compat as sqlite3
import urllib.request
from finance import web_queue,review_queue,ledger as finledger,manual_settlement,investments
from decimal import Decimal, ROUND_HALF_EVEN
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import SimpleCookie
from urllib.parse import urlparse, parse_qs
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=os.environ.get('DATABASE_URL','')
HOST=os.environ.get('DOIT_HOST','127.0.0.1'); PORT=int(os.environ.get('PORT','8080'))
SECURE=os.environ.get('DOIT_SECURE_COOKIE','0')=='1'
ADMIN_EMAIL=os.environ.get('DOIT_ADMIN_EMAIL','').strip().lower()
# Les demandes manuelles restent actives indépendamment de l'ancien indicateur DOIT_MANUAL_TEST.
MANUAL_OPERATIONS=True
ADMIN_SECRET=os.environ.get('DOIT_ADMIN_REVIEW_SECRET','')
ADMIN_PASSWORD=os.environ.get('DOIT_ADMIN_BOOTSTRAP_PASSWORD','')
WITHDRAW_FEE_PERCENT=os.environ.get('DOIT_WITHDRAW_FEE_PERCENT','2').strip()
RATE={}; RATE_LOCK=threading.Lock()
CURRENCIES=['USD','EUR','XOF','GBP','NGN','GHS','CAD','CNY','JPY']
FX_LOCK=threading.Lock()
FX_LAST_ATTEMPT=0
FX_LAST_FAILED=False
FX_URL='https://open.er-api.com/v6/latest/USD'
PLANS=[{'name':'Starter','min_xof':25000,'max_xof':31000,'rate':40},{'name':'Silver','min_xof':50000,'max_xof':75000,'rate':45},{'name':'Gold','min_xof':100000,'max_xof':150000,'rate':50},{'name':'Premium','min_xof':200000,'max_xof':300000,'rate':55}]
def db():
 return sqlite3.connect(DB,timeout=10)
def now(): return datetime.now(timezone.utc).isoformat()
def token_hash(s): return hashlib.sha256(s.encode()).hexdigest()
def pass_hash(password,salt=None):
 salt=salt or secrets.token_hex(16)
 digest=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1,dklen=32).hex()
 return 'scrypt$'+salt+'$'+digest
def pass_check(password,stored):
 try:
  _,salt,_=stored.split('$'); return hmac.compare_digest(pass_hash(password,salt),stored)
 except (ValueError,TypeError): return False
def init():
 with db() as c:
  c.executescript('''PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, first_name TEXT NOT NULL,last_name TEXT NOT NULL,phone TEXT NOT NULL,email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,referral_code TEXT NOT NULL UNIQUE, referred_by INTEGER REFERENCES users(id), display_currency TEXT NOT NULL DEFAULT 'USD',created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),csrf TEXT NOT NULL,expires INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT NOT NULL,created_at TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS ledger(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),kind TEXT NOT NULL,amount_usd_minor INTEGER,amount_xof_minor INTEGER,created_at TEXT NOT NULL,description TEXT NOT NULL);
  CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger BEGIN SELECT RAISE(ABORT,'ledger immutable'); END;
  CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger BEGIN SELECT RAISE(ABORT,'ledger immutable'); END;
  CREATE TABLE IF NOT EXISTS fx_cache(id INTEGER PRIMARY KEY CHECK(id=1), rates_json TEXT NOT NULL, source_timestamp TEXT NOT NULL, fetched_at INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS admin_principals(user_id INTEGER PRIMARY KEY REFERENCES users(id));
  CREATE TABLE IF NOT EXISTS user_profiles(user_id INTEGER PRIMARY KEY REFERENCES users(id),avatar_url TEXT);
  CREATE TABLE IF NOT EXISTS user_account_status(user_id INTEGER PRIMARY KEY REFERENCES users(id),is_active INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,body TEXT NOT NULL,created_at TEXT NOT NULL,read_at TEXT);
  CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),sender TEXT NOT NULL CHECK(sender IN ('client','admin')),message TEXT NOT NULL,created_at TEXT NOT NULL,read_at TEXT);
  CREATE INDEX IF NOT EXISTS notifications_user ON notifications(user_id,created_at DESC);
  CREATE INDEX IF NOT EXISTS support_user ON support_messages(user_id,created_at);
  ''')
 if ADMIN_EMAIL and ADMIN_PASSWORD:
  if len(ADMIN_PASSWORD)<12:raise RuntimeError('Mot de passe administrateur trop court.')
  with db() as c:
   existing=c.execute('SELECT id FROM users WHERE email=?',(ADMIN_EMAIL,)).fetchone()
   if existing:
    if not c.execute('SELECT 1 FROM admin_principals WHERE user_id=?',(existing['id'],)).fetchone():
     raise RuntimeError('Adresse administrateur déjà utilisée par un compte non administrateur.')
   else:
    cur=c.execute('INSERT INTO users(first_name,last_name,phone,email,password_hash,referral_code,created_at) VALUES(?,?,?,?,?,?,?)',('Admin','DO IT','non renseigné',ADMIN_EMAIL,pass_hash(ADMIN_PASSWORD),secrets.token_urlsafe(9),now()))
    c.execute('INSERT INTO admin_principals(user_id) VALUES(?)',(cur.lastrowid,))
 web_queue.init(DB)
 manual_settlement.init(DB)
 investments.init(DB)

def is_admin(session):
 if not ADMIN_EMAIL or session['email'].lower()!=ADMIN_EMAIL:return False
 with db() as c:return c.execute('SELECT 1 FROM admin_principals WHERE user_id=?',(session['id'],)).fetchone() is not None

def conversion(amount,from_currency,to_currency):
 global FX_LAST_ATTEMPT, FX_LAST_FAILED
 if from_currency not in CURRENCIES or to_currency not in CURRENCIES:
  raise ValueError('Devise non prise en charge.')
 try:
  value=Decimal(amount)
  if not value.is_finite() or value<0 or value>Decimal('1000000000'):
   raise ValueError()
 except Exception:
  raise ValueError('Montant invalide.')
 with FX_LOCK:
  with db() as c: cached=c.execute('SELECT * FROM fx_cache WHERE id=1').fetchone()
  degraded=FX_LAST_FAILED
  if (not cached or time.time()-cached['fetched_at']>=3600) and time.monotonic()-FX_LAST_ATTEMPT>=60:
   FX_LAST_ATTEMPT=time.monotonic()
   try:
    request=urllib.request.Request(FX_URL,headers={'User-Agent':'DO-IT/1.0'})
    with urllib.request.urlopen(request,timeout=4) as response:
     payload=json.loads(response.read(262145),parse_float=Decimal)
    if payload.get('result')!='success' or payload.get('base_code')!='USD':
     raise ValueError('Réponse de taux invalide')
    raw=payload['rates']; checked={}
    for currency in CURRENCIES:
     rate=Decimal(str(raw[currency]))
     if not rate.is_finite() or rate<=0 or rate>Decimal('10000000000'):
      raise ValueError('Taux invalide')
     checked[currency]=str(rate)
    if Decimal(checked['USD'])!=1: raise ValueError('Base invalide')
    stamp=str(payload['time_last_update_utc'])
    if len(stamp)>100: raise ValueError('Horodatage invalide')
    with db() as c:
     c.execute('INSERT OR REPLACE INTO fx_cache VALUES(1,?,?,?)',(json.dumps(checked),stamp,int(time.time())))
     cached=c.execute('SELECT * FROM fx_cache WHERE id=1').fetchone()
    FX_LAST_FAILED=False
    degraded=False
   except Exception:
    FX_LAST_FAILED=True
    degraded=True
  if not cached: raise ConnectionError('Source de taux indisponible. Réessayez plus tard.')
  rates=json.loads(cached['rates_json'])
  rate=Decimal(rates[to_currency])/Decimal(rates[from_currency])
  result=(value*rate).quantize(Decimal('0.01'),rounding=ROUND_HALF_EVEN)
  return {'amount':str(value),'from':from_currency,'to':to_currency,'result':str(result),
          'rate':str(rate.quantize(Decimal('0.00000001'),rounding=ROUND_HALF_EVEN)),
          'source':'ExchangeRate-API','source_time':cached['source_timestamp'],
          'retrieved_at':datetime.fromtimestamp(cached['fetched_at'],timezone.utc).isoformat(),
          'stale':degraded or time.time()-cached['fetched_at']>=86400,
          'note':'Conversion indicative uniquement, sans transaction.'}

def allow(ip):
 with RATE_LOCK:
  t=time.monotonic(); a=[x for x in RATE.get(ip,[]) if t-x<300]; a.append(t); RATE[ip]=a
  if len(RATE)>10000:
   for k,v in list(RATE.items()):
    if not v or t-v[-1]>300: RATE.pop(k,None)
  return len(a)<=25
class Handler(BaseHTTPRequestHandler):
 server_version='DOIT/1.0'
 def log_message(self,fmt,*args): logging.info('%s %s',self.address_string(),fmt%args)
 def headers_common(self):
  self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: https:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
 def reply(self,code,obj,cookie=None):
  content=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(code); self.headers_common(); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(content)))
  if cookie is not None: self.send_header('Set-Cookie',cookie)
  self.end_headers(); self.wfile.write(content)
 def body(self):
  if not self.headers.get('Content-Type','').lower().startswith('application/json'): raise ValueError('Format de requête invalide.')
  try: n=int(self.headers.get('Content-Length','0'))
  except ValueError: raise ValueError('Requête invalide.')
  if n<1 or n>8192: raise ValueError('Taille de requête invalide.')
  try:
   data=json.loads(self.rfile.read(n));
   if not isinstance(data,dict): raise ValueError()
   return data
  except (ValueError,UnicodeDecodeError): raise ValueError('Données invalides.')
 def session(self):
  cookie=SimpleCookie()
  try: cookie.load(self.headers.get('Cookie','')); raw=cookie.get('doit_session'); raw=raw.value if raw else ''
  except Exception: return None
  if not raw: return None
  with db() as c:
   row=c.execute('SELECT u.id,u.first_name,u.last_name,u.email,u.phone,u.referral_code,u.display_currency,p.avatar_url,COALESCE(st.is_active,1) AS is_active,s.csrf FROM sessions s JOIN users u ON u.id=s.user_id LEFT JOIN user_profiles p ON p.user_id=u.id LEFT JOIN user_account_status st ON st.user_id=u.id WHERE s.token_hash=? AND s.expires>?',(token_hash(raw),int(time.time()))).fetchone()
   if row and not row['is_active']:return None
   return row
 def auth(self):
  s=self.session()
  if not s: self.reply(401,{'error':'Connectez-vous pour continuer.'}); return None
  return s
 def new_session(self,uid):
  raw=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
  with db() as c:
   c.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),)); c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(token_hash(raw),uid,csrf,int(time.time())+43200))
  return 'doit_session='+raw+'; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200'+('; Secure' if SECURE else '')
 def csrf_ok(self,s): return bool(s and hmac.compare_digest(self.headers.get('X-CSRF-Token',''),s['csrf']))
 def do_GET(self):
  path=urlparse(self.path).path
  if path=='/api/health':
   try:
    with db() as c:c.execute('SELECT COUNT(*) FROM users').fetchone()
    return self.reply(200,{'status':'ok','manual_operations':'enabled'})
   except (sqlite3.Error,RuntimeError):
    return self.reply(503,{'status':'database_unavailable','manual_operations':'enabled'})
  if path=='/api/plans': return self.reply(200,{'plans':PLANS,'note':'Rendements théoriques non garantis. Seuils XOF convertis en USD au taux publié lors de l’activation.'})
  if path=='/api/investments':
   s=self.auth()
   if not s:return
   return self.reply(200,{'investments':investments.list_for_user(DB,s['id'])})
  if path=='/api/manual/config':
   try: fee_bps=web_queue.fee_bps_from_percent(WITHDRAW_FEE_PERCENT)
   except ValueError: fee_bps=None
   sess=self.session()
   admin=bool(sess and is_admin(sess))
   return self.reply(200,{'enabled':True,'is_admin':admin,'deposit_address':web_queue.ADDRESS,'network':'USDT TRC20','fee_bps':fee_bps,'minimum_withdrawal_cents':1000,'notice':'Traitement manuel : chaque dépôt et retrait est contrôlé par l’administrateur.'})
  if path=='/api/manual/requests':
   s=self.auth()
   if not s:return
   return self.reply(200,{'requests':web_queue.list_user(DB,s['id'])})
  if path=='/api/convert':
   query=parse_qs(urlparse(self.path).query)
   try:
    result=conversion(query.get('amount',[''])[0],query.get('from',[''])[0],query.get('to',[''])[0])
    return self.reply(200,result)
   except ValueError as e:return self.reply(400,{'error':str(e)})
   except ConnectionError as e:return self.reply(503,{'error':str(e)})
  if path=='/api/notifications':
   s=self.auth()
   if not s:return
   with db() as c:rows=[dict(r) for r in c.execute('SELECT id,title,body,created_at,read_at FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 100',(s['id'],))]
   return self.reply(200,{'notifications':rows,'unread':sum(1 for r in rows if not r['read_at'])})
  if path=='/api/support':
   s=self.auth()
   if not s:return
   with db() as c:rows=[dict(r) for r in c.execute('SELECT id,sender,message,created_at FROM support_messages WHERE user_id=? ORDER BY id DESC LIMIT 100',(s['id'],))]
   return self.reply(200,{'messages':rows[::-1]})
  if path=='/api/calendar':
   s=self.auth()
   if not s:return
   rows=investments.list_for_user(DB,s['id'])
   return self.reply(200,{'events':[{'id':x['id'],'title':x['plan'],'maturity':datetime.fromtimestamp(x['maturity'],timezone.utc).isoformat(),'status':x['status']} for x in rows]})
  if path=='/api/admin/dashboard':
   s=self.auth()
   if not s:return
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   with db() as c:
    users=c.execute('SELECT COUNT(*) n FROM users').fetchone()['n']
    active=c.execute('SELECT COUNT(*) n FROM users u LEFT JOIN user_account_status st ON st.user_id=u.id WHERE COALESCE(st.is_active,1)=1').fetchone()['n']
    deposits=c.execute("SELECT COUNT(*) n FROM review_requests WHERE kind='deposit'").fetchone()['n']
    withdrawals=c.execute("SELECT COUNT(*) n FROM review_requests WHERE kind='withdrawal'").fetchone()['n']
    pending=c.execute("SELECT COUNT(*) n FROM review_requests WHERE state='pending'").fetchone()['n']
    inv=c.execute("SELECT COUNT(*) n FROM fin_investments WHERE status='active'").fetchone()['n']
   return self.reply(200,{'users':users,'active_users':active,'deposits':deposits,'withdrawals':withdrawals,'pending_requests':pending,'active_investments':inv})
  if path=='/api/admin/support':
   s=self.auth()
   if not s:return
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   with db() as c:rows=[dict(r) for r in c.execute("SELECT m.id,m.user_id,u.first_name,u.last_name,u.email,m.message,m.created_at FROM support_messages m JOIN users u ON u.id=m.user_id WHERE m.sender='client' ORDER BY m.id DESC LIMIT 200")]
   return self.reply(200,{'messages':rows})
  if path=='/api/admin/user-ledger':
   s=self.auth()
   if not s:return
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   q=parse_qs(urlparse(self.path).query);uid=q.get('user_id',[''])[0]
   if not uid.isdigit():return self.reply(400,{'error':'Identifiant client invalide.'})
   with db() as c:
    user=c.execute('SELECT id,first_name,last_name,email FROM users WHERE id=?',(int(uid),)).fetchone()
    if not user:return self.reply(404,{'error':'Client introuvable.'})
    rows=[dict(r) for r in c.execute('SELECT kind,amount_usd_minor,amount_xof_minor,created_at,description FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 200',(int(uid),))]
    audit=[dict(r) for r in c.execute('SELECT rr.id AS request_id,rr.kind,e.actor,e.action,e.reason,e.created_at FROM review_events e JOIN review_requests rr ON rr.id=e.request_id WHERE rr.user_id=? ORDER BY e.id DESC LIMIT 200',(int(uid),))]
    finance_entries=[dict(r) for r in c.execute('SELECT t.kind,t.idem_key,t.created_at,p.account,p.amount FROM fin_postings p JOIN fin_transactions t ON t.id=p.transaction_id WHERE p.account LIKE ? ORDER BY t.id DESC LIMIT 300',(f'user:{int(uid)}:%',))]
   return self.reply(200,{'user':dict(user),'entries':rows,'audit':audit,'finance_entries':finance_entries})
  if path=='/api/admin/users':
   s=self.auth()
   if not s:return
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   q=parse_qs(urlparse(self.path).query).get('q',[''])[0].strip()[:100]
   with db() as c:rows=[dict(r) for r in c.execute("SELECT u.id,u.first_name,u.last_name,u.email,u.phone,COALESCE(st.is_active,1) AS is_active,u.created_at FROM users u LEFT JOIN user_account_status st ON st.user_id=u.id WHERE u.email LIKE ? OR CAST(u.id AS TEXT)=? OR u.first_name LIKE ? OR u.last_name LIKE ? ORDER BY u.id DESC LIMIT 100",(f'%{q}%',q,f'%{q}%',f'%{q}%'))]
   return self.reply(200,{'users':rows})
  if path=='/api/admin/export':
   s=self.auth()
   if not s:return
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   import csv,io
   out=io.StringIO();w=csv.writer(out);w.writerow(['id','user_id','type','montant_usd_centimes','montant_xof_centimes','date','description'])
   with db() as c:
    for r in c.execute('SELECT id,user_id,kind,amount_usd_minor,amount_xof_minor,created_at,description FROM ledger ORDER BY id DESC LIMIT 10000'):w.writerow(list(r))
    w.writerow(['FINANCE_LEDGER','transaction_id','kind','account','amount_usd_cents','created_at','idempotency_key'])
    for r in c.execute('SELECT t.id,t.kind,p.account,p.amount,t.created_at,t.idem_key FROM fin_postings p JOIN fin_transactions t ON t.id=p.transaction_id ORDER BY t.id DESC LIMIT 50000'):w.writerow(['FINANCE_LEDGER',r['id'],r['kind'],r['account'],r['amount'],r['created_at'],r['idem_key']])
    w.writerow(['ADMIN_AUDIT','request_id','kind','actor','action','reason','created_at'])
    for r in c.execute('SELECT rr.id,rr.kind,e.actor,e.action,e.reason,e.created_at FROM review_events e JOIN review_requests rr ON rr.id=e.request_id ORDER BY e.id DESC LIMIT 50000'):w.writerow(['ADMIN_AUDIT',r['id'],r['kind'],r['actor'],r['action'],r['reason'],r['created_at']])
   raw=('\ufeff'+out.getvalue()).encode('utf-8');self.send_response(200);self.headers_common();self.send_header('Content-Type','text/csv; charset=utf-8');self.send_header('Content-Disposition','attachment; filename="do-it-operations.csv"');self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
  if path=='/api/admin':
   s=self.auth()
   if not s:return
   if not is_admin(s):
    return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   with db() as c:
    users=c.execute('SELECT COUNT(*) AS n FROM users').fetchone()['n']
    test_bonuses=c.execute("SELECT COUNT(*) AS n FROM ledger WHERE kind='bonus_test'").fetchone()['n']
   return self.reply(200,{'users':users,'test_bonuses':test_bonuses,'payments_enabled':False,
                          'note':'Tableau de contrôle limité en lecture seule, sans fonctions financières.'})
  if path in ['/api/me','/api/dashboard','/api/referrals']:
   s=self.auth()
   if not s:return
   with db() as c:
    if path=='/api/me': return self.reply(200,{'user':dict(s)})
    if path=='/api/dashboard':
     rows=[dict(r) for r in c.execute('SELECT kind,amount_usd_minor,amount_xof_minor,description,created_at FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 30',(s['id'],))]
     bal=finledger.snapshot(DB,s['id'])
     inv=investments.list_for_user(DB,s['id'])
     return self.reply(200,{'available_usd':bal['available']/100,'invested_usd':bal['invested']/100,'accrued_usd':sum(x['total_accrued_cents'] for x in inv if x['status']!='settled')/100,'commissions_usd':investments.funded_commissions(DB,s['id'])/100,'bonus_xof':5000,'bonus_usd':None,'reserved_usd':bal['reserved']/100,'entries':rows,'investments':inv,'payments_enabled':False})
    members=[dict(r) for r in c.execute('''WITH RECURSIVE network(id,first_name,last_name,created_at,depth) AS (
      SELECT id,first_name,last_name,created_at,1 FROM users WHERE referred_by=?
      UNION ALL
      SELECT u.id,u.first_name,u.last_name,u.created_at,n.depth+1 FROM users u JOIN network n ON u.referred_by=n.id WHERE n.depth<5
     ) SELECT first_name,substr(last_name,1,1) || '.' AS last_initial,created_at,depth FROM network ORDER BY depth,created_at LIMIT 1000''',(s['id'],))]
    return self.reply(200,{'code':s['referral_code'],'members':members,'truncated':len(members)==1000,'commission_rates':[15,7,5,3,2],'commission_credited_usd':investments.funded_commissions(DB,s['id'])/100})
  if path not in ['/','/admin','/admin/','/index.html','/app.js','/style.css','/logo.png']: return self.reply(404,{'error':'Page introuvable.'})
  f=ROOT/'static'/('index.html' if path in ['/','/admin','/admin/','/index.html'] else path[1:])
  try: content=f.read_bytes()
  except OSError:return self.reply(404,{'error':'Fichier introuvable.'})
  mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.png':'image/png'}[f.suffix]
  self.send_response(200); self.headers_common(); self.send_header('Content-Type',mime); self.send_header('Content-Length',str(len(content))); self.send_header('Cache-Control','no-cache'); self.end_headers(); self.wfile.write(content)
 def do_POST(self):
  path=urlparse(self.path).path
  if path in ['/api/register','/api/login'] and not allow(self.client_address[0]): return self.reply(429,{'error':'Trop de tentatives. Réessayez plus tard.'})
  try: data=self.body()
  except ValueError as e:return self.reply(400,{'error':str(e)})
  if path=='/api/register':
   first=str(data.get('first_name','')).strip(); last=str(data.get('last_name','')).strip(); phone=str(data.get('phone','')).strip(); email=str(data.get('email','')).strip().lower(); pw=data.get('password',''); ref=str(data.get('referral','')).strip()
   if ADMIN_EMAIL and email==ADMIN_EMAIL:return self.reply(409,{'error':'Cet e-mail est déjà utilisé.'})
   if not (1<=len(first)<=80 and 1<=len(last)<=80 and 5<=len(phone)<=30 and re.fullmatch(r'[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}',email) and isinstance(pw,str) and 12<=len(pw)<=256): return self.reply(400,{'error':'Vérifiez les champs. Le mot de passe doit contenir au moins 12 caractères.'})
   try:
    with db() as c:
     parent=c.execute('SELECT id FROM users WHERE referral_code=?',(ref,)).fetchone() if ref else None
     if ref and not parent:return self.reply(400,{'error':'Code de parrainage invalide.'})
     code=secrets.token_urlsafe(9); cur=c.execute('INSERT INTO users(first_name,last_name,phone,email,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?,?,?,?)',(first,last,phone,email,pass_hash(pw),code,parent['id'] if parent else None,now())); uid=cur.lastrowid
     c.execute('INSERT INTO ledger(user_id,kind,amount_xof_minor,created_at,description) VALUES(?,?,?,?,?)',(uid,'bonus_test',500000,now(),'Bonus de test non retirable, conversion USD en attente de source de taux fiable.'))
     c.execute('INSERT INTO audit(user_id,action,created_at) VALUES(?,?,?)',(uid,'register',now()));c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)',(uid,'Bienvenue sur DO IT','Votre espace personnel est créé. Consultez vos informations et les conditions des services.',now()))
    return self.reply(201,{'ok':True},self.new_session(uid))
   except sqlite3.IntegrityError:return self.reply(409,{'error':'Cet e-mail est déjà utilisé.'})
  if path=='/api/login':
   email=str(data.get('email','')).strip().lower(); pw=data.get('password','')
   if not isinstance(pw,str) or len(pw)>256:return self.reply(400,{'error':'Identifiants invalides.'})
   with db() as c: user=c.execute('SELECT u.id,u.password_hash,COALESCE(st.is_active,1) AS is_active FROM users u LEFT JOIN user_account_status st ON st.user_id=u.id WHERE u.email=?',(email,)).fetchone()
   if not user or not pass_check(pw,user['password_hash']) or not user['is_active']:
    if not user: pass_check(pw,'scrypt$'+'00'*16+'$'+'00'*32)
    return self.reply(401,{'error':'Identifiants invalides.'})
   with db() as c:c.execute('INSERT INTO audit(user_id,action,created_at) VALUES(?,?,?)',(user['id'],'login',now()))
   return self.reply(200,{'ok':True},self.new_session(user['id']))
  if path in ['/api/manual/admin/list','/api/manual/admin/decide','/api/manual/admin/credit','/api/manual/admin/complete']:
   admin_session=self.auth()
   if not admin_session:return
   if not is_admin(admin_session):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   if not self.csrf_ok(admin_session):return self.reply(403,{'error':'Session invalide. Rechargez la page.'})
   actor='admin:'+str(admin_session['id'])
   try:
    if path.endswith('/list'):return self.reply(200,{'requests':web_queue.list_admin(DB)})
    if path.endswith('/credit'):
     changed=manual_settlement.credit_deposit(DB,data.get('id'),actor,data.get('reason'),data.get('usdt'),data.get('rate'),data.get('source'))
     return self.reply(200,{'changed':changed,'notice':'Crédit manuel enregistré après vérification par l’administrateur.'})
    if path.endswith('/complete'):
     changed=manual_settlement.complete_withdrawal(DB,data.get('id'),actor,data.get('reason'),data.get('txid'))
     return self.reply(200,{'changed':changed,'notice':'Paiement manuel enregistré. Le site n’a effectué aucun transfert.'})
    request_id=data.get('id'); decision=data.get('decision')
    rows=[r for r in web_queue.list_admin(DB) if r['id']==request_id]
    state=review_queue.decide(DB,request_id,decision,actor,'TXID et montant vérifiés par l’administrateur' if decision=='approve' else 'Demande rejetée par l’administrateur')
    if rows:
     with db() as c:c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)',(rows[0]['user_id'],'Mise à jour de votre demande','Votre demande de '+('dépôt' if rows[0]['kind']=='deposit' else 'retrait')+' a été '+('approuvée' if decision=='approve' else 'rejetée')+'.',now()))
    if decision=='approve' and rows and rows[0]['kind']=='deposit' and rows[0].get('declared_currency') in ('USD','XOF'):
     row=rows[0]
     manual_settlement.credit_deposit(DB,request_id,actor,'Dépôt approuvé après vérification du TXID et du montant',row['declared_usdt'],'1','Valeur USD/XOF convertie au taux publié à la demande')
     state='credited_test'
    return self.reply(200,{'state':state,'notice':'Demande approuvée et solde mis à jour.' if decision=='approve' and rows and rows[0]['kind']=='deposit' and rows[0].get('declared_currency') in ('USD','XOF') else 'Décision administrative enregistrée.'})
   except (ValueError,sqlite3.IntegrityError):return self.reply(400,{'error':'Demande invalide ou déjà traitée.'})
  s=self.auth()
  if not s:return
  if not self.csrf_ok(s):return self.reply(403,{'error':'Session invalide. Rechargez la page.'})
  if path=='/api/profile':
   first=str(data.get('first_name','')).strip();last=str(data.get('last_name','')).strip();phone=str(data.get('phone','')).strip();avatar=str(data.get('avatar_url','')).strip()
   if not (1<=len(first)<=80 and 1<=len(last)<=80 and 5<=len(phone)<=30):return self.reply(400,{'error':'Vérifiez le prénom, le nom et le téléphone.'})
   if avatar and (len(avatar)>500 or not re.fullmatch(r'https://[^\s]+',avatar)):return self.reply(400,{'error':'Photo : utilisez une URL HTTPS valide.'})
   with db() as c:c.execute('UPDATE users SET first_name=?,last_name=?,phone=? WHERE id=?',(first,last,phone,s['id']))
   with db() as c:c.execute('INSERT INTO user_profiles(user_id,avatar_url) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET avatar_url=excluded.avatar_url',(s['id'],avatar or None))
   return self.reply(200,{'ok':True})
  if path=='/api/notifications/read':
   nid=data.get('id')
   with db() as c:
    if nid=='all':c.execute('UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL',(now(),s['id']))
    else:c.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=? AND read_at IS NULL',(now(),nid,s['id']))
   return self.reply(200,{'ok':True})
  if path=='/api/support':
   msg=str(data.get('message','')).strip()
   if not 2<=len(msg)<=2000:return self.reply(400,{'error':'Le message doit contenir entre 2 et 2 000 caractères.'})
   with db() as c:c.execute("INSERT INTO support_messages(user_id,sender,message,created_at) VALUES(?,?,?,?)",(s['id'],'client',msg,now()))
   return self.reply(201,{'ok':True})
  if path=='/api/admin/users/status':
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   uid=data.get('user_id');active=data.get('active')
   if not isinstance(uid,int) or uid<=0 or not isinstance(active,bool):return self.reply(400,{'error':'Paramètres invalides.'})
   if uid==s['id']:return self.reply(400,{'error':'Vous ne pouvez pas suspendre votre propre compte.'})
   with db() as c:
    c.execute('INSERT INTO user_account_status(user_id,is_active) VALUES(?,?) ON CONFLICT(user_id) DO UPDATE SET is_active=excluded.is_active',(uid,1 if active else 0))
    c.execute('INSERT INTO audit(user_id,action,created_at) VALUES(?,?,?)',(uid,'admin_activate' if active else 'admin_suspend',now()))
   return self.reply(200,{'ok':True})
  if path=='/api/admin/support/reply':
   if not is_admin(s):return self.reply(403,{'error':'Accès administrateur non autorisé.'})
   uid=data.get('user_id');msg=str(data.get('message','')).strip()
   if not isinstance(uid,int) or not 1<=len(msg)<=2000:return self.reply(400,{'error':'Réponse invalide.'})
   with db() as c:
    if not c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():return self.reply(404,{'error':'Client introuvable.'})
    c.execute("INSERT INTO support_messages(user_id,sender,message,created_at) VALUES(?,?,?,?)",(uid,'admin',msg,now()))
    c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)',(uid,'Réponse du support',msg[:300],now()))
   return self.reply(201,{'ok':True})
  if path=='/api/invest':
   try:
    if not isinstance(data.get('plan'),str) or data['plan'] not in investments.PLANS:raise ValueError('Plan invalide')
    web_queue.parse_cents(data.get('usd'))
    finledger.valid_key(data.get('request_key'))
    quote=conversion('1','USD','XOF')
    result=investments.create(DB,s['id'],data.get('plan'),data.get('usd'),data.get('request_key'),quote)
    return self.reply(201 if result['created'] else 200,result)
   except ConnectionError:return self.reply(503,{'error':'Taux de change indisponible. Réessayez plus tard.'})
   except (ValueError,sqlite3.IntegrityError) as e:return self.reply(400,{'error':str(e)})
  if path.startswith('/api/manual/'):
   if not allow('manual:'+self.client_address[0]):return self.reply(429,{'error':'Trop de tentatives. Réessayez plus tard.'})
   try:
    if path=='/api/manual/deposit':
     currency=data.get('currency')
     if currency in ('USD','XOF'):
      amount=data.get('amount')
      converted=conversion(amount,currency,'USD')
      if converted.get('stale'):raise ConnectionError('Taux de change trop ancien. Réessayez plus tard.')
      usd=converted['result'];usdt=usd
      rid=web_queue.deposit(DB,s['id'],usd,usdt,data.get('txid'),currency,amount)
     else:
      rid=web_queue.deposit(DB,s['id'],data.get('usd'),data.get('usdt'),data.get('txid'),None,None)
     with db() as c:c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)',(s['id'],'Dépôt enregistré','Votre demande de dépôt a été enregistrée et attend son traitement.',now()))
     return self.reply(201,{'id':rid,'state':'pending','notice':'Déclaration reçue. Le crédit nécessite une décision de l’administrateur.'})
    if path=='/api/manual/withdraw':
     rid=web_queue.withdraw(DB,s['id'],data.get('usd'),data.get('address'),WITHDRAW_FEE_PERCENT,data.get('accepted_fee_bps'),data.get('accepted_fee_cents'))
     with db() as c:c.execute('INSERT INTO notifications(user_id,title,body,created_at) VALUES(?,?,?,?)',(s['id'],'Retrait enregistré','Votre demande de retrait a été enregistrée et attend son traitement.',now()))
     return self.reply(201,{'id':rid,'state':'pending','notice':'Demande reçue. Le paiement sera effectué manuellement par l’administrateur.'})
    if path=='/api/manual/withdraw-quote':
     return self.reply(200,web_queue.quote(data.get('usd'),WITHDRAW_FEE_PERCENT))
    return self.reply(404,{'error':'Action introuvable.'})
   except (ValueError,sqlite3.IntegrityError) as e:
    return self.reply(400,{'error':'Demande invalide, déjà utilisée ou solde disponible insuffisant.'})
  if path=='/api/logout':
   cookie=SimpleCookie(); cookie.load(self.headers.get('Cookie','')); raw=cookie.get('doit_session')
   if raw:
    with db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(token_hash(raw.value),))
   return self.reply(200,{'ok':True},'doit_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'+('; Secure' if SECURE else ''))
  if path=='/api/preferences':
   currency=data.get('currency')
   if currency not in ['USD','EUR','XOF','GBP','NGN','GHS','CAD','CNY','JPY']: return self.reply(400,{'error':'Devise non prise en charge.'})
   with db() as c:c.execute('UPDATE users SET display_currency=? WHERE id=?',(currency,s['id']))
   return self.reply(200,{'ok':True})
  if path in ['/api/deposit','/api/withdraw']: return self.reply(503,{'error':'Service non activé : aucune transaction réelle ne peut être effectuée.'})
  return self.reply(404,{'error':'Action introuvable.'})
 def do_HEAD(self): self.send_response(405); self.end_headers()
def settlement_worker():
 while True:
  try:
   stats=investments.settle_due(DB)
   if stats['completed'] or stats['awaiting_funding']:logging.info('Échéances : %s',stats)
  except Exception:logging.exception('Erreur de traitement des échéances')
  time.sleep(60)
if __name__=='__main__':
 logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s'); init()
 threading.Thread(target=settlement_worker,daemon=True).start()
 print(f'DO IT: http://{HOST}:{PORT} | transferts manuels',flush=True); ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
