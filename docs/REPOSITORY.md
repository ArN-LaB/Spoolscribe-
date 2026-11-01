# Structure et maintenance — v0.3.5

[Documentation](README.md) · [Développement](DEVELOPMENT.md) · [Validation de la release](validation/v0.3.5.md)

La racine conserve six fichiers visibles : `README.md`, `CHANGELOG.md`, `LICENSE`,
`NOTICE`, `pyproject.toml` et le lanceur personnel `install-local.command`.
Les trois fichiers cachés de règles Git et du manifeste macOS restent à leur place.

| Dossier | Rôle |
| --- | --- |
| `src/spoolscribe/` | Application, CLI, traductions UI et logique métier Python |
| `scripts/` | Adaptateurs, stockage et workers d’acquisition |
| `packaging/` | Entrée PyInstaller et spec multiplateforme |
| `requirements/` | Dépendances source et snapshot de compilation |
| `data/` | Ressources, licences et jeux de régression ; les catalogues ne sont pas installés |
| `orca_profiles/` | 48 profils officiels de régression, non embarqués |
| `translations/` | Catalogue JSON des quatre langues et consignes |
| `tests/` | Tests hors réseau et fixtures |
| `docs/` | Guides actuels, wiki, visuels et index |
| `docs/validation/` | Preuves de la release actuelle |
| `docs/archive/` | Rapports datés v0.2.2, v0.3.0 et préparation v0.3.5 |
| `.github/` | Workflows, politiques, maintenance et vérifications |

## Nettoyage retenu

- Déplacement des dix modules Python dans un package ; imports et relance source adaptés.
- Regroupement du spec et des dépendances ; chemins CI et manifeste d’installation mis à jour.
- Anciens audits, huit passes UX et journal de publication regroupés par version,
  avec un bandeau d’archive et des liens recalculés. Leurs résultats ne sont pas réécrits.
- Guide utilisateur courant sans numéro obsolète dans son nom ; roadmap consolidée.
- Wiki du dépôt utilisable avec des liens Markdown standards ; outil de copie
  vers le Wiki GitHub, sans suppression de pages supplémentaires.

La miniature `data/printer_photos/bambu-cover.png`, remplacée par le PNG transparent X1 Carbon et absente du manifeste, a été supprimée. Aucun chemin du code ou du catalogue ne la référence. Les catalogues et les profils Orca restent identiques à ceux de la release.
Les anciens scrapers restent nécessaires aux fixtures, à l’enrichissement optionnel
ou à la lecture des pipelines historiques : ils ne sont pas supprimés sur la seule
absence de lien Markdown. Les licences, attributions et actifs de marque sont conservés.

Les répertoires ignorés `build/`, `dist/` et les caches locaux ne sont pas publiés.
Les anciens paquets de recette locaux ne sont pas supprimés : ce sont des preuves
distinctes des fichiers sources suivis, pas des documents courants du dépôt.

## Contrôles de maintenance

`python .github/scripts/check_repository.py` vérifie les liens locaux de tous les
Markdown, les versions, la structure et le manifeste macOS. La CI l’exécute avant
les tests. Le build et les sondes restent identiques dans leur finalité : absence
de données personnelles, quatre langues, TLS et exports NFC hors réseau.

La maintenance garde la version applicative **0.3.5**. Elle ne déplace pas le tag
existant et ne remplace pas les six fichiers de la release publiée. Les nouveaux
builds de contrôle sont des artefacts CI, distincts de cette release.

Dependabot suit explicitement `/` et `/requirements`, conformément à la [configuration multi-dossiers GitHub](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#directories-or-directory). Les bornes PySide6 et PyInstaller sont conservées.

## Vérifications locales du 1er novembre 2026

- 269 tests réussis sous Python 3.10 et 3.12, dont les 267 tests de la release et
  deux contrôles des nouvelles entrées source et de la relance en package.
- Installation éditable sans accès réseau validée dans l’environnement temporaire ;
  commande CLI et imports exécutés depuis un dossier extérieur au dépôt.
- Build macOS isolé : fenêtre réelle dans quatre langues, TLS strict, NTAG215/216,
  193 ressources comparées aux sources et signature stricte valides. Le passage de
  194 à 193 correspond uniquement à la miniature Bambu supprimée.
- Liens locaux de tous les Markdown et `git diff --check` sans erreur.

Un premier build dans le dossier synchronisé Proton Drive a échoué au contrôle
strict de signature à cause d’attributs de fichiers. La reconstruction dans un
dossier temporaire non synchronisé passe le contrôle, sans désactiver Gatekeeper,
effacer globalement des attributs ou modifier les sources du catalogue.
Cette vérification locale ne vaut pas exécution des builds Windows/Linux : leurs
résultats doivent être lus dans les contrôles GitHub Actions de la PR de maintenance.
