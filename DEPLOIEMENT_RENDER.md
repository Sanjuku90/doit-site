# Déploiement Render — Supabase PostgreSQL

Le fichier `render.yaml` configure le serveur Python pour Supabase PostgreSQL. Dans les variables d'environnement du service Render, configurer `DATABASE_URL` avec l'URI PostgreSQL du projet Supabase. Cette valeur est un secret : ne pas l'inscrire dans le dépôt, un journal ou une conversation.

Renseigner aussi les variables d'administration :

- `DOIT_ADMIN_EMAIL` : adresse unique du compte administrateur.
- `DOIT_ADMIN_BOOTSTRAP_PASSWORD` : mot de passe fort, 12 caractères minimum.

Conserver `DOIT_SECURE_COOKIE=1` et `DOIT_WITHDRAW_FEE_PERCENT=2`. La connexion PostgreSQL impose TLS. Au premier démarrage, le serveur crée les tables dans le schéma `public` et la base est vide : aucune donnée SQLite n'est importée. Prévoir et vérifier une migration de données distincte avant de remplacer un service qui contient déjà des comptes.

Après déploiement, ouvrir `/admin`, se connecter avec le compte administrateur, puis contrôler les parcours avec des données de faible valeur et des comptes autorisés. Ne jamais communiquer le mot de passe dans un chat ou l’inscrire dans le dépôt.

Les demandes de dépôt et de retrait sont gérées manuellement. L’application ne surveille pas la blockchain et ne transfère pas d’USDT. Vérifier les dépôts hors du site avant crédit ; effectuer les paiements dans le portefeuille puis consigner leur TXID. Faire auditer la sécurité, la conformité, les réserves et les mécanismes de protection avant toute utilisation avec les fonds de tiers.

## Ping de santé Render

Le workflow GitHub Actions `.github/workflows/render-keepalive.yml` appelle `/api/health` toutes les 10 minutes et peut aussi être lancé manuellement. Il lit l'URL de base depuis la variable Actions `RENDER_URL` du dépôt GitHub.

Si le workflow échoue, vérifier que `RENDER_URL` contient l'URL de base du service Render, sans chemin `/api/health`, puis lancer **Keep Render service awake → Run workflow** dans l'onglet Actions.

Ces requêtes peuvent limiter la veille d'un service gratuit, mais elles ne garantissent pas une disponibilité permanente : GitHub peut retarder les tâches planifiées et Render peut redémarrer ou suspendre le service. Pour une disponibilité continue, utiliser une instance Render payante. Le ping ne remplace ni une base PostgreSQL persistante ni une sauvegarde.

## Vérifications après déploiement

Ouvrir `/api/health` et confirmer que le statut est `ok`, puis contrôler les journaux Render et les fonctions d'administration avec des comptes de test. Ne pas utiliser de paiements réels. Les dépôts et retraits sont traités manuellement : l'application ne surveille pas la blockchain et n'envoie pas d'USDT. Faire auditer la sécurité, la conformité, les réserves et les mécanismes de protection avant toute utilisation avec les fonds de tiers.
