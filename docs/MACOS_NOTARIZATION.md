# Signer et notariser SpoolScribe pour macOS (procédure locale)

[Développement](DEVELOPMENT.md) · [Politique de versions](RELEASE_POLICY.md) · [Installation personnelle](LOCAL_MACOS_INSTALL.md)

Cette procédure produit la distribution macOS **hors Mac App Store** : signature
Developer ID, Hardened Runtime, notarisation Apple, ticket staplé, puis
`SpoolScribe-macos.zip`. Elle est **locale d'abord** et pilotée par
[`packaging/macos_notarize.py`](../packaging/macos_notarize.py) (bibliothèque standard).

État des versions : v0.8.0 reste historiquement signée ad hoc et **non notarisée**.
La release v0.8.1 utilise un nouveau build local Developer ID, notarisé et staplé ;
les résultats exacts sont consignés dans la [validation v0.8.1](validation/v0.8.1.md).
Le [workflow](../.github/workflows/build.yml) ne signe ni ne notarise. Cette procédure ne publie
rien, ne crée ni tag ni release et ne remplace aucun fichier existant. Le pilote couvre **arm64
seulement** ; Intel/universal2 et les versions de macOS en deçà du minOS relevé ne sont pas promis.

## Prérequis à réunir par le titulaire du compte

1. Xcode, `notarytool`, `stapler` et un interpréteur **Python 3.12** arm64 explicite.
2. Une identité **Developer ID Application** valide, avec sa clé dans le trousseau.
   Apple Development, Apple Distribution, Developer ID Installer et la signature ad hoc sont refusés.
   Le sujet d'un certificat de compte individuel peut afficher le **nom légal** du titulaire, lisible
   dans tout binaire distribué : relire ce sujet en privé et accepter cette conséquence avant diffusion.
3. Un profil `notarytool` créé par le titulaire, par saisie interactive (aucun mot de passe en option) :

   ```sh
   xcrun notarytool store-credentials "spoolscribe-notary-local"
   ```

La procédure ne crée aucun certificat, n'exporte aucune clé, ne modifie ni trousseau ni compte
Apple. Elle reçoit seulement l'empreinte SHA-1 de l'identité choisie et le **nom** du profil.

## Étapes

Lancer l'outil depuis le checkout relu ; `WS` est un dossier **neuf**, absolu, hors du checkout et
hors stockage synchronisé (iCloud, Proton Drive, File Provider). Il est créé en mode 0700 avec un
marqueur ; les étapes suivantes refusent tout autre dossier, lien ou copie déplacée.

```sh
PY312=/chemin/python3.12
WS=/chemin/prive/spoolscribe-notarisation-AAAAMMJJ
python3 -B packaging/macos_notarize.py preflight --python "$PY312" [--identity SHA1] [--profile NOM]
python3 -B packaging/macos_notarize.py prepare --workspace "$WS" --commit SHA_COMPLET --python "$PY312"
python3 -B packaging/macos_notarize.py build    --workspace "$WS"
python3 -B packaging/macos_notarize.py inspect  --workspace "$WS"
python3 -B packaging/macos_notarize.py probes   --workspace "$WS"
python3 -B packaging/macos_notarize.py sanitize --workspace "$WS"
# Étapes réseau/Apple : chacune exige l'accord explicite du pilote et sa propre confirmation.
python3 -B packaging/macos_notarize.py sign     --workspace "$WS" --identity SHA1 --confirm-signing
python3 -B packaging/macos_notarize.py probes   --workspace "$WS"
python3 -B packaging/macos_notarize.py notarize --workspace "$WS" --profile NOM --confirm-submission
python3 -B packaging/macos_notarize.py staple   --workspace "$WS" --confirm-stapling
python3 -B packaging/macos_notarize.py package  --workspace "$WS"
python3 -B packaging/macos_notarize.py assess   --workspace "$WS" --confirm-assessment
python3 -B packaging/macos_notarize.py status   --workspace "$WS"
```

Codes de sortie : 0 étape réussie ; 1 bloqué ; 2 usage ; 3 **READY TO NOTARIZE — PRÉREQUIS
HUMAINS MANQUANTS** (outillage présent, identité ou profil absent) ; 4 **PENDING**.

| Étape | Ce qu'elle fait | Ce qu'elle ne fait jamais |
| --- | --- | --- |
| `preflight` | Outils, interpréteur, nombre d'identités par type | Build, signature, appel Apple, profil deviné |
| `prepare` | `git archive` du commit approuvé, contrôle blob par blob, venv privée au snapshot `requirements-build.txt` | Déplacer une ref, inclure des changements non commités |
| `build` | PyInstaller avec la spec inchangée, cache PyInstaller privé | Réutiliser le `dist/` du checkout |
| `inspect` | Mach-O par en-tête, `lipo`, `otool` (minOS/SDK, rpaths, dépendances), liens, Info.plist, ressources, plan de signature | Modifier le candidat |
| `probes` | Oracles QA installés après PyInstaller, quatre sondes gelées hors ligne, candidat inchangé | Lancer sur un candidat staplé |
| `sanitize` | Retire `com.apple.FinderInfo` / `com.apple.ResourceFork` de la copie neuve | Toucher le checkout ou la quarantaine |
| `sign` | Code imbriqué puis bundles, de l'intérieur vers l'extérieur, `--options runtime --timestamp` | `--deep` pour signer, ad hoc, entitlements par défaut |
| `notarize` | ZIP de soumission privé, envoi, attente bornée, `info`, lecture du journal | Mot de passe en argument, renvoi automatique |
| `staple` | `stapler staple` + `validate` + `codesign --verify --deep --strict` | Stapler un ZIP, re-signer après stapling |
| `package` | `ditto -c -k --norsrc --noextattr --keepParent`, `.sha256` après création, extraction neuve vérifiée | Changer le workflow si le ticket est perdu |
| `assess` | `spctl --assess --type execute -vvv` sur une nouvelle extraction | Prétendre mesurer l'essai utilisateur |

