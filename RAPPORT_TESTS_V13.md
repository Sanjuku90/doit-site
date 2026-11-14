# Rapport de vérification V13

- Tests automatisés : `python -m pytest -q`
- Résultat au moment de la préparation : **37 tests réussis**.
- Vérification syntaxique Python : `python -m py_compile server.py`
- Vérification syntaxique JavaScript : `node --check static/app.js`
- Routes V13 exercées par le test d'intégration : profil, assistance, notifications, calendrier, tableau de bord administrateur, recherche de clients, réponse support, export CSV et suspension de compte.

Ces tests vérifient le comportement logiciel couvert par les tests. Ils ne constituent pas un audit de sécurité, un test de charge, une validation réglementaire ou une preuve de réception/paiement sur blockchain.
