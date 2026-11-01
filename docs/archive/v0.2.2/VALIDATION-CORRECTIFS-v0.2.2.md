> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# SpoolScribe v0.2.2 — validation des correctifs R1 à R4

Date : 31 octobre 2026. Branche `main`, HEAD
`5197234c68885618492039061d4228f6848d024c` inchangé. Modifications locales non
commitées. Périmètre : corrections autorisées après `REVUE-FINALE-v0.2.2.md`.

**Résultat local : R1, R2 et R3 corrigés ; R4 durci avec limite documentée.**
Les contrôles ci-dessous passent. Aucune release n'est autorisée par ce résultat.
Les deux rapports précédents restent conservés comme preuves historiques.

## Corrections réalisées

| Point | Comportement corrigé | Preuve exécutée |
|---|---|---|
| R1 — sources et statuts | Réponses Spoolman vides, sans filaments ou sans couleurs utilisables : `unavailable`. Index Polymaker TheFilamentDB vide : `unavailable`. En multimarque, absence de toutes les marques cibles : `unavailable` ; absence d'une partie : `partial`. Source valide sans nouveauté : `unchanged`. | Véritables fonctions de scripts, réponses et dumps gzip locaux : cas vides, couleurs invalides, données sans marque cible, données valides et sources partiellement disponibles. |
| R1 — assets | Métadonnées vides rejetées. Si aucune marque n'est vérifiée, `sync_multibrand_assets` retourne `unavailable` ; si une partie réussit, `partial`. | Échec des deux sources, deux réponses vides, une source valide, deux sources valides, puis répétition sans changement. |
| R1 — date | Un résultat indispensable indisponible empêche le statut global `complete` et conserve `_last_updated`. | Pour chacun des quatre scripts de couleurs concernés, résultat réel d'une source vide injecté dans le vrai agrégateur, autres étapes simulées valides : statut `partial`, date ancienne inchangée. |
| R2 — restauration | Une restauration réussie marque le chemin en mémoire pour le processus courant. Les contrôles automatiques CLI/GUI et l'initialisation/fusion du bundle respectent ce marqueur. Les préférences restent intactes. | Vrai `convert_profile.main()` et vrai `app_gui.main()` avec fenêtre Qt offscreen, consentement et auto-update actifs, base ancienne puis corrompue, restauration confirmée. Aucun démarrage automatique ; égalité stricte des octets restaurés. |
| R3 — couleurs | Les deux seeds appliquent `requires_manual_color` avant de compléter un HEX vide existant. | `PM-PLA-JETBLACK` et `R3-PETG-BLACK` : HEX nul + alpha `00`, HEX nul + couleurs supplémentaires, couleur nommée transparente ; valeurs et notes conservées, export refusé sans HEX représentatif. HEX non vide + alpha également conservés. |
| R4 — concurrence | Contrôle supplémentaire après écriture/flush/fsync du temporaire, immédiatement avant `os.replace`. En cas de changement détecté, sauvegarde refusée et octets détectés conservés dans `.concurrent-*`. | Écriture concurrente pendant la sauvegarde `.bak`, pendant le fsync du fichier préparé, et révision déjà obsolète. Fichier concurrent conservé, copie de récupération exacte, verrou et temporaire nettoyés. |

La protection R2 est liée au chemin du fichier et reste en mémoire ; elle ne
modifie pas la configuration persistante. La mise à jour manuelle CLI reste
possible sur choix explicite, vérifié par test. Le contrôle de démarrage redevient
actif avec les mêmes préférences quand le marqueur de session est absent,
également vérifié. Le parcours GUI laisse passer le délai réel du timer de
démarrage dans une boucle Qt puis rappelle le contrôle : les deux restent inertes
après restauration. Les variantes source et bundle sont exercées.

Le mécanisme R4 conserve les octets bruts, même si l'éditeur externe n'a pas
terminé son JSON. Une suppression concurrente n'a pas d'octets à copier ; elle
fait néanmoins refuser la publication. Aucun stockage supplémentaire complexe
ni dépendance nouvelle n'a été introduit. Les appels existants restent
compatibles ; `atomic_write` reçoit un argument optionnel réservé au contrôle
juste avant remplacement. Les fonctions et formats d'export restent inchangés.

La documentation de restauration, de statut et de concurrence est actualisée
dans `docs/wiki/Updating-the-Database.md`.

## Tests ajoutés avant correction : échec puis réussite

Les tests ont été ajoutés et exécutés avant toute modification corrective du
code applicatif. Les 11 méthodes ciblées produisaient **32 échecs d'assertions
ou sous-tests**, répartis sur dix méthodes ; le cas témoin « sources valides
sans changement » passait déjà. Ces échecs reproduisaient les constats de revue,
notamment le lancement automatique CLI/GUI et la perte de l'écriture concurrente.
Après correction : **11/11 méthodes ciblées réussies**.

