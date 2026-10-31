# SpoolScribe v0.2.2 — validation locale

Date : 31 octobre 2026 (Asia/Shanghai). Base de travail : main, HEAD
`5197234c68885618492039061d4228f6848d024c`. Modifications locales, version non publiée.

## Périmètre implémenté

- Export NFC compact, mêmes champs que l'ancien JSON ; archive lisible séparée.
- Validation OpenSpool 1.0, nombres finis, plages ordonnées, HEX explicite,
  transparence/multicolore conservés quand fournis, confinement des noms de fichiers.
- Valeurs physiques locales prioritaires ; priorité Orca disponible sur choix
  explicite dans les paramètres GUI ou avec `--orca-overrides` en CLI.
- Écritures atomiques, sauvegardes .bak et .pre-update.bak, restauration explicite,
  refus d'écrasement d'un fichier corrompu, d'une sauvegarde obsolète ou d'une
  suppression de données locales. Les nouveaux SKU sans produit sont refusés.
- Fusion additive des nouveaux catalogues intégrés ; conflits consignés et valeurs
  locales conservées, y compris les couleurs nulles intentionnelles.
- Statuts de mise à jour explicites. Seul le succès complet avance `_last_updated`.
  Le retour des workers utilise aussi un fichier privé temporaire, afin de ne pas
  dépendre de la console d'un exécutable GUI Windows.
- Consentement persistant, révocable ; aucune nouvelle source réseau automatique.
- Tests avant packaging et sur PR/push ; trois builds conservés pour tags/manuels.

Les 13 scripts d'acquisition utilisent le même module de stockage. Le changement
est plus large qu'une simple modification de `core.save_db` parce qu'ils écrivaient
auparavant directement dans le fichier final.

## Catalogue, aucune correction inventée

Le fichier `data/polymaker_db.json` reste identique à celui audité :

```
SHA256 ddf48fbbaf9addf3c8751e6d69ea2daae0d061d8bb2a595f4b62d1fcb164cc35
```

- 1 084 SKU, 91 produits, 48 profils Orca.
- 1 008 références génèrent un export valide avec leur couleur connue.
- 74 références résolubles exigent un choix de couleur explicite.
- FM01001 et FM01002 restent non exportables : produit Fiberon PPS-CF10 absent.
- Total des couleurs manquantes du catalogue : 76, en comptant ces deux orphelins.

Les 1 008 exports valides occupent 389–802 octets JSON UTF-8 et 416–829 octets
avec un enregistrement MIME NDEF `application/json`, TLV Type 2 et terminateur.
Aucun ne dépasse la zone NTAG216 standard de 872 octets selon cette hypothèse.
Les enregistrements supplémentaires éventuellement ajoutés par un programmateur
ne sont pas inclus dans cette estimation.

Les fixtures matérielles conservent les observations PETG Black / 070908,
PLA ECO Yellow / A78403 et PLA Silk Green / 91C500. Les deux dernières
correspondances catalogue restent explicitement incertaines ; aucun SKU,
UID physique, température ou densité n'a été inventé pour les identifier.

## Vérifications reproductibles

```sh
python -B -m unittest discover -s tests -t . -v
```

Les tests bloquent les connexions réseau et utilisent des bases temporaires.
Un vrai worker hors ligne est exécuté sur une fixture ; les sources réseau et
les autres résultats de pipeline sont simulés. Aucun serveur Spoolman personnel,
imprimante, NAS ni étiquette physique n'est contacté ou modifié.

| Environnement local macOS ARM64 | Résultat |
|---|---|
| Python 3.10.20 + PySide6 6.12.0 | 59 tests réussis, aucune exclusion |
| Python 3.12.13 + PySide6 6.12.0 | 59 tests réussis, aucune exclusion |
| Python 3.14.10 sans PySide6 | 55 tests réussis ; 4 tests GUI explicitement exclus |
| YAML, dépendance du build aux tests, syntaxe Python 3.10 | Contrôlés localement |
| `git diff --check` | Sans erreur |

