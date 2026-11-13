> **Version 10 :** l’accès /admin est public sans authentification. Lire `ADMIN_V10.md` ; les instructions admin ci-dessous peuvent être obsolètes.

# DO IT : préparer une migration Render sans perdre les comptes

**Aucun déploiement ni modification de votre base n'a été effectué.** Cette procédure est destinée à une base SQLite DO IT existante. Elle ne s'applique pas à une base Postgres. Les opérations avec des fonds et données client ne sont pas prêtes pour la production : les contrôles et audits ne sont pas terminés.

## Avant de commencer : identifier la source

Dans Render, identifiez le **service existant**, sa version déployée, `DOIT_DB`, le nom du disque attaché, son point de montage et le chemin exact de la base. Ne supposez pas que votre base se trouve à `/var/data/doit.sqlite3` : cette valeur n'est correcte que si votre service existant la configure ainsi. La base doit être sous le point de montage du disque pour persister. Ne publiez ni mots de passe, ni fichiers de base, ni secrets dans le dépôt ou dans une conversation.

- Un disque persistant Render nécessite un service payant et conserve seulement les fichiers dans son point de montage. Le service gratuit n'a pas de disque persistant et son système de fichiers est effacé au redémarrage, redéploiement ou arrêt automatique. Ne redéployez pas et ne redémarrez pas si les comptes sont encore dans un stockage éphémère : identifiez d'abord comment exporter la base vivante. Les services gratuits n'ont pas accès à Shell/SSH Render ; faites-vous assister par le support Render pour la récupération. Si le service a déjà redémarré et qu'il n'y a pas de sauvegarde, les données peuvent déjà avoir disparu.
- Si vous voulez **conserver le disque actuel**, mettez à jour le même service, après vérification du chemin `DOIT_DB` et du montage. Ne créez pas un nouveau service/Blueprint en supposant qu'il recevra automatiquement le disque existant. Ne changez pas le nom du disque, le point de montage ou le chemin de la base sans un plan de copie distinct et vérifié.
- Il n'y a pas de mode maintenance dans l'application actuelle. Faites bloquer temporairement les accès en écriture par votre infrastructure en amont ; vérifiez que les inscriptions, connexions qui écrivent, demandes et tâches en cours sont arrêtées. Maintenez ce gel jusqu'à la fin de la migration et des vérifications. La sauvegarde SQLite est cohérente au moment où elle est prise, mais ne contiendra pas les écritures reçues après sa création.

## 1. Sauvegarder avant le déploiement

Depuis un Shell/SSH **du service en cours** si disponible, prenez une sauvegarde cohérente avec l'API SQLite. Les scripts du nouveau ZIP ne sont pas forcément présents sur l'ancien service : la commande autonome ci-dessous n'en dépend pas. Remplacez les chemins par les chemins constatés. Le dossier de sauvegarde doit exister, être privé et situé sur un stockage persistant. Le nom de sauvegarde doit être nouveau : la commande refuse d'écraser un fichier.

```sh
export SOURCE_DB='/chemin/exact/de/la/base-existante.sqlite3'
export BACKUP_DB='/chemin/persistant/protege/doit-avant-migration.sqlite3'
python3 - <<'PY'
import os, sqlite3, urllib.parse
src=os.environ['SOURCE_DB']; dst=os.environ['BACKUP_DB']
if not os.path.isfile(src): raise SystemExit('Source introuvable : arrêt sans modification')
conn=sqlite3.connect('file:'+urllib.parse.quote(os.path.abspath(src),safe='/')+'?mode=ro',uri=True)
if conn.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise SystemExit('Source corrompue : arrêt')
fd=os.open(dst,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600); os.close(fd)
out=sqlite3.connect(dst)
try:
 conn.backup(out); out.commit()
 if out.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]: raise RuntimeError('Sauvegarde invalide')
 if out.execute('PRAGMA foreign_key_check').fetchmany(1): raise RuntimeError('Clés étrangères invalides')
 print('Sauvegarde SQLite cohérente créée. Conserver et exporter de manière sécurisée.')
finally:
 out.close(); conn.close()
PY
```

