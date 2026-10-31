# SpoolScribe v0.2.2 — préparation de la validation CI

Date : 31 octobre 2026. **Préparation locale terminée ; validation distante et
publication non exécutées.** Aucun changement fonctionnel supplémentaire.
Les correctifs R1–R4 acceptés restent inchangés.

## État Git contrôlé

- Branche courante : `main`, HEAD
  `5197234c68885618492039061d4228f6848d024c`.
- À l'ouverture de cette passe : **29 fichiers suivis modifiés et 19 nouveaux**,
  conformément au rapport précédent. Aucun fichier supprimé, aucun renommage,
  index vide. La référence locale `origin/main` est au même commit : 0 devant,
  0 derrière. Aucune interrogation ni actualisation du dépôt distant pendant
  cette préparation ; ce constat ne certifie pas sa situation actuelle.
- Seuls ajouts de cette passe : trois exclusions de récupération dans
  `.gitignore` et le présent rapport. État final : **30 fichiers suivis modifiés
  et 20 nouveaux**, soit 50 fichiers proposés pour les futurs commits.
- Empreintes des 120 fichiers initiaux enregistrées : seul `.gitignore` change
  pendant cette passe. Le code, les tests, dépendances, workflow, catalogue,
  profils et rapports précédents sont préservés.
- HEAD, références locales et index inchangés ; aucun commit, push, tag, PR,
  release ou lancement GitHub Actions. Branche proposée :
  **`release/v0.2.2`**, non créée.

## Inventaire exhaustif proposé

`M` = modification suivie ; `N` = fichier nouveau non suivi. Les répertoires
`tests/` sont détaillés fichier par fichier, et non comptés comme une seule entrée.

| État | Catégorie | Fichier |
|---|---|---|
| M | CI / packaging | `.github/workflows/build.yml` |
| M | CI / packaging | `pyproject.toml` |
| N | CI / packaging | `requirements-build.txt` |
| M | CI / packaging | `spoolscribe.spec` |
| M | Code | `app_gui.py` |
| M | Code | `convert_profile.py` |
| M | Code | `core.py` |
| N | Code | `scripts/__init__.py` |
| N | Code | `scripts/db_io.py` |
| M | Code | `scripts/download_orca_profiles.py` |
| M | Code | `scripts/import_orca_profiles.py` |
| M | Code | `scripts/scrape_internal_exact_hex.py` |
| M | Code | `scripts/scrape_spoolman_hex.py` |
| M | Code | `scripts/scrape_spoolman_multibrand_hex.py` |
| M | Code | `scripts/scrape_thefilamentdb_hex.py` |
| M | Code | `scripts/scrape_thefilamentdb_multibrand_hex.py` |
| M | Code | `scripts/scrape_wholesale.py` |
| M | Code | `scripts/scrape_wiki_hex.py` |
| M | Code | `scripts/seed_prusament.py` |
| M | Code | `scripts/seed_rosa3d.py` |
| M | Code | `scripts/sync_multibrand_assets.py` |
| M | Code | `scripts/sync_polymaker_brand_assets.py` |
| M | Documentation | `.github/CONTRIBUTING.md` |
| M | Documentation | `CHANGELOG.md` |
| M | Documentation | `docs/DATA_SOURCES.md` |
| N | Documentation | `docs/PREPARATION-CI-v0.2.2.md` |
| M | Documentation | `docs/PRIVACY.md` |
| N | Documentation | `docs/REVUE-FINALE-v0.2.2.md` |
| M | Documentation | `docs/ROADMAP.md` |
| N | Documentation | `docs/VALIDATION-CORRECTIFS-v0.2.2.md` |
| N | Documentation | `docs/VALIDATION-v0.2.2.md` |
| M | Documentation | `docs/wiki/FAQ.md` |
| M | Documentation | `docs/wiki/Getting-Started.md` |
| M | Documentation | `docs/wiki/Updating-the-Database.md` |
| M | Documentation | `docs/wiki/Writing-RFID-Tags.md` |
| M | Documentation | `README.md` |
| M | Hygiène Git | `.gitignore` |
| N | Tests / fixtures | `tests/__init__.py` |
| N | Tests / fixtures | `tests/fixtures/catalogue_exceptions.json` |
| N | Tests / fixtures | `tests/fixtures/observed_filaments.json` |
| N | Tests / fixtures | `tests/support.py` |
| N | Tests / fixtures | `tests/test_catalogue.py` |
| N | Tests / fixtures | `tests/test_cli.py` |
| N | Tests / fixtures | `tests/test_db_io.py` |
| N | Tests / fixtures | `tests/test_gui.py` |
| N | Tests / fixtures | `tests/test_nfc_size.py` |
| N | Tests / fixtures | `tests/test_openspool.py` |
| N | Tests / fixtures | `tests/test_orca.py` |
| N | Tests / fixtures | `tests/test_regressions_v022.py` |
| N | Tests / fixtures | `tests/test_updates.py` |