Couverture : tous les SKU, trois marques, schéma/types/valeurs physiques,
valeurs nulles/non finies, HEX absent/invalide, transparence/multicolore,
UTF-8 et changements d'en-têtes NDEF/TLV, capacité, aperçu/export identiques,
archives, 48 profils Orca, conflits et refus de pertes locales, interruption
avant publication, écriture obsolète, sauvegarde/restauration, fusion de bundle,
consentement, échecs/indisponibilités/timeouts de pipeline et workers sans console.
Les tests GUI utilisent Qt offscreen : ce sont des contrôles fonctionnels, pas
une recette visuelle humaine.

## Packaging et dépendances

`requirements-build.txt` est un instantané universel résolu pour le build Python
3.12, avec marqueurs Windows/macOS. Il ne remplace pas la déclaration du support
runtime Python 3.10+. Les dépendances installées de l'environnement 3.12 ont été
vérifiées par `uv pip check`.

Build local dans un répertoire temporaire :

```sh
pyinstaller spoolscribe.spec --noconfirm --distpath /tmp/spoolscribe-qa/dist --workpath /tmp/spoolscribe-qa/build
```

Le build utilise PyInstaller 6.22.3 et PySide6 6.12.0 ; le bundle macOS déclare
la version applicative 0.2.2. Les essais
du binaire isolent les données avec `SPOOLSCRIBE_DATA_HOME` et les préférences
avec `SPOOLSCRIBE_CONFIG_PATH` ; ils ne réutilisent pas le dossier utilisateur réel.
Résultats finaux sur le binaire reconstruit :

- Build `.app` macOS ARM64 réussi.
- Import des 13 scripts embarqués réussi, sans exécuter d'acquisition réseau.
- Deux exécutions du worker `seed_prusament.py` : code 0, résultat privé
  `unchanged`, correction HEX locale conservée.
- Démarrage offscreen : processus actif, données initialisées en environ 15 s,
  fusion du bundle effectuée, correction locale conservée et conflit consigné.
- Le binaire est arrêté après cette sonde. Aucun contrôle visuel humain n'est déduit
  de ce simple test de démarrage.

Les artefacts et journaux de cette session sont isolés dans
`/private/tmp/spoolscribe-v022-qa-s3hpxexb/` (temporaires, non publiés).

Avertissement observé : PyInstaller annonce la suppression future du mode
onefile combiné au bundle .app dans sa version 7. Le build reste en version
6.22.3 ; aucune migration de packaging n'est faite dans cette stabilisation.
Qt signale aussi un remplacement de police lors des tests offscreen, sans échec.

## Limites et validation humaine restante

- GitHub Actions n'a pas été lancé : aucun push, commit, tag ou release créé.
- Binaires Windows/Linux et leur exécution : NON MESURÉS localement ; la matrice
  CI est conservée mais ne constitue pas une preuve de réussite tant qu'elle
  n'a pas été exécutée.
- Parcours visuel humain et comportement sur les machines cibles : NON MESURÉS.
- SpoolFlux iPhone, écriture/read-back des NTAG216 et lecture U1 : NON MESURÉS
  dans cette implémentation. Le calcul de capacité ne remplace pas ce contrôle.
- Mise à jour de vraies sources réseau : NON EXÉCUTÉE ; les cas de réussite et
  d'échec sont testés avec des fixtures, pour préserver les données personnelles.

Recette physique à effectuer avant publication : exporter PETG Black et les deux
références PLA après vérification de leur identité, programmer en MIME
application/json avec SpoolFlux, relire le contenu et contrôler matériau/couleur
sur la U1. Le CC incorrect et le NDEF vide restent des diagnostics de puce ou de
programmation externe ; aucun défaut de ce type n'est attribué à SpoolScribe.

Spoolman, associations UID, firmware Paxx12 et NAS restent hors développement.
Les PR Paxx12 #767/#799 ne sont pas intégrées ici. La PR Dependabot #3 pour les
nouvelles majeures des actions reste à examiner séparément.
