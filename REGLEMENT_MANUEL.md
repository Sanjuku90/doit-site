> **Version 10 :** l’accès /admin est public sans authentification. Lire `ADMIN_V10.md` ; les instructions admin ci-dessous peuvent être obsolètes.

> **Version 9 :** informations historiques ; pour les règles actuelles, consulter `REGLES_V9.md`.

> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# Règlement manuel expérimental : données fictives seulement

Le site inclut un flux expérimental activable en mode test. Un administrateur peut approuver une déclaration de dépôt puis saisir le montant USDT de test, un taux USD/USDT et sa source ; le montant USD est alors crédité dans le registre de test. Il peut aussi approuver un retrait, déclarer un TXID de test après paiement simulé ou rejeter la demande et libérer la réservation. Les modifications et les décisions sont enregistrées.

**Les valeurs saisies sont de simples déclarations** : ce logiciel ne valide ni ne transfère des cryptomonnaies, ne prouve pas le solde de trésorerie, n'exécute pas le paiement et n'est pas prêt pour des fonds réels. Le site est désactivé par défaut, y compris sur Render. Ne collectez aucune donnée client et ne recevez aucun dépôt réel sur cette version. Les reçus sont des justificatifs de demandes de test, pas des preuves de paiement.

Les tests automatisés utilisent des données fictives. Il faut notamment concevoir et auditer un accès administrateur sécurisé, des vérifications indépendantes des dépôts et paiements, la gestion des clés, KYC/AML, les règles de conversion et les rapprochements, avant de procéder avec des fonds. Voir MODE_MANUEL.md.
