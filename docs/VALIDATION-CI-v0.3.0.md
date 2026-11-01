# Validation CI — SpoolScribe v0.3.0

Validation automatique, intégration sur `main` et préparation de la publication stable, le 1er novembre 2026.

Les deux exécutions documentées ci-dessous sont attachées à leurs commits. Les
SHA-256 des archives de validation ne sont pas ceux d’une reconstruction de release ;
les fichiers `.zip.sha256` joints à la release sont la référence de téléchargement.

- Code validé : `2338be17f22f541375b02141c27664e52f5f81e8` ; branche `feature/universal-catalogue`.
- [Exécution complète : 41277583138](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41277583138).
- `origin/main` avant intégration : `e82d43fc525221955eaab6759224af2228443072`, ancêtre du code validé. Intégration locale par avance rapide, sans écrasement des ajouts parallèles de soutien et de licence.
- Les changements qui accompagnent ce rapport sont exclusivement documentaires. Les exécutions complémentaires sur `main` restent consultables dans [Actions](https://github.com/ArN-LaB/Spoolscribe-/actions/workflows/build.yml?query=branch%3Amain).

## Tests réellement exécutés

| Configuration distante | Résultat | Durée de la suite |
|---|---|---|
| Linux / Python 3.10 | 237 réussis, aucun ignoré | 36,794 s |
| Linux / Python 3.12 | 237 réussis, aucun ignoré | 24,358 s |
| Windows / Python 3.12 | 237 réussis, aucun ignoré | 33,107 s |
| macOS / Python 3.12 | 237 réussis, aucun ignoré | 33,169 s |

Localement, macOS ARM64 : 237 réussis sous Python 3.10.20 (18,345 s) et 3.12.13 (16,376 s). La suite inclut le contrat des 1 008 exports OpenSpool historiques, les copies personnelles et les protections de stockage. Aucun accès réseau réel dans les tests métier/GUI ni dans les sondes des exécutables.

## Exécutables et archives

Les trois builds ont réellement été exécutés après les quatre jobs de tests. Chaque exécutable a réussi les sondes TLS et catalogue : fenêtre principale affichée hors écran, logos et photos décodés, exports synthétiques NTAG215/216 relus, première installation sans catalogue embarqué. Les 193 ressources embarquées ont été comparées octet par octet aux objets Git.

Les six fichiers ont été téléchargés et vérifiés localement : trois ZIP et leurs trois `.zip.sha256`. CRC, racine unique, format natif et permissions exécutables ont été contrôlés. Windows : un `.exe` x64 ; Linux : un ELF x64 ; macOS : un `.app` ARM64 seul, avec ses liens symboliques.

| Archive | Taille (octets) | SHA-256 de cette exécution |
|---|---:|---|
| `SpoolScribe-linux.zip` | 88,747,851 | `148cca729399dff22b9a0961d95351db68a0af449cb7c43f0129b960f5ef9c2e` |
| `SpoolScribe-macos.zip` | 42,618,562 | `d6ea877b79899873544592af1304790c8a029ed5256d03e87c07e257d068cb6e` |
| `SpoolScribe-windows.zip` | 54,862,291 | `fab4c372313ec6253ef2cb6788b975d77bc942fd75e030e35c60955876365da0` |

Les archives ci-dessus appartiennent au commit de code validé ; une reconstruction ultérieure peut avoir des empreintes différentes. PySide6/Shiboken6 6.11.3, PyInstaller 6.22.3 et certifi 2026.10.23 restent contraints. Pillow est désormais installé dans les quatre jobs de tests pour mesurer la transparence des images.

## Anomalies corrigées

- Verrou Windows abandonné : interrogation non destructive du processus via l’API système. Un processus vivant ou inaccessible reste protégé, même après quinze minutes. Les tests incluent un vrai processus enfant vivant puis arrêté, et l’échec a été reproduit avant correction pour le verrou actif ancien. [API Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-openprocess).
- Initialisation Qt hors écran : le backend Windows ne trouvait aucune police ; la famille résolue était vide et « Fabricants » occupait 130 px à une taille déclarée de 13 px. Après initialisation des polices système avant `QApplication`, Segoe UI est résolue et le même texte occupe 59 px. Les boutons utilisent une largeur mesurée et une typographie compacte cohérente.
- Assertions portables : les chemins Windows courts/longs sont comparés après résolution ; le test de repli des lignes d’imprimantes vérifie la hauteur calculée et la stabilité des redimensionnements, avec les métriques de chaque plateforme.
- Vérificateur CI : ajout du dépôt au chemin d’import des scripts Python temporaires ; lecture des ressources macOS dans `Contents/Resources` plutôt que parcours des liens de `Contents/Frameworks`.
- Les premiers échecs restent visibles dans Actions. Aucun test n’a été désactivé ou transformé en succès artificiel. Le job de publication est ignoré sur une référence de branche et ne compte pas comme une validation.

## Conservation et limites

- Les 222 fichiers `data/` et `orca_profiles/` présents au début de cette passe, dont les 48 profils Orca, sont identiques. Aucun catalogue utilisateur n’a été utilisé dans les builds ou commité.
- Le journal parallèle, le financement, la licence MIT standard et `NOTICE` sont conservés ; l’ajout au journal est appenditif.
- `git diff --check` sans erreur ; versions `core.py`, `pyproject.toml` et changelog cohérentes avec 0.3.0, alors encore indiquée Unreleased.
- Le verrou coopératif et les vérifications de révision ne peuvent exclure absolument un éditeur externe qui ignore le verrou.
- Recette visuelle humaine sur les trois OS, tests réseau dans les applications téléchargées, écriture/lecture physique NTAG215/216 et imprimante réelle : non exécutés ici. Aucun résultat matériel n’est revendiqué.
- macOS reste signé ad hoc, sans notarisation Developer ID ; Windows sans certificat de signature commerciale. Voir les instructions de premier lancement du README.
- Aucun tag ni nouvelle GitHub Release n’avait été créé pendant cette première intégration. La publication stable a ensuite été explicitement autorisée par l’utilisateur.


## Validation complémentaire sur `main`

- Commit : `7d901db2c585fabbe7819015923976f67037596b`.
- [Exécution complète sur main : 41278081495](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41278081495).
- Linux / Python 3.10 : 237 réussis en 35,491 s.
- Linux / Python 3.12 : 237 réussis en 38,398 s.
- Windows / Python 3.12 : 237 réussis en 50,497 s.
- macOS / Python 3.12 : 237 réussis en 20,208 s.
- Aucun test ignoré ; trois builds réussis. Les trois fenêtres ont été rendues hors
  écran par les exécutables natifs, les exports NTAG215/216 vérifiés et les
  193 ressources comparées à Git. Six fichiers téléchargés, CRC et SHA-256 vérifiés.
- Le `.app` extrait du ZIP macOS a également passé `codesign --verify --deep
  --strict` puis les sondes TLS et catalogue/GUI avec des dossiers de données vierges.

| Archive de validation sur main | SHA-256 |
|---|---|
| `SpoolScribe-linux.zip` | `cd3359bbfe9a356d89a58445ac4895a52d09739cfa081d6143b0b243c9921fd0` |
| `SpoolScribe-macos.zip` | `3f61e6eef78a49ecd21358404afe84085752511db4db1a658a1b0f1287de09d6` |
| `SpoolScribe-windows.zip` | `6a5c5c91ac391741442a0ae389fec9ad717627803f45a0a9489579308dbb5d2b` |

## Audit de synchronisation et préparation de release

À l’ouverture de cette passe, `main` local et GitHub avaient le même commit et le
même arbre Git (`1fe54a09d199d4088f070a9e47ec4cb92931f7b4`). Les 348 fichiers
suivis, dont les 40 Markdown, avaient un contenu identique. La release était
encore v0.2.2 ; les builds Actions ne constituaient pas une publication.

Les 237 tests ont été relancés localement : Python 3.10 en 17,570 s, Python 3.12
en 15,581 s, tous réussis. Cette passe ne change que la documentation et la date
de publication du changelog. Le code, les dépendances, les workflows, les données
et les 48 profils Orca restent identiques au commit `7d901db`. Les rapports datés
sont conservés ; un index distingue les références actuelles de ces preuves historiques.

L’utilisateur a ensuite autorisé **v0.3.0 stable**. Le tag annoté déclenche une
nouvelle validation complète avant publication ; la release, ses six fichiers
et l’identité locale/GitHub doivent être vérifiés à la fin. La recette physique
NFC et l’acceptation visuelle humaine restent ouvertes dans la roadmap.
