# Modèles universels pour les nouvelles traces

**Version : 4.0 — 2026-11-07.** Exemples adaptables, pas des fichiers à créer intégralement à chaque fois. **Ne jamais créer une QA, une décision ou un dossier PREUVES fictifs.**

## 1. `docs/agent-runs/INDEX.md`

```markdown
# Historique du développement — [nom réel du projet]

| Phase (lien) | Début attesté | Objectif | État | Dernière QA | Dernière décision humaine | Prochaine action autorisée |
|---|---|---|---|---|---|---|
| [AAAA-MM-JJ-SUJET](AAAA-MM-JJ-SUJET/00-PHASE.md) | AAAA-MM-JJ | ... | EN_COURS | NON_REALISEE | AUCUNE | Attendre cadrage |

## Dépendances / parallélismes
- ... (seulement si attestés)
```

## 2. `00-PHASE.md`

```markdown
# Phase — [objectif explicite]

- **Début attesté :** AAAA-MM-JJ / date non établie
- **Objectif :** ...
- **Périmètre / hors périmètre :** ...
- **État :** EN_COURS / EN_ATTENTE_HUMAIN / BLOQUEE / CLOTUREE / ABANDONNEE
- **Source de la décision d'ouverture :** référence, ou NON_ETABLIE
- **Dernière QA :** lien ou NON_REALISEE
- **Dernière décision humaine :** lien ou AUCUNE_ETABLIE
- **Prochaine action autorisée :** ...

## Boucles réelles
- [B01-OBJECTIF](B01-OBJECTIF/00-BOUCLE.md) — ...

## Synthèse / bilan
- [Synthèse](80-SYNTHESE.md) si créée
- [Bilan](90-BILAN.md) si créé
```

## 3. `00-BOUCLE.md`

```markdown
# Boucle B01 — [objectif]

- **Phase :** ...
- **But précis :** ...
- **Statut :** EN_COURS / EN_ATTENTE_HUMAIN / QA_FAIL / QA_PASS / INCOMPLETE_ENV / TERMINEE
- **Mandat humain :** lien / NON_ETABLI

## Événements dans l'ordre réel
| Date/ordre attesté | Auteur | Pièce | État de transmission / résultat |
|---|---|---|---|
| AAAA-MM-JJ | Codex | [Mission](02-CODEX-MISSION-CLAUDE.md) | PREPAREE, NON TRANSMISE |

## Dernière QA, conclusion et suite
- **Verdict et preuve :** ... / NON_REALISEE
- **Décision humaine :** ... / EN_ATTENTE
- **Prochaine étape permise :** ...
```

## 4. Métadonnées d'un rapport (`NN-AUTEUR-TYPE.md`)

```yaml
---
trace_id: "PROJET:PHASE:B01:02"
phase: "AAAA-MM-JJ-SUJET"
boucle: "B01-OBJECTIF"
sequence: 2
auteur: "CODEX"
fonction: "MISSION-CLAUDE"
date: "AAAA-MM-JJ"
statut: "PREPARE"
transmis: false
source_ref: "NON_ETABLI"
---
```

Puis : `## Objectif`, `## Faits observés et hypothèses`, `## Périmètre et exclusions`, `## Travail demandé ou réalisé`, `## Preuves et tests`, `## Limites`, `## État et prochaine action`.

### Passation Codex → Claude (facultative, après cadrage)

`02-CODEX-MISSION-CLAUDE.md` : objectif unique ; faits vérifiés ; base de travail et modifications préexistantes ; fichiers autorisés et exclus ; critères d'acceptation ; tests ; livrables ; **STOP et transmission humaine exclusivement**. Ne jamais écrire « transmises » avant acte humain.

### Rapport Claude → utilisateur et préparation de QA

`03-CLAUDE-IMPLEMENTATION.md` : fichiers réellement modifiés, résultats et limites, commandes/tests et environnements réels, preuves. `04-CLAUDE-PASSATION-CODEX.md` : delta et points de re-QA à examiner **indépendamment**. **STOP ; pas de lancement de Codex.**

### QA Codex

`05-CODEX-QA.md` : version vérifiée, diff réel, tests reproduits ou non exécutés, preuves, risques, verdict (`PASS`, `PASS_AVEC_RESERVES`, `FAIL`, `INCOMPLET_ENV`, `BLOQUE_HUMAIN`), action proposée et **STOP pour décision humaine**. Ne jamais changer le verdict d'une ancienne QA après un correctif.

### Décision humaine

`06-HUMAIN-DECISION.md` **uniquement sur décision réelle de l'humain**, avec source et portée. Sa présence n'autorise pas implicitement commit, push ou publication.

## 5. `70-REGISTRE-ESSAIS.md` (uniquement si essai réel)

```markdown
# Registre des essais — [phase]

| ID | Boucle | Environnement/copie | Chemin réel | Créateur / date | Version de référence | Résultat / preuve | État de fin de vie | Décision de nettoyage |
|---|---|---|---|---|---|---|---|---|
| T001 | B01 | build de test isolé | chemin absolu | ... | ... | ... | CONSERVER | À déterminer après QA |
```

L'enregistrement peut rester dans un registre technique déjà existant si un pointeur fiable est ajouté ici ; pas de duplication de volumes.

## 6. `PREUVES/MANIFESTE.csv` (uniquement avec preuves)

```csv
preuve_id,chemin_relatif,type,horodatage,essai_id,environnement,commande_ou_methode,resultat,sha256_ou_NON_MESURE,retention
E001,E001-TEST-SUJET.txt,TEST,2026-11-07T10:00:00+08:00,T001,LOCAL,commande-executee,PASS,NON_MESURE,CONSERVER
```

L'exemple illustre le schéma, **pas un test réellement exécuté**. Ne pas réutiliser la ligne fictive dans un vrai manifeste.

## 7. `80-SYNTHESE.md` et `90-BILAN.md`

**Synthèse** : objectif, boucles accomplies, résultats, échecs, choix retenus/abandonnés, connaissances utiles, limites et action suivante. **Bilan** : état (provisoire ou clôturé sur acte humain), liens vers QA et décisions, produits livrés, essais en cours ou terminés, nettoyage réalisé ou non, occupation et gain disque **mesurés**, suites permises. Ne jamais inscrire `CLOTUREE` en l'absence d'une décision humaine requise.
