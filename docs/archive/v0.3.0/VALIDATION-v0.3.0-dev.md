> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Validation locale — catalogue universel v0.3.0 (développement)

Date : 2026-10-31. Branche : `feature/universal-catalogue`.
Base Git : `3c80d8299762a80078f96154396b45c75b9a3181`.
Les modifications décrites ici sont locales, non commitées et non publiées.
La version stable publiée reste v0.2.2.

## Périmètre réalisé

- Import générique OFD et complément SpoolmanDB, avec instantanés séparés,
  provenance, licences, validation et conservation des corrections locales.
- Filtres fabricant/matière/qualité, recherche multi-mots et tri à deux niveaux,
  numérique lorsque nécessaire ; pagination de 250 lignes après filtrage global.
  Clic sur un en-tête : tri 1 ; Maj-clic : tri 2. CLI équivalente.
- Affichage des références source, SKU fabricant lorsqu'il existe, masse et
  caractéristiques ; correction locale explicite des paramètres physiques.
- Logos locaux contrôlés, proportions conservées et fond contrasté.
- Choix NTAG215/NTAG216, profil complet/essentiel explicite, réserve d'écriture,
  capacité calculée et égalité entre aperçu et fichier exporté.
- README, roadmap, contrat des données, sources, confidentialité, marques,
  guides wiki et changelog actualisés. Workflow enrichi d'un contrôle du
  catalogue et des exports dans chaque exécutable construit.

## Données et couverture

| Ensemble | Marques source | Références | Exportables sans correction |
|---|---:|---:|---:|
| Catalogue historique préservé | 3 | 1 084 | 1 008 |
| OFD ajouté | 157 | 22 838 | 20 828 |
| SpoolmanDB complémentaire | 14 | 599 | 548 |
| Total | 174 | 24 521 | 22 384 |

Les marques source peuvent inclure des sous-marques. Une référence représente
une variante de couleur/taille/conditionnement ; ce n'est pas nécessairement
une formulation unique ou un SKU commercial. Les identifiants internes sont
distincts des SKU fabricant. La couverture n'est pas une garantie d'exhaustivité
mondiale : 20 dossiers OFD n'ont aucune variante exploitable ; les trois marques
historiques gardent leurs entrées contrôlées, sans rapprochement approximatif.

Les 2 137 fiches non exportables restent consultables et signalées. Le premier
obstacle rencontré est : couleur inconnue (1 008), température buse manquante
(719), température plateau minimale manquante (406), maximale manquante (2),
produit absent (2). Plusieurs champs peuvent manquer sur une même fiche.
Les deux références orphelines `FM01001` et `FM01002` existaient déjà ; elles
ne sont pas réparées avec des caractéristiques supposées. Aucune nouvelle
référence orpheline n'est introduite. Aucun rejet de format dans les deux
instantanés retenus ; les valeurs inconnues sont des `null` explicites.

Les audits JSON contiennent les empreintes et exclusions ; les sources et
licences sont détaillées dans [DATA_SOURCES.md](../../DATA_SOURCES.md).
Les 144 fichiers générés (instantanés, audits, logos, manifeste, licences)
sont reproductibles hors ligne depuis les deux téléchargements conservés.

137 nouveaux logos sont retenus. Vingt visuels OFD sont écartés après contrôles
et revue des planches ; 14 fabricants complémentaires n'ont pas de logo validé.
Ces 34 cas affichent le nom. Les SVG conservent leur caractère vectoriel ;
les bitmaps ne sont pas agrandis. Trois lignes vides indentées de SVG importés
ont été normalisées sans changer leur dessin. Aucun logo distant n'est chargé
lors d'une sélection.

## Contrôles réellement exécutés

| Contrôle | Résultat |
|---|---|
| macOS ARM64, Python 3.10.20, Qt 6.11.3 | 109 tests réussis, aucun ignoré |
| macOS ARM64, Python 3.12.13, Qt 6.11.3 | 109 tests réussis, aucun ignoré |
| 1 008 exports OpenSpool historiques | Identiques octet pour octet au contrat de référence |
| 24 521 références, validation et mesure des exports possibles | 22 384 exportables ; 2 137 explicitement incomplètes |
| Catalogue historique, anciennes ressources et 48 profils Orca | 58 fichiers protégés, empreintes inchangées |
| R1–R4 : sources vides/partielles, restauration CLI/Qt, couleurs inconnues, concurrence | Tests existants conservés et réussis ; nouveaux workers testés sur fixtures |
| Compilation PyInstaller 6.22.3, macOS ARM64 | Réussie |
| Ressources dans l'exécutable | 221 fichiers présents et identiques aux sources locales |
| Exécutable : catalogue hors ligne | 24 521 références, 174 marques, 137 nouveaux logos ; exports NTAG215/216 réussis |
| Exécutable : confiance TLS hors ligne | certifi 2026.10.23, 128 racines par défaut, 118 embarquées ; vérification certificat/hôte active |
| Archive macOS | Une seule racine `SpoolScribe.app`, Mach-O ARM64, version 0.3.0, permissions et CRC valides |
| Versions et workflow | core/pyproject/CHANGELOG cohérents ; 4 configurations de tests, 3 builds dépendant des tests |
| Git | `git diff --check` sans erreur ; aucun commit/push/tag/PR/release créé |

