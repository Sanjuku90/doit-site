# Administration — correctif V12

L’ancienne configuration publique de `/admin` a été supprimée. Toutes les routes `/api/manual/admin/*` exigent désormais une session authentifiée, le rôle administrateur et un jeton CSRF valide.

Configurer avant le premier démarrage : `DOIT_ADMIN_EMAIL` et `DOIT_ADMIN_BOOTSTRAP_PASSWORD` (au moins 12 caractères). Le serveur crée le compte et son rôle administrateur. Ne jamais exposer ces secrets ni les placer dans le code source.

L’accès à `/admin` sans session administrateur ne donne accès à aucune demande. Les actions sont attribuées à l’identifiant du compte administrateur et journalisées.
