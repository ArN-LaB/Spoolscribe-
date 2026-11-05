# Structure du dépôt SpoolScribe v0.8.0

[Documentation](README.md) · [Audit actuel](validation/repository-v0.8.0.md) · [Ressources](../data/README.md) · [Fixtures](../tests/fixtures/README.md)

| Dossier | Rôle |
| --- | --- |
| `src/spoolscribe/` | Logique, interface Qt, CLI et contrats NFC/QR |
| `scripts/` | Stockage, sources, workers autonomes et compatibilité CLI |
| `packaging/` | Entrée et spec PyInstaller multiplateforme |
| `requirements/` | Dépendances et snapshot de build |
| `data/` | Ressources runtime déclarées : app, UI, marques, imprimantes, traductions, licences |
| `tests/fixtures/` | Catalogues publics, 48 profils Orca et vecteurs historiques, jamais embarqués |
| `docs/wiki/` | Source relue de l’aide GitHub Wiki |
| `docs/images/` | Captures réelles et manifeste, hors application |
| `docs/validation/` | Preuves publiques datées des releases et audits |
| `.github/` | Workflows, politiques et outils de maintenance/QA |

Les dossiers locaux `docs/agent-runs/` et `docs/agents-prompts/` sont des dossiers de
travail ignorés, préservés sur le Mac. Publier une preuve utile nécessite une
sélection explicite et une copie relue dans `docs/validation/`. Les builds, caches,
réglages utilisateur et métadonnées OS sont également ignorés.

Aucune base personnelle n’est embarquée. Les téléchargements initiaux construisent
le catalogue après consentement. `data/printers.json` conserve son chemin public
pour les installations existantes. Les ressources sont déclarées dans
`packaging_rules.py`, pas collectées aveuglément dans les dossiers.

Les scripts historiques ne sont pas des fichiers orphelins dès lors que CLI,
compatibilité ou régressions les utilisent. Voir l’[audit](validation/repository-v0.8.0.md)
pour les familles conservées et les exclusions motivées.

Le [bilan de structure antérieur](https://github.com/ArN-LaB/Spoolscribe-/blob/v0.8.0/docs/REPOSITORY.md)
et l’[archive historique](archive/README.md) restent consultables sans réécrire
les résultats datés. [Développement](DEVELOPMENT.md) · [Politique de versions](RELEASE_POLICY.md).
