> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Retours sur écran — SpoolScribe 0.3.0

Date : 1er novembre 2026. Suite de [VALIDATION-AUDIT-v0.3.0.md](VALIDATION-AUDIT-v0.3.0.md), après les captures utilisateur de 08:44–08:53.

**Résultat : corrections locales testées et paquet macOS de recette construit. Aucune publication.** Les tests automatisés et captures Qt ne remplacent pas une recette humaine de l’application installée.

## Corrections réalisées

| Retour | Diagnostic et comportement corrigé |
| --- | --- |
| Choix de l’imprimante | Les modèles sont présentés par leur nom. Le logiciel installé est demandé seulement lorsqu’il change la compatibilité. Une configuration GUI neuve ne suppose plus que la Snapmaker U1 dispose du firmware paxx12 : le choix reste à confirmer avant l’export. Les anciens choix explicites sont conservés. |
| Fenêtre déformée et champs coupés | Largeur de la barre latérale bornée, migration de l’ancien partage en deux panneaux, textes longs qui ne forcent plus la largeur. Les fenêtres Matériel et Sources défilent au lieu d’écraser leurs contrôles. Les commandes d’export restent visibles sous la fiche. La pagination inutile disparaît. |
| Texte trop technique | Aides courtes, réglages avancés repliés, provenance et références détaillées sur demande. Les commandes internes et chemins d’erreur quittent le choix des sources ; ils restent consultables dans le rapport. Libellés de boutons francisés. Une version de développement plus récente que la version publiée est explicitement identifiée. |
| Références similaires | Le regroupement d’affichage normalise notamment le préfixe fabricant des noms de couleur. Il distingue matière, diamètre, transparence, couleurs multiples et caractéristiques de variante. Les conditionnements restent sélectionnables. Une divergence HEX bloque l’export jusqu’au choix d’une référence ; aucune couleur moyenne n’est inventée. |
| Analyse et fusion de sources | Correction d’un accès à des métadonnées OFD absentes après normalisation d’une gamme ; conservation des anciennes métadonnées de marque comme alias pour respecter la protection contre les suppressions ; rejet d’une combinaison incohérente de demi-plages de températures en conservant la paire précédente. |
| Propagation entre références | Une fiche produit historique peut être partagée par des SKU de diamètres différents. Une modification physique acceptée pour un SKU reçoit désormais sa propre fiche lorsque nécessaire. Les autres références ne changent pas ; les index de rapprochement sont actualisés pendant la fusion. Le scénario 1,75/2,85 mm et sa seconde exécution sont testés. |
| Favoris instables | Fabricants favoris ajoutés/retirés explicitement par étoile ou menu ; la simple navigation ne les modifie plus. Favoris filaments fondés sur une identité stable, complétée par les références membres. Ajout, retrait, filtrage, rechargement et export/import des préférences sont testés. |

Les logos existants sont conservés, redimensionnés sans découpe dans la fiche. Les explications ne présentent pas les températures du fichier comme des réglages automatiquement appliqués par toute imprimante. Le diamètre est visible dans le libellé produit, même lorsque sa colonne est masquée.

## Tests réellement exécutés

Les suites utilisent des dossiers temporaires et refusent les connexions réseau. Aucun test n’est désactivé. Les 13 nouveaux tests portent le total de 164 à **177**.

| Contrôle final | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6/Shiboken6 6.11.3 | 177 tests, 9,398 s, OK |
| macOS ARM64, Python 3.12.13, PySide6/Shiboken6 6.11.3 | 177 tests, 8,518 s, OK |
| Contrat historique du catalogue et des 1 008 exports compacts | OK, test `test_legacy_catalogue_and_1008_compact_exports_are_identical` dans les deux suites |
| Restaurations, mises à jour partielles, nulls intentionnels, protection des corrections et concurrence | Tests de régression existants conservés et exécutés |
| Rafraîchissements Qt | 30 restaurations consécutives des préférences dans un nouveau test ; cartes de grille réutilisées |
| Contrôle visuel Qt offscreen | Captures claire/sombre à 1360 × 860, fenêtre à 1000 × 720, Matériel à 640 × 440 et Sources ; inspection des captures |
| Ressources protégées | 215 fichiers inchangés par SHA-256, dont les 48 profils Orca |
| Base personnelle et configuration en fin de passe | Octets identiques aux copies prises au début, voir incident d’isolation ci-dessous |
| `git diff --check` | OK |

Les 1 008 exports sont comparés au contrat actuellement versionné dans ce dépôt ; ce résultat ne requalifie pas rétroactivement toutes les sorties de versions antérieures.

## Vérification séparée des sources réelles

Une synchronisation réseau a été exécutée hors des tests, sur une **copie isolée de la base utilisateur initiale**, sans écrire dans la base de l’application installée. Elle a duré 21,02 s et s’est terminée avec le statut `complete`.

| Source exécutée | Code | Statut |
| --- | --- | --- |
| Polymaker officiel | 0 | Données modifiées |
| Open Filament Database | 0 | Données modifiées |
| SpoolmanDB | 0 | Inchangées |
| Bambu Lab officiel | 0 | Inchangées |
| SUNLU officiel | 0 | Inchangées |