Résumé initial : 18 fichiers de code, 13 tests/fixtures, 13 documents et
4 fichiers CI/packaging = 48. La préparation ajoute `.gitignore` aux modifications
et ce rapport aux nouveaux fichiers. Aucun fichier temporaire dans cet inventaire.

Les changements fonctionnels couvrent l'export OpenSpool compact et sa validation,
la priorité aux corrections locales, le stockage partagé et les 13 workers,
les statuts de mise à jour et les restaurations. Les tests couvrent également R1–R4.
Le diff important du changelog comprend la suppression de blocs historiques
répétés ; les entrées publiées 0.2.0/0.2.1 et l'historique 0.1.x restent présents.
Aucun nettoyage supplémentaire du changelog n'a été effectué dans cette passe.

## Sécurité et fichiers à exclure

Revue des fichiers candidats et recherche ciblée, sans afficher de valeurs
sensibles : clés privées PEM, formats de jetons GitHub/AWS/services courants,
identifiants intégrés dans une URL, secrets affectés en clair et adresses privées
de services personnels. **Aucun secret détecté.** Les fichiers candidats sont
des textes UTF-8 réguliers ; aucun lien symbolique ni binaire de compilation.

- Aucun `.env`, clé SSH, configuration personnelle, base SQLite, log, ZIP,
  exécutable ou export utilisateur parmi les fichiers proposés.
- Les fixtures contiennent des données de test et trois observations matériau/
  couleur, avec provenance et correspondances incertaines explicites. Aucun UID
  physique, identifiant de bobine personnelle, hôte NAS ou secret Spoolman.
- Le catalogue public existant et les 48 profils ne sont pas modifiés. Aucune
  base personnelle n'est ajoutée.
- Le seul fichier ignoré présent est `.DS_Store`, conservé et exclu. Aucun
  `build/`, `dist/`, backup, sortie NFC ou cache utilisateur n'est candidat.
- Les copies de récupération du stockage n'étaient pas couvertes par les
  exclusions existantes : ajout de `*.json.before-restore-*`,
  `*.json.concurrent-*` et `*.json.lock`. Aucune copie de ce type n'était
  présente ; aucun fichier n'a été supprimé. Vérification avec `git check-ignore`
  sur ces trois motifs, les deux formes de backup et `output/` : correcte.
  Le catalogue source reste admissible dans Git.
- Les builds, bases modifiées pour les sondes et journaux sont isolés dans un
  répertoire temporaire hors du dépôt. Ils ne font partie d'aucun commit proposé.

Cette vérification ciblée ne constitue pas une preuve d'absence de tout secret
possible ni un audit de tout l'historique Git. `gitleaks` et `actionlint` ne
sont pas installés ; aucun de ces outils n'est présenté comme exécuté.
Les futurs ajouts devront utiliser la liste explicite des fichiers approuvés.

## Vérifications techniques réellement exécutées