Si cette commande échoue après création du fichier, considérez-le comme invalide, ne l'écrasez pas et faites diagnostiquer l'erreur avant de refaire une sauvegarde sous un **autre nom**. Une copie brute du seul fichier `.sqlite3` d'une base active peut omettre des écritures WAL : utilisez l'API SQLite ci-dessus. Exportez une copie chiffrée hors du service par un moyen approuvé et vérifiez sa restauration sur une base isolée. Gardez également une sauvegarde privée et la version exacte du code déployé avant migration. Un snapshot Render est complémentaire et peut dater de la veille ; restaurer un snapshot écrase les modifications postérieures. Un rollback du code ne restaure pas le disque.

## 2. Répéter sur une copie, sans toucher à la base active

Sur une machine privée disposant de Python 3.10+, décompressez ce ZIP et placez-vous dans son dossier `doit-site`. Transférez de manière sécurisée la sauvegarde créée à l'étape 1. Exemples : remplacez les chemins et l'e-mail par vos valeurs, sans publier la sortie.

```sh
python3 migration/prepare_sqlite.py inspect --source '/chemin/prive/sauvegarde.sqlite3' --admin-email 'admin@example.com'
python3 migration/prepare_sqlite.py rehearse --source '/chemin/prive/sauvegarde.sqlite3' --destination '/chemin/prive/repetition.sqlite3' --admin-email 'admin@example.com'
```

Le script vérifie l'intégrité, crée la destination uniquement si elle n'existe pas, initialise la **copie** avec le nouveau code, compare les lignes et les colonnes de toutes les tables préexistantes, et affiche les comptes par table. Il ne déploie rien, ne modifie ni ne remplace la source. La répétition ne configure pas l'admin et ne teste pas les services externes. Arrêtez-vous si le script échoue, si les nombres ne correspondent pas ou si `legacy_pending_withdrawals_without_fee` est supérieur à zéro : un ancien retrait sans frais ne peut pas être finalisé par v9. Son traitement doit être analysé et réconcilié avant reprise, sans modifier les montants silencieusement.

Si l'outil signale un **conflit admin**, ne donnez pas automatiquement des droits à ce compte. La v9 refuse le démarrage si l'e-mail administrateur configuré correspond à un utilisateur existant qui n'a pas déjà le rôle admin. Définissez une procédure d'identification et de migration contrôlée avant déploiement. La répétition n'ajoute pas de compte admin pour éviter de modifier les comptes existants.

## 3. Déploiement contrôlé du même service

Seulement après sauvegarde externe vérifiée, répétition réussie et résolution de tous les blocages, maintenir le gel puis mettre à jour le code du service existant. Confirmer à nouveau que le disque et `DOIT_DB` sont identiques à l'ancienne configuration. L'application crée les tables manquantes au démarrage : les tests de répétition ne sont pas une garantie pour tous les états possibles.

Avant démarrage, vérifier les variables existantes, notamment l'e-mail admin et le secret. Ne pas réinitialiser l'admin ou régénérer un secret sans plan. Pour éviter d'activer le traitement manuel pendant la vérification, définir `DOIT_MANUAL_TEST=0` ; le code v9 l'active par défaut si la variable est absente. Le pourcentage de retrait `DOIT_WITHDRAW_FEE_PERCENT` n'a pas été défini par le propriétaire : ne l'inventez pas. Aucune transaction financière ne doit être acceptée pendant cette migration.

Le disque persistant désactive le déploiement sans interruption : prévoir une période d'indisponibilité. Contrôler les journaux et `/api/health`, puis comparer les comptes et les totaux aux résultats de la sauvegarde ; tester la connexion d'un compte de contrôle autorisé, l'historique, les soldes et l'administration. Ne pas lever le gel tant qu'une différence ou une erreur subsiste. Ne tester aucun paiement réel.

## 4. Si quelque chose échoue

Gardez l'accès en écriture bloqué. Ne supprimez, ne remplacez et ne restaurez rien automatiquement. Le retour à l'ancien code seul ne restaure pas le schéma ni le contenu du disque. Une restauration peut écraser toutes les écritures depuis la sauvegarde ou le snapshot : évaluer les différences et obtenir une autorisation explicite avant toute restauration destructive. Faites d'abord un diagnostic sur une copie et conservez chaque sauvegarde de manière sécurisée.

Sources Render : https://render.com/docs/disks · https://render.com/docs/free · https://render.com/docs/ssh · https://render.com/docs/rollbacks
