# Audit du dépôt et promotion Desktop v0.8.0

Date : 5 novembre 2026. Base contrôlée : `89c08a657bcd752c9f6b95e15192c8390d54d156`.
[Tag logiciel](https://github.com/ArN-LaB/Spoolscribe-/tree/v0.8.0) · [Validation des binaires](v0.8.0.md) · [Politique de versions](../RELEASE_POLICY.md).

## Périmètre et résultat

La passe porte sur la documentation, les captures réelles, la cohérence du canal
GitHub, les métadonnées du projet et la propreté du dépôt. Elle ne change aucun
module applicatif, protocole, ressource runtime, catalogue, profil Orca ou dépendance
par rapport au tag v0.8.0. La promotion stable conserve le tag et les six fichiers
publiés. Elle ne certifie pas toutes les configurations matérielles.

## Structure et ménage justifié

- 437 fichiers suivis à la base ; 6 fichiers visibles à la racine : `CHANGELOG.md`, `LICENSE`, `NOTICE`, `README.md`, `install-local.command`, `pyproject.toml`.
- 41 scripts audités : 26 sous `scripts/`, 15 outils CI/maintenance.
- Les modules applicatifs restent sous `src/spoolscribe/`, les builds sous `packaging/`, les ressources déclarées sous `data/` et les données historiques sous `tests/fixtures/`.
- Les anciens scrapers sont encore des entrées CLI/compatibilité ou des fixtures de régression, pas des doublons à supprimer sur simple absence dans le parcours graphique. Les outils de captures, logos, wiki, archives et sondes compilées ont un rôle de maintenance explicite.
- Aucun script de production n’est supprimé sur la seule base d’un nom ancien. Le contrôle de ressources conserve 198 fichiers déclarés, les 54 fixtures protégées dont 48 profils Orca et le contrat des 1 008 exports.
- `docs/REPOSITORY.md` est recentré sur la structure actuelle ; l’ancien bilan daté reste accessible dans Git. Les erreurs de version courante, anciens compteurs et conseils de logiciels d’écriture sont corrigés dans l’aide active.
- Les captures sont centralisées et référencées par un manifeste de version, dimensions, SHA-256 et scénario. Les captures de démonstration ne sont pas embarquées dans l’application.
- 1999 fichiers locaux des dossiers `docs/agent-runs/` et `docs/agents-prompts/` sont conservés, empreintes vérifiées. Deux exclusions Git explicites évitent de publier brouillons, chemins locaux et preuves intermédiaires. Les preuves publiques de release restent sous `docs/validation/`.
- Les sorties `dist/`, caches, réglages utilisateur et métadonnées `.DS_Store` restent ignorés. Le contrôle final compare l’ensemble des chemins et octets non ignorés avec Git ; il ne prétend pas synchroniser les dossiers locaux exclus.

## Outils conservés et raison

| Famille | Utilisation |
| --- | --- |
| Workers d’acquisition / seeds | Sources choisies, compléments historiques, CLI et tests sans réseau |
| `db_io`, fusion et adaptateurs | Écriture protégée, rapprochement et validation des données |
| Icônes et ressources | Régénération de ressources/provenances, alias compatibles |
| Sondes `probe_frozen_*` / `check_frozen_*` | Vérification des vrais exécutables sur chaque runner |
| `verify_archive`, `check_repository` | Structure native, liens, version, fixtures et ressources |
| `render_readme_*`, `sync_wiki` | Reproduction des visuels réels et publication de l’aide |
| `build_catalogue_snapshot`, `import_brand_logos` | Préparations explicites de maintenance, hors installation utilisateur |

## QR et disponibilité mobile

SSQR1 est conservé octet pour octet. Un QR visible peut être lu par une autre
application ; M/Q corrige des dommages et SHA-256 détecte des altérations, sans
exclusivité applicative ni chiffrement. Le parcours mobile recommandé est le
scanner Companion ; l’ouverture par caméra via liens vérifiés est un autre chantier,
avec domaine contrôlé et configuration mobile. Aucun lien de store n’est inventé.
[Explication et sources](../wiki/Companion-and-QR.md).

## Vérifications et limites

- Python 3.10 : 618/618 tests réussis, 104,677 s ; Python 3.12 : 618/618, 94,221 s, sur macOS avec Qt offscreen et fixtures isolées, sans accès réseau réel dans les tests.
- Contrôle de structure : 52 Markdown actifs, 304 liens locaux, zéro erreur ; ancres de l’aide vérifiées séparément ; `git diff --check` réussi.
- 30 captures : dimensions et SHA-256 conformes au manifeste ; revue visuelle de la planche complète et des écrans détaillés.
- Quatre QR présents dans les captures décodés indépendamment avec ZXing : NDEF identiques aux empreintes attendues du manifeste.
- 1 999 fichiers de travail locaux conservés sans changement d’empreinte ; aucune donnée personnelle ou clé privée ajoutée au diff.
- La condition réelle de publication distingue v0.8.0 stable, les préversions historiques et les tags suffixés, sans désactiver de contrôle.
- Un formulaire de résultat matériel recueille la configuration exacte, les versions et le read-back, sans assimiler un retour individuel à une certification de gamme.


Le contrôle du dépôt, des légendes, des empreintes des captures, des fichiers
orphelins, des versions et de la condition de publication est exécuté avant la PR.
Les quatre checks GitHub requis restent appliqués sans contournement.
La [PR #21](https://github.com/ArN-LaB/Spoolscribe-/pull/21) est fusionnée au commit
`afeef1d71532106bbb01928804332e52d64d3440` après [CI réussie](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41959317795) :
618 tests dans chacune des quatre configurations. Les builds de cette passe
strictement documentaire sont ignorés, et ne sont pas comptés comme réussis :
les trois builds natifs réels restent ceux de la [publication initiale](https://github.com/ArN-LaB/Spoolscribe-/actions/runs/41954082388).

La release v0.8.0 est promue stable avec `prerelease=false`, `draft=false` et
l’API `releases/latest` pointe sur v0.8.0. Les six URL publiques répondent HTTP 200 ;
identifiants, tailles et empreintes des six artefacts restent identiques au relevé
initial. Le tag annoté demeure `552576556b2d0f1cc9cd4c7328173e314e6996c8`,
sur le commit logiciel `89c08a657bcd752c9f6b95e15192c8390d54d156`.
Le wiki est publié depuis les mêmes sources, avec les routes adaptées au wiki.

Le rendu HTML GitHub a été contrôlé pour le README et deux pages représentatives :
centrage, titres et légendes sont conservés. Aucun navigateur automatisable n’étant
disponible pour cette passe, la page complète n’a pas fait l’objet d’une recette
visuelle dans un navigateur ; les captures Qt, elles, ont été revues.

Les captures Qt sont réelles, avec données publiques ou exemples synthétiques
signalés (mesures, réglages d’appareil et rapport d’actualisation). Elles ne sont
ni une mesure d’instrument ni un téléchargement réel pour la démonstration.
L’audit ne certifie pas App Store, Companion, les téléphones, l’impression ni toutes
les imprimantes/lecteurs. La documentation mobile de confidentialité doit décrire
l’application mobile effectivement soumise.