| Contrôle local macOS ARM64 | Résultat |
|---|---|
| Python 3.10.20 + PySide6 6.12.0, suite entière | **70/70 réussis**, aucune exclusion |
| Python 3.12.13 + PySide6 6.12.0, suite entière | **70/70 réussis**, aucune exclusion |
| Comparaison avec les exports de `v0.2.1` | **1 008/1 008** : mêmes champs, types, valeurs, ordre et noms de fichiers ; archives identiques octet pour octet |
| NFC compact | **1 008/1 008** dans la capacité calculée |
| Conservation des corrections locales | **13/13** fonctions d'acquisition, sur copies et sources simulées ; 48 profils conservés |
| Migration → mise à jour partielle → restauration | Corrections conservées, date complète inchangée en cas partiel, sauvegardes et restauration exactes |
| Syntaxe Python 3.10 | 30 fichiers applicatifs/scripts/tests analysés |
| Versions | `core.APP_VERSION`, `pyproject.toml`, changelog non publié et bundle : **0.2.2** |
| Dépendances | 16 entrées épinglées dans `requirements-build.txt` ; versions applicables conformes dans l'environnement local 3.12 ; `uv pip check` réussi en 3.10 et 3.12 |
| YAML et dépendances entre jobs | Matrices, événements, conditions, permissions et précédence des tests contrôlés localement |
| Nouveau build PyInstaller macOS ARM64 | **Réussi**, PyInstaller 6.22.3, PySide6 6.12.0 |
| Ressources du binaire | **74/74 identiques octet pour octet** aux sources : 10 fichiers data, 16 scripts, 48 profils ; modules `core` et `scripts.db_io` présents dans PYZ |
| Sonde du binaire corrigé | Code 0 ; import de 13 workers, exécution des deux seeds, restauration exacte, octets concurrents détectés conservés |
| `git diff --check` | Aucune erreur |

Commande des tests : `python -B -m unittest discover -s tests -t . -v`.
Les connexions réseau des tests et de la sonde gelée sont bloquées par un garde
d'audit ; les sources sont simulées. Aucun test ajouté ni dépendant d'un NAS,
d'un serveur Spoolman personnel, d'une U1 ou d'un service privé.

La comparaison des 1 008 exports charge uniquement les imports/classes/fonctions
de l'ancien code depuis Git, sans exécuter ses initialisations avec écriture.
Les 74 SKU résolubles sans couleur et les deux orphelins FM01001/FM01002 restent
explicitement non exportables. Maximum NFC : **829/872 octets, marge 43**,
avec un seul MIME `application/json`, TLV Type 2 et terminateur, sans ID et
CC exclu. Les ajouts réels de SpoolFlux restent à mesurer.

Les dépendances sont cohérentes localement ; disponibilité des paquets sur les
runners Windows/Linux, règles du compte et résolution des références d'actions
seront validées par GitHub Actions. Aucun paquet ni action n'a été mis à jour.

## Parcours GitHub Actions préparé, non lancé

Le workflow existant `.github/workflows/build.yml` satisfait les matrices demandées :

| Job | Environnements | Précédence / sortie |
|---|---|---|
| `tests` | Linux Python 3.10 et 3.12 ; Windows 3.12 ; macOS 3.12 | Suite entière, Qt offscreen, cohérence des versions |
| `verify` | Ubuntu | Contrôle du tag uniquement si référence de tag |
| `build` | Windows, macOS, Linux ; Python 3.12 | `needs: [verify, tests]` : les quatre variantes de tests doivent réussir avant les trois builds |
| `release` | Ubuntu | Dépend des builds et exige une référence `refs/tags/v*` |

Aucun `continue-on-error` ne neutralise les tests. Les builds installent le
snapshot des dépendances, exécutent PyInstaller, puis préparent ZIP et SHA-256
et téléversent les artefacts du run. Permission globale `contents: read` ;
`contents: write` seulement sur le job de release.

Parcours proposé **après autorisations Git et validation distante** :

1. Créer la branche `release/v0.2.2`, constituer les commits approuvés et revoir
   leur contenu exact, puis pousser uniquement cette branche.
2. Le push déclenche les quatre variantes de tests ; les builds sont ignorés
   sur un simple push de branche.
3. Déclencher manuellement `build.yml` sur `release/v0.2.2` : les tests
   précèdent alors les trois builds et leurs artefacts.
4. Examiner les résultats et télécharger les artefacts pour les recettes.
   Sur cette référence de branche, la condition du job de release est fausse.

**Ne créer ni pousser de tag pour cette validation.** Un tag `v*` activerait
le parcours de publication existant. Le workflow n'a pas besoin d'être modifié
pour valider les trois builds sans release. Le déclenchement manuel distant
nécessite encore l'autorisation de l'utilisateur.

## Proposition de commits

Branche proposée : `release/v0.2.2`, à créer depuis le HEAD contrôlé en
conservant les modifications locales. Découpage proposé, **aucun commit créé** :

