# Structure du dépôt — SpoolScribe

[Documentation](README.md) · [Ressources](../data/README.md) · [Fixtures](../tests/fixtures/README.md) · [Développement](DEVELOPMENT.md)

**Préversion actuelle v0.7.0 :** les encodeurs NFC et SSQR1 sont conservés.
`colour_measurements.py`, `colour_import.py`, `colour_targets.py`,
`measurement_store.py` et `ui_colour_measurements.py` ajoutent la saisie/import
et un registre de mesures distinct du catalogue.
[Validation actuelle](validation/v0.7.0.md) · [Captures et génération](images/README.md).
Les résultats de structure ci-dessous restent datés de v0.3.5 : ils ne sont pas
présentés comme les résultats de la version actuelle.

## Organisation actuelle

La racine conserve six fichiers visibles : README, changelog, licence,
attributions, pyproject et lanceur personnel macOS.

| Dossier | Rôle |
| --- | --- |
| `src/spoolscribe/` | Application, CLI, interface Qt et logique métier |
| `scripts/` | Stockage, adaptateurs, workers et alias de ressources |
| `packaging/` | Entrée PyInstaller et spec multiplateforme |
| `requirements/` | Dépendances et snapshot de compilation |
| `data/` | Ressources runtime classées : app, UI, marques, imprimantes, langues, licences |
| `tests/fixtures/` | Catalogues, audits, 48 profils Orca et instantané historique, jamais embarqués |
| `docs/` | Guides actuels, wiki et preuves de la release |
| `docs/archive/README.md` | Index vers les rapports historiques dans Git |
| `.github/` | Workflows, politiques, outils de contrôle et de maintenance |

Les captures de démonstration et leur manifeste restent sous `docs/images/`,
hors des ressources embarquées. Les vecteurs SSQR1 sont sous `tests/fixtures/qr/` ;
les oracles de scan restent des outils de QA/CI, installés après compilation.

## Suppressions et déplacements justifiés (passe historique v0.3.5)

- **54 fichiers de référence** déplacés hors de `data/` et de la racine : leurs
  octets sont identiques, contrôlés par `tests/fixtures/manifest.json` à partir
  du commit `5d652232e5b989028f13704ad6ca13b65724332b`.
- **Sept copies exactes de logos** supprimées ; les entrées de provenance partagent
  désormais la même image. Ancien PNG Prusament supprimé au profit du SVG actuel.
  Les 147 entrées restent présentes, avec 141 images distinctes.
- Logo ROSA3D historique conservé comme repli : ce fichier a encore une utilité.
- **22 rapports intermédiaires** retirés de l’arborescence active. L’[index](archive/README.md)
  donne leurs liens Git immuables ; aucun résultat historique n’est réécrit.
- **1 525 810 840 octets** d’anciens builds, paquets de recette et caches locaux
  supprimés. Leur archive locale provisoire a également été retirée.
- `data/printers.json` reste volontairement à son chemin public : les applications
  déjà publiées y téléchargent leur liste. Ce fichier n’est pas dupliqué.

## Compatibilité et qualité

Les catalogues de filaments, les 48 profils Orca et le contrat des 1 008 exports
gardent leur contenu. Les chemins de logos déjà enregistrés restent lisibles par
des alias ; les fichiers du dossier utilisateur ne sont ni déplacés ni réécrits.
Les anciennes copies de manifestes et les personnalisations de logos restent prises
en compte. Cette passe historique conservait la version **0.3.5** ; la préversion actuelle est **0.7.0**.

Le packaging utilise une liste déclarée, pas une collecte de toutes les images
trouvées dans `data/`. Le contrôle du dépôt refuse les ressources orphelines,
les images binaires dupliquées et les modifications des fixtures protégées.
Les téléchargements d’une nouvelle installation ne contiennent aucun catalogue.

Les outils de préparation écrivent dans un dossier de revue vide et partagent
les images strictement identiques. L’import de logos actualise les empreintes
de toutes les entrées partageant l’image retraitée. Dependabot suit `/` et
`/requirements`, selon la [configuration multi-dossiers GitHub](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#directories-or-directory).

## Vérification de la passe historique v0.3.5

La suite comprend les 269 tests précédents et neuf cas supplémentaires : identité
des 54 fixtures, anciens chemins et logos utilisateur, exclusion d’images non
déclarées, instantané optionnel, endpoint imprimantes, cohérence des images
partagées retraitées, stockage utilisateur par défaut des 13 workers autonomes et
repli sur l’image ROSA3D déclarée sans copie dans les données utilisateur.
Les essais locaux sont hors réseau et isolés : **278 tests réussis** sous Python
3.10 et 3.12.

Le build macOS utilise un dossier temporaire non synchronisé : quatre langues,
TLS strict, NTAG215/216, **186 ressources** et signature stricte contrôlés.
Aucune application de `/Applications`, aucun catalogue personnel ou firmware n’est modifié.

La [campagne GitHub Actions](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41302882188)
porte sur le code `798b75001b82ae52800c7f1340920dddf503ae89` :

| Vérification | Résultat |
| --- | --- |
| Linux / Python 3.10 et 3.12, Windows et macOS / Python 3.12 | 278 tests réussis dans chacune des quatre configurations |
| Builds Windows, macOS et Linux | Trois builds exécutés et réussis après les tests |
| Trois ZIP et trois fichiers SHA-256 | Téléchargés et contrôlés indépendamment ; structure et empreintes valides |
| Ressources embarquées | 186 fichiers identiques aux blobs Git dans chaque build ; aucune fixture |
| Bundle macOS téléchargé | Signature stricte vérifiée |

Ces archives sont des **artefacts de validation CI**. Le job de publication est
ignoré sur cette branche, conformément au workflow ; aucune release n’est publiée
par cette campagne. Les exécutables Windows et Linux sont testés sur leurs runners
natifs, pas exécutés sur le Mac de développement.

Les [preuves de la release](validation/v0.3.5.md) et celles de la
[première passe de structure](https://github.com/ArN-LaB/Spoolscribe-/blob/5d652232e5b989028f13704ad6ca13b65724332b/docs/REPOSITORY.md)
conservent leurs propres commits et empreintes. Le tag et les six fichiers de
la release v0.3.5 ne sont pas déplacés ou remplacés par cette maintenance.
Les essais NFC physiques et la recette humaine exhaustive restent à effectuer.
