#!/usr/bin/env python3
"""Backup/inspect/rehearse only. Never modifies the source or deploys anything."""
import argparse, hashlib, json, os, sqlite3, subprocess, sys, urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def connect_readonly(path):
 path=Path(path).expanduser().resolve(strict=True)
 if not path.is_file():raise ValueError('La source doit être un fichier SQLite existant.')
 return sqlite3.connect('file:'+urllib.parse.quote(str(path),safe='/')+'?mode=ro',uri=True,timeout=15)

def validate(conn):
 result=conn.execute('PRAGMA integrity_check').fetchall()
 if result!=[('ok',)]:raise RuntimeError('Échec integrity_check : '+str(result[:3]))
 violations=conn.execute('PRAGMA foreign_key_check').fetchmany(5)
 if violations:raise RuntimeError('Échec foreign_key_check : '+str(violations))

def backup(src,dest):
 dest=Path(dest).expanduser().absolute()
 if not dest.parent.is_dir():raise ValueError('Le dossier de destination doit déjà exister.')
 c=connect_readonly(src);owned=False;out=None
 try:
  validate(c)
  fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd);owned=True
  out=sqlite3.connect(str(dest));c.backup(out,pages=128,sleep=0.05);out.commit();validate(out);out.close();out=None
  return str(dest)
 except Exception:
  if out is not None:out.close()
  if owned:
   try:dest.unlink()
   except FileNotFoundError:pass
  raise
 finally:c.close()

def hash_value(v):
 if v is None:return b'N'
 if isinstance(v,bytes):return b'B'+v
 return (type(v).__name__+':'+str(v)).encode('utf-8')
def inventory(path):
 c=connect_readonly(path)
 try:
  validate(c);tables={}
  names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
  for name in names:
   safe='"'+name.replace('"','""')+'"';cols=[x[1] for x in c.execute('PRAGMA table_info('+safe+')')]
   hashes=[]
   for row in c.execute('SELECT * FROM '+safe):
    h=hashlib.sha256()
    for v in row:
     b=hash_value(v);h.update(len(b).to_bytes(8,'big'));h.update(b)
    hashes.append(h.digest())
   h=hashlib.sha256()
   for rh in sorted(hashes):h.update(rh)
   tables[name]={'rows':len(hashes),'columns':cols,'digest':h.hexdigest()}
  if 'users' not in tables:raise ValueError('Base incompatible : table users absente.')
  if not {'id','email','password_hash','referral_code'}.issubset(tables['users']['columns']):raise ValueError('Schéma utilisateur incompatible.')
  old=0
  if 'review_requests' in tables:
   if 'withdrawal_fee_snapshot' in tables:
    old=c.execute("SELECT COUNT(*) FROM review_requests r LEFT JOIN withdrawal_fee_snapshot f ON f.request_id=r.id WHERE r.kind='withdrawal' AND r.state IN ('pending','approved_payment_pending') AND f.request_id IS NULL").fetchone()[0]
   else:old=c.execute("SELECT COUNT(*) FROM review_requests WHERE kind='withdrawal' AND state IN ('pending','approved_payment_pending')").fetchone()[0]
  return {'tables':tables,'legacy_pending_withdrawals_without_fee':old}
 finally:c.close()

def admin_conflict(path,email):
 if not email:return None
 c=connect_readonly(path)
 try:
  row=c.execute('SELECT id FROM users WHERE email=?',(email.strip().lower(),)).fetchone()
  if not row:return 'aucun compte existant avec cet e-mail'
  exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_principals'").fetchone()
  if exists and c.execute('SELECT 1 FROM admin_principals WHERE user_id=?',(row[0],)).fetchone():return 'compte déjà administrateur'
  return 'CONFLIT : compte existant non administrateur ; ne pas modifier ni promouvoir automatiquement'
 finally:c.close()

def summary(report):
 return {'user_count':report['tables']['users']['rows'],'counts':{k:v['rows'] for k,v in report['tables'].items()},'legacy_pending_withdrawals_without_fee':report['legacy_pending_withdrawals_without_fee']}

def rehearsal(src,dest,email):
 before=inventory(src);path=backup(src,dest)
 env={**os.environ,'DATABASE_URL':str(Path(path).resolve()),'DOIT_TEST_SQLITE':'1','DOIT_ADMIN_EMAIL':'','DOIT_ADMIN_BOOTSTRAP_PASSWORD':'','DOIT_ADMIN_REVIEW_SECRET':'','DOIT_MANUAL_TEST':'0'}
 try:
  run=subprocess.run([sys.executable,'-c','import server; server.init()'],cwd=ROOT,env=env,text=True,capture_output=True,timeout=60)
  if run.returncode:raise RuntimeError('Initialisation sur copie échouée : '+run.stderr[-1200:])
  after=inventory(path);changes=[]
  for name,old in before['tables'].items():
   new=after['tables'].get(name)
   if not new or old['columns']!=new['columns'] or old['rows']!=new['rows'] or old['digest']!=new['digest']:changes.append(name)
  if changes:raise RuntimeError('Données ou colonnes existantes modifiées : '+', '.join(changes))
  return {'resultat':'OK sur la copie','avant':summary(before),'apres':summary(after),'admin':admin_conflict(src,email),'copie':path,'avertissement':'Les tables et lignes préexistantes correspondent. Aucun test de paiement réel, audit ou garantie de migration en production.'}
 except Exception:
  # Retain the isolated copy for diagnosis, never remove or mutate the source.
  raise

def main():
 p=argparse.ArgumentParser(description='Sauvegarde et répétition DO IT : ne déploie rien et ne modifie jamais la source.')
 sp=p.add_subparsers(dest='cmd',required=True)
 b=sp.add_parser('backup');b.add_argument('--source',required=True);b.add_argument('--destination',required=True)
 i=sp.add_parser('inspect');i.add_argument('--source',required=True);i.add_argument('--admin-email')
 r=sp.add_parser('rehearse');r.add_argument('--source',required=True);r.add_argument('--destination',required=True);r.add_argument('--admin-email')
 args=p.parse_args()
 try:
  if args.cmd=='backup':
   path=backup(args.source,args.destination);result={'resultat':'sauvegarde créée','fichier':path,'inventaire':summary(inventory(path))}
  elif args.cmd=='inspect':result={'inventaire':summary(inventory(args.source)),'admin':admin_conflict(args.source,args.admin_email)}
  else:result=rehearsal(args.source,args.destination,args.admin_email)
  print(json.dumps(result,ensure_ascii=False,indent=2))
 except Exception as e:
  print('ERREUR : '+str(e),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()
