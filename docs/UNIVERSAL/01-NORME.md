# Norme universelle — phases, boucles, rapports et preuves

**Version : 4.0 — 2026-11-07**
**Autorité :** règles de production et de classement des traces des agents.
**Portée :** tous les projets **individuellement**, sans spécialisation sectorielle ni obligation d'utiliser Git.

## 1. Finalité et règles de base

Le dossier des traces doit expliquer **quand**, **pourquoi**, **par qui**, **avec quel résultat** et **sur quelle décision** le développement a progressé. La navigation principale montre une phase datée par objectif, ses cycles d'agents, les résultats et la prochaine action réellement autorisée.

- **Une phase** = un objectif fonctionnel cohérent, ouvert à une date attestée. Elle peut être active, bloquée, close, abandonnée ou parallèle à une autre phase. Pas de faux ordre horaire.
- **Une boucle** = un cycle de travail dans une phase, depuis le cadrage et les éventuelles passations jusqu'à la QA et à la décision. Une transition Codex → Claude n'est **pas à elle seule** une nouvelle boucle. Une correction suivant une QA négative peut ouvrir `B02`, `B03`, etc., sur décision humaine.
- **Un rapport** = une pièce distincte et datée ; pas de remplacement silencieux d'un rapport de QA par le suivant.
- **Une preuve** = un élément rattaché à une affirmation ou à un essai effectivement réalisé ; pas d'accumulation de captures ou logs sans lien avec une conclusion.
- Les **anciens chemins peuvent être renommés** ; les faits, résultats, décisions et verdicts historiques doivent garder leur sens. Toute migration comprend un registre ancien → nouveau et une vérification des liens.
- Une seule organisation principale. Pas de second arbre de phases ni de milliers de pages-redirects. Aucun dossier vide créé pour anticiper une étape possible.

## 2. Arborescence canonique

```text
docs/
├── UNIVERSAL.md                          # point d'entrée commun (ce kit)
├── UNIVERSAL/                           # norme et outils (ce kit)
└── agent-runs/                          # créé si des traces existent
    ├── INDEX.md                        # vue chronologique vivante
    ├── 2026-11-07-[ID-]SUJET-EXPLICITE/ # début réel de la phase
    │   ├── 00-PHASE.md                 # contexte et état actuel
    │   ├── B01-OBJECTIF-DE-LA-BOUCLE/
    │   │   ├── 00-BOUCLE.md            # progression et STOP humains
    │   │   ├── 01-CODEX-CADRAGE.md       # si cadrage réalisé
    │   │   ├── 02-CODEX-MISSION-CLAUDE.md# si mission préparée
    │   │   ├── 03-CLAUDE-IMPLEMENTATION.md # si exécutée
    │   │   ├── 04-CLAUDE-PASSATION-CODEX.md # si préparée
    │   │   ├── 05-CODEX-QA.md           # si réellement exécutée
    │   │   ├── 06-HUMAIN-DECISION.md    # uniquement si décision établie
    │   │   └── PREUVES/                # seulement si preuves externes
    │   │       ├── MANIFESTE.csv
    │   │       └── E001-TEST-SUJET.txt
    │   ├── B02-CORRECTION-CIBLEE/       # si une nouvelle boucle est autorisée
    │   ├── 70-REGISTRE-ESSAIS.md        # si des essais ont existé
    │   ├── 80-SYNTHESE.md               # à la conclusion du travail
    │   └── 90-BILAN.md                  # état de clôture et nettoyage
    └── 2026-11-08-AUTRE-SUJET/
        └── ...
```

Les exemples de dates et de noms sont illustratifs. **Ne créer que les dossiers/fichiers effectivement nécessaires.** L'index d'une phase ou d'une boucle peut être créé dès son ouverture ; les fichiers de QA et de décision ne doivent pas exister avant les faits.

## 3. Convention de nommage stable

| Élément | Nom canonique | Précision |
|---|---|---|
| Phase | `AAAA-MM-JJ-[ID-METIER-]SUJET/` | Date de début attestée, pas un numéro de rang arbitraire ; sujet explicite. |
| Boucle | `B01-SUJET/`, `B02-CORRECTION-.../` | `Bxx` croissant **dans sa phase**, sous-titre descriptif. |
| Accueil | `INDEX.md`, `00-PHASE.md`, `00-BOUCLE.md` | Courtes vues vivantes, source de navigation. |
| Rapport | `NN-AUTEUR-TYPE[-SUJET].md` | Numéro sur deux chiffres, puis rôle et type ; contexte porté par phase/boucle. |
| Synthèse | `80-SYNTHESE.md` | Résultats, limites et enseignements. |
| Bilan | `90-BILAN.md` | État, décision attestée, suite, nettoyage. |
| Essais | `70-REGISTRE-ESSAIS.md` | Créé dès le premier essai/copie/VM/simulateur. |
| Preuve | `PREUVES/E001-TYPE-SUJET.ext` | `E001` croissant dans la boucle, avec manifeste. |

