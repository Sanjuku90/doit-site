# DO IT v11

La bannière supérieure indiquant que les dépôts et retraits sont traités par l'administration a été retirée. Les informations relatives au traitement manuel restent dans les pages de dépôt et retrait.

## Résultat de la vérification des investissements

- Les quatre plans et leurs seuils/taux sont disponibles en simulation.
- Le simulateur présente des valeurs théoriques en XOF, pas des investissements réels.
- Le serveur renvoie 503 à la demande de création d'investissement : aucune somme n'est investie. Les gains quotidiens et commissions réels ne sont pas reliés au site.
- Le module financier expérimental isolé possède des tests, mais n'est pas relié au parcours utilisateur et ne rend pas l'investissement réel opérationnel.
- Les tests locaux ne prouvent ni le fonctionnement sur Render ni la sécurité du système.

L'administration `/admin` est toujours publique et sans authentification selon la demande précédente. Toute personne qui découvre ce chemin ou son API peut accéder aux demandes et modifier des soldes. Ne pas utiliser avec des clients ou de vrais fonds. Les opérations financières ne sont pas auditée ni vérifiées sur la blockchain.

## Déploiement et données

Si une version existante contient des comptes, suivre `MIGRATION_RENDER.md` avant tout redéploiement, sauvegarder la base et ne pas recréer le disque. Ne pas déployer sur `/var/data` sans disque persistant monté : Render refuse l'écriture. En service gratuit, une base dans `/tmp` est éphémère et peut disparaître au redémarrage.
