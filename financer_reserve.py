#!/usr/bin/env python3
"""Privileged internal accounting command, NOT proof or transfer of funds."""
import argparse,sys
import server
from finance import ledger,web_queue
p=argparse.ArgumentParser(description='Enregistrer un financement de réserve déjà vérifié hors du système.')
p.add_argument('--usd',required=True,help='Montant USD, ex. 125.50')
p.add_argument('--reference',required=True,help='Référence unique alphanumérique du rapprochement')
a=p.parse_args()
try:
 amount=web_queue.parse_cents(a.usd);ledger.valid_key(a.reference);server.init()
 result=ledger.book_verified_operator_funding(server.DB,amount,a.reference)
 print('Écriture créée.' if result[1] else 'Écriture déjà présente, aucune modification.')
 print('Attention : cette écriture ne prouve pas la disponibilité des fonds et ne transfère aucun argent.')
except Exception as e:print('Erreur :',str(e),file=sys.stderr);sys.exit(1)
