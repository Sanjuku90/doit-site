> **Version 10 :** l’accès /admin est public sans authentification. Lire `ADMIN_V10.md` ; les instructions admin ci-dessous peuvent être obsolètes.

> **Version 9 :** informations historiques ; pour les règles actuelles, consulter `REGLES_V9.md`.

> **Version 8 :** ce document contient des informations historiques. Pour la configuration et les limites actuelles, lire `GUIDE_MANUEL_V8.md`.

# DO IT : site web et serveur

**Ce projet est une fondation fonctionnelle, pas une plateforme financière prête à ouvrir au public.** Il crée de vrais comptes sur votre serveur et enregistre les données dans SQLite. Les dépôts, retraits et investissements restent désactivés. Le convertisseur indicatif nécessite un accès Internet sortant. Ne pas accepter d'argent ni promouvoir un rendement avant les intégrations, audits et validations nécessaires.

## Démarrage local

Prérequis : Python 3.10 ou plus récent. Aucun paquet tiers n'est requis.

```sh
unzip do-it-site.zip
cd doit-site
python3 server.py
```

Visiter `http://127.0.0.1:8080`. L'inscription, la connexion, la déconnexion, le profil, les préférences, la conservation des comptes, le bonus de test non retirable, le lien de parrainage et le réseau de parrainage jusqu’à cinq niveaux fonctionnent. Les commissions ne sont pas calculées. La base SQLite est créée dans `data/doit.sqlite3`. Les sessions durent 12 heures. Les calculs de plan affichent uniquement des scénarios en XOF, pas de vrais gains.

## Sur un serveur

Utiliser un hébergement capable d'exécuter un processus Python de longue durée avec un stockage persistant, pas un hébergement statique seul. Installer le projet, assurer la persistance et les sauvegardes de `data/`, placer un proxy HTTPS en frontal, puis définir :

```sh
export DOIT_HOST=127.0.0.1
export PORT=8080
export DOIT_SECURE_COOKIE=1
# Facultatif : active l’aperçu administrateur en lecture seule
export DOIT_ADMIN_EMAIL=adresse-de-l-administrateur@example.com
export DOIT_DB=/chemin/persistant/doit.sqlite3
python3 server.py
```

L’aperçu administrateur est limité aux comptes et bonus de test. L'e-mail doit correspondre à un compte créé par l'administrateur avant d'exposer le service ; il n'y a ni validation d’e-mail ni MFA. Ce mécanisme n’est pas suffisant pour une mise en production.

Le proxy doit transmettre au serveur local et imposer HTTPS. Le serveur écoute sur l'interface locale par défaut. Ne pas exposer directement le port HTTP à Internet. Configurer des limites de requêtes au proxy, protections réseau, sauvegardes testées, supervision et restriction d'accès aux données avant tout déploiement.

## Moteur financier expérimental

Une bibliothèque de registre et de contrôles a été ajoutée mais reste totalement déconnectée du site et des services financiers. Elle ne vérifie ni ne déplace des fonds. Voir `FINANCE.md`.

## Ce qui manque impérativement

- Authentification renforcée, MFA, vérification d'e-mail, récupération de compte, durcissement anti-abus et sessions adaptées à la production.
- Fournisseur KYC/AML et contrôles réglementaires adaptés aux pays ciblés.
- Infrastructure serveur réelle de dépôt TRC20, token USDT officiel, gestion d'adresses, confirmations, correspondance des événements et protection anti-doublons ; conservation sécurisée des clés, signatures et procédures de reprise.
- Retraits réels : réservation atomique, approbations multiples, exécution idempotente, suivi du TXID, vérification et restitution.
- Registre financier complet à double entrée, rapprochements blockchain, séparation des fonds, réserves et contrôle de solvabilité. Le registre présent ne contient que le bonus de test initial ; il n'est pas une comptabilité complète.
- Le convertisseur indicatif utilise ExchangeRate-API (actualisation quotidienne, attribution affichée), cache le dernier taux et signale les données anciennes ou indisponibles. Il doit être testé en ligne sur votre hébergement. Il ne sert pas au règlement et ne convertit pas le bonus ni les seuils dans la comptabilité. À construire : règle USDT/USD, taux transactionnels, conversion bonus à l’attribution, seuils XOF/USD et frais.
- Création d'investissements, calculs journaliers financés et échéances, parrainage jusqu'à cinq niveaux et commissions réellement acquises, fonctions d’administration financières et statistiques complètes. Un aperçu très limité, en lecture seule, existe pour l’administrateur configuré.
- Tests d'intégration et de concurrence, revue indépendante de sécurité, protection des données et audit financier/juridique. Les rendements proposés ne sont pas garantis ; leur faisabilité et leur communication doivent être validées.

Le serveur est une base de développement. Ne pas lui confier de capitaux ni de données sensibles de clients sans durcissement et audit indépendants.

## Tests

```sh
python3 -m unittest discover -s tests -v
```