Commandes de tests : `QT_QPA_PLATFORM=offscreen python -B -m unittest discover
-s tests -t . -v`, exécutées dans les deux environnements Python. Les tests
interdisent les accès réseau. La collecte publique des sources a été réalisée
séparément ; aucun serveur Spoolman personnel, NAS ou équipement n'est utilisé.

L'interface Qt a été rendue et inspectée hors écran en clair/sombre, notamment
avec Bambu Lab et un logo Dremel blanc. Mesure indicative sur cette machine :
initialisation 0,56 s, deux changements de filtres 0,024 s pour 24 521 références.
Ces mesures locales ne constituent pas une garantie de performance multiplateforme.
La revue a corrigé une colonne Produit trop étroite et le contraste des logos
blancs. Les noms matière contenant `/` (par exemple PA6/66) ne sont plus
interprétés comme chemins de profils Orca.

L'inventaire des fichiers modifiés/nouveaux ne contient pas de configuration
personnelle, sauvegarde, clé ou artefact de compilation. Recherche de motifs
usuels de secrets et de chemins privés : aucun résultat. Les données publiques
et notices d'attribution sont conservées. Les cinq rapports historiques v0.2.2
restent présents et inchangés.

## Capacité NFC mesurée

Calcul : un enregistrement MIME `application/json`, enveloppe NDEF, TLV et
terminateur. Capacité déclarée : NTAG215 496 octets ; NTAG216 872 octets.
Les chiffres ci-dessous utilisent une réserve supplémentaire de zéro octet.

| Profil | Références qui tiennent | Plus grande taille qui tient | Marge correspondante |
|---|---:|---:|---:|
| NTAG215 essentiel | 22 384 | 242 octets (`FG03001`) | 254 octets |
| NTAG215 complet | 13 418 | 496 octets (`OFD-00403301-45ED-4ECC-867B-17954AD1B506`) | 0 octet |
| NTAG216 essentiel | 22 384 | 242 octets (`FG03001`) | 630 octets |
| NTAG216 complet | 22 384 | 829 octets (`CA02027`) | 43 octets |

Les 8 966 autres exports complets dépassent NTAG215 : ils sont refusés avant
écriture. Le profil essentiel est un choix explicite, conserve les paramètres
d'impression/couleurs compatibles et omet les descriptions/logos. Aucun champ
n'est supprimé silencieusement pour faire tenir un fichier. L'archive lisible
conserve tous les champs de l'export complet ; ce n'est pas une sauvegarde du
catalogue. Les couleurs multiples non représentables restent bloquantes.

SpoolFlux ou un autre logiciel peut ajouter des données/enregistrements :
leur volume réel n'a pas été mesuré. La réserve est configurable, la marge
diminue d'autant et l'export est bloqué s'il ne tient plus. Une marge de zéro
ne laisse aucune place à un ajout. Détails et référence NXP dans
[Writing RFID Tags](../../wiki/Writing-RFID-Tags.md).

## Limites et prochaines validations

- GitHub Actions n'a pas été exécuté pour cette révision locale. Les résultats
  historiques de v0.2.2 ne valident pas ce nouveau code. Builds Windows/Linux
  et quatre configurations CI : à exécuter après une autorisation de publication
  de branche adaptée à cette nouvelle phase.
- Pas de recette humaine interactive ni de test physique NTAG215/216,
  SpoolFlux ou Snapmaker U1. Compatibilité des lecteurs avec les champs couleur
  supplémentaires et logiciels qui ajoutent un enregistrement : à vérifier.
- Le contrôle TLS confirme la présence et l'usage des racines dans le binaire,
  pas la disponibilité future de chaque site. L'absence de couleurs ROSA3D dans
  TheFilamentDB reste une limite distincte de TLS et donne un statut partiel.
- Les mises à jour conservent les valeurs locales, y compris `null` ; elles ne
  remplacent donc pas automatiquement une ancienne valeur par une nouvelle
  valeur amont. Les conflits sont signalés. L'exclusion absolue d'un éditeur
  externe qui ignore le verrou n'est toujours pas garantie.
- La compilation conserve l'architecture actuelle onefile dans `.app`.
  PyInstaller avertit que ce mode deviendra incompatible avec sa future version
  7 ; il reste opérationnel avec la version verrouillée 6.22.3. L'application
  locale n'est pas signée avec un certificat Developer ID ni notarisée.
- L'API REST OFD ayant répondu par des erreurs/redirections lors de la collecte,
  l'adaptateur utilise son archive officielle HTTPS. L'indisponibilité future
  d'une source doit rester visible, sans date de succès artificielle.

La roadmap distingue ces validations restantes des fonctions déjà implémentées.
L'intégration Spoolman personnelle, le firmware, les associations RFID et le NAS
n'ont pas été modifiés. Aucun changement distant n'a été effectué pour cette phase.
