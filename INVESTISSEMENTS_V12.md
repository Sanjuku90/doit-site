# DO IT v12 : parcours d'investissement

## Ce qui est branché

Un utilisateur connecté peut choisir un plan et un montant USD, confirmer les conditions et engager son solde comptabilisé. Le bonus de test n'est pas utilisé. Le serveur vérifie les minimum et maximum en XOF avec un taux USD/XOF récent, conserve le taux et la date, débite le solde disponible et comptabilise le capital investi dans une transaction unique. Une source de change inaccessible ou périmée bloque la création. Les taux utilisés dans les tests sont fictifs ; l'accès au fournisseur sur Render reste à vérifier.

L'utilisateur voit le cumul quotidien de capital et de bénéfice théorique sur 30 jours. Le cumul n'est pas présenté comme un solde retirable. Un processus en arrière-plan vérifie les échéances toutes les 60 secondes quand le serveur fonctionne. À échéance, si la réserve comptable couvre la totalité du bénéfice et des commissions, le capital, le bénéfice et les commissions sont crédités en une transaction ; sinon la totalité reste en attente de financement. Les commissions sur cinq niveaux sont calculées sur les bénéfices et comptabilisées uniquement à l'échéance. Les gains ne sont pas garantis.

## Réserve et rapprochement

La réserve est vide initialement. Tant qu'elle ne couvre pas les bénéfices et commissions dus, les investissements échus ne sont pas crédités et restent en attente ; même le capital demeure bloqué dans cette implémentation. L'enregistrement interne d'une réserve ne prouve pas que des fonds existent et ne transfère pas d'argent. Une procédure de rapprochement financière indépendante et une vraie garde sont indispensables. Un outil local réservé aux opérateurs `financer_reserve.py` permet de constater une écriture déjà vérifiée ; il ne doit pas servir à fabriquer un solde. L'interface `/admin` actuelle ne permet pas de vérifier ou de financer la réserve.

## Limites critiques

- `/admin` est public sans mot de passe, par choix de configuration précédent. Toute personne qui trouve l'adresse ou l'API peut modifier des demandes et créditer des soldes. **Ne pas utiliser avec de vrais fonds ou données de clients.**
- Aucun contrôle automatique TRON, aucune preuve de dépôt, aucun paiement automatique, aucune vérification d'identité, aucun audit financier ou de sécurité. Un solde comptable ne démontre pas la disponibilité réelle d'argent. Les dépôts et paiements sont déclarés manuellement.
- La version actuelle du serveur ne vérifie ni ne sépare physiquement les fonds des clients et de l'entreprise, ne gère ni le KYC ni les obligations de chaque pays. Les taux de rendement envisagés de 40 à 55 % par 30 jours et jusqu'à 32 % des bénéfices en commissions impliquent de fortes obligations ; leur viabilité et la conformité doivent être validées.
- Le processus d'échéance tourne uniquement quand le serveur est actif ; son démarrage ne garantit pas la disponibilité ni la continuité du service. Les 35 tests locaux utilisent des données et taux fictifs ; le navigateur, Render, la vraie source FX et les paiements n'ont pas été testés de bout en bout.
- Un plan déjà commencé est conservé avec son taux et sa date. Les valeurs configurées ensuite ne sont pas rétroactives. Aucune sortie anticipée n'est implémentée.

## Base de données

Les données sont directement dans Supabase PostgreSQL (`DATABASE_URL`) : aucune migration ni import depuis SQLite. Les tables sont créées au premier démarrage sur une base vide.
