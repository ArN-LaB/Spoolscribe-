# Validation locale — correctifs de l'audit du 31 octobre 2026 (v0.3.0, version test)

Date : 31 octobre 2026. Branche : `feature/universal-catalogue`.
Point de départ : `0130e67` (état de développement commité tel quel avant correctifs).
Dernier commit du code validé : `d97aaaa`. Ce rapport est commité juste après ;
le binaire de test correspond donc à `d97aaaa` (les documents n'entrent pas dans
l'application). Rien n'est poussé, tagué ni publié.

## Ce qui a été corrigé, par commit

| Commit | Lot | Contenu |
|---|---|---|
| `9e33578` | Données | Identités de fusion (« + » conservé, couleur incluse quand un article est réutilisé), une source ne vide plus sa propre valeur, source réduite de moitié refusée, vraisemblance couleur/physique (« À vérifier », export bloqué tant que non corrigé), Orca sans plateau = inconnu, workers vers le dossier utilisateur, provenance sur les instantanés de développement, SpoolmanDB limité aux fabricants non couverts, `test_ux` sans PySide6, `tests/test_integrity.py`. |
| `c191161` | Synchro | Cadence au lancement (quotidienne par défaut, réglable), ETag OFD/SpoolmanDB/Bambu, annulation et fermeture pendant une synchro, pas de réécriture de la base hors ligne, instance unique, verrou orphelin récupéré, téléchargeurs Polymaker/Orca bornés, lien symbolique OFD ignoré, `--run-script` restreint, vérification de version sans redirection, `tests/test_sync.py`. |
| `9f45662` | NFC | Profil essentiel recommandé (tient sur NTAG215 pour toutes les références), complet explicite, clés nulles omises, CLI (`--nfc-profile auto`, casse, `parse_args`, base vide). |
| `36d6aab`, `ad497f6` | Interface | Cases à cocher visibles, champs désactivés, pastilles, bouton Colonnes, raccourcis, référence fabricant en colonne, recherche temporisée, préférences écrites une fois, pastilles et logos en cache, logos à pleine taille Retina, plus de repli Polymaker, sélection et page conservées, blocs NFC masqués sans export, grille désélectionnable, champ Fabricant non réécrit, import de réglages cohérent, séparateur de milliers, colonnes par défaut lisibles, code mort retiré. |
| `71898ef` | Build/CI | `.app` macOS en onedir, actions épinglées par SHA, concurrency et timeouts, Dependabot (PyInstaller ≥ 7, PySide6 ≥ 6.12 ignorés), `pyinstaller<7`, PyYAML retiré, attribution TheFilamentDB embarquée, archive macOS par `ditto` sans attributs étendus. |
| `d97aaaa` | Docs | README en trois étapes, PRIVACY/DATA_SOURCES/DATA_FORMAT/ROADMAP/TRADEMARKS/UX/wiki/CONTRIBUTING alignés, anciens rapports dans `docs/archive/`. |

Le détail figure dans [CHANGELOG.md](../CHANGELOG.md), section « Audit fixes (31 October 2026) ».

## Mesures avant / après

| Point | Avant | Après |
|---|---|---|
| Synchro OFD sur base vide (22 838 références en entrée) | 22 189 en sortie : 649 références absorbées, 15 produits renommés, 170 HEX réécrits | 22 674 en sortie : 164 absorptions (135 doublons stricts, 26 mêmes article/couleur/physique sous un nom « V2 », 3 doublons internes à OFD) ; aucune valeur d'un autre produit réécrite |
| Fiches signalées « À vérifier » sur l'instantané du dépôt (24 521 références) | 0 | 25 couleurs (HEX noir pour un nom clair) et 151 fiches physiques (dont 110 buses à 85 °C) ; exportables : 22 320 |
| Exports historiques (1 008) | identiques v0.2.2 | 963 identiques ; 45 ne diffèrent que par des clés `null` omises (vérifié en réinsérant les nulls : empreinte v0.2.2 reproduite, conservée dans la fixture) |
| Profil NFC recommandé | complet (8 966 références ne tenaient pas en NTAG215) | essentiel (toutes tiennent en NTAG215 et NTAG216) |
| Tests | 131 | 153 (Python 3.10.20 et 3.12.13, PySide6 6.11.3, aucun ignoré, aucun échec) |

## Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| `python -B -m unittest discover -s tests -t .` (Qt hors écran) | 3.10 : 153 OK ; 3.12 : 153 OK |
| Réseau pendant les tests | interdit par `tests/support.py` ; aucune connexion |
| `git diff --check`, index vide après chaque commit | OK |
| PyInstaller 6.22.3, Python 3.12.13, macOS ARM64 | compilation sans avertissement ; `.app` onedir de 102 Mo |
| Sonde TLS gelée (`check_frozen_tls.py`) | certifi 2026.10.23, 128 racines par défaut, 118 embarquées, vérification du certificat et du nom d'hôte |
| Sonde catalogue gelée (`check_frozen_catalogue.py`) | première installation vide, export NTAG215/216 d'une référence synthétique, 137 logos vérifiés par empreinte, hors ligne |
| Ressources du bundle | 175 fichiers identiques aux sources (`data/`, `scripts/`), aucun catalogue, cache ni profil Orca |
| `verify_archive.py --version 0.3.0` | une seule racine `SpoolScribe.app`, Mach-O, version 0.3.0, permissions, CRC |
| Archive extraite | `codesign --verify --deep --strict` OK ; lancement hors écran avec un dossier de données vierge : base vide créée, verrou d'instance posé, application vivante après 6 s |
| Captures Qt hors écran | clair, sombre, Bambu (blocs NFC masqués), « À compléter » SUNLU (couleur à vérifier), dialogue des sources (cases visibles) |

SHA-256 de `SpoolScribe-macos.zip` (`d97aaaa`) :

```text
91aa5ed315c057802895f23f71ead99053bc6b2f074e1e16f20b43ee003b0e01
```

Livraison locale, hors Git : `dist/test-audit-v0.3.0/` (archive, empreinte,
journaux des deux suites, journal de compilation, captures).

## Non exécuté, à faire avant une publication

- GitHub Actions sur ces commits (quatre configurations de tests, trois builds).
  Windows et Linux ne sont pas validés par ce build macOS.
- Recette humaine sur écran : macOS (ce `.app`), puis Windows et Linux.
- Collecte réseau complète avec le binaire final (les parseurs sont inchangés ;
  les nouveaux garde-fous sont couverts par les tests hors ligne). Les ETag
  dépendent des en-têtes réellement renvoyés par codeload.github.com,
  donkie.github.io et raw.githubusercontent.com : sans ETag, le téléchargement
  complet a lieu, sans autre effet.
- Lecture physique NTAG215/NTAG216 sur un U1 : l'enveloppe est calculée, pas mesurée.
- Décision de passer les scripts hérités (`scrape_*`, `seed_*`,
  `sync_*_assets`) dans `scripts/legacy/` et de compresser
  `data/catalogue_ofd.json` : non faits, sans impact fonctionnel.

Aucun commit n'a été poussé ; aucune donnée personnelle ni application installée
n'a été modifiée.
