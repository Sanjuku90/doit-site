# DO IT v10 : /admin sans authentification, frais de retrait 2 %

## DANGER : interface administrative publique

Conformément au choix demandé, l'administration est accessible à `/admin` sans compte, sans mot de passe et sans code. **Toute personne sur Internet peut découvrir l'adresse et l'API, consulter les données des demandes, approuver ou rejeter des opérations, créditer des soldes et déclarer des paiements.** Cacher le lien ne constitue pas une protection. L'identité des personnes qui font des actions ne peut pas être établie. Les opérations et données des clients peuvent être compromises ; ce site ne doit pas être utilisé avec de vrais fonds ni des données personnelles.

Les frais sont fixés à 2 % par défaut et dans `render.yaml`, et sont calculés sur le montant brut. Le retrait minimum est de 10 USD. Les anciens retraits conservent leurs frais précédents. Sur un service Render existant, vérifier explicitement `DOIT_WITHDRAW_FEE_PERCENT=2` dans les variables d'environnement avant le déploiement : une configuration existante peut primer ou ne pas être modifiée automatiquement. Les frais réseau et la conversion USDT ne sont pas calculés.

## Administration

Après déploiement, aller sur `https://ADRESSE-DU-SITE/admin`. Une approbation de dépôt précède la saisie du montant USDT constaté et du taux pour créditer le solde. L'approbation du retrait ne paie pas automatiquement : l'opérateur doit effectuer le transfert dans son portefeuille et enregistrer le TXID. La blockchain n'est pas vérifiée par le site ; les statuts de paiement sont des déclarations manuelles, pas des preuves. Les investissements réels ne sont pas disponibles.

## Migration

Si une base existe déjà, **ne pas utiliser ce ZIP pour recréer le service ou écraser son disque**. Lire `MIGRATION_RENDER.md`, sauvegarder, répéter la migration sur une copie, puis évaluer les risques avant toute mise en ligne. Un déploiement réel sur Render, les transactions blockchain, la connexion mobile et l'impression physique n'ont pas été vérifiés ici. `DOIT_MANUAL_TEST=1` active le traitement manuel ; la désactivation ne rend pas public l'accès aux données via la file, mais l'accès admin ouvert doit néanmoins être considéré comme non protégé.

Ne jamais partager de clé privée, ni placer de données réelles sur une version non auditée.
