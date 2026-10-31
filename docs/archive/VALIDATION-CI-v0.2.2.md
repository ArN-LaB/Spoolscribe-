# SpoolScribe v0.2.2 — validation GitHub Actions

> Rapport historique sur le commit `7159a6b`, avant correction de CI-01.
> Les échecs ci-dessous sont conservés pour traçabilité. Le jeu de dépendances
> correctif est décrit dans le changelog de v0.2.2.

Date : 31 octobre 2026. **Résultat global : ÉCHEC CI, validation d'intégration
non acquise.** Linux/Python 3.10 s'arrête dans le binding Qt sur les deux
exécutions. Les trois configurations Python 3.12 réussissent. Les trois builds
sont bloqués et aucun artefact distant n'est produit.

## Branche, commits et contrôle du périmètre

Actualisation initiale par `git fetch --no-tags origin` : `main`, `origin/main`
et HEAD correspondaient au commit attendu
`5197234c68885618492039061d4228f6848d024c`. Aucune divergence détectée.

Branche créée puis poussée :
[release/v0.2.2](https://github.com/ArN-LaB/Spoolscribe-/tree/release/v0.2.2).
Les trois commits approuvés ont été constitués dans l'ordre, avec sélection
explicite de fichiers, vérification de l'index et contrôle des contenus :

| SHA complet | Sujet | Fichiers |
|---|---|---:|
| `73b532ef13ed5ec160684184bb7567cdc2c3ecef` | fix: stabiliser les exports et les données de v0.2.2 | 33 |
| `0100ed915570ec833c9357636cd9d4acd39eba2e` | ci: préparer les builds et exclure les fichiers de récupération | 3 |
| `7159a6b0604d6fc9e5a8205ed57a0331e9f3b836` | docs: documenter v0.2.2 et les validations avant publication | 14 |

Les 50 fichiers correspondent à l'inventaire accepté. Recherche ciblée de
secrets, vérification des empreintes et de la nature des fichiers : aucun secret,
lien symbolique, fichier personnel ou artefact temporaire détecté dans les lots.
Aucun fichier de `data/` ou `orca_profiles/` dans les diffs des commits.

Seul ajustement avant le commit documentaire : suppression d'une ligne blanche
superflue à la fin de `PREPARATION-CI-v0.2.2.md`, détectée par
`git diff --cached --check`. Son contenu rédactionnel reste inchangé.

Push explicite d'une seule référence, avec le suivi automatique des tags désactivé :

```sh
git -c push.followTags=false push --set-upstream origin refs/heads/release/v0.2.2:refs/heads/release/v0.2.2
```

Les deux runs ci-dessous portent exactement sur le HEAD documentaire
`7159a6b0604d6fc9e5a8205ed57a0331e9f3b836`. Aucun changement de code,
de test, de dépendance ni de workflow n'a été appliqué entre les runs ou après
leurs échecs. Aucun test n'a été retiré, désactivé ou rendu facultatif.

## Contrôles locaux avant push

| Contrôle sur la branche préparée | Résultat |
|---|---|
| Python 3.10.20 + PySide6 6.12.0, macOS ARM64 | **70/70 réussis**, aucune exclusion |
| Python 3.12.13 + PySide6 6.12.0, macOS ARM64 | **70/70 réussis**, aucune exclusion |
| 1 008 exports comparés au code de v0.2.1 | Champs, types, valeurs, ordre et noms identiques ; archives identiques octet pour octet |
| Conservation des corrections sur copies | 13/13 scripts ; 48 profils conservés ; migration, mise à jour partielle et restauration contrôlées |
| Version et configuration PyInstaller | 0.2.2 cohérent ; spec syntaxiquement valide, helper `scripts.db_io` déclaré |
| Rapports précédents | Les quatre rapports sont présents et suivis dans le troisième commit |
| `git diff --check` et contrôle du diff complet depuis la base | Sans erreur après correction du blanc final |
| Catalogue et profils | Aucun changement par rapport au commit de base |

Commande de suite : `python -B -m unittest discover -s tests -t . -v`.
Les tests locaux bloquent les connexions réseau et utilisent des copies et des
réponses simulées. Le build local macOS et l'inventaire de ses 74 ressources
documentés dans `PREPARATION-CI-v0.2.2.md` n'ont pas été reconstruits ici : les
sources correspondantes sont inchangées. Cela ne vaut pas validation des builds CI.

## Exécutions GitHub Actions

- [Push — run 41175139078](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41175139078) : événement `push`, **failure**.
- [Déclenchement manuel — run 41175307202](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41175307202) : événement `workflow_dispatch`, **failure**.

Le second run a été déclenché explicitement sur `release/v0.2.2` avec :

```sh
gh workflow run build.yml --repo ArN-LaB/Spoolscribe- --ref release/v0.2.2
```

Il reproduit l'erreur initiale sans modification du dépôt. Aucun run n'a été
relancé jusqu'à obtenir artificiellement un statut vert.

### Résultats exacts des tests

Chaque résultat positif ci-dessous est confirmé par un job `success` et le
journal de la commande réelle : `Ran 70 tests` puis `OK`, sans test exclu.
Les versions correctives sont celles effectivement installées par les runners.

| Configuration | Python effectif | Push | Manuel |
|---|---|---|---|
| Linux / Python 3.10 | 3.10.22 | **ÉCHEC**, arrêt natif, code 134 | **ÉCHEC**, même arrêt natif, code 134 |
| Linux / Python 3.12 | 3.12.15 | **70/70 OK**, 2.429 s | **70/70 OK**, 3.172 s |
| Windows / Python 3.12 | 3.12.10 | **70/70 OK**, 5.828 s | **70/70 OK**, 5.301 s |
| macOS / Python 3.12 | 3.12.10 | **70/70 OK**, 3.889 s | **70/70 OK**, 2.967 s |

Linux 3.10 n'émet aucun bilan final unittest : la suite est interrompue avant
son terme. Ses tests restants ne sont donc pas considérés comme exécutés ou
réussis. La réussite locale macOS/3.10 ne remplace pas ce résultat Linux.

### Builds et garde de publication

`build.needs` exige les jobs `verify` et `tests`, donc la réussite de toute la
matrice des quatre configurations. Aucun `continue-on-error` ni commande
masquant l'échec des tests n'est configuré.

| Construction distante attendue | Résultat réel |
|---|---|
| Windows | **NON EXÉCUTÉE** : matrice de builds bloquée par l'échec Linux 3.10 |
| macOS | **NON EXÉCUTÉE** : même blocage |
| Linux | **NON EXÉCUTÉE** : même blocage |

Sur le push de branche, la condition des builds ne les demandait pas. Sur le
run manuel, la condition est vraie mais la dépendance aux tests empêche leur
démarrage. GitHub présente un job non développé `Build ${{ matrix.os }}` avec
conclusion `skipped` ; aucun job PyInstaller par OS n'est lancé. Ce `skipped`
n'est pas compté comme une réussite de build.

Le job `Verify tag matches version` termine avec `success`, mais son étape de
comparaison de tag est intentionnellement ignorée sur cette branche ; il n'est
pas compté comme un test de tag exécuté.

La condition de publication a été vérifiée avant le push et le déclenchement :
`startsWith(github.ref, 'refs/tags/v')` est fausse pour
`refs/heads/release/v0.2.2`. `Publish release` est effectivement `skipped` dans
les deux runs. Aucun chemin de publication n'a été activé.

## Artefacts et empreintes

L'API des artefacts des deux runs retourne **`total_count: 0`**.

| Sortie attendue | ZIP produit | Fichier SHA-256 produit | Empreinte |
|---|---|---|---|
| SpoolScribe-windows | Aucun | Aucun | Non disponible |
| SpoolScribe-macos | Aucun | Aucun | Non disponible |
| SpoolScribe-linux | Aucun | Aucun | Non disponible |

Les noms prévus sont `SpoolScribe-{windows,macos,linux}.zip` et
`SpoolScribe-{windows,macos,linux}.zip.sha256`. Ils ne sont pas générés ni
téléversés parce que les builds ne démarrent pas. Aucun hash de binaire local
ou d'une ancienne release ne leur est substitué.

## Anomalie CI-01 — arrêt natif Linux / Python 3.10

**Bloquante pour la validation d'intégration.**

- Job initial : [Tests ubuntu-latest / Python 3.10, 124461020993](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41175139078/job/124461020993).
- Reproduction : [même configuration, 124461514864](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41175307202/job/124461514864).
- Étape : `Offline business and GUI tests`.
- Commande : `python -B -m unittest discover -s tests -t . -v`.
- Environnement observé : Ubuntu 26.04.1 x86_64, CPython 3.10.22,
  PySide6 / PySide6_Essentials / PySide6_Addons / Shiboken6 6.12.0.
- Erreur : `Fatal Python error: none_dealloc: deallocating None`, puis
  `Aborted (core dumped)` et code de sortie **134**.
- Point d'arrêt : construction de `MainWindow` dans le `setUp` de
  `test_manual_color_and_transparency_are_saved_and_exported`, avant le corps
  du test. Pile : `app_gui.py:_populate`, ligne 990 dans le premier run et 989
  dans le second, appels `QTableWidgetItem` / `QTableWidget.setItem`, depuis
  `_reload_table` et `MainWindow.__init__`.

**Classification : défaut de dépendance native / compatibilité du binding Qt
probable ; cause racine exacte non établie.** L'installation des paquets
réussit, Qt fonctionne jusqu'au remplissage de la table, puis l'interpréteur
abandonne sur son singleton `None`. Il ne s'agit pas d'une assertion Python
en échec ni d'une erreur de PyInstaller, qui n'a pas encore été exécuté.
GitHub Actions signale correctement la panne et bloque le packaging.

Contexte primaire consulté : les
[notes de développement Qt](https://wiki.qt.io/Qt_for_Python_Development_Notes)
mentionnent PYSIDE-3424, la compatibilité des wheels ABI limité entre Python
3.12 et 3.10 et les différences de macros INCREF/DECREF. La
[PEP 683](https://peps.python.org/pep-0683/) décrit l'immortalité d'objets
introduite en Python 3.12. Ces éléments rendent l'hypothèse cohérente avec
l'écart entre configurations ; ils ne prouvent pas à eux seuls que ce crash
précis est PYSIDE-3424.

Une petite sonde locale macOS/3.10, 100 appels Qt de chaque type, ne montre
pas de baisse systématique du compteur de références de `None`. Le défaut
n'est donc pas reproduit par cette sonde sur le wheel macOS ARM64.

Suite proposée, **non appliquée** : établir un reproducteur minimal sur
Linux/Python 3.10, comparer des ensembles PySide6/Shiboken cohérents, puis
adapter les contraintes de dépendances si cette piste est confirmée. Conserver
les quatre configurations et tous les tests. Une telle correction change le
jeu de dépendances validé et demande une décision avant modification.

## Avertissements et vérifications restantes

- macOS CI : Qt signale le remplacement de la police `Sans Serif` (94 ms puis
  67 ms de recherche d'alias), sans échec de la suite.
- Aucun avertissement PyInstaller distant à évaluer : les builds n'ont pas
  démarré. L'avertissement local antérieur `.app` + onefile reste consigné dans
  les rapports précédents, sans nouveau résultat de packaging distant.
- À réaliser après résolution de CI-01 : matrice entière verte, trois vrais
  builds, récupération des trois ZIP, vérification de leurs SHA-256, démarrage
  et comportement des binaires sur les systèmes cibles.
- Recette visuelle humaine macOS, Gatekeeper/notarisation, programmation et
  relecture SpoolFlux/NTAG216, lecture Snapmaker U1 : **NON EXÉCUTÉES**.
- Les deux références PLA observées restent à identifier définitivement ; aucune
  donnée catalogue, intégration Spoolman, fonction NAS ou firmware Paxx12 modifié.
- La limite de concurrence R4 demeure documentée : les éditeurs externes ignorant
  le verrou ne sont pas exclus de manière absolue.

## État final et preuves

`main` local et distant reste à
`5197234c68885618492039061d4228f6848d024c` ; la branche distante de validation
pointe sur `7159a6b0604d6fc9e5a8205ed57a0331e9f3b836`.
Les listes distantes de tags et de releases, capturées avant et après, sont
identiques (deux tags et deux releases préexistants). Les tags locaux sont
également inchangés. Aucune PR n'existe pour cette branche au contrôle final.

**Aucun tag, aucune release, aucune fusion vers `main`, aucune nouvelle version
ni publication d'application créés.** Seuls les trois commits autorisés et leur
branche de validation ont été poussés.

Catalogue et profils inchangés. SHA-256 de `data/polymaker_db.json` :

```
ddf48fbbaf9addf3c8751e6d69ea2daae0d061d8bb2a595f4b62d1fcb164cc35
```

Le présent rapport est créé localement et reste **non commité / non poussé**.
L'index est vide ; aucun quatrième commit n'a été ajouté. Les quatre rapports
précédents sont dans la branche distante.

Preuves temporaires hors dépôt :
`/var/folders/fm/zkl1jp692vl4thdkp_m1hspr0000gn/T/spoolscribe-validation-ci-cfn2dxg9/`.
Elles comprennent le plan et les diffs des commits, les contrôles locaux,
les métadonnées des deux runs et de leurs jobs, leurs journaux complets,
`ci-results.json`, les réponses d'artefacts et les états tags/releases avant/après.
Les URLs GitHub ci-dessus conservent l'accès aux exécutions selon la rétention
du service ; les fichiers locaux restent soumis au nettoyage temporaire.

**STOP après cette validation en échec. Attente de décision humaine sur CI-01.
Aucune modification supplémentaire ni publication.**
