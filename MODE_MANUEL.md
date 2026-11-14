# Traitement manuel des dépôts et retraits

Le parcours manuel est actif. `DOIT_MANUAL_TEST` est un ancien paramètre sans effet sur l’activation.

## Dépôts

1. Le membre déclare un montant USD, un montant USDT et le TXID.
2. La demande apparaît dans `/admin` pour le compte administrateur authentifié.
3. L’administrateur vérifie hors du site le TXID sur un explorateur TRON, le réseau TRC20, le contrat du jeton, l’adresse de destination, le montant et les confirmations.
4. L’administrateur approuve la demande, puis enregistre les valeurs réellement vérifiées pour créditer le registre.

L’approbation seule ne crédite rien. Le crédit manuel constitue une écriture du registre à partir des informations saisies par l’administrateur ; il ne s’agit pas d’une preuve blockchain automatique.

## Retraits

1. Le membre saisit le montant et son adresse TRON. Le serveur calcule les frais (2 % par défaut) et réserve le montant brut. Minimum : 10 USD.
2. L’administrateur approuve ou refuse la demande. Un refus restitue le montant réservé.
3. En cas d’approbation, l’administrateur effectue lui-même le transfert depuis son portefeuille, puis saisit le TXID du paiement pour clôturer la demande.

L’approbation ne déclenche pas le transfert. Le site ne conserve aucune clé privée.

## Accès administrateur

Configurer `DOIT_ADMIN_EMAIL` et `DOIT_ADMIN_BOOTSTRAP_PASSWORD` dans les variables d’environnement du serveur avant son premier démarrage. Le mot de passe doit compter au moins 12 caractères. Les routes d’administration exigent une session administrateur valide et un jeton CSRF.
