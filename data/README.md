# Ressources de l’application — v0.3.5

Ce dossier contient uniquement les ressources utilisées par SpoolScribe.
Il ne contient ni catalogue de filaments utilisateur, ni ancien export, ni profil
de régression. [Documentation](../docs/README.md) · [Données de test](../tests/fixtures/README.md)

| Emplacement | Contenu et usage |
| --- | --- |
| `app/` | Icônes Windows/macOS/Linux et sources SVG du logo statique/animé |
| `ui/` | Icônes SVG utilisées par les contrôles Qt |
| `brands/manifest.json` | 147 entrées de provenance, empreintes et chemins des logos revus |
| `brands/logos/` | 141 images référencées par le manifeste, plus le logo historique ROSA3D de repli |
| `printers/photos/` | Quatre photos et leur manifeste de provenance |
| `translations/` | Catalogue local des quatre langues et consignes de traduction |
| `licenses/` | Licences des sources et attribution TheFilamentDB |
| `printers.json` | Catalogue matériel public et embarqué ; chemin stable utilisé par les versions déjà publiées |

Plusieurs entrées de marque peuvent référencer une même image **strictement
identique**, sans dupliquer les octets ni perdre les noms et sources de provenance.
Les anciens chemins de logos restent lisibles via `scripts/resource_paths.py` :
les fichiers personnels ne sont ni déplacés, ni écrasés.

Les catalogues, audits, profils Orca et l’instantané historique TheFilamentDB sont
dans `tests/fixtures/`, avec leurs empreintes antérieures inchangées.
La base de l’utilisateur reste dans son dossier système habituel, hors du dépôt.

Le packaging utilise une liste de ressources déclarées ; une image ajoutée sans
référence dans les manifestes n’est pas embarquée. Le contrôle du dépôt refuse
les ressources orphelines et les images binaires identiques en double.
