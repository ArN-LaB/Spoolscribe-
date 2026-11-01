# Alignements et commandes visibles — quatrième passe UX

1er novembre 2026, après les captures de 10:42–10:44.
Suite de [la troisième passe](VALIDATION-UX-RETOURS-3-v0.3.0.md).

**Résultat : corrections locales, 203 tests réussis sur Python 3.10 et 3.12,
paquet macOS de recette reconstruit. Aucune publication.**

## Changements

- Export sur toute la largeur, puis deux boutons visibles : **Voir le JSON** et **Dossier d’export**. Les bords sont partagés avec la fiche ; l’inspection défile vers le fichier à son ouverture.
- Hauteur commune des commandes de recherche/synchronisation/menu et de liste/grille/colonnes. Marges de la fiche et du pied d’export alignées. Champs, onglets, boutons et menus suivent le même style.
- Les fabricants non favoris n’ont plus d’étoile permanente. L’étoile apparaît à droite au survol ; les favoris gardent leur étoile pleine. Cliquer le nom sélectionne sans modifier les favoris. Le clic droit reste disponible.
- Ligne Favoris simplifiée ; statut de sélection court, informations de base compactes et absence de répétition du type NTAG dans le message de capacité.
- Bobine redessinée en perspective : deux flasques, cylindre enroulé, rayons et fil. HEX conservé ; couleur inconnue neutre. Les logos colorés ne reçoivent plus le large halo dédoublé. Un bord d’un pixel de rendu reste réservé aux logos presque invisibles sur le fond courant.
- Les répétitions de fabricant comme « Artillery Artillery Basic PLA » sont nettoyées pour l’affichage seulement, sans changer les données, identités de favoris, noms d’export ni fichiers JSON.
- Paramètres Export : colonnes Masse/Format alignées, libellés courts, onglets harmonisés et commandes de sauvegarde de même hauteur.

## Correction de la méthode de vérification

Les aperçus des passes précédentes créaient une `MainWindow` sans reproduire
l’initialisation complète de l’application : style Fusion et agrandissement de
police de 0,5 point manquaient. Ils ne prouvaient donc pas la géométrie exacte du
paquet installé, même s’ils utilisaient la plateforme Cocoa. Cette limite est
ajoutée au rapport précédent, sans effacer ses résultats historiques.

`configure_application()` est maintenant partagé par le démarrage réel et les
fixtures GUI. Il est aussi appelé par la capture native ; son idempotence est
testée pour éviter l’agrandissement répété de la police.

## Contrôles exécutés

| Contrôle | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6 6.11.3 | 203 tests, 10,149 s, OK |
| macOS ARM64, Python 3.12.13, PySide6 6.11.3 | 203 tests, 9,233 s, OK |
| Répétition 3.10 avant ajout du cas d’inspection JSON | 202 tests, 9,394 s, OK |
| Contrat des 1 008 exports compacts, R1–R4 et préférences | Tests existants conservés et exécutés |
| Nouveaux cas d’alignement | Huit : bords/visibilité des exports et de la fiche, étoiles et clics fabricants, hauteur des commandes, formulaire, démarrage idempotent, logo sans halo, préfixe d’affichage et ouverture du JSON |
| Reproduction initiale | Quatre premiers cas exécutés avant correction : trois échecs, un succès |
| Captures natives | Cocoa + Fusion + police du démarrage réel ; 1360 × 860 et 1000 × 720, grille, JSON, menu, matériel, sources, paramètres et thème sombre inspectés |
| Menu général | Géométrie contenue dans l’écran disponible, vérifiée pendant la capture native |
| `git diff --check` | OK |

Les tests bloquent le réseau et isolent les données/réglages. Aucun test n’est
désactivé. Aucun crash natif n’a été observé dans les exécutions de cette passe ;
le crash Qt intermittent de la passe précédente reste documenté, sans cause
interne démontrée et sans garantie générale sur les bindings Qt.

## Paquet et intégrité

Archive : `dist/test-ux-v0.3.0-r4/SpoolScribe-macos.zip`.

SHA-256 : `1d1457afb66633cb8dc78e1fe81ae79edd2d2a8fa71ab51c10b7c74aa5c2e58e`.

- Build Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Une seule `.app` à la racine ; exécutable Mach-O, version 0.3.0, permissions, CRC et chemins vérifiés sur 581 entrées.
- 190 ressources attendues comparées au dépôt. Catalogue et profils Orca absents de l’installateur.
- Probes gelés hors ligne : première installation vide, écriture/relecture de fixture, exports NTAG215/216, 147 chemins de logos, rendu des trois marques historiques, trois photos d’imprimantes et bobines connue/inconnue.
- TLS : validation du certificat et du nom d’hôte active ; 128 racines par défaut, 118 racines embarquées. Ce probe ne remplace pas un téléchargement HTTPS de catalogue par le binaire.
- Archive extraite, signature ad hoc vérifiée, application lancée six secondes hors ligne puis arrêtée volontairement. Pas de signature Developer ID ni de notarisation.

Les **219 fichiers protégés** de début de passe, dont les **48 profils Orca**,
sont identiques par SHA-256. La base et les réglages personnels sont identiques
aux copies initiales. Les captures utilisent une copie isolée de la base actuelle ;
son état d’actualisation échouée préexistant est affiché sans le masquer. Aucune
nouvelle collecte réseau n’est effectuée et aucune donnée de catalogue n’est corrigée.
Les anciens paquets et rapports sont conservés.

Branche `feature/universal-catalogue`, HEAD
`fba000b69048cf9e595274cdc253d5eb3ceacfce`, index vide. Aucun commit, push, tag,
PR, fusion ni release. L’application installée n’a pas été remplacée.

Restent non exécutés : recette humaine de ce nouveau paquet, CI distante et builds
Windows/Linux, essais NFC physiques. Les assertions de géométrie portent sur les
dimensions et parcours testés, pas sur toute combinaison d’écran ou d’accessibilité.
