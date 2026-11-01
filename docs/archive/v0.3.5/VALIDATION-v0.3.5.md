> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Validation locale — SpoolScribe v0.3.5

Date : 1 novembre 2026. Version préparée, non publiée.
La campagne initiale ci-dessous est complétée par la passe langue/redémarrage en fin de document, qui décrit le dernier artefact.
Branche : `feature/v0.3.5-languages-facets`, créée sur `main` à
`8a5375ad34a36fe4cde2eb7b5a812c9d71506ede`. Références distantes actualisées
par SSH avant modification : aucune divergence. À la fin de la campagne locale : changements encore non committés ; voir la préparation Git ci-dessous.

## Livraison

- Logo animé rétabli dans le README : GIF local de 75 images / 3 secondes,
  exporté du SVG d’origine par `.github/scripts/render_readme_logo.py`.
- Interface anglais / français / espagnol / chinois simplifié. Détection des
  langues préférées du système via Qt, repli anglais, choix persistant dans
  Paramètres → Interface (appliqué au prochain lancement). Réglage exportable.
- 485 messages traduits, variables nommées contrôlées. Les noms commerciaux,
  identités fabricant/matière, favoris et JSON OpenSpool ne sont pas traduits.
  Les diagnostics techniques externes restent dans leur langue d’origine.
- Croix de recherche centrée, zone de clic 24 × 24, icône transparente suivant
  le thème et retour du focus au champ après effacement.
- « Actualiser le catalogue » remplace « Synchroniser », à droite de la recherche :
  action globale distincte de la mise à jour de l’application, accessible dans les réglages.
- Fabricants et matières se limitent réciproquement aux choix disponibles. Leurs
  compteurs respectent l’autre facette ainsi que recherche, état et filtres favoris.
  Une option « Tous » reste accessible ; une intersection vide reste réinitialisable.
  Les recherches internes aux listes masquent les libellés, sans effacer les favoris.
- Même grille pour Effacer et les deux boutons favoris. En-têtes dimensionnés
  pour la traduction après restauration d’une disposition d’une autre langue.

## Contrôles réellement exécutés

| Contrôle | Résultat |
| --- | --- |
| Python 3.10.20 / PySide6 6.11.3 / macOS arm64 | 250 tests, 250 réussis, aucune exclusion |
| Python 3.12.13 / PySide6 6.11.3 / macOS arm64 | 250 tests, 250 réussis, aucune exclusion |
| Contrat des 1 008 exports historiques | Test `test_legacy_catalogue_and_1008_compact_exports_are_identical` réussi dans les deux suites |
| Langues et données | Repli système, préférence enregistrée, import invalide atomique, variables des 485 messages et 4 langues contrôlés ; JSON exporté identique dans les 4 langues |
| Filtres et favoris | Intersection dans les deux sens, compteurs, restauration des filtres, remise à zéro, conservation des favoris vérifiés sur données synthétiques |
| Ressources existantes | Comparaison octet par octet des 222 fichiers suivis de `data/` et `orca_profiles/` avec HEAD : identiques, dont 48 profils Orca |
| Interface Qt offscreen | Fenêtre, réglages, sources, rapport, imprimantes et À propos rendus ; contrôle des libellés traduits et du bouton d’effacement |
| PyInstaller 6.22.3 macOS | Build 0.3.5 réussi hors du dossier synchronisé |
| Exécutable compilé | Probe catalogue hors ligne réussi : démarrage sans catalogue embarqué, fenêtre dans les 4 langues, 147 logos approuvés, 4 visuels imprimantes, export NTAG215/216 |
| TLS de l’exécutable | Probe hors ligne réussi : 128 racines système / 118 embarquées, vérification des certificats et noms d’hôtes active |
| Signature macOS | `codesign --verify --deep --strict` réussi sur le build final et après extraction du ZIP |
| Archive macOS | ZIP contrôlé : une seule racine `SpoolScribe.app`, exécutable Mach-O, versions 0.3.5, liens et permissions conservés, CRC valide ; 587 entrées |
| Métadonnées | `core.APP_VERSION`, `pyproject.toml` et Info.plist = 0.3.5 ; syntaxe Python 3.10 valide |
| Git | `git diff --check` réussi ; workflows existants inchangés |

La campagne utilise des dossiers temporaires et bloque les connexions dans les
tests. Aucun catalogue utilisateur, fichier de réglages personnel ou application
installée dans `/Applications` n’a été remplacé.

## Anomalies rencontrées et résolues

