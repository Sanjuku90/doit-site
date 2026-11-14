# Rapport de vérification — correctif V12

Vérifications exécutées dans l’environnement de travail :

- `python -m py_compile server.py finance/*.py` : réussi.
- `node --check static/app.js` : réussi.
- `python -m unittest discover -s tests -q` : 35 tests réussis.

Les tests couvrent notamment les demandes de dépôt, les retraits et réservations, les frais, le registre comptable, les doubles soumissions, l’approbation manuelle, l’enregistrement du paiement et le refus d’accès administrateur aux utilisateurs non autorisés.

Limites : ces tests locaux ne remplacent pas un audit de sécurité, un déploiement réel, une vérification de la blockchain, un test de transfert USDT ni une vérification réglementaire. Le test de conversion dépend d’un fournisseur de taux externe et d’une connexion réseau.
