> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# File manuelle branchée au site : tests uniquement

Le site prend en charge les déclarations de dépôt et demandes de retrait de test, une file d'approbation/rejet, un historique utilisateur et un justificatif de demande imprimable. Les justificatifs ne sont PAS des reçus de paiement ou de dépôt confirmé. Aucun fonds réel ne doit être envoyé.

Cette version ne vérifie pas TRON, ne crédite pas de dépôts, ne réalise aucun retrait, ne met pas les investissements et commissions en production. Elle ne doit pas être utilisée avec des clients ni leurs données. L'adresse communiquée est affichée uniquement comme référence de test et sa propriété n'a pas été vérifiée.

## Utilisation locale

Le mode est désactivé par défaut, y compris sur Render. Pour le tester localement avec des comptes fictifs :

1. Installer Python 3.10+, puis ouvrir un terminal dans le dossier.
2. Définir les variables d'environnement suivantes en local :

```sh
export DOIT_MANUAL_TEST=1
export DOIT_ADMIN_EMAIL=admin-test@example.invalid
export DOIT_ADMIN_REVIEW_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
python3 server.py
```

3. Créer d'abord le compte admin fictif avec cet e-mail et garder le secret dans un gestionnaire sûr. À la page Administration, entrer le secret pour afficher et traiter la file. L'accès exige à la fois la session, l'adresse configurée, le jeton CSRF et le secret. Ce mécanisme simple n'est pas un MFA ni une authentification admin auditée.
4. Créer un second compte fictif. Dans Dépôts, déclarer un montant USD, un montant USDT et un TXID de test de 64 caractères hexadécimaux. Le reçu imprimable est disponible dans Mes demandes. Après approbation, l'admin peut saisir un montant USDT de test, un taux et sa source pour créditer le registre fictif. Aucune transaction n'est vérifiée sur la blockchain.
5. Un retrait exige un solde déjà disponible dans le registre expérimental. Un crédit de test peut alimenter le registre via l'admin. La validation d'un retrait ne paie pas : un second formulaire permet de déclarer un TXID de test et de finaliser l'écriture fictive. Son rejet restitue la réservation de test. Rien ne prouve qu'un paiement a été effectué.

Il faut en plus intégrer une vérification indépendante des transactions et des confirmations, un flux de paiement manuel sécurisé, KYC, double authentification, autorisations administrateur robustes et audit avant toute utilisation réelle. Ne pas activer le mode de test sur un service public.