## Garde-fous de signature et de notarisation

- Inventaire par format Mach-O, pas par extension. Les frameworks Qt sont signés par
  version (`Versions/A`, etc.) ; les liens (`Versions/Current`, alias racine) sont conservés et
  jamais signés. Un lien cassé, absolu, en boucle ou sortant du bundle bloque la suite, comme une
  dépendance absolue hors système.
- Les frameworks QtQml/QtQuick embarqués par le plugin de clavier virtuel ne sont pas retirés.
  Leur présence ne justifie **aucune** exception JIT. Aucun entitlement par défaut ; une exception
  (`allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation`) exige un échec
  reproduit, documenté et validé, puis s'applique à l'app seulement. `get-task-allow` est interdit.
- Vérification de chaque objet : type Developer ID Application, chaîne Developer ID, équipe unique,
  drapeau `runtime`, `Timestamp` sécurisé (un `Signed Time` seul est refusé), entitlements embarqués.
  Chaque lecture doit avoir réussi avant d'être interprétée : une extraction d'entitlements en échec,
  expirée ou partielle bloque, elle ne vaut jamais « aucun entitlement ». Une exception approuvée vaut
  pour l'app et son exécutable principal, aucun autre objet. Les sorties détaillées restent privées.
- Statut Apple : seul `Accepted` avec un journal relu (identifiant, empreinte du ZIP soumis,
  issues, couverture `ticketContents`) permet le stapling. Les types du journal sont validés avant
  toute normalisation : un champ absent ou `null` est admis, une valeur trompeuse (`{}`, `false`,
  `0`, `""`) est une erreur de schéma. `Invalid`, statut inconnu, JSON inattendu ou erreur
  d'authentification bloquent ; `--acknowledge-log-warnings` ne lève qu'un avertissement relu,
  jamais une erreur.
- Une attente interrompue ou expirée vaut **PENDING**. Reprendre avec l'identifiant conservé :

  ```sh
  python3 -B packaging/macos_notarize.py notary-status --workspace "$WS" --profile NOM \
      --confirm-apple-query [--wait-timeout 30m]
  ```

- Toute modification du candidat après signature invalide la suite : reconstruire dans un nouvel espace.

## Gatekeeper et essai utilisateur standard (manuel)

`spctl` accepté ne prouve pas le parcours réel. Sur un Mac ou un compte **standard** n'ayant jamais
approuvé SpoolScribe, avec Gatekeeper actif : télécharger le ZIP par un navigateur (quarantaine
effective), extraire, lancer depuis le Finder, noter les dialogues. Refaire un lancement hors ligne.
Avant tout lancement de test, isoler les données :

```sh
export SPOOLSCRIBE_DATA_HOME=/chemin/test/donnees
export SPOOLSCRIBE_CONFIG_PATH=/chemin/test/config.json
```

Sans cet environnement, consigner **NON MESURÉ**. Ne jamais retirer la quarantaine pour obtenir un PASS.

## Traces

`WS/logs/` et `WS/private/` (journaux de commandes, journal notarial, sujet de l'identité,
sorties `codesign -dvvv`, `spctl`) restent privés, hors dépôt, hors Pages et hors archive.
Les sorties partageables (terminal, `status`, `WS/summary.md`) ne montrent que des catégories
d'un vocabulaire fermé, des compteurs et l'emplacement privé du détail : jamais le texte d'un
diagnostic Apple, une identité, une équipe ou un chemin personnel. Une erreur interne inattendue
affiche seulement son type ; sa trace va dans `WS/private/`.

## Intégration CI future (non réalisée)

Après un pilote local validé, et par un mandat séparé : étape macOS de confiance avant le packaging
et son checksum, environnement GitHub protégé, aucun secret sur PR/fork, trousseau temporaire et
supprimé en fin de job, aucune clé dans le dépôt, les journaux ou les artefacts (base64 n'est pas
un chiffrement), permissions globales `contents: read` conservées. Un échec de signature ou de
notarisation devra empêcher toute release partielle. Une distribution notarisée utilisera une
nouvelle version ; ne jamais relancer un ancien tag pour remplacer ses fichiers.

Références Apple : [notarisation](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
[workflow personnalisé](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[problèmes courants](https://developer.apple.com/documentation/security/resolving-common-notarization-issues),
[TN2206](https://developer.apple.com/library/archive/technotes/tn2206/_index.html),
[QA1940](https://developer.apple.com/library/archive/qa/qa1940/_index.html).
