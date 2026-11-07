# Mission universelle — adopter la norme dans le projet ouvert

**Version : 4.0 — 2026-11-07**
**Destinataire :** Codex, ou l'agent explicitement mandaté par l'utilisateur.
**Autorité :** ce fichier n'est exécutable **que si l'utilisateur demande expressément de l'appliquer**.

## 1. Périmètre non négociable

Travailler **uniquement sur le projet actuellement ouvert et explicitement désigné**. Identifier sa racine (Git si présent, sinon répertoire du projet), sans remonter vers un parent pour rechercher d'autres projets. Si plusieurs workspaces sont ouverts et que le projet cible n'est pas établi, STOP avec le constat ; ne pas choisir un dépôt voisin.

Ne parcourir aucun projet voisin, bibliothèque personnelle, NAS, cloud, dépôt Git distant, machine virtuelle ou dossier hors projet. Les traces d'essais externes déjà mentionnées dans le projet peuvent être **répertoriées par leurs références**, sans aller les lire. L'inventaire extérieur et le nettoyage requièrent un mandat humain distinct et ciblé.

## 2. Lecture efficace

1. Lire `docs/UNIVERSAL.md`, `docs/UNIVERSAL/01-NORME.md`, `03-MODELES.md` et `04-ESSAIS-ET-NETTOYAGE.md`.
2. Lire les instructions locales actives (si elles existent) : `AGENTS.md`, `CLAUDE.md`, `docs/AGENT_WORKFLOW.md`, `README.md` et leurs éventuels documents **pertinents**. Ne pas remplacer un contrat métier par une règle générique.
3. Lire `docs/agent-runs/INDEX.md`, s'il existe, puis les **derniers** rapports de normalisation et l'état de la phase en cours. Réutiliser leurs inventaires : ne pas relire inutilement des centaines de pièces historiques ni refaire une migration validée.
4. Exécuter une fois en lecture seule : `python3 docs/UNIVERSAL/OUTILS/verifier.py --root .`.

## 3. Application demandée

- Déterminer si le projet est **neuf**, **déjà organisé**, ou **hérité**. Aucun dépôt Git à initialiser automatiquement ; ne pas supposer de branche ni de SHA hors Git.
- Établir un **point d'entrée documentaire** : `docs/agent-runs/INDEX.md` si les phases existent, et un lien court vers `docs/UNIVERSAL.md` dans les fichiers d'instructions actifs **si leur modification est autorisée**. Ne jamais écraser `AGENTS.md`, `CLAUDE.md` ou `AGENT_WORKFLOW.md` : éditer uniquement leurs clauses documentaires contradictoires, sans retirer leurs règles de sécurité, outils, test, métier, architecture, déploiement et publication.
- Pour les **nouvelles phases et boucles**, appliquer immédiatement les noms, documents et preuves standardisés. Ne pas créer de documents fictifs ni de répertoires vides.
- Pour un **projet déjà restructuré**, préserver l'arborescence conforme. Corriger seulement les anomalies concrètes de nommage, navigation, liens ou statut. Ne pas refaire une migration cosmétique massive.
- Si une **migration physique des anciens documents** est explicitement autorisée par l'utilisateur : organiser d'après les dates attestées et les objectifs, renommer/déplacer les originaux nécessaires, réparer les références actives, garder une table unique ancien → nouveau, sauvegarder les préimages, exécuter un seul contrôle consolidé. Ne pas conserver d'alias inutiles ni un deuxième arbre concurrent.
- Vérifier les dossiers vides du périmètre documentaire et supprimer **seulement** les dossiers inutiles dont le retrait a été autorisé, après vérification de l'absence de contenu caché ou de dépendance contractuelle.
- Intégrer l'inventaire et le bilan des essais dans les phases réelles. **N'effectuer aucune purge extérieure ni suppression de copies de projet** sans instruction ultérieure portant sur des cibles qualifiées.

## 4. Règles de sûreté

Aucune modification du code métier, des données utilisateur, des données sensibles, de `.git`, des dépôts voisins ni de la configuration des outils sans mandat adapté. Aucun commit, stage, push, merge, publication, TestFlight, CI, mise en production ou lancement d'un autre agent implicite. Ne jamais utiliser `git reset --hard`, `git clean -fd`, `rm -rf` sur des ensembles de projets ou `pkill`/`killall` pour nettoyer les ressources.

Ne pas interpréter un rapport PASS comme une autorisation humaine ni une ancienne mise en quarantaine comme espace effectivement libéré. Le travail présent porte sur la **gouvernance et la documentation**, pas la QA applicative.

## 5. Contrôle et livrable minimal

Après changements autorisés, refaire **une seule** vérification :

```bash
python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
```

Contrôler également les références actives mises à jour et l'état Git (si applicable) ; les avertissements du script ne constituent pas des validations implicites. Produire **un seul compte rendu** dans la phase documentaire existante ou, si nécessaire, une phase de gouvernance réellement ouverte ; ne pas ajouter plusieurs niveaux de rapports pour expliquer une opération simple.

Le compte rendu mentionne : état initial et final, chemins modifiés, ancienne → nouvelle destination, liens réparés, dossiers vides retirés, exceptions, essai/nettoyage (ou `AUCUNE_PURGE`), éléments préservés, prochaine action humaine. Marquer `PARTIEL` si des critères pertinents ne sont pas satisfaits.

**STOP.** Ne prépare pas une passation vers Claude Code sauf si l'utilisateur la demande explicitement ; aucune transmission automatique.