« Inchangées » signifie que la source a été vérifiée sans changement à appliquer, pas que son exécution a été ignorée. L’analyse séparée de l’archive OFD courante a produit 23 990 références sans rejet de parsing. La synchronisation finale conserve **24 649 références, 16 708 groupes de filaments et 165 fabricants** ; 14 731 groupes ont les données requises complètes. Cette mesure concerne la copie de la base existante, pas la couverture mondiale ni une installation vierge.

Restent **157 groupes présentant des divergences de teinte** et **876 rapprochements en attente** (62 Polymaker, 814 OFD). Les rapprochements incertains ne sont pas ajoutés au tableau. Le succès technique des cinq sources ne signifie donc pas que leurs données sont exhaustives ou concordantes. Le complément historique TheFilamentDB, absent du paquet, n’est pas présenté comme une source réseau exécutée ; son choix est désactivé lorsqu’il est indisponible.

## Échecs rencontrés et traitement

- Les nouveaux cas ont d’abord reproduit les défauts de normalisation, de plage thermique, de parsing, de favoris, de géométrie et de sélection de référence. Le cas de partage du diamètre a également échoué avant correction.
- Deux exécutions ont rencontré un crash natif Qt au renouvellement de la grille (`QListWidget.clear`, code 139). La grille réutilise maintenant ses cartes et les cellules couleur du tableau sont actualisées en place. Le test de 30 restaurations et plusieurs suites complètes Python 3.12 passent depuis. La cause interne exacte dans les bindings Qt n’est pas démontrée ; aucune garantie d’absence de tout crash natif n’est avancée.
- Un ancien test isolait la base mais pas `CONFIG_PATH`. Il a écrit temporairement `last_update_attempt` et deux clés de favoris vides dans la configuration personnelle. Le test est corrigé ; la configuration initiale a été rétablie **octet pour octet**, après vérification que seules ces clés avaient changé. La base personnelle est restée identique. Les suites finales ajoutent une isolation par variables d’environnement à celle des fixtures.
- Le contrôle ad hoc des ressources du paquet cherchait initialement dans `Contents/Frameworks` sans suivre les liens de répertoires macOS : il a été corrigé pour inspecter `Contents/Resources`. Une relance du probe « première installation » dans son dossier déjà peuplé a aussi été rejetée ; le contrôle final utilise un nouveau dossier vide. Il ne s’agissait pas de fichiers manquants dans le paquet.
- L’erreur Proter Print montrée dans la capture est tronquée. Sa cause exacte historique n’est pas prouvée. La combinaison incohérente de plages a été reproduite et protégée ; l’import courant complet a réussi.

## Paquet local macOS

Construction avec Python 3.12.13, PyInstaller 6.22.3, PySide6 6.11.3 et certifi 2026.10.23. L’archive de recette et ses preuves sont dans `dist/test-retours-v0.3.0/`, dossier ignoré par Git.

- Une seule application `SpoolScribe.app` à la racine du ZIP ; exécutable Mach-O, permissions, version 0.3.0, chemins et CRC contrôlés.
- 186 ressources embarquées comparées octet par octet au code et aux ressources attendus ; pas de catalogue ni de profils Orca personnels embarqués.
- Probe TLS du binaire : vérification des certificats et du nom d’hôte active, 128 racines par défaut et 118 racines embarquées. Ce probe contrôle la configuration TLS, pas une synchronisation HTTPS complète du binaire.
- Probe catalogue du binaire : première installation vide, fixture importable, 147 nouveaux logos approuvés, exports NTAG215 et NTAG216, réseau désactivé.
- Archive extraite à nouveau, signature ad hoc vérifiée avec `codesign --verify --deep --strict`, application lancée six secondes en Qt offscreen dans un profil vide hors ligne, puis arrêtée volontairement.

L’empreinte exacte est dans `SpoolScribe-macos.zip.sha256` et le journal `package.log` livré à côté. Le paquet n’est ni signé Developer ID ni notarié. L’application déjà installée n’a pas été remplacée.

## Dépôt, documentation et limites

Branche `feature/universal-catalogue`, HEAD de départ et de fin `fba000b69048cf9e595274cdc253d5eb3ceacfce`. Index vide ; modifications locales de code, tests et documentation uniquement. **Aucun commit, push, tag, fusion ou release dans cette passe.** Les fichiers du catalogue, des logos et des profils Orca sont inchangés.

README, changelog, format des données, sources, guide UX, prise en main et roadmap ont été adaptés. Le rapport d’audit antérieur reste accessible et renvoie vers ce complément, sans réécriture de ses résultats historiques.

Restent non exécutés sur ces changements : GitHub Actions Windows/Linux/macOS, builds Windows/Linux, recette interactive humaine macOS et essais physiques SpoolFlux/NTAG215/NTAG216/Snapmaker U1. Aucun firmware, service Spoolman personnel, NAS ou association RFID n’a été modifié. La compatibilité matérielle ne se déduit pas du seul fait qu’un fichier tient sur une étiquette.


## Retours suivants, 09:27–09:32

La seconde passe est documentée dans
[VALIDATION-UX-RETOURS-2-v0.3.0.md](VALIDATION-UX-RETOURS-2-v0.3.0.md).
Le paquet et les mesures ci-dessus restent les preuves de la première passe.
