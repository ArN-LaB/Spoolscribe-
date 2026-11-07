# UNIVERSAL — point d'entrée des agents

**Version de la norme : 4.0 — 7 novembre 2026**
**Applicable à tout projet, quel que soit son langage, son dépôt ou son outillage.**

> **Instruction de lecture :** tout agent chargé du développement, d'une revue, d'une passation ou de la maintenance des traces de ce projet commence par ce fichier. Le dossier `UNIVERSAL/` contient la norme commune. Il ne décrit aucune application particulière.

## Ordre de lecture obligatoire

1. [`UNIVERSAL/01-NORME.md`](UNIVERSAL/01-NORME.md) — source normative unique : phases, boucles, fichiers Markdown, décisions et preuves.
2. [`UNIVERSAL/03-MODELES.md`](UNIVERSAL/03-MODELES.md) — modèles et champs à respecter uniquement pour les nouvelles traces.
3. [`UNIVERSAL/04-ESSAIS-ET-NETTOYAGE.md`](UNIVERSAL/04-ESSAIS-ET-NETTOYAGE.md) — cycle de vie des copies, tests, VM, simulateurs et caches.
4. [`UNIVERSAL/02-MISSION-ADOPTION.md`](UNIVERSAL/02-MISSION-ADOPTION.md) **seulement si l'utilisateur a demandé l'installation / la mise en conformité** du projet courant.
5. Lire ensuite les consignes techniques **déjà présentes** du projet (`AGENTS.md`, `CLAUDE.md`, `docs/AGENT_WORKFLOW.md`, `README.md`, etc.), si elles existent et sont pertinentes.

## Ce qui est universel — et ce qui ne l'est pas

- La **nomenclature et l'organisation des traces de développement** suivent `UNIVERSAL/01-NORME.md`.
- Les exigences de sécurité, métier, pédagogie, Git, publication, tests et outils du projet **restent applicables**. Ne pas les écraser par une adaptation générique.
- En cas de contradiction sur le **format documentaire**, appliquer la norme commune aux nouvelles pièces et signaler les références actives à mettre en cohérence. En cas de contradiction technique ou d'autorisation : ne pas décider à la place de l'humain.
- Les **décisions humaines expresses et récentes** priment sur les propositions des agents. Une QA PASS n'est pas une autorisation de Git ou de déploiement.

## Périmètre et contrôle

**Projet courant uniquement.** La racine est celle du projet ouvert explicitement désigné par l'utilisateur, pas un dossier parent. Ne jamais explorer d'autres projets, comptes, dépôts ou espaces de stockage pour « harmoniser globalement ». Les essais temporaires situés ailleurs ne peuvent être **repérés** que dans les limites d'un mandat humain explicite et d'une appartenance vérifiable ; ils ne sont jamais nettoyés implicitement.

Vérificateur documentaire, sans modification :

```bash
python3 docs/UNIVERSAL/OUTILS/verifier.py --root .
```

**Mission d'installation demandée ?** Lire `UNIVERSAL/02-MISSION-ADOPTION.md`, traiter uniquement ce projet, puis STOP avec un rapport court. **Pas de passation automatique Codex ↔ Claude Code.**