Pour un cycle Codex / Claude Code standard, les étapes possibles sont : `01-CODEX-CADRAGE.md`, `02-CODEX-MISSION-CLAUDE.md`, `03-CLAUDE-IMPLEMENTATION.md`, `04-CLAUDE-PASSATION-CODEX.md`, `05-CODEX-QA.md`, `06-HUMAIN-DECISION.md`. **Ce sont des emplacements conditionnels**, non des fichiers à fabriquer. Un projet utilisant d'autres agents conserve les mêmes types de traces, avec les rôles réellement employés (`NN-AGENT-ROLE.md`) ; la norme n'oblige pas à utiliser Claude ou Codex.

Pas de `(1)`, `(2)`, `final-final`, `02b`, `03b`, suffixes temporels imaginaires ni réutilisation d'un numéro. Si le même auteur produit une nouvelle pièce dans la même boucle sans nouvelle correction, attribuer le **prochain** `NN` disponible et un intitulé précis. Les exports hors de leur dossier peuvent être préfixés par l'ID du projet, de phase et de boucle **uniquement à l'export**, pour éviter les collisions de téléchargements.

Une phase dont le début historique n'est pas datable avec certitude est classée avec une **date non établie documentée**, sans inventer une date. Dans les nouveaux travaux, enregistrer la date d'ouverture dès le début.

## 4. Responsabilités, transmissions et autorisations

Circuit usuel, lorsque Codex et Claude Code sont utilisés :

```text
HUMAIN (mandat) → CODEX (cadrage/mission) → STOP
HUMAIN (lit, autorise, transmet personnellement)
→ CLAUDE CODE (travail + rapport + passation) → STOP
HUMAIN (lit, autorise, transmet personnellement)
→ CODEX (QA indépendante et verdict) → STOP
HUMAIN (décide : clôture, correction, report, Git, publication)
```

- **Aucun appel, lancement ni transfert inter-agents automatique**, même via outil, sous-agent, API, script, CI ou automatisation.
- Un document préparé n'est pas nécessairement transmis ; `transmis: true` exige une preuve d'acte humain, non l'existence d'un fichier.
- Une QA technique ne clôt pas la phase et ne vaut ni autorisation Git ni déploiement. Une autorisation Git doit être explicite et correspondre aux opérations réellement demandées.
- Codex n'engage pas de correctif applicatif sur la seule base d'un PASS/FAIL ; le passage humain décide de la suite. Les tâches ciblées restent proportionnées : ne pas répéter inutilement un audit complet ou les mêmes campagnes.
- Si des règles du projet prévoient un autre circuit expressément validé, **ne pas créer de fausses interventions Codex/Claude** : conserver le responsable réel et le contrôle humain prévu.

## 5. Contenu minimal de chaque pièce

Les nouvelles pièces documentaires contiennent un front matter ou équivalent :

```yaml
---
trace_id: "PROJET:PHASE:B01:02"       # unique, persistant
phase: "2026-11-07-ID-SUJET"
boucle: "B01-OBJECTIF"
sequence: 2
auteur: "CODEX"                     # ou l'auteur attesté
fonction: "MISSION-CLAUDE"
date: "2026-11-07"
statut: "PREPARE"                  # état de cette pièce, pas QA
transmis: false                    # preuves de transmission requises
source_ref: "NON_ETABLI"           # SHA/branche si Git existe
---
```

- Nom et date attestés ; quand inconnus, `NON_ETABLI`, jamais une reconstruction fictive.
- Objectif, faits vs hypothèses, périmètre/exclusions, contexte de référence Git **ou hors Git**, actions réellement faites ou demandées, commandes/tâches et résultats, preuves, limites, statut, prochaine action **autorisée**.
- QA : verdict distinct (`PASS`, `PASS_AVEC_RESERVES`, `FAIL`, `INCOMPLET_ENV`, `BLOQUE_HUMAIN`) ; ne pas transformer `NON_TESTE` en succès. Le rapport initial garde son verdict après correction ultérieure.
- Décision humaine : pièce seulement si une décision réelle est attestée ; source, date, portée et restrictions. Une proposition n'est pas une décision.
- Fichiers de retour : mission autonome, chemin exact à lire, faits vérifiés et différences, critères et tests de la prochaine étape. Le chat indique le chemin et un résumé court ; aucun agent ne transmet lui-même la mission au suivant.

Ne jamais consigner de secrets, clés, tokens, mots de passe, données personnelles ou données utilisateurs dans les rapports/preuves.

## 6. Preuves

Créer `PREUVES/` **uniquement** lorsqu'une pièce probatoire distincte du rapport est réellement produite ou référencée. Un `MANIFESTE.csv` unique comporte :

```csv
preuve_id,chemin_relatif,type,horodatage,essai_id,environnement,commande_ou_methode,resultat,sha256_ou_NON_MESURE,retention
```

