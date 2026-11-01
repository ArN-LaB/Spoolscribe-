> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Exports et copies personnelles — huitième passe UX

1er novembre 2026, après les retours de 12:20–12:21.
Suite de [la septième passe](VALIDATION-UX-RETOURS-7-v0.3.0.md).
L’utilisateur a explicitement retenu la création de copies personnelles.

**233 tests réussis sous Python 3.10 et 3.12 ; paquet macOS reconstruit et
contrôlé. Modifications locales uniquement.**

## Changements et garanties

- Chaque export propose un **dossier de destination**, mémorise le dernier choix et confirme le chemin après l’écriture réussie. Annuler ne crée rien et n’affiche pas de succès. Le dossier est également configurable dans Paramètres → Export ; « Dossier d’export » ouvre le dernier dossier utilisé.
- Le JSON apparaît dans la zone de défilement existante. Les appels de redimensionnement automatique ont été retirés ; trois cycles ouverture/fermeture gardent la même taille de fenêtre.
- **Modifier…** propose un suffixe `Personnel`, modifiable en `U1`, etc. L’enregistrement crée une référence indépendante `Produit @suffixe`, avec sa propre identité SKU/produit. La référence source et ses autres conditionnements restent inchangés.
- Enregistrer le même suffixe pour la même référence met à jour la copie existante. Changer de suffixe permet une autre copie. Aucun doublon automatique d’une même personnalisation.
- Les copies sont exclues des index de rapprochement des sources. Les valeurs copiées portent une priorité personnelle ; les caractéristiques explicitement saisies gardent la provenance Utilisateur. Les nulls intentionnels sont conservés. Une copie ne confirme pas silencieusement une couleur source incohérente.
- Publication de la copie par le stockage existant, avec validation et contrôle de révision avant mutation de l’objet GUI. Un échec d’écriture conserve fichier et objet en mémoire. L’ancienne API de correction partagée reste disponible ; le parcours GUI utilise désormais la copie.
- « Effacer » occupe exactement la colonne du bouton Filaments : même largeur, bord droit et hauteur.
- GitHub et Buy Me a Coffee forment une paire de boutons de même dimension dans À propos.
- Le message de vérification de version est effacé dès le résultat, y compris en erreur ; une durée maximale d’affichage de 15 secondes évite un texte d’attente permanent.

## Formats RFID/NFC

**OpenSpool 1.0 n’est pas le seul format existant.** La vérification et les sources
primaires sont réunies dans [FORMATS-NFC.md](../../FORMATS-NFC.md) : OpenSpool 1.0,
OpenTag3D et OpenPrintTag sont des formats distincts. La documentation de la branche
develop du firmware U1 décrit aussi plusieurs systèmes de lecture. Elle ne prouve
pas les capacités de la version effectivement installée.

Le sérialiseur SpoolScribe reste **OpenSpool 1.0** ; aucun nouvel encodeur, firmware
ou accès aux imprimantes n’est ajouté. Les noms de copies sont des libellés locaux,
pas de nouveaux types de matière reconnus automatiquement par une imprimante.

## Validation exécutée

| Contrôle | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6 6.11.3 | **233 tests**, 18,560 s, OK |
| macOS ARM64, Python 3.12.13, PySide6 6.11.3 | **233 tests**, 16,660 s, OK |
| Nouveaux tests | Onze : création/préservation/fusion/rechargement, édition/reprise du même suffixe et échec atomique, valeurs/suffixes invalides, couleur incohérente non confirmée, cycles JSON, destination et confirmation, annulation, copie GUI sélectionnée et persistée, fin de vérification, alignement Effacer, paire À propos |
| Reproduction initiale | Neuf tests avant correction : quatre échecs et huit erreurs, dont sous-tests ; nouvelles API absentes |
| 1 008 exports historiques, R1–R4, préférences et autres régressions | Tests conservés et exécutés |
| Tests GUI préexistants | Le sélecteur de dossier est simulé vers la fixture isolée ; aucun dialogue natif ne bloque les suites |
| Captures natives du code | Cocoa + Fusion + police réelle ; copie @U1 et source visibles, formulaire, confirmation, JSON, paramètres, À propos et alignements |
| Exécutable extrait du ZIP | Création et enregistrement réels d’une copie dans la base isolée ; source comparée, export réellement écrit, confirmation capturée, dossier mémorisé, trois cycles JSON à taille constante |
| `git diff --check` | OK |

Le choix du dossier et la fermeture des dialogues sont automatisés par réponses
simulées ; l’écriture et la relecture des fichiers sont réelles dans les fixtures.
Aucune manipulation humaine du sélecteur natif n’est revendiquée. Les tests sont
hors ligne, sauf la recherche documentaire réalisée séparément sur les formats.

Une assertion intermédiaire de test attendait trois valeurs de retour de
`merge_catalogue`, dont l’API en retourne deux ; le test a été corrigé. Aucun test
n’a été retiré, contourné ou marqué artificiellement réussi.

## Archive et état du dépôt

Paquet : `dist/test-ux-v0.3.0-r8/SpoolScribe-macos.zip`.

SHA-256 : `aeb06ae33f8392e226015b03ba59d9577e0f7760cf669a805a11cf9f1e59de87`.

- Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Une seule `.app`, **584 entrées**, version/Mach-O/permissions/CRC/chemins vérifiés. **193 ressources** identiques au dépôt ; pas de catalogue ni profils Orca dans l’installateur.
- Probes gelés hors ligne : installation vide, fixture, exports NTAG215/216, 147 chemins de logos, trois marques historiques rendues, quatre visuels et bobines connue/inconnue.
- TLS : validation du certificat et du nom d’hôte active ; 128 racines par défaut, 118 embarquées. Aucun téléchargement HTTPS de catalogue réel testé.
- Signature ad hoc vérifiée ; démarrage hors ligne de six secondes puis arrêt volontaire. Ni Developer ID ni notarisation.
- **222 fichiers protégés**, dont **48 profils Orca**, inchangés par SHA-256 depuis le début de passe. Base et réglages personnels identiques aux copies initiales. Toutes les copies @U1 de recette vivent dans les fixtures temporaires.
- README, guide UX, schéma des données locales, wiki, changelog et roadmap actualisés ; anciens paquets et rapports conservés.

Branche `feature/universal-catalogue`, HEAD
`1e9dc164277dcee0b8a72719c53a5740ad5b30d0` inchangé, index vide. Les travaux locaux
précédents et les fichiers ajoutés par ailleurs sont conservés. Aucun commit,
push, tag, PR, fusion ni release ; application installée non remplacée.

Avertissements présents dans les logs : plateforme offscreen, alias de police et
`sandbox_extension_issue_file_to_process` macOS non bloquant. Probe natif terminé
avec le code 0. Les limites historiques des bindings Qt restent documentées.

Non exécutés : acceptation humaine de ce paquet, CI distante/builds Windows/Linux,
NFC physique et restauration réelle de la base personnelle. La protection des
copies est testée sur fusion et rechargement isolés, pas sur une collecte réseau
réelle ou un matériel distant.