| Ordre | Sujet proposé | Périmètre explicite | Fichiers |
|---|---|---|---:|
| 1 | `fix: stabiliser les exports et les données de v0.2.2` | `app_gui.py`, `convert_profile.py`, `core.py`, les 13 scripts d'acquisition, `scripts/__init__.py`, `scripts/db_io.py`, tous les fichiers de `tests/`, `pyproject.toml`, `spoolscribe.spec` | 33 |
| 2 | `ci: préparer les builds et exclure les fichiers de récupération` | `.github/workflows/build.yml`, `requirements-build.txt`, `.gitignore` | 3 |
| 3 | `docs: documenter v0.2.2 et les validations avant publication` | Les 14 fichiers de documentation de l'inventaire, y compris les quatre rapports | 14 |

Code et tests restent ensemble car les protections, le stockage partagé et les
13 workers sont interdépendants. La version applicative et le spec qui embarque
le helper accompagnent ce premier lot. Le second définit la validation distante
et l'exclusion des données de récupération. Le troisième conserve les preuves
historiques et l'état final. Les validations présentes portent sur l'état final
complet ; chaque état intermédiaire de ce découpage reste à contrôler lors de
la constitution des commits.

## Rapports accessibles et données préservées

Les quatre rapports sont présents dans le dépôt local et explicitement inclus
dans le troisième commit proposé :

- [Validation locale initiale](VALIDATION-v0.2.2.md).
- [Revue finale avant correctifs](REVUE-FINALE-v0.2.2.md).
- [Validation des correctifs acceptés](VALIDATION-CORRECTIFS-v0.2.2.md).
- [Présente préparation CI](PREPARATION-CI-v0.2.2.md).

Ils sont encore non suivis à ce stade et ne sont donc pas encore accessibles
dans l'historique distant. Aucun rapport antérieur n'a été réécrit.

Tous les fichiers de `data/` et `orca_profiles/` sont inchangés.
Catalogue : 1 084 SKU, 91 produits, 76 HEX manquants dont les deux orphelins.
SHA-256 de `data/polymaker_db.json` :

```
ddf48fbbaf9addf3c8751e6d69ea2daae0d061d8bb2a595f4b62d1fcb164cc35
```

## Risques résiduels et validations différées

- **GitHub Actions non exécuté** : résultats des quatre runners, installation
  des dépendances, commandes shell Windows et création/téléversement des trois
  artefacts restent à confirmer. Les contrôles YAML locaux ne sont pas une
  validation par le moteur GitHub. Accès, politiques Actions et quotas du compte
  ne sont pas interrogés dans cette passe.
- Les références d'actions utilisent des tags majeurs, pas des SHA immuables.
  Aucune modification de dépendances ou de politique de pinning n'est introduite.
- Packaging macOS : avertissement PyInstaller sur `.app` + onefile, qui deviendra
  une erreur en v7 ; version actuelle épinglée à 6.22.3. La sonde émet aussi
  `sandbox_extension_issue_file_to_process ... Operation not permitted`,
  avec code final 0 et assertions réussies. Gatekeeper, notarisation et recette
  visuelle humaine ne sont pas validés par cette sonde. Qt signale une police
  « Sans Serif » de remplacement pendant les tests offscreen.
- R4 reste une détection renforcée : un éditeur externe ignorant le verrou peut
  écrire entre le dernier contrôle et le remplacement. Pas d'exclusion absolue.
  Les mises à jour partielles restent appliquées ; les sauvegardes ne constituent
  pas un historique immuable ni une transaction globale des assets et profils.
- **Matériel réel non testé** : programmation/relecture SpoolFlux des NTAG216,
  ajouts NDEF, lecture Snapmaker U1 et identification définitive des deux PLA
  observés. Aucun développement Spoolman, NAS ou firmware Paxx12.
- Les journaux locaux restent temporaires. Les rapports et tests candidats
  permettent de conserver les résultats et de relancer les vérifications.

Preuves de cette passe, hors dépôt :
`/var/folders/fm/zkl1jp692vl4thdkp_m1hspr0000gn/T/spoolscribe-preparation-ci-idx3k016/`
(manifeste initial, inventaire sécurité, journaux Python 3.10/3.12,
comparaison des exports et conservation, contrôle workflow/dépendances,
build et inventaire des ressources, sonde du binaire).

**STOP : aucune création de commit, aucun push, aucune PR ou release.
Attente de l'autorisation avant toute validation distante.**
