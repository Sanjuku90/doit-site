# DO IT — version V12 corrigée

Cette version reprend le projet d’origine et réactive le parcours des demandes de dépôt et de retrait. Les opérations sont **manuelles** : aucun contrôle blockchain ni aucun transfert de cryptomonnaie n’est lancé automatiquement par le site.

## Parcours membre

- Dépôt : montant USD, montant USDT déclaré et TXID TRON ; la demande reste en attente jusqu’à la décision administrative.
- Retrait : adresse TRON, montant, frais calculés côté serveur (2 % par défaut) et minimum de 10 USD ; le montant brut est réservé à la soumission.
- Le membre consulte le statut et son reçu dans son historique.

## Parcours administrateur

- Connexion obligatoire avec le compte administrateur provisionné au démarrage.
- File des demandes réservée à l’administrateur authentifié et protégée par jeton CSRF.
- Dépôt : approuver pour passer à la vérification manuelle, puis saisir le montant USDT réellement contrôlé, le taux USD/USDT, la source et le motif pour enregistrer le crédit.
- Retrait : approuver ou refuser. Après avoir effectué toi-même le transfert dans ton portefeuille, saisir le TXID pour enregistrer le paiement manuel. Un refus restitue le montant réservé.
- Les décisions et règlements sont enregistrés dans le journal comptable et les événements d’audit.

## Configuration administrateur

Définir les variables d’environnement **avant le premier démarrage** :

- `DOIT_ADMIN_EMAIL` : adresse e-mail réservée au compte administrateur.
- `DOIT_ADMIN_BOOTSTRAP_PASSWORD` : mot de passe initial long d’au moins 12 caractères. Utiliser un gestionnaire de secrets ; ne jamais le mettre dans le code ni dans un dépôt public.
- `DOIT_WITHDRAW_FEE_PERCENT=2` : frais de retrait.
- `DOIT_DB` : chemin vers le stockage persistant SQLite.
- `DOIT_SECURE_COOKIE=1` en production HTTPS.

Au premier démarrage, le serveur crée le compte administrateur. Connecte-toi ensuite avec ces identifiants et ouvre `/admin`. Si la base contient déjà un compte ordinaire avec l’adresse choisie, le démarrage refuse de lui accorder les privilèges : il faut choisir une adresse admin distincte.

L’ancien paramètre `DOIT_MANUAL_TEST` n’active ni ne désactive plus les demandes : les opérations manuelles sont actives par défaut.

## Démarrage local

```bash
python server.py
```

Puis ouvrir `http://127.0.0.1:8080`.

## Limites et précautions

L’application enregistre les déclarations et les décisions administratives ; elle ne prouve pas qu’un dépôt est arrivé sur la blockchain. L’administrateur doit vérifier lui-même le réseau, le contrat USDT, l’adresse de réception, le montant et les confirmations avant de créditer. Pour un retrait, le paiement doit être réalisé séparément dans le portefeuille, puis son TXID consigné. Les clés privées et phrases de récupération ne doivent jamais être saisies dans ce site.

Le compte de registre est un registre applicatif, pas une preuve de réserves ni un compte bancaire. Avant d’accepter des fonds de tiers, il faut faire auditer le déploiement, mettre en place les contrôles d’identité et de fraude requis, vérifier les obligations réglementaires locales et faire évaluer les risques de conservation et de liquidité. Les rendements ne sont jamais garantis.

## Tests

Exécuter `python -m unittest discover -s tests -v`. Les tests couvrent les demandes, les réservations, les frais, l’idempotence, les validations manuelles et le contrôle d’accès administrateur. Le test de conversion de devises dépend d’une source de taux externe ; il peut échouer si le réseau est indisponible et qu’aucun taux n’est en cache.
