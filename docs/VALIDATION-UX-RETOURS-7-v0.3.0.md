# Finitions, catégories et soutien — septième passe UX

1er novembre 2026, après les captures de 11:45–11:53.
Suite de [la sixième passe](VALIDATION-UX-RETOURS-6-v0.3.0.md).

**222 tests réussis sous Python 3.10 et 3.12 ; paquet macOS reconstruit et
vérifié. Modifications locales uniquement, aucune publication.**

## Changements

- Boutons secondaires : marge verticale ramenée à 6 px, cohérente avec les commandes de 32 px. Les paires conservent largeur/hauteur communes ; l’export principal reste à 48 px. Aucune commande d’export cachée dans un menu.
- Paramètres : suppression du tracé de base natif des onglets, responsable de la ligne qui coupait visuellement la rangée. Les onglets conservent leur style et les espaces entre boutons.
- Navigateur d’imprimantes : filtre **Compatibles SpoolScribe · OpenSpool**, **RFID / NFC non compatibles SpoolScribe**, **Sans lecteur OpenSpool**, plus Toutes. Le filtre se combine avec la recherche. Il utilise les drapeaux du catalogue existant ; aucun firmware ni format RFID supplémentaire n’est déclaré pris en charge.
- L’aide rappelle que les configurations compatibles peuvent exiger un logiciel installé ou un lecteur externe. Les entrées de la catégorie RFID/NFC non compatible restent consultables ; leur lecteur ne lit pas les fichiers OpenSpool exportés par SpoolScribe.
- À propos : bouton **Soutenir le projet · Buy Me a Coffee**, haut de 32 px, ouvrant seulement au clic `https://buymeacoffee.com/arn_lab`. Aucun widget JavaScript ou chargement de télémétrie ajouté.
- Le fichier [FUNDING.yml](../.github/FUNDING.yml), absent du checkout initial mais présent sur [main](https://github.com/ArN-LaB/Spoolscribe-/blob/main/.github/FUNDING.yml), est repris à l’identique : `buy_me_a_coffee: arn_lab`.

## Visuels transparents

Les fichiers sont téléchargés depuis les sources du fabricant, inspectés et
embarqués sans retouche. Aucun détourage artificiel ni agrandissement de fichier source.

| Entrée | Résultat | Source |
| --- | --- | --- |
| Anycubic Kobra S1 / Kobra 3 | Ajout d’un exemple Kobra S1, PNG RGBA 180 × 180, 11 273 octets ; alpha 0–255, environ 36 % des pixels totalement transparents | [AnycubicSlicerNext officiel](https://github.com/ANYCUBIC-3D/AnycubicSlicerNext/blob/main/resources/profiles/Anycubic/Anycubic%20Kobra%20S1_cover.png) |
| Bambu Lab, avec ou sans lecteur externe | Nouveau PNG X1 Carbon 320 × 320, 92 554 octets ; alpha 0–255. Le manifeste remplace la miniature de 181 × 180 ; l’ancien fichier est conservé | [Bambu Studio officiel](https://github.com/bambulab/BambuStudio/blob/master/resources/images/printer_thumbnail_x1c_png.png) |
| Snapmaker U1 et QIDI Plus4 | Visuels existants déjà transparents ; fichiers inchangés | Voir [provenance des visuels](PRINTER_VISUALS.md) |
| Prusa | Les images examinées dans la page médias sont des JPEG opaques. Aucun nouveau visuel ajouté ; entrée textuelle conservée | [Ressources médias Prusa](https://www.prusa3d.com/page/media-assets_987/) |

La recherche n’établit pas l’absence de tout détourage Prusa disponible ailleurs.
La page Anycubic directe a expiré et une URL Creality a répondu 404 pendant la
recherche ; aucun asset n’est prétendu validé sur cette base. Les téléchargements
finaux Anycubic/Bambu proviennent de leurs dépôts officiels.

## Contrôles exécutés

| Contrôle | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6 6.11.3 | 222 tests, 17,291 s, OK |
| macOS ARM64, Python 3.12.13, PySide6 6.11.3 | 222 tests, 15,611 s, OK |
| Cinq nouveaux tests | Catégories et conditions/recherche, absence de ligne native d’onglets, soutien sans ouverture automatique, URL exacte au clic, hash/alpha des visuels référencés |
| Reproduction initiale des quatre premiers tests | Un échec et trois erreurs avant correction ; fonctionnalités absentes |
| Contrats historiques | Tests des 1 008 exports, R1–R4 et préférences conservés et exécutés |
| Captures natives | Cocoa, Fusion et police réelle ; catégories, recherche, quatre visuels, paramètres, À propos, fiche/JSON/provenance, stockage et thème sombre |
| Exécutable extrait du ZIP | Assertions/captures des catégories, Kobra S1, À propos, onglets sans ligne native, formulaire et pied d’export |
| `git diff --check` | OK |

Les suites sont hors ligne et isolées. Seule la recherche explicite des assets et
du fichier FUNDING a utilisé le réseau. Les clics de soutien sont interceptés dans
les tests : aucun navigateur de paiement ni contribution n’est ouvert.

## Archive et intégrité

Paquet : `dist/test-ux-v0.3.0-r7/SpoolScribe-macos.zip`.

SHA-256 : `aa01cccdb15f2d25612037cf51a3b74d94bfd24e89833026ffc63603eef3a2a5`.

- Build Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Une seule `.app`, version 0.3.0/Mach-O/permissions/CRC/chemins vérifiés : **584 entrées**, **193 ressources** identiques au dépôt.
- Probes gelés hors ligne : installation vide, fixture écrite/relue, NTAG215/216, 147 chemins de logos, trois marques historiques rendues, quatre visuels d’imprimantes et bobines connue/inconnue.
- TLS vérifié : certificat et nom d’hôte actifs ; 128 racines par défaut, 118 embarquées. Pas de téléchargement HTTPS de catalogue réel revendiqué.
- Signature ad hoc vérifiée et démarrage hors ligne de six secondes, puis arrêt volontaire. Aucun Developer ID ni notarisation.
- Sur **220 fichiers protégés** initiaux, **219 sont identiques**. Seul `data/printer_photos/manifest.json` change pour référencer les deux nouveaux PNG. Les anciens fichiers image sont conservés. Les **48 profils Orca** et toutes les données de catalogue sont inchangés.
- Base et réglages personnels identiques aux copies initiales. Ancien ZIP r6 inchangé. README, guide UX, roadmap, changelog et provenance des visuels actualisés.

État initial propre sur `feature/universal-catalogue`, HEAD
`1e9dc164277dcee0b8a72719c53a5740ad5b30d0`. Ce HEAD reste inchangé ; index vide.
Aucun nouveau commit, push, tag, PR, fusion ou release. Application installée non remplacée.

Logs : avertissements offscreen/alias de police et avertissement macOS
`sandbox_extension_issue_file_to_process` non bloquant ; probe natif terminé avec
le code 0. Les limites historiques des bindings Qt restent documentées.

Non exécutés : acceptation humaine de ce paquet, CI distante, builds Windows/Linux,
tests physiques NFC. Les catégories décrivent les configurations documentées,
sans constituer une nouvelle recette matérielle.