Fichiers de tests ajoutés ou complétés :

- `tests/test_regressions_v022.py` : sources vides/valides/partielles et seeds.
- `tests/test_cli.py` : restauration exacte, préférences, action manuelle et
  portée de session.
- `tests/test_gui.py` : vrai démarrage/restauration Qt offscreen, source et bundle.
- `tests/test_db_io.py` : conflits à plusieurs instants, copie de récupération,
  y compris données concurrentes non valides.

Après les derniers changements, la suite entière a été relancée :

| Environnement macOS ARM64 | Résultat final |
|---|---|
| Python 3.10.20 + PySide6 6.12.0 | **70/70 réussis**, aucune exclusion |
| Python 3.12.13 + PySide6 6.12.0 | **70/70 réussis**, aucune exclusion |

Commande : `python -B -m unittest discover -s tests -t . -v`.
Les connexions réseau sont bloquées par le garde d'audit des tests ; les réponses
distantes sont simulées. Le worker autonome existant n'exécute qu'un seed local.
La sonde du binaire dispose également d'un garde d'audit réseau. Aucun serveur
personnel, NAS, Spoolman, programmateur ou firmware Paxx12 n'a été contacté.

## Nouvelle vérification des 1 008 exports

Comparaison avec le code de `v0.2.1`, extrait localement par Git. Seuls ses
imports, classes et fonctions sont chargés ; ses initialisations avec effets
d'écriture ne sont pas exécutées. Entrées : catalogue inchangé et profils Orca
locaux inchangés.

| Contrôle | Résultat |
|---|---|
| Champs, types et valeurs JSON | **1 008/1 008 identiques** |
| Ordre des champs | **1 008/1 008 identiques** |
| Ancien export lisible / nouvelle archive, octets UTF-8 | **1 008/1 008 identiques** |
| Noms de fichiers | **1 008/1 008 identiques** |
| Exports compacts dans la capacité calculée | **1 008/1 008** |
| SKU sans HEX nécessitant un choix explicite | 74, inchangés |
| SKU sans produit | FM01001 et FM01002, inchangés |

Maximum : CA02027, **802 octets JSON UTF-8, 824 octets NDEF, 829 octets avec
TLV et terminateur, marge 43/872 octets**. PA05007 et PA07046 restent à 828
octets, CA09003 à 824. Hypothèse : un enregistrement MIME `application/json`
sans ID, zone NTAG216 disponible de 872 octets, CC exclu. La marge inclut tout
ajout éventuel de SpoolFlux ; son contenu réellement écrit n'a pas été mesuré.

Les changements intentionnels déjà revus restent applicables aux bases
personnalisées : couleurs inconnues refusées et valeurs physiques locales
prioritaires, avec choix explicite possible des valeurs Orca. L'équivalence
mesurée ci-dessus porte sur les 1 008 références du catalogue courant.

## Conservation des modifications locales

Une matrice complémentaire exécute les **13 véritables fonctions d'acquisition**
sur des copies temporaires complètes, sources simulées. Le catalogue de test
comporte 1 085 SKU après ajout d'une référence locale. Corrections injectées :
HEX et nom de couleur, densité `1.2711`, métadonnées de marque, notes libres,
HEX intentionnellement nuls avec alpha ou plusieurs couleurs.

Résultat : **13/13 scripts conservent les valeurs locales non vides, les champs
libres et les entrées locales testées**. Les trois entrées explicitement
protégées avec HEX nul restent strictement identiques. Les **48 profils Orca**
copiés restent identiques octet pour octet après téléchargement/import simulés.
Les scripts peuvent compléter des valeurs ordinaires absentes ; un statut
`changed` peut aussi résulter de la remise en forme de la copie JSON temporaire.

Une séquence sur le catalogue complet corrigé vérifie aussi :

1. Migration du bundle : champs locaux conservés ; `.bak` égale à l'état initial.
2. Mise à jour partielle : une étape ajoute un SKU valide, douze sont
   indisponibles ; corrections conservées, statut `partial`, date complète
   inchangée, `.pre-update.bak` égale à l'état avant le pipeline.
3. Restauration puis rechargement : fichier identique octet pour octet à la
   sauvegarde sélectionnée ; état remplacé conservé dans `.before-restore-*`.

Ces vérifications utilisent exclusivement des copies ; aucun correctif de
données n'est appliqué au catalogue réel.

## CI et packaging effectivement vérifiés

