# Validation locale — correctifs de l'audit du 31 octobre 2026 (v0.3.0, version test)

Date : 31 octobre 2026. Branche : `feature/universal-catalogue`.
Point de départ : `0130e67` (état de développement commité tel quel avant correctifs).
Dernier commit du code validé : `df2ff78` (binaire de test régénéré depuis ce
commit). Rien n'est poussé, tagué ni publié.

## Ce qui a été corrigé, par commit

| Commit | Lot | Contenu |
|---|---|---|
| `9e33578` | Données | Identités de fusion (« + » conservé, couleur incluse quand un article est réutilisé), une source ne vide plus sa propre valeur, source réduite de moitié refusée, vraisemblance couleur/physique (« À vérifier », export bloqué tant que non corrigé), Orca sans plateau = inconnu, workers vers le dossier utilisateur, provenance sur les instantanés de développement, SpoolmanDB limité aux fabricants non couverts, `test_ux` sans PySide6, `tests/test_integrity.py`. |
| `c191161` | Synchro | Cadence au lancement (quotidienne par défaut, réglable), ETag OFD/SpoolmanDB/Bambu, annulation et fermeture pendant une synchro, pas de réécriture de la base hors ligne, instance unique, verrou orphelin récupéré, téléchargeurs Polymaker/Orca bornés, lien symbolique OFD ignoré, `--run-script` restreint, vérification de version sans redirection, `tests/test_sync.py`. |
| `9f45662` | NFC | Profil essentiel recommandé (tient sur NTAG215 pour toutes les références), complet explicite, clés nulles omises, CLI (`--nfc-profile auto`, casse, `parse_args`, base vide). |
| `36d6aab`, `ad497f6` | Interface | Cases à cocher visibles, champs désactivés, pastilles, bouton Colonnes, raccourcis, référence fabricant en colonne, recherche temporisée, préférences écrites une fois, pastilles et logos en cache, logos à pleine taille Retina, plus de repli Polymaker, sélection et page conservées, blocs NFC masqués sans export, grille désélectionnable, champ Fabricant non réécrit, import de réglages cohérent, séparateur de milliers, colonnes par défaut lisibles, code mort retiré. |
| `71898ef` | Build/CI | `.app` macOS en onedir, actions épinglées par SHA, concurrency et timeouts, Dependabot (PyInstaller ≥ 7, PySide6 ≥ 6.12 ignorés), `pyinstaller<7`, PyYAML retiré, attribution TheFilamentDB embarquée, archive macOS par `ditto` sans attributs étendus. |
| `d97aaaa` | Docs | README en trois étapes, PRIVACY/DATA_SOURCES/DATA_FORMAT/ROADMAP/TRADEMARKS/UX/wiki/CONTRIBUTING alignés, anciens rapports dans `docs/archive/`. |
| `7e79d24` | Interface | Correctif : plantage au rafraîchissement des accès rapides (régression de `ad497f6`, présente dans la première version test `d97aaaa`, trouvée par les captures). |
| `df2ff78` | NFC | Choix d'étiquette par défaut enregistré explicitement (bouton « Définir par défaut », `--save-nfc-default`) ; un changement ponctuel ne modifie plus le défaut. |

Le détail figure dans [CHANGELOG.md](../CHANGELOG.md), section « Audit fixes (31 October 2026) ».

## Mesures avant / après

| Point | Avant | Après |
|---|---|---|
| Synchro OFD sur base vide (22 838 références en entrée) | 22 189 en sortie : 649 références absorbées, 15 produits renommés, 170 HEX réécrits | 22 674 en sortie : 164 absorptions (135 doublons stricts, 26 mêmes article/couleur/physique sous un nom « V2 », 3 doublons internes à OFD) ; aucune valeur d'un autre produit réécrite |
| Fiches signalées « À vérifier » sur l'instantané du dépôt (24 521 références) | 0 | 25 couleurs (HEX noir pour un nom clair) et 151 fiches physiques (dont 110 buses à 85 °C) ; exportables : 22 320 |
| Exports historiques (1 008) | identiques v0.2.2 | 963 identiques ; 45 ne diffèrent que par des clés `null` omises (vérifié en réinsérant les nulls : empreinte v0.2.2 reproduite, conservée dans la fixture) |
| Profil NFC recommandé | complet (8 966 références ne tenaient pas en NTAG215) | essentiel (toutes tiennent en NTAG215 et NTAG216) |
| Tests | 131 | 157 (Python 3.10.20 et 3.12.13, PySide6 6.11.3, aucun ignoré, aucun échec) |

## Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| `python -B -m unittest discover -s tests -t .` (Qt hors écran) | 3.10 : 157 OK ; 3.12 : 157 OK |
| Réseau pendant les tests | interdit par `tests/support.py` ; aucune connexion |
| `git diff --check`, index vide après chaque commit | OK |
| PyInstaller 6.22.3, Python 3.12.13, macOS ARM64 | compilation sans avertissement ; `.app` onedir de 102 Mo |
| Sonde TLS gelée (`check_frozen_tls.py`) | certifi 2026.10.23, 128 racines par défaut, 118 embarquées, vérification du certificat et du nom d'hôte |
| Sonde catalogue gelée (`check_frozen_catalogue.py`) | première installation vide, export NTAG215/216 d'une référence synthétique, 137 logos vérifiés par empreinte, hors ligne |
| Ressources du bundle | 175 fichiers identiques aux sources (`data/`, `scripts/`), aucun catalogue, cache ni profil Orca |
| `verify_archive.py --version 0.3.0` | une seule racine `SpoolScribe.app`, Mach-O, version 0.3.0, permissions, CRC |
| Archive extraite | `codesign --verify --deep --strict` OK ; lancement hors écran avec un dossier de données vierge : base vide créée, verrou d'instance posé, application vivante après 6 s |
| Captures Qt hors écran | clair, sombre, Bambu (blocs NFC masqués), « À compléter » SUNLU (couleur à vérifier), dialogue des sources (cases visibles), bouton « Définir par défaut » |

SHA-256 de `SpoolScribe-macos.zip` (`df2ff78`, remplace l'archive `d97aaaa`
qui contenait le plantage des accès rapides) :

```text
1dbf776b65c45ffc0eb3def7bd560bd082f37f20b48773d6baf576acaeb5889d
```

Livraison locale, hors Git : `dist/test-audit-v0.3.0/` (archive, empreinte,
journaux des deux suites, journal de compilation, captures).

## Seconde revue sur données réelles (1er novembre 2026)

Point de départ : retours de l'utilisateur sur l'application installée
(`df2ff78`) avec sa base réelle (24 649 références). Dernier commit validé :
`66fd347` ; binaire de test régénéré depuis ce commit.

### Diagnostic sur la base réelle (copie, hors du dossier utilisateur)

| Constat | Cause | Correctif |
|---|---|---|
| Synchro « partielle », `Polymaker officiel : 'Fiberon PPS-CF10'` | Référence historique orpheline (produit absent) rencontrée par la fusion | La fusion crée le produit manquant ; synchro Polymaker rejouée sur la copie : succès en 5 s, 20 HEX corrigés |
| OFD et SpoolmanDB « timed out » (300 s / 90 s) | Réseau : 2 Mo en plus de 120 s depuis la liaison testée (`curl`), la fusion elle-même prend 1,3 s | Délais 900 s / 300 s ; 429/503 réessayés après `Retry-After` puis « source saturée » |
| Trois « Polymaker PETG Teal » de teintes différentes | Les 24 649 fiches n'avaient aucune provenance (base créée par un ancien build qui embarquait le catalogue) : toutes « protégées », aucune source fabricant ne pouvait les corriger | Provenance explicite (`Utilisateur` rang 1000 jamais remplacé ; champ sans provenance corrigeable par un fabricant) ; après synchro Polymaker : PB01010/PB05009/PM70130 alignés sur `74CABF` (fabricant), PB01023 absent du catalogue grossiste reste `0091A5` et la ligne regroupée affiche la teinte de meilleure provenance avec un avertissement |
| « PolyLite », « Panchroma », « Fiberon »… listés comme fabricants | Dossiers de lignes de produits dans OFD | Rattachement au fabricant (174 → 165 marques), ligne conservée sur le produit |
| 58 libellés de matière (`EASYASA`, `ABS+MATTE`, `HTPLA+`…) | Libellés source hétérogènes | 33 familles pour le filtre ; valeur source et export inchangés |
| Doublons de conditionnements | Une ligne par référence | Une ligne par filament (24 649 → 15 492), conditionnements dans la fiche |

