# Déploiement Render — V12 corrigée

Le fichier `render.yaml` définit le serveur Python, le disque persistant SQLite et les variables d’environnement non secrètes. Lors de la création du service, renseigner les deux secrets demandés :

- `DOIT_ADMIN_EMAIL` : adresse unique du compte administrateur.
- `DOIT_ADMIN_BOOTSTRAP_PASSWORD` : mot de passe fort, 12 caractères minimum.

Conserver `DOIT_DB=/var/data/doit.sqlite3`, `DOIT_SECURE_COOKIE=1` et `DOIT_WITHDRAW_FEE_PERCENT=2`. Le serveur crée le compte administrateur au premier démarrage si les variables sont définies.

Après déploiement, ouvrir `/admin`, se connecter avec le compte administrateur, puis contrôler les parcours avec des données de faible valeur et des comptes autorisés. Ne jamais communiquer le mot de passe dans un chat ou l’inscrire dans le dépôt.

Les demandes de dépôt et de retrait sont gérées manuellement. L’application ne surveille pas la blockchain et ne transfère pas d’USDT. Vérifier les dépôts hors du site avant crédit ; effectuer les paiements dans le portefeuille puis consigner leur TXID. Faire auditer la sécurité, la conformité, les réserves et les mécanismes de protection avant toute utilisation avec les fonds de tiers.