- Les deux premiers contrôles de réglages signalaient la nouvelle position des
  onglets. L’onglet Interface est finalement ajouté après Catalogue / Bobines /
  Export ; les positions existantes sont préservées et le test vérifie les quatre.
- Le premier build dans le checkout synchronisé portait `com.apple.FinderInfo`
  sur 15 frameworks : refus de la vérification stricte de signature. Build
  régénéré dans un dossier local hors synchronisation : vérification réussie.
  Le mécanisme exact d’ajout de ces métadonnées n’a pas été isolé.
- Un premier ZIP exploratoire avec `--sequesterRsrc` contenait `__MACOSX` et a
  été refusé par le contrôleur. Le ZIP final utilise les options du workflow
  existant : `--norsrc --noextattr --keepParent` ; contrôle et signature après
  extraction réussis. Ces essais initiaux ne sont pas des artefacts à distribuer.

## Artefact macOS de test final

Construit hors du checkout synchronisé, dans le dossier local de builds ArN-LaB.
`SpoolScribe-macos.zip` et son fichier `.zip.sha256` sont prêts pour essai local.
Empreinte du ZIP :

```text
b020387d4c5b3ec64e54c135112cf7be0eb772497858c3edb5f181eeef048bcc
```

## Limites et état distant

- Windows et Linux : suites et builds non exécutés pour cette passe. La matrice
  existante prévoit Linux 3.10/3.12, Windows 3.12, macOS 3.12 puis les trois builds.
  La probe intégrée à ces builds exige maintenant les quatre langues.
- Pas de CI distante déclenchée, aucun commit, push, tag ou release v0.3.5.
  La version publique demeure v0.3.0 ; les téléchargements publics ne sont pas
  présentés comme mis à jour par cette livraison locale.
- Pas de recette humaine complète de l’interface native ni de validation par
  des locuteurs natifs des traductions ; les captures sont des rendus Qt offscreen.
- Pas d’écriture/lecture NFC réelle ni de test matériel Snapmaker U1, SpoolFlux,
  Bambu, Prusa, NAS ou Spoolman. Les formats et firmwares pris en charge restent inchangés.
- Le choix manuel de langue demande un redémarrage de l’application ; aucune
  traduction en ligne et aucune dépendance supplémentaire.


## Complément — langue système et proposition de redémarrage

La détection initiale utilisait seulement `QLocale.system().uiLanguages()`.
Le diagnostic réel de cette passe donne `['C']` côté Qt, contre `['fr-FR']`
pour les langues préférées de macOS : l’ancien repli anglais explique l’écart
reproduit dans cet environnement. L’API native est maintenant prioritaire sur
macOS, avec repli Qt si elle est indisponible ; Windows/Linux conservent Qt.
Une préférence manuelle enregistrée garde la priorité. Les langues du bundle
macOS sont déclarées (`en`, `fr`, `es`, `zh-Hans`), avec repli `en`.

Après enregistrement ou import d’un choix différent, une boîte propose
« Redémarrer maintenant » / « Plus tard ». La préférence est sauvegardée avant
la proposition. Une actualisation en cours désactive le redémarrage immédiat,
sans l’annuler. Le choix automatique affiche sa langue effective.

`app_lifecycle.py` relance le même exécutable (ou le même interpréteur et le
script source absolu). Le verrou de l’ancienne instance est libéré avant le
lancement. `PYINSTALLER_RESET_ENVIRONMENT=1` isole le nouveau processus gelé.
Un échec de création du processus réaffiche l’ancienne fenêtre seulement si
son verrou est repris ; le choix enregistré reste conservé.

### Vérification finale de cette passe

- Python 3.10.20 : **267/267 tests réussis**, aucune exclusion.
- Python 3.12.13 : **267/267 tests réussis**, aucune exclusion.
- 17 tests supplémentaires couvrent langues macOS/Qt divergentes, repli,
  préférence manuelle, sauvegarde avant proposition, annulation, choix inchangé,
  échec de sauvegarde, import, « Plus tard », actualisation active, ordre du
  déverrouillage et échecs de lancement/verrou simulés.
- Une relance réelle en deux processus du parcours Qt source est exécutée
  dans un dossier temporaire : nouveau PID, verrou appartenant au nouveau PID,
  interface espagnole, préférence sauvegardée et favoris conservés. Un lanceur
  de fixture pilote les dialogues ; aucune instance utilisateur n’est fermée.
