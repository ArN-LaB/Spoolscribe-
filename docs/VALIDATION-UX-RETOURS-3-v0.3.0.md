# Fiche visuelle et préférences — troisième passe UX

1er novembre 2026. Retours sur les captures de 09:55–09:58.
Suite de [VALIDATION-UX-RETOURS-2-v0.3.0.md](VALIDATION-UX-RETOURS-2-v0.3.0.md).

**État : changements locaux testés, paquet macOS de recette reconstruit. Aucune publication.**

## Interface livrée

| Demande | Résultat |
| --- | --- |
| Zone filament plus visuelle | Aperçu vectoriel de bobine avec enroulement, volume et fil ; la couleur provient du HEX sélectionné. Une couleur inconnue ou ambiguë reste neutre avec un point d’interrogation. Le logo, le produit, la matière et la couleur sont regroupés dans un seul bloc. |
| Caractéristiques trop proches d’une liste | Quatre blocs : buse, plateau, diamètre, densité. L’édition et les aides propres à l’imprimante restent disponibles. Références et provenance sont repliées sous « Détails et sources ». |
| Grille et placement des boutons | Cartes de même taille, nom du produit, couleur, diamètre et étoile ; bobine commune à la grille et à la fiche. Le changement de vue et les colonnes sont près des résultats. Le pied de fiche garde un export principal ; les outils secondaires sont sous « ⋯ ». |
| Favoris incohérents | Étoiles ☆/★ pour les fabricants, la grille et la fiche ; les étoiles des lignes/cartes se cliquent directement. Deux boutons identiques filtrent fabricants ou filaments favoris. La remise à zéro conserve les listes enregistrées. Les deux filtres et la recherche fabricant sont mémorisés. |
| Conditionnement préféré | Onglet Export des paramètres : poids préféré, avec bobine/recharge/indifférent. Présélection initiale 1 kg. Les références existantes seules sont utilisées ; un poids absent est signalé. Un choix manuel reste prioritaire pendant la session. Une divergence de teinte reste à confirmer explicitement. |
| Interface trop chargée | Synchronisation directe des sources enregistrées après consentement. Configuration des sources dans Paramètres → Catalogue, détails des sources dépliables. Les outils JSON et dossier ne prennent plus une rangée permanente dans la fiche. |
| Imprimantes peu crédibles | Dessin générique retiré. Images originales revues pour U1, X1 Carbon et QIDI Plus4 ; le modèle illustré est indiqué pour une famille. Descriptions propres aux entrées, faits techniques limités au modèle documenté et recherche dans la sélection. Les autres entrées restent textuelles. |

Le conditionnement choisi correspond à une véritable référence et à ses données.
L’aperçu de bobine ne modifie ni le JSON ni le catalogue. Une image ne rend pas une
imprimante compatible avec OpenSpool. La couleur affichée reste une approximation
d’écran, pas une mesure du filament physique.

Les sources et limites des visuels/descriptifs sont dans
[PRINTER_VISUALS.md](PRINTER_VISUALS.md). Les images promotionnelles examinées pour
Prusa/Anycubic ont été écartées ; aucune image approximative ne les remplace.

## Tests et observations

| Contrôle final | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6/Shiboken6 6.11.3 | 195 tests, 10,670 s, OK |
| macOS ARM64, Python 3.12.13, PySide6/Shiboken6 6.11.3 | 195 tests, 9,845 s, OK |
| Répétitions après durcissement du rendu Qt | Trois suites 3.10 complètes consécutives réussies : 11,328 s, 10,142 s, 10,319 s ; puis la suite finale ci-dessus. Une suite 3.12 intermédiaire réussie en 10,342 s. |
| Contrat catalogue et 1 008 exports compacts | OK dans les deux suites finales |
| R1–R4, restauration, nulls intentionnels et corrections locales | Tests existants conservés et exécutés |
| Nouveaux tests | Neuf : préférence réelle et absence de mutation, export/import et refus d’un poids booléen, choix manuel/couleur, filtres favoris, bobine HEX, synchronisation directe, blocs/grille, sélection et étoile de carte, sauvegarde GUI des préférences |
| Répétition des restaurations de filtres | Les 30 restaurations conservent maintenant l’identité des cellules du tableau comme celle des cartes de grille |
| Rendu natif Cocoa | Captures inspectées : liste, teinte choisie, fenêtre 1000 × 720, grille 1360 × 860, thèmes, matériel U1/Prusa, petite fenêtre avancée, sources compactes, paramètres Catalogue/Export |
| `git diff --check` | OK |

Tous les tests refusent le réseau et utilisent une configuration/base isolée.
Les sept premiers nouveaux cas ont d’abord échoué avant implémentation : deux échecs
et cinq erreurs. Deux cas ont ensuite complété la sauvegarde GUI et les interactions
de grille. Aucun test n’a été désactivé.

