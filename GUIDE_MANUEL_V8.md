> **Version 10 :** l’accès /admin est public sans authentification. Lire `ADMIN_V10.md` ; les instructions admin ci-dessous peuvent être obsolètes.

> **Version 9 :** informations historiques ; pour les règles actuelles, consulter `REGLES_V9.md`.

# DO IT v8 : traitement manuel

Cette version active la file manuelle par défaut (`DOIT_MANUAL_TEST=1`, nom historique de la variable). Le logiciel ne vérifie pas la blockchain, n'envoie pas de paiement, ne prouve pas les réserves et n'a pas été audité. L'administrateur doit effectuer ses vérifications et paiements hors du site. Toute inscription dans le registre dépend des déclarations administrateur : une erreur ou fraude peut créditer à tort un compte. NE PAS accepter de capitaux ni de données client sans validation indépendante, contrôles adaptés et conformité.

## Render

1. Décompresser l'archive, mettre le contenu du dossier `doit-site/` à la racine d'un dépôt privé, puis lancer un Blueprint Render sur ce dépôt.
2. `render.yaml` prévoit un service payant avec disque persistant et demande `DOIT_ADMIN_EMAIL` et `DOIT_ADMIN_BOOTSTRAP_PASSWORD` (12 caractères minimum). Un secret séparé `DOIT_ADMIN_REVIEW_SECRET` est généré par Render : le récupérer dans les variables d'environnement de Render et le conserver confidentiellement. Ne pas transmettre ces secrets dans une conversation.
3. Au premier démarrage, le serveur crée le compte admin depuis ces paramètres. S'il existe déjà un compte non administrateur avec cet e-mail, le démarrage échoue pour éviter une promotion silencieuse. Utiliser une base neuve ou effectuer une migration administrateur contrôlée. Ne modifiez pas manuellement la base en production.
4. Se connecter au compte admin, ouvrir Administration et saisir le secret de validation. Le mot de passe bootstrap est utilisé seulement lors de la première création du compte ; le modifier dans les variables Render ne change pas le mot de passe enregistré.
5. Tester avec des données fictives avant toute publication. Le taux de change externe, l'accès réseau, la persistance, le fonctionnement du navigateur et le site Render déployé ne sont pas vérifiés ici.

## Dépôt

L'utilisateur déclare montant USD, montant USDT et TXID. L'admin approuve ou rejette. L'approbation seule ne crédite pas. Après contrôle indépendant hors du site, l'admin saisit le montant USDT effectivement constaté, le taux USD/USDT et sa source et utilise « Créditer le solde ». Le crédit est ajouté au registre une seule fois. Il ne faut pas supposer que 1 USDT = 1 USD. Le site ne contrôle ni le token ni l'adresse ni les confirmations.

## Retrait

Le solde est réservé à la demande. L'admin peut rejeter et restituer la réservation ou approuver. Pour payer, l'admin doit effectuer le transfert lui-même depuis son portefeuille. Le site ne signe ni n'envoie de transaction. Après paiement, l'admin saisit le TXID pour déclarer la finalisation ; les réserves sont alors débitées. Sans cette seconde action, le retrait reste réservé. Le site ne vérifie pas le TXID ni les frais : une politique de frais et la validation d'identité restent à construire.

## Limites

Les investissements, gains et commissions réels ne sont pas branchés au site. Les justificatifs imprimables ne prouvent pas qu'un transfert a eu lieu. Le bonus reste un crédit de test non retirable. Le service d'e-mail, la récupération de compte, la 2FA, KYC/AML, l'accès administrateur robuste et l'audit ne sont pas disponibles. Un navigateur, un vrai appareil et un déploiement Render n'ont pas été testés de bout en bout ici.
