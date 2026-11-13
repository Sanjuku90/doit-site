> **Version 10 :** l’accès /admin est public sans authentification. Lire `ADMIN_V10.md` ; les instructions admin ci-dessous peuvent être obsolètes.

> **Version 9 :** informations historiques ; pour les règles actuelles, consulter `REGLES_V9.md`.

> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# Moteur financier expérimental : NON ACTIVÉ

Le module `finance/ledger.py` est une bibliothèque interne de développement. Il n'est pas connecté aux routes du site, aux soldes affichés, à TRON, à un prestataire ou à une véritable trésorerie. **Il ne vérifie aucun dépôt et n'exécute aucun paiement. Ne pas l'utiliser avec de l'argent réel.** Les routes du site continuent à refuser dépôts, retraits et investissements.

## Fonctions et tests ajoutés

- Écritures en centimes USD équilibrées, transactions atomiques SQLite et écritures immuables.
- Clés d'idempotence et détection de réutilisation contradictoire d'identifiants.
- Réservation de retrait, restitution en cas de refus, enregistrement d'un paiement déjà vérifié, unicité du TXID et protection des réservations simultanées.
- Blocage du capital, échéance, restitution du capital et distribution du bénéfice et des commissions selon cinq niveaux, uniquement si la réserve opérateur inscrite au registre couvre l'ensemble.
- Tests des cas ci-dessus : les entrées `book_verified_*` utilisées dans les tests sont des assertions simulées, pas des vérifications blockchain ou bancaires.

## Frontière d'intégration importante

Les fonctions `book_verified_deposit`, `book_verified_operator_funding` et `book_verified_payout` supposent qu'un composant fiable a déjà fait la vérification réelle. Elles ne doivent jamais être exposées directement aux utilisateurs ni appelées sur leur simple déclaration. La réserve enregistrée dans cette base ne prouve pas que les fonds existent. Les paramètres de l'investissement et de ses parrains sont fournis par le code appelant, ils ne sont pas récupérés ou validés automatiquement contre les règles de l'application.

Avant toute activation :
1. Définir le fournisseur de garde/signature et les sources fiables TRON, vérifier le token USDT officiel, l'événement et son index, le réseau, l'adresse, le montant et les confirmations ; rapprocher les fonds. Enregistrer distinctement USDT, prix USD, horodatage et preuve. Définir le traitement des reorgs et montants insuffisants.
2. Mettre en place KYC/AML, vérification d'adresse et MFA, approbations avec séparation des rôles, plafonds et vérification des réserves ; configurer frais et réseau. Pour les paiements, gérer les états intermédiaires, le résultat incertain, les reprises et la confirmation réelle sur chaîne avant toute écriture finale.
3. Relier les comptes, le journal, l'historique, les plans, la configuration administrateur et les commissions à une véritable application, avec contrôles d'accès stricts, snapshots des taux, date de démarrage, gestion des échéances et rapprochements.
4. Examiner le modèle comptable avec un expert ; séparer la garde, les fonds de l'entreprise et les engagements ; prévoir les corrections par contre-écriture, la piste d'audit, les sauvegardes, la reprise et le contrôle de solvabilité indépendant.
5. Tester en environnement de test blockchain, puis faire auditer les contrôles, la sécurité, la conformité et la viabilité financière avant mise en production. Le code fourni n'est pas un audit.

## Tests locaux

`python3 -m unittest discover -s tests -v`
