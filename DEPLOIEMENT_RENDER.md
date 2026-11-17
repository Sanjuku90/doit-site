# Déploiement Render — V12 corrigée

Le fichier `render.yaml` définit le serveur Python, et les variables d’environnement non secrètes. Les données sont stockées directement dans Supabase PostgreSQL : aucun disque Render ni migration. Lors de la création du service, renseigner les secrets demandés :

- `DATABASE_URL` : URI PostgreSQL Supabase (pooler Session, port 5432) avec le vrai mot de passe.

- `DOIT_ADMIN_EMAIL` : adresse unique du compte administrateur.
- `DOIT_ADMIN_BOOTSTRAP_PASSWORD` : mot de passe fort, 12 caractères minimum.

Conserver `DOIT_SECURE_COOKIE=1` et `DOIT_WITHDRAW_FEE_PERCENT=2`. Le serveur crée le compte administrateur au premier démarrage si les variables sont définies.

Après déploiement, ouvrir `/admin`, se connecter avec le compte administrateur, puis contrôler les parcours avec des données de faible valeur et des comptes autorisés. Ne jamais communiquer le mot de passe dans un chat ou l’inscrire dans le dépôt.

Les demandes de dépôt et de retrait sont gérées manuellement. L’application ne surveille pas la blockchain et ne transfère pas d’USDT. Vérifier les dépôts hors du site avant crédit ; effectuer les paiements dans le portefeuille puis consigner leur TXID. Faire auditer la sécurité, la conformité, les réserves et les mécanismes de protection avant toute utilisation avec les fonds de tiers.

## Ping externe pour limiter la mise en veille

Le workflow `.github/workflows/render-keepalive.yml` appelle `https://<votre-service>.onrender.com/api/health` toutes les 10 minutes depuis GitHub Actions. Pour l'activer :

1. Pousser ce dossier dans le dépôt GitHub connecté à Render, sur sa branche par défaut.
2. Dans GitHub, ouvrir **Settings → Secrets and variables → Actions → Variables → New repository variable**.
3. Créer `RENDER_URL` avec l'URL de base du service, par exemple `https://nom-du-service.onrender.com` (sans chemin `/api/health`).
4. Ouvrir **Actions**, activer les workflows si GitHub le demande, puis lancer **Keep Render service awake → Run workflow** pour vérifier le ping.

Ce ping entrant peut réduire les mises en veille après inactivité sur une instance gratuite, mais ce contournement n'est pas une garantie ni une fonctionnalité officielle de disponibilité permanente. GitHub peut retarder les tâches planifiées et Render peut redémarrer ou suspendre un service. Pour une disponibilité continue, utiliser une instance Render payante. Les données étant dans Supabase, un redémarrage de Render n'en fait perdre aucune ; le ping appelle aussi la base, ce qui évite la pause d'un projet Supabase gratuit inactif.
