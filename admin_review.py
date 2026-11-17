#!/usr/bin/env python3
"""Trusted local operator utility; intentionally not exposed over the web."""
import argparse, getpass, json, os, sys
from finance import review_queue as q
p=argparse.ArgumentParser(description='DO IT - file de validation locale, sans exécution financière')
p.add_argument('--db',default=os.environ.get('DATABASE_URL',''))
sub=p.add_subparsers(dest='command',required=True)
l=sub.add_parser('liste');l.add_argument('--etat',default=None)
a=sub.add_parser('historique');a.add_argument('id')
for name in ('approuver','rejeter'):
 s=sub.add_parser(name);s.add_argument('id');s.add_argument('--motif',required=True)
args=p.parse_args()
try:
 q.migrate(args.db)
 if args.command=='liste': result=q.list_requests(args.db,args.etat)
 elif args.command=='historique':result=q.events(args.db,args.id)
 else:
  actor=getpass.getuser()
  result={'etat':q.decide(args.db,args.id,'approve' if args.command=='approuver' else 'reject',actor,args.motif),'message':'Décision enregistrée. Aucun dépôt crédité ni paiement exécuté.'}
 print(json.dumps(result,ensure_ascii=False,indent=2))
except Exception as exc:
 print('Erreur : '+str(exc),file=sys.stderr);sys.exit(1)
