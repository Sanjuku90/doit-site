> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# Rapport de tests : version 6

## Vérifié localement

- 23 tests Python automatisés : comptes et sessions, contrôle CSRF, confidentialité des demandes, fonctionnement de la file manuelle de test, approbation et rejet, restitution du montant réservé, TXID en double, réservations et décisions concurrentes, plafonds, simulation des échéances et commissions, intégrité du registre et persistance après redémarrage.
- Convertisseur : réponses du fournisseur simulées et panne simulée ; aucun appel en ligne dans cet environnement.
- Tests de rendu des fonctions JavaScript avec données fictives : demandes de test visibles dans l'historique et filtres dépôt/retrait, contenu des justificatifs et encodage HTML. Ces tests ne sont pas un test de navigateur complet.
- Syntaxe JavaScript et Python vérifiée. Aperçu d'impression sur tailles mobiles simulées effectué sur la version précédente du reçu ; aucun vrai téléphone ni imprimante utilisé.

## Amélioration apportée

L'historique affiche maintenant les demandes de dépôt et retrait de test et donne accès aux justificatifs correspondants. Les justificatifs restent des demandes, pas des preuves de paiement.

## Non vérifié et non opérationnel

Aucun déploiement sur Render, test navigateur complet de toutes les pages, service de change en direct, vérification TRON, ni transaction blockchain réelle. L'accès admin, l'authentification, la protection des données et le système financier n'ont pas fait l'objet d'un audit indépendant.

Les dépôts, paiements et investissements réels restent désactivés. Les commissions et le moteur financier expérimental ne sont pas reliés à un système financier réel. Ne pas utiliser avec de vrais fonds ni des données de clients.

## Rejouer

```
python3 -m unittest discover -s tests -v
node tests/test_ui.js
node --check static/app.js
```