Chaque preuve doit être rapportée à la bonne **boucle**, avec une date, son contexte de test (simulation/local/navigateur/appareil réel/VM/production), la commande utile, un résultat observable et les limites. Si une preuve volumineuse reste hors dépôt : référencer l'emplacement stable et son empreinte quand c'est pertinent, **ne pas importer** les caches et archives géants juste pour fabriquer une trace. Une preuve absente ne devient pas « PASS ». Conserver les artefacts nécessaires à la reproduction et la QA, pas chaque byte de chaque build régénérable.

## 7. Index, histoire et clôture

- `docs/agent-runs/INDEX.md` : toutes les phases dans l'ordre de **début attesté**, avec parallélismes/dépendances, statut, dernière décision/QA réellement valide, prochaine action humaine.
- `00-PHASE.md` : objectif, début attesté, état et liens vers les boucles. `00-BOUCLE.md` : les pièces dans leur ordre réel, décisions de transmission et QA.
- `80-SYNTHESE.md` : résultats, échecs, solutions retenues/refusées, ce que les essais ont appris, risques résiduels ; peut être provisoire.
- `90-BILAN.md` : état opérationnel, décisions humaines établies, prochaine action, registre des environnements en cours/nettoyés/protégés, mesure réelle d'espace libéré. Ne pas déclarer une phase `CLOTUREE` tant que la décision humaine attendue n'est pas établie.
- En fin de boucle : synthèse courte et mise à jour de l'index ; pas de nouveau dossier pour un simple arrêt de l'agent.

**Aucun dossier « vide pour plus tard »**. Les répertoires vides ou ne contenant que `.DS_Store` dans les traces doivent être signalés et, si autorisés et sans dépendance contractuelle, retirés. Ne jamais nettoyer automatiquement des `docs/` métier voisins ou des dossiers Git/build pour améliorer une métrique.

## 8. Migration historique : une seule fois, et seulement si nécessaire

Quand un historique existe déjà, ne réexécuter **aucune** restructuration totale sans besoin explicite. Si l'utilisateur demande sa mise en conformité :

1. Lire l'index existant, les décisions et les rapports précédents du **projet courant**, sans recherche extérieure.
2. Construire un mapping unique des chemins réellement changés et le plan par phase/objectif, sans supposer une chronologie artificielle.
3. Sauvegarder les préimages pertinentes, y compris les fichiers non suivis, et vérifier leur intégrité ; respecter les protections Git applicables.
4. Renommer et déplacer **les originaux si nécessaire**, corriger les liens actifs, ancres, scripts, références et règles d'agents. Conserver les données de preuve brutes datées comme traces, et les traduire par la correspondance.
5. Supprimer uniquement les alias purement redondants après preuve d'absence de contenu unique et récupération possible ; aucun effacement de décision, QA, rapport ou preuve originale.
6. Faire un seul contrôle consolidé (liens locaux, collision Unicode/casse, dossiers vides, statut Git, conservation des verdicts et registres).
7. Livrer une courte synthèse et un registre de migration **dans la phase documentaire concernée**, sans créer un second système de navigation.

Le déplacement, le renommage et la réparation des références sont autorisés **uniquement dans le périmètre documentaire explicitement approuvé**. L'installation de ce kit n'autorise pas à elle seule une suppression, une purge de quarantaines, un commit ni un push.

## 9. Coexistence avec les consignes spécifiques

Cette norme est la **référence commune de classement et de traçabilité**. Elle ne remplace pas les règlements de sécurité, architecture, vie privée, pédagogie, test navigateur, signature, QA matérielle ou CI/CD d'un projet.

- Conserver `AGENTS.md`, `CLAUDE.md`, `AGENT_WORKFLOW.md`, `README.md` et autres entrées obligatoires **à leurs chemins reconnus** ; y ajouter, lors d'une adaptation autorisée, un renvoi court vers `docs/UNIVERSAL.md` et remplacer seulement les prescriptions contradictoires de nommage.
- Les instructions techniques et la sécurité du projet prévalent pour leurs domaines. Les règles documentaires de ce kit prévalent pour les **nouvelles traces**, sauf arbitrage humain explicite.
- Toute contradiction réelle est signalée et résolue localement, sans fusion massive ni réécriture de consignes historiques figées.

## 10. Efficacité et contrôle

Un agent doit éviter les centaines de contrôles et de rapports de migration répétés : **réutiliser les références stables et vérifier seulement le delta**, puis un contrôle final consolidé. `docs/UNIVERSAL/OUTILS/verifier.py` fournit une vérification **en lecture seule** du nommage, des fichiers structurants, des liens locaux détectables et des dossiers vides ; ce n'est pas une QA applicative ni une garantie absolue de toutes les URLs ou liens dynamiques.

## 11. Référence complémentaire

Lire [`04-ESSAIS-ET-NETTOYAGE.md`](04-ESSAIS-ET-NETTOYAGE.md) pour le cycle de vie des environnements de test : recensement dès création, bilan après QA, protection des travaux uniques et suppression sur autorisation ciblée.
