# DO IT — fonctionnalités V13

## Ajouts de cette version

- Tableau de bord administrateur : nombre de comptes, comptes actifs, demandes de dépôt/retrait, demandes en attente et investissements en cours.
- Gestion des clients : recherche par identifiant, nom ou e-mail, suspension et réactivation d'un compte, consultation du journal du client.
- Journal financier : consultation des écritures comptables, des écritures immuables et des événements de validation (acteur, action, motif et date lorsqu'ils existent).
- Export du registre au format CSV UTF-8 avec BOM, ouvrable dans Excel. Ce n'est pas un fichier XLSX natif.
- Assistance intégrée sous forme de messagerie asynchrone entre le client et l'administrateur ; ce n'est pas un chat en temps réel.
- Profil modifiable : prénom, nom, téléphone et URL HTTPS facultative pour une photo de profil. L'image est hébergée à son adresse HTTPS ; le site ne reçoit pas de fichier image.
- Centre de notifications avec lecture individuelle ou globale. Notifications créées lors de l'inscription, du dépôt/retrait déclaré, de la décision administrative et d'une réponse du support.
- Calendrier des échéances calculé à partir des dates de maturité enregistrées.
- Convertisseur USD/XOF affiché directement dans le formulaire de dépôt avant envoi.
- Le justificatif de demande présente le statut courant au lieu de la grande phrase précédente. Il ne prétend pas qu'une demande en attente est un paiement confirmé.

## Limites importantes

- Le convertisseur donne une équivalence indicative. Il ne réalise aucun échange monétaire.
- Le profil accepte une URL de photo HTTPS, pas un téléversement de fichier.
- L'export est un CSV compatible Excel, pas un classeur XLSX.
- L'assistance est une messagerie de support, pas une IA ni un chat instantané.
- Les suspensions empêchent l'ouverture d'une session active ; les sessions d'un compte suspendu sont refusées lors des requêtes suivantes.
- Les événements d'audit détaillés sont disponibles pour les opérations qui traversent la file de validation. Les écritures comptables immuables sont listées séparément.
- Le projet n'intègre pas de vérification TRON/USDT sur chaîne, de garde de fonds, ni d'envoi de paiements. Une approbation enregistre un mouvement dans le registre interne ; elle ne prouve pas à elle seule qu'un transfert blockchain a été reçu.
- Ne pas utiliser le site pour accepter des fonds réels avant intégration et audit indépendants des fonctions de garde, de vérification, de paiement, de sécurité et de conformité réglementaire.