### Commits

| Commit | Contenu |
|---|---|
| `d0178cc` | Données : provenance explicite, orphelins, 429, lignes de produits, familles, regroupement, délais |
| `84d4866` | Imprimantes et lecteurs en données (`data/printers.json`, 16 entrées, groupes natif / lecteur externe / propriétaire / sans lecteur, firmwares) |
| `a75d35b` | Interface : barre latérale de facettes, fiche regroupée, « Mon matériel », rapport de synchronisation |
| `17469b4`, `5abf6a8` | CHANGELOG et documentation (README, PRIVACY, DATA_*, ROADMAP, TRADEMARKS, UX, wiki dont `Printers-and-Readers.md`) |
| `5f6206a` | Logos : 55 fonds rendus transparents, outil d'import, test de transparence, manifeste prioritaire |
| `dde78fb`, `7fb380a`, `3f77d0d`, `9dfcaf7` | Instantané OFD aligné, liste des imprimantes rechargée après résolution des chemins, appel obsolète au chargement des réglages (trouvé par la relecture documentaire) |
| `ce4d854` | 58 logos officiels actuels importés avec provenance (Polymaker 2025, Bambu Lab, Prusament, Creality, eSUN, Elegoo…) ; 8 introuvables, 10 non retenus à la revue |
| `66fd347` | Barre latérale synchronisée avec le filtre courant |

### Contrôles exécutés

| Contrôle | Résultat |
|---|---|
| Tests (Qt hors écran) | Python 3.10.20 : 164 OK ; Python 3.12.13 : 164 OK |
| Fusion de l'instantané OFD dans la base réelle | 0,4 s ; 22 838 fiches reçoivent une provenance ; 0 HEX modifié par la source communautaire (elle ne remplace jamais une valeur existante) |
| Worker Polymaker officiel sur la copie de la base réelle (réseau) | code 0, 5 s, 1 085 références examinées, 14 valeurs locales conservées, 20 HEX corrigés |
| PyInstaller 6.22.3, macOS ARM64 (`66fd347`) | compilation OK ; sondes TLS et catalogue gelées OK (147 logos vérifiés par empreinte) ; archive conforme ; `codesign --verify` après extraction OK |
| Application compilée lancée hors écran avec une copie de la base réelle | vivante après 12 s, lecture des 24 649 références et de `printers.json` |
| Captures hors écran | clair, sombre, Bambu (export masqué), Mon matériel, rapport de synchronisation, sources |

SHA-256 de `SpoolScribe-macos.zip` (`66fd347`) :

```text
7ec9110320d0fa5962071d7b84be4cad188e1306b69c7616b3b9f52626a17c9c
```

### Logos

147 entrées de manifeste (115 PNG, 21 SVG revus, dont 58 logos officiels
récupérés le 1er novembre sur les sites des fabricants ; provenance dans le
manifeste et `.github/brand-logo-sources.json`). Fond transparent vérifié par
test ; 3 logos pleins (Patron, RS PRO, SOVB 3D) marqués comme tels ;
Professional LAB retiré (nom affiché). Introuvables (anti-bot ou TLS) :
Hatchbox, Inland, AmazonBasics, Smartfil, Voxelab, Renkforce, Fiberthree ;
Kimya a cessé son activité. Non retenus : logos blancs seuls (MatterHackers,
Phrozen, Push Plastic, AzureFilm, IEMAI), trop petits (3D Power, nobufil),
Artillery et GIANTARM (visuels inexploitables), SUNLU et ROSA3D (existants
conservés).

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
- Collecte réseau complète (OFD + SpoolmanDB) avec le binaire final : non
  rejouée ici, la liaison testée étant trop lente ; la base réelle de
  l'utilisateur sera resynchronisée à son prochain lancement (quotidien) ou
  par « Synchroniser », et le rapport en rendra compte.
- Le tableau des imprimantes reprend une recherche documentaire du
  31 octobre ; ses points « non confirmés » sont listés dans `data/printers.json`.

Aucun commit n'a été poussé ; aucune donnée personnelle ni application installée
n'a été modifiée.