- YAML analysé localement : matrice Linux Python 3.10/3.12, Windows/macOS 3.12,
  Qt offscreen et commande de suite complète présents. Les builds dépendent des
  tests et de la vérification de version. Publication conditionnée à un tag,
  permission d'écriture limitée au job de release. **Aucun workflow déclenché.**
- Syntaxe des 30 fichiers Python applicatifs/scripts/tests contrôlée avec la
  grammaire Python 3.10 ; versions `core.py` / `pyproject.toml` cohérentes.
- `uv pip check` : environnements 3.10 et 3.12 compatibles, sans installation
  ni mise à jour de dépendances.
- **Nouveau build local macOS ARM64 réussi**, PyInstaller 6.22.3, PySide6 6.12.0,
  avec `spoolscribe.spec` ; version du bundle contrôlée à 0.2.2. Module partagé
  de stockage embarqué. Build et données d'essai isolés hors du dépôt.
- **Sonde du binaire corrigé réussie, code 0** : import des 13 scripts embarqués,
  exécution réelle des deux seeds avec HEX nul + alpha conservés, restauration
  exacte d'une sauvegarde sans marqueur de bundle, préférences inchangées,
  conflit d'écriture détecté avec copie brute conservée.
- `git diff --check` : aucune erreur.

Avertissements observés : Qt remplace la police « Sans Serif » ; PyInstaller
annonce que `.app` + onefile deviendra une erreur en version 7. Le lancement
du binaire émet aussi `sandbox_extension_issue_file_to_process ... Operation
not permitted` sur ce Mac ; son processus termine avec le code 0 et toutes les
assertions de la sonde réussissent. Aucune recette Gatekeeper ou notarisation
n'est déduite de ce lancement.

## Limites et vérifications non exécutées

- **R4 : limite maintenue explicitement.** Un éditeur ou synchroniseur ignorant
  le verrou peut encore écrire entre le dernier contrôle et `os.replace`.
  La copie protège la version détectée, sans exclusion absolue de tout écrivain
  externe. Fermer les autres écrivains pendant les modifications/restaurations.
- Un index exploitable ne prouve pas l'exhaustivité de toute une source amont.
  Les cas sans données exploitables et les marques cibles absentes sont couverts ;
  les sources réseau réelles n'ont pas été actualisées.
- Les mises à jour partielles restent appliquées aux données disponibles.
  Pas de transaction globale catalogue/logos/profils ni d'historique immuable
  de toutes les sauvegardes. La résistance à une coupure d'alimentation n'est
  pas mesurée par les injections d'interruption logicielle.
- **NON EXÉCUTÉS :** GitHub Actions distant, builds et exécution Windows/Linux,
  parcours visuel humain macOS, écriture/relecture SpoolFlux sur NTAG216 et
  recette physique Snapmaker U1. Qt offscreen et la sonde du binaire sont des
  contrôles fonctionnels, pas une recette visuelle ou matérielle.

## État du dépôt et preuves

L'empreinte de tous les fichiers initiaux a été enregistrée avant la passe.
Les seuls fichiers initiaux modifiés dans cette passe sont les 11 fichiers de
code nécessaires à R1–R4, trois fichiers de tests et la page de documentation
des mises à jour. Ajouts : le fichier de tests de régression et ce rapport.
Les autres modifications locales préexistantes sont conservées.

**Tous les fichiers de `data/` et `orca_profiles/` restent inchangés.**
Catalogue : 1 084 SKU, 91 produits, 76 HEX manquants, dont les deux orphelins.
SHA-256 de `data/polymaker_db.json` :

```
ddf48fbbaf9addf3c8751e6d69ea2daae0d061d8bb2a595f4b62d1fcb164cc35
```

État global constaté après cette passe : 29 fichiers suivis modifiés et 19
fichiers nouveaux, index vide. HEAD et références Git inchangés ; aucun commit,
push, tag, PR, release ou publication créé.

Les journaux et scripts de vérification complémentaires sont temporaires dans :
`/var/folders/fm/zkl1jp692vl4thdkp_m1hspr0000gn/T/spoolscribe-correctifs-enuo4p6b/`.
Ils comprennent `before-fixes.log`, `after-targeted.log`, `tests-py310.log`,
`tests-py312.log`, `verify_exports_and_preservation.py`,
`exports-preservation.log`, `export-fingerprints.json`, `pyinstaller.log`,
`probe_frozen_correctifs.py`, `frozen-correctifs.log` et `initial-manifest.json`.
Leur durée de conservation dépend du nettoyage des répertoires temporaires.

**STOP après cette passe corrective. Attente de l'accord humain avant toute
publication ou modification supplémentaire.**
