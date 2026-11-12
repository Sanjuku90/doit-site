> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# Déployer DO IT sur Render

Cette archive contient un site partiel, pas une plateforme financière complète. Les paiements, dépôts, retraits et investissements réels sont désactivés. Ne pas y inscrire de données de vrais clients ni recevoir des fonds : l'authentification et l'application n'ont pas fait l'objet d'un audit de production. Réserver le déploiement à des tests contrôlés.

## Étapes

1. Décompressez l'archive. Placez le contenu du dossier `doit-site/` à la racine d'un nouveau dépôt GitHub ou GitLab privé, puis envoyez-le sur ce dépôt. Vérifiez que `render.yaml` se trouve à la racine du dépôt et qu'aucune base de données ni secret n'est importé.
2. Sur Render, sélectionnez **New > Blueprint**, connectez ce dépôt et validez la création du service selon l'interface affichée. Le fichier `render.yaml` déclare un service Python payant `0.5c-512mb` et un disque persistant de 1 Go : vérifiez le tarif et la disponibilité dans votre compte avant de confirmer.
3. Attendez que Render ait construit et démarré le service. Ouvrez l'URL HTTPS fournie par Render. Le contrôle de santé est `/api/health`.
4. Créez un compte de test avec des données fictives, reconnectez-vous, vérifiez les pages et testez le convertisseur. Pour vérifier la persistance, redéployez et reconnectez-vous au même compte. Les cookies ne fonctionnent en mode Render qu'en HTTPS.
5. Le fichier SQLite est enregistré dans `/var/data/doit.sqlite3` sur le disque persistant. Restez sur **une seule instance** : un disque Render ne peut pas être partagé par plusieurs instances. Le disque limite le déploiement sans interruption. Prévoyez des sauvegardes et vérifiez la restauration avant tout usage de données importantes.

## Important

- Le plan gratuit Render ne supporte pas les disques persistants. Sans disque, les comptes et sessions SQLite sont perdus après redémarrage/redéploiement ; n'utiliser la configuration proposée qu'avec le disque attaché.
- Ne définissez pas `DOIT_ADMIN_EMAIL` sur un service public : la vérification d'e-mail et le MFA ne sont pas implémentés ; un tiers pourrait s'inscrire avec cette adresse. L'administration est donc désactivée par défaut.
- Le limiteur de connexion est en mémoire et peut considérer que les visiteurs derrière un proxy partagent la même adresse. Il n'est pas une protection anti-abus de production. Déployer des contrôles adaptés en amont.
- La source de taux ExchangeRate-API nécessite une connexion Internet sortante depuis Render. Les données sont indicatives, mises à jour quotidiennement et ne servent pas à des règlements.
- L'URL `/api/health` vérifie l'accès à la base, pas le convertisseur externe ni la sécurité. Après déploiement, vérifier les journaux Render et tester séparément les parcours.
- Il n'y a pas de validation e-mail, 2FA, KYC, conformité AML, traitement de paiements, comptabilité financière complète ou audit de sécurité. Les calculs des plans sont des simulations et ne créent aucun investissement.

Les instructions génériques et le détail des fonctionnalités manquantes sont dans `README.md`.