Un premier test de grille comparait le premier enregistrement non trié à la première
carte triée : son attente a été corrigée pour vérifier le produit réellement affiché.
La revue native a aussi révélé un mauvais fond de carte en thème clair, un état de
bouton liste/grille mal restauré et une sélection perdue lorsque le conditionnement
différait du représentant du groupe ; ces comportements ont été corrigés et testés.

## Incident natif Qt — limite explicite

Une répétition Python 3.10 s’est terminée par un signal de segmentation, code **-11**,
alors que le dernier test affiché était celui de l’aperçu HEX. Une suite 3.12 parallèle
avait réussi. Trois relances de diagnostic, avec `faulthandler`, ont ensuite passé les
195 tests sans reproduire le crash. Le journal de la première exécution a été remplacé
par une relance au même chemin ; le code de sortie demeure consigné dans la trace
de session, sans pile native exploitable. La cause interne exacte n’est pas prouvée.

Deux fragilités inutiles ont été retirées : le tableau réutilise ses cellules au lieu
de détruire/recréer toutes les lignes, et Qt ne reçoit plus les structures imbriquées
du catalogue comme données de cartes. Il ne conserve que le SKU texte ; les données
de présentation restent dans le délégué Python. Le rendu est suspendu pendant le
rafraîchissement. Les suites répétées après ces changements, puis les deux suites
finales, ont toutes réussi. Cela ne constitue pas une garantie d’absence de tout
crash des bindings Qt ; une recette humaine prolongée reste nécessaire.

## Archive macOS de recette

`dist/test-ux-v0.3.0-r3/SpoolScribe-macos.zip`

SHA-256 : `5ee6cea5a9aadb24d6e3e8527bb2a643a5585cd43540874fd9ac5db9bf64de06`.

- Construction Python 3.12.13, PyInstaller 6.22.3, Qt/PySide6 6.11.3, certifi 2026.10.23.
- Une seule `SpoolScribe.app`, exécutable Mach-O, version 0.3.0 et permissions contrôlés ; CRC et chemins des 581 entrées ZIP valides.
- 190 ressources comparées aux fichiers attendus ; aucun catalogue ni profil Orca dans l’installateur.
- Probe gelé : installation vide, fixture écrite/relue, exports NTAG215/216, 147 chemins de logos, rendu des trois marques historiques, décodage et empreintes des trois images d’imprimantes, bobines connue/inconnue.
- Probe TLS : vérification des certificats et noms d’hôtes active, 128 racines par défaut et 118 racines embarquées ; ce n’est pas une synchronisation HTTPS complète du binaire.
- Archive extraite, signature ad hoc contrôlée avec `codesign --verify --deep --strict`, application lancée six secondes hors ligne puis arrêtée volontairement.

Les journaux et captures sont à côté du paquet. L’application installée n’a pas été
remplacée. Le paquet n’est pas signé Developer ID ni notarié. Les messages de cache
de police Qt et de service de saisie Cocoa observés dans les captures automatisées
n’ont pas interrompu leur exécution ; ils restent dans les journaux.

## Intégrité et périmètre

Les **215 fichiers protégés** présents au début de cette passe, dont les **48 profils
Orca**, sont inchangés par SHA-256. La base personnelle et les réglages personnels
sont identiques aux copies de début de passe. Les seuls ajouts sous `data/` sont les
trois visuels d’imprimantes et leur manifeste. Les données filaments, logos existants
et drapeaux de compatibilité matériel restent intacts.

Les captures utilisent une copie isolée de l’analyse précédente. Aucune nouvelle
mesure réseau exhaustive du catalogue n’est annoncée ici ; les 157 groupes de teintes
divergentes et 876 rapprochements en attente de la première passe ne sont pas résolus
par cette refonte visuelle. Les seuls accès réseau de cette passe sont la recherche
documentaire et le téléchargement manuel des visuels examinés.

Branche `feature/universal-catalogue`, HEAD `fba000b69048cf9e595274cdc253d5eb3ceacfce`,
index vide. Changements locaux des trois passes conservés, rapports antérieurs
accessibles. Aucun commit, push, tag, PR, fusion ou release créé.

Restent non exécutés sur ce paquet : recette interactive humaine, CI distante,
builds Windows/Linux, écriture et relecture NFC physique. Les photos ne couvrent pas
toutes les machines ; l’entrée historique da Vinci conserve une incertitude technique
explicite. Aucun firmware, NAS, service Spoolman personnel ni association RFID n’a été
modifié.


## Retours suivants et écart de contrôle visuel

La passe suivante est dans
[VALIDATION-UX-RETOURS-4-v0.3.0.md](VALIDATION-UX-RETOURS-4-v0.3.0.md).
Elle identifie un écart des aperçus précédents : ils utilisaient Cocoa sans
appliquer le style Fusion et l’agrandissement de police du démarrage réel.
Les captures de cette troisième passe ne prouvent donc pas la géométrie exacte
de l’application installée ; leurs autres résultats restent historiques.