- Build macOS PyInstaller régénéré hors synchronisation. La probe de l’exécutable
  compilé réussit : **langue automatique `fr`**, quatre langues manuelles,
  ressources et exports NTAG215/216 hors ligne. La probe TLS reste réussie.
- Signature stricte réussie sur le bundle final et après extraction du ZIP ;
  archive 0.3.5 vérifiée (587 entrées, seule racine `SpoolScribe.app`).
- Les 1 008 exports historiques restent vérifiés dans les deux suites ; aucun
  changement du catalogue ni des 48 profils Orca. `git diff --check` réussi.
- Rendus Qt offscreen examinés pour les paramètres et la proposition de relance.
  Cela ne constitue pas une recette humaine de l’application macOS installée.

Dernier ZIP local : dossier de builds `v0.3.5-langue-redemarrage` (remplace
l’artefact de test indiqué plus haut). SHA-256 :

```text
c4ac24e197d80f626d6d83ac7b7d1b1863cd7c193f39f02f60e774a96fb1eb86
```

Pas de relance réelle d’un binaire Windows/Linux mesurée : préparation de la
commande gelée vérifiée avec des doubles de test, builds et recette distante
restant à effectuer. Le redémarrage réel automatisé porte sur le parcours source ;
le binaire macOS a été démarré et rendu dans sa probe, sans recette humaine.
Aucune installation dans `/Applications`, aucun changement des préférences de
langue macOS, aucune publication, aucun commit, push ou tag.

Références techniques consultées :
[Apple — langues préférées](https://developer.apple.com/documentation/corefoundation/cflocalecopypreferredlanguages%28%29),
[Apple — langues gérées par l’application](https://developer.apple.com/documentation/bundleresources/information-property-list/cfbundlelocalizations),
[PyInstaller — relance indépendante](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#using-sys-executable-to-spawn-subprocesses-that-outlive-the-application-process-implementing-application-restart).


## Préparation Git autorisée

L’utilisateur a accepté la livraison et autorisé le commit et le push sur la
branche de travail `feature/v0.3.5-languages-facets`. Cette étape ne crée pas de
release, de tag ni de fusion vers `main`.

Contrôles avant commit : 267 tests Python 3.12 relancés et réussis ;
`git diff --check` propre. Sélection explicite de 27 fichiers de code, tests,
traductions, documentation et logo animé. Aucun fichier `data/`, `orca_profiles/`,
`build/`, `dist/`, réglage utilisateur ni changement de workflow inclus.
Recherche ciblée de clés privées, jetons et chemins personnels : aucun élément
détecté dans cette sélection. Les SHA du commit et le statut du push sont vérifiés
et communiqués au terme de l’opération Git, indépendamment des résultats de cette
campagne locale.


## Correctif CI Windows après le premier push

L’exécution [41293604627](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41293604627)
a réussi sur Linux 3.10/3.12 et macOS 3.12, mais a échoué sur Windows 3.12 :
`test_catalogues_are_complete_with_identical_named_placeholders` lisait les sources
UTF-8 avec l’encodage système cp1252. Erreur observée : `UnicodeDecodeError`,
caractère `0x90`, dans `Path.read_text()` de `tests/test_v035.py`.

Les lectures/écritures de texte des deux nouveaux fichiers de tests déclarent
maintenant UTF-8, y compris le lanceur de fixture de redémarrage. Aucun test
supprimé ou désactivé ; aucun changement de code applicatif ni de données.
Le défaut cp1252 a été reproduit localement et l’analyse AST avec lecture UTF-8
réussit. Suite locale Python 3.12 après correction : 267/267 tests réussis.
Les résultats distants du correctif seront consignés dans le rapport CI séparé.


## Contrôle complémentaire des traductions embarquées

La première validation complète du correctif (`41294045043`, commit `22ddaf1`)
a réussi : 267 tests sur chacune des quatre configurations, trois builds exécutés
et réussis, six fichiers d’artefacts présents. Le contrôle complémentaire des
archives téléchargées a trouvé sous Windows 2 482 fins de ligne CRLF dans
`translations/messages.json`, contre LF dans Git. Le JSON décodé était identique.
Les règles existantes `-text` couvraient `data/`, `scripts/` et `orca_profiles/`,
mais pas le nouveau dossier de traductions.

Le dossier `translations/` reçoit la même règle `-text` ; le workflow inclut
maintenant ce dossier dans la comparaison octet par octet des ressources
embarquées avec Git. Ce renforcement doit être vérifié par de nouveaux builds
sur les trois plateformes avant de retenir les archives définitives.
