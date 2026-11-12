> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# Note : une file web de test a été ajoutée. Voir MODE_MANUEL.md. Aucun crédit ou paiement réel.

# File de validation administrative (développement)

La file est une brique **locale**, non connectée au site ni à un fournisseur crypto. Elle est conçue pour être intégrée après sécurisation de l'accès administrateur. Ne l'utilisez pas pour de l'argent réel.

- Un dépôt transmis à la file est `pending`. L'administrateur peut le rejeter ou l'approuver. L'approbation devient `approved_verification_required` : le TXID, le token, le réseau, les confirmations, le montant et la contre-valeur doivent encore être vérifiés. **Aucun crédit n'est effectué.**
- Un retrait peut être envoyé à la file uniquement s'il est déjà réservé dans le registre expérimental. L'approbation devient `approved_payment_pending`, sans envoi automatique. Le refus annule atomiquement la réservation et restitue le solde du registre expérimental.
- Les décisions concurrentes sont sérialisées : une seule est acceptée. Toute décision doit inclure un motif et crée un événement d'audit immuable. Les TXID de dépôts et les demandes de retrait ne peuvent être réutilisés dans la file.

## Consulter et décider en ligne de commande

Ces commandes ne sont accessibles qu'à une personne disposant d'un accès système à l'hébergement et à la base. L'identité enregistrée est celle du compte système. Il n'y a pas d'authentification administrateur web ni de MFA ; cet outil n'est pas une interface adaptée à la production.

```sh
python admin_review.py --db /chemin/vers/base.sqlite3 liste
python admin_review.py --db /chemin/vers/base.sqlite3 liste --etat pending
python admin_review.py --db /chemin/vers/base.sqlite3 historique ID_DEMANDE
python admin_review.py --db /chemin/vers/base.sqlite3 approuver ID_DEMANDE --motif 'Contrôlé'
python admin_review.py --db /chemin/vers/base.sqlite3 rejeter ID_DEMANDE --motif 'Non conforme'
```

L'intégrateur doit appeler `finance.review_queue.submit_deposit(...)` ou `submit_reserved_withdrawal(...)` depuis un service de confiance pour alimenter la file ; **les utilisateurs du site actuel ne peuvent pas encore soumettre de demandes**. Le module ne protège pas les autres appels directs au registre expérimental : l'intégration future doit imposer la décision admin dans le workflow côté serveur, sans chemin de contournement. Après approbation du dépôt, une vérification indépendante TRON et le rapprochement restent obligatoires. Après approbation du retrait, KYC, autorisation, signature sécurisée et confirmation du paiement restent à construire. Ne stockez jamais de clés privées dans ce projet.
