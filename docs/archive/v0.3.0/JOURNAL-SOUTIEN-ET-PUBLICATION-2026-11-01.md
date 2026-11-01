> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Journal des ajustements — soutien Buy Me a Coffee, licences, profil et publication v0.3.0

Session du 1er novembre 2026. Compte GitHub : `ArN-LaB`. Lien de soutien :
<https://buymeacoffee.com/arn_lab>.

Les heures sont en UTC lorsqu'elles proviennent de GitHub.

## Synthèse

| Périmètre | Modification | Commits / référence | État |
|---|---|---|---|
| SpoolScribe `main` | FUNDING.yml, badge, section *Support* | `35095f1` | Publié (PR #4 fusionnée) |
| SpoolScribe `main` | LICENSE MIT standard, `NOTICE`, CHANGELOG `[Unreleased]` | `e82d43f` | Publié (PR #4 fusionnée) |
| Zenith `main` | FUNDING.yml, badge | `e9143bf` | Publié (PR #1 fusionnée) |
| Zenith `main` | LICENSE MIT standard, `NOTICE`, renvoi README, CHANGELOG `[Unreleased]` | `3763586` | Publié (PR #1 fusionnée) |
| SpoolScribe et Zenith | Bouton « Sponsor » (Sponsorships) activé | Réglage du dépôt | Actif |
| Profil GitHub | Bio et lien social Buy Me a Coffee | Réglage du compte | Actif |
| GitHub CLI | Reconnexion `ArN-LaB`, droit `user`, protocole SSH | Configuration locale | Fait |
| SpoolScribe v0.3.0 | 4 commits par lot, premier push de la branche | `24bb467` → `1e9dc16` | Publié, CI Windows en échec |
| SpoolScribe v0.3.0 | Fusion de `main` dans la branche | — | **Non exécuté** |

## 1. Audit initial

Dépôts publics du compte : `Spoolscribe-`, `Zenith`, `vpn-tools` (fork),
`homebrew-tap`, `lfipekin-cdn`. Aucun dépôt privé, pas de dépôt de profil.

- Aucun `FUNDING.yml` et aucun lien de soutien existant : pas de doublon ni de
  lien obsolète.
- Licences de SpoolScribe et Zenith détectées `NOASSERTION` par GitHub, à cause
  des notes ajoutées après le texte MIT.
- Liens vérifiés : page Buy Me a Coffee et image du badge en HTTP 200.

Décisions :

- **Retenus** : SpoolScribe et Zenith (projets originaux, MIT, destinés au public).
- **Exclus** : `vpn-tools` (fork d'un projet tiers encore actif),
  `homebrew-tap` (distribution), `lfipekin-cdn` (dépôt d'images). Vous avez
  ensuite confirmé de laisser ces dépôts de côté.

## 2. SpoolScribe — branche `main`

PR [#4](https://github.com/ArN-LaB/Spoolscribe-/pull/4), fusionnée le
2026-11-01 à 03:15:22 UTC par avance rapide de `main`. L'historique reste
linéaire et les commits gardent leur signature.

### Commit `35095f1` — docs: lien de soutien Buy Me a Coffee facultatif

- **Créé** `.github/FUNDING.yml` :

  ```yaml
  buy_me_a_coffee: arn_lab
  ```

- **Modifié** `README.md` :
  - badge Buy Me a Coffee à la fin de la rangée de badges HTML existante ;
  - section **Support** placée avant **License** : projet gratuit, open source,
    développé sur du temps libre, sans version payante ni contrepartie, soutien
    entièrement facultatif.
- Le paragraphe « Made by » et la section « License » sont inchangés : ils ont
  été réécrits sur la branche v0.3.0 et y toucher aurait créé des conflits.

### Commit `e82d43f` — docs: licence MIT standard reconnue par GitHub, note de portée dans NOTICE

- **Modifié** `LICENSE` : seul le texte MIT reste, sans changement. Titulaire
  conservé : « SpoolScribe contributors ».
- **Créé** `NOTICE` : note de portée déplacée sans modification (jeux de
  données tiers, marques, renvois vers `docs/DATA_SOURCES.md` et
  `docs/TRADEMARKS.md`).
- **Modifié** `CHANGELOG.md` : section `[Unreleased]` → *Documentation*.
- Effet : GitHub détecte maintenant **MIT**. `LICENSE` n'est lu ni par le
  packaging ni par la CI, donc la distribution ne change pas.

### Vérifications

- CI de la PR : 13 succès, 4 jobs de release ignorés. CI sur `main` : succès.
- Branche `docs/buy-me-a-coffee` supprimée après fusion.

## 3. Zenith — branche `main`

PR [#1](https://github.com/ArN-LaB/Zenith/pull/1), fusionnée le 2026-11-01 à
03:15:40 UTC par avance rapide de `main`.

### Commit `e9143bf` — docs: lien de soutien Buy Me a Coffee facultatif

- **Créé** `.github/FUNDING.yml` (`buy_me_a_coffee: arn_lab`).
- **Modifié** `README.md` : badge Buy Me a Coffee ajouté après le badge de licence.

### Commit `3763586` — docs: licence MIT standard reconnue par GitHub, attribution dans NOTICE

- **Modifié** `LICENSE` : seul le texte MIT reste (« Copyright (c) 2026 ArN-LaB »).
- **Créé** `NOTICE` : attribution vpn-tools (MIT © 2025 Valera) déplacée sans
  modification.
- **Modifié** `README.md` : `See [NOTICE](../../../NOTICE).` ajouté à la section License.
- **Modifié** `CHANGELOG.md` : section `[Unreleased]` → *Documentation*.
- Effet : GitHub détecte maintenant **MIT**.

### Vérifications

- CI de la PR : 5 succès, dont CodeQL Swift. Build sur `main` : succès.
- Branche `docs/buy-me-a-coffee` supprimée après fusion.

## 4. Réglages GitHub

- **Sponsorships** activés sur `Spoolscribe-` et `Zenith` (GraphQL
  `updateRepository`, `hasSponsorshipsEnabled: true`). GitHub lit bien le lien
  `BUY_ME_A_COFFEE → https://buymeacoffee.com/arn_lab`.
- **Profil `ArN-LaB`** :
  - bio : « Free-time, open-source hobby projects — SpoolScribe · Zenith » ;
  - lien social : <https://buymeacoffee.com/arn_lab>.
- Pas de README de profil, jugé inutile.

## 5. Environnement local

- **GitHub CLI** :
  - protocole Git passé de `https` à `ssh` ;
  - reconnexion faite par vous : compte `ArN-LaB` à la place de l'ancien nom
    `ArN-Ld`, droit `user` ajouté.
- **SSH** : le port 22 coupe à cause du VPN. Les opérations Git passent par SSH
  sur le port 443, avec vérification par la clé d'hôte github.com déjà connue :

  ```sh
  GIT_SSH_COMMAND="ssh -o HostName=ssh.github.com -o Port=443 -o HostKeyAlias=github.com"
  ```

  `~/.ssh/config`, `known_hosts` et les clés sont inchangés.
- **Agent 1Password** : un refus de signature passager a bloqué un fetch,
  puis tout est rentré dans l'ordre sans intervention.
- **Mémoire Claude** : ajout de la fiche `github-access` (accès SSH sur 443,
  droits de gh, fusion par avance rapide, branche v0.3 qui n'était qu'en local).

## 6. SpoolScribe v0.3.0 — branche `feature/universal-catalogue`

### Précautions

- Une autre session modifiait l'arbre de travail. Je n'ai committé qu'après
  5 minutes sans aucune modification, puis j'ai revérifié chaque fichier de
  code par rapport à l'état testé.
- Les états cumulés des lots ont été reconstitués et testés dans un clone
  jetable : l'historique n'a jamais été réécrit.

### Commits par lot (tous signés)

| Commit | Lot | Fichiers |
|---|---|---|
| `24bb467` | fix(data): regroupements d'affichage et fusion des sources sans perte | `core.py`, `scripts/catalogue_merge.py`, `scripts/catalogue_sources.py`, `tests/test_regressions_v022.py` |
| `bbca7f2` | feat(imprimantes): fiches documentées, visuels fabricant et repli 404 | `printer_profiles.py`, `printer_presentations.py`, `data/printer_photos/` (3 images + `manifest.json`), `packaging_rules.py`, `.github/scripts/probe_frozen_catalogue.py`, `docs/PRINTER_VISUALS.md`, `docs/TRADEMARKS.md` |
| `e846add` | feat(ui): espace de travail visuel, favoris explicites et ergonomie | `ui_widgets.py`, `ui_catalogue.py`, `app_gui.py`, `data/chevron-down.svg`, `tests/test_gui.py`, `tests/test_ux.py`, `tests/test_alignment.py`, `tests/test_ergonomics.py`, `tests/test_feedback.py`, `tests/test_feedback_polish.py`, `tests/test_visual_workspace.py`, `tests/test_expanded_layout.py` |
| `1e9dc16` | docs: retours d'écran v0.3.0 (passes 1 à 6) et documentation alignée | `CHANGELOG.md`, `README.md`, `docs/DATA_FORMAT.md`, `docs/DATA_SOURCES.md`, `docs/ROADMAP.md`, `docs/UX-v0.3.0.md`, `docs/VALIDATION-AUDIT-v0.3.0.md`, `docs/VALIDATION-RETOURS-v0.3.0.md`, `docs/VALIDATION-UX-RETOURS-2…6-v0.3.0.md`, `docs/wiki/Getting-Started.md`, `docs/wiki/Printers-and-Readers.md` |

### Tests locaux

- État final (`e846add`, identique pour le code à `1e9dc16`) : **217 tests OK**
  en Python 3.10 et en Python 3.12, en mode offscreen.
- États intermédiaires (`24bb467`, `bbca7f2`) : les tests GUI se bloquent,
  comme à l'état d'origine `fba000b`. Le défaut d'isolation des tests (verrou
  d'instance, réglages réels de l'utilisateur) est corrigé dans `e846add`.

### Publication

- Premier push de `feature/universal-catalogue` vers `origin` : la branche
  pointe sur `1e9dc16` et contient 29 commits de plus que `main`.
- CI (run `41272173901`) :
  - **en succès** : Ubuntu 3.10, Ubuntu 3.12, macOS 3.12 ;
  - **en échec** : Windows 3.12, avec 2 échecs et 1 erreur :
    - `test_ergonomics.test_characteristic_actions_are_equal_and_grouped_below_tiles`
      (largeur 164 au lieu de 210) ;
    - `test_expanded_layout.test_printer_rows_do_not_grow_after_narrow_wide_narrow_sequence`
      (hauteur des lignes hors de la plage 80–160) ;
    - `test_sync.LockTests.test_a_lock_left_by_a_dead_process_is_recovered`
      (verrou non récupéré sous Windows ; code des verrous issu de `c191161`).
- `main` passe sous Windows : ces problèmes sont propres à la v0.3.0, qui
  n'avait jamais tourné sur la CI.

### Point de vigilance

`data/printer_photos/` contient des visuels de fabricants (Snapmaker, Bambu Lab,
QIDI) sans licence libre. Ils sont documentés dans `docs/PRINTER_VISUALS.md` et
sont désormais publics. L'image Bambu provient du dépôt Bambu Studio, publié
sous AGPL.

## 7. Opérations non exécutées

| Opération | Cause | Suite |
|---|---|---|
| Fusion de `origin/main` dans `feature/universal-catalogue` | Une autre session modifiait encore l'arbre (passe « Final interface polish »), et son `.github/FUNDING.yml` non suivi bloquait la fusion. Git l'a annulée sans rien modifier. | Une fois cette passe committée : supprimer le `FUNDING.yml` local (identique à celui de `main`), fusionner, déplacer les lignes `[Unreleased]` du CHANGELOG dans `[0.3.0] — Unreleased`. |
| Correction des 3 tests Windows | Code en cours de modification par une autre session. | À traiter dans la v0.3.0. |
| Vérification des doublons dans le README après fusion | La fusion n'a pas eu lieu. | Badge et section *Support* (venant de `main`) d'un côté, phrase « About → Support the project » (passe en cours) de l'autre : à harmoniser. |

## 8. Hors périmètre, inchangé

Code de Zenith, dépendances, workflows CI/CD, cask Homebrew, processus de
distribution, `~/.ssh/config`. Dépôts `vpn-tools`, `homebrew-tap` et
`lfipekin-cdn` non modifiés.


## 9. Complément — validation multiplateforme et intégration autorisée

Les sections précédentes conservent les constats de la session parallèle. Le
travail a ensuite été committé, puis l’utilisateur a autorisé le push vers `main`
et la remise en fonctionnement des trois distributions.

- `origin/main` (`e82d43f`) a été intégré à la branche de travail ; `LICENSE`,
  `NOTICE`, le financement et les ajouts README sont conservés. Le conflit du
  changelog a été résolu en gardant les deux ensembles de notes ; aucun fichier
  de soutien n’a été supprimé.
- Les échecs Windows sont corrigés : verrou de processus abandonné, police Qt
  absente du backend hors écran, dimensions des actions, repli des cartes et
  comparaison des chemins Windows courts/longs. Les contrôles de ressources CI
  ont également été corrigés pour les scripts temporaires et les liens macOS.
- Code validé : `2338be17f22f541375b02141c27664e52f5f81e8`.
  [CI complète](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41277583138) :
  quatre configurations à 237 tests chacune, aucun ignoré ; trois builds réussis ;
  trois ZIP et trois SHA-256 téléchargés et vérifiés.
- `main` local a été avancé sans réécriture d’historique vers ce code validé ;
  cette documentation accompagne l’intégration distante autorisée.
- Voir [le rapport CI](VALIDATION-CI-v0.3.0.md) pour les empreintes, les contrôles
  réellement exécutés et les limites. Les données et les 48 profils Orca sont
  inchangés par cette passe. Pas de nouveau tag ou release ; recette physique
  NFC et acceptation visuelle humaine encore distinctes de la CI.
- Incident d’authentification : GitHub acceptait la clé publique SSH, mais
  l’agent 1Password échouait pendant la signature avec « communication with
  agent failed ». Les pushes autorisés ont abouti avec l’authentification GitHub
  CLI disponible, sans modification de `~/.ssh/config` ni export de clé privée.


## 10. Complément — cohérence locale/GitHub et publication stable v0.3.0

L’utilisateur a signalé à juste titre que les artefacts Actions ne mettaient pas
à jour la page Releases, puis a explicitement choisi « Publier v0.3.0 stable ».

- Avant cette préparation, les 348 fichiers suivis, dont 40 Markdown, ont été
  comparés aux objets GitHub : aucun écart de contenu, aucun fichier manquant ou
  supplémentaire ; `main` local et distant étaient sur `7d901db`. Les dossiers
  ignorés de builds et caches sont conservés localement et ne sont pas publiés.
- La release publique était encore v0.2.2. Le workflow ne publie que les tags
  `v*` : un push sur `main` seul avait donc laissé les téléchargements inchangés.
- Le README, le changelog, la roadmap et l’index documentaire sont actualisés pour
  v0.3.0. Le journal historique reste intact dans son contenu ; son exemple de
  lien NOTICE de Zenith est présenté comme code pour ne pas produire un lien
  relatif cassé dans ce document SpoolScribe.
- Le rapport CI ajoute les résultats réellement obtenus sur `main`, distincts des
  premières validations sur la branche. Les notes historiques ne sont pas
  réécrites comme si les contrôles ultérieurs avaient déjà eu lieu.
- La publication passe par le tag annoté `v0.3.0` et le workflow complet : quatre
  configurations de tests, trois builds, vérification des six fichiers, mise en
  ligne depuis un brouillon uniquement après contrôle des empreintes.
- La recette physique NFC et l’acceptation visuelle humaine restent non exécutées
  dans cette procédure automatique. Aucune donnée de catalogue, aucun profil
  Orca, aucune préférence utilisateur ni infrastructure n’est modifié.
