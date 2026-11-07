# Cycle de vie universel des essais et nettoyage raisonné

**Version : 4.0 — 2026-11-07.** Ces règles valent pour les copies de projet, laboratoires, clones, worktrees, caches, builds, environnements virtuels, VM, containers, navigateurs, Xcode, simulateurs et autres bancs d'essai ; elles n'imposent aucun outil spécifique.

## 1. À la création

Quand un essai crée une ressource distincte, enregistrer **immédiatement** son `T001`, le projet courant, la phase/boucle, l'objectif, l'auteur, le chemin absolu réel, la source/révision, le processus éventuel, son état et les conditions de fin de vie. Ne pas multiplier les copies complètes pour de simples tests répétables si un build isolé ou une fixture suffit.

Le registre de phase est `70-REGISTRE-ESSAIS.md` ou un journal technique existant référencé depuis celui-ci. Un essai terminé n'est pas « supprimé de l'histoire » : son résultat, sa conclusion et l'emplacement de ses preuves restent lisibles.

## 2. Après un essai, une QA ou la fin de phase

Vérifier que les résultats utiles, erreurs, conclusions, décisions, diffs uniques et preuves nécessaires à la reproduction sont conservés **hors de la copie à nettoyer**. Préciser si la copie possède du code non intégré, des branches/commits uniques, données, secrets, profils, identifiants ou dépendances de tests encore ouverts.

Classement :

- `ACTIF` : utilisé par un processus ou une campagne encore en cours ; ne pas toucher.
- `CONSERVER` : essentiel à la reproduction, à une QA en attente ou unique.
- `PARTAGE` : partagé avec d'autres étapes/projets ; ne pas traiter comme un temporaire exclusif.
- `INCERTAIN` : origine, diff ou utilité non démontrés ; conserver en l'état.
- `NETTOYABLE_APRES_ACCORD` : redondance et absence de valeur unique démontrées ; attente d'autorisation ciblée.
- `QUARANTAINE` : déplacement réversible, manifeste de restauration obligatoire, **aucun gain disque revendiqué par défaut**.
- `NETTOYE` : action de suppression attestée, chemin exact et mesure réelle du résultat.

## 3. Qui peut nettoyer quoi ?

**À la fin d'une exécution**, l'agent ferme uniquement **ses propres** processus, sessions, sockets, serveurs et profils temporaires, dont il a prouvé la propriété et le cycle de vie. Le mandat doit autoriser le retrait de la ressource créée. Pas de fermeture d'une instance utilisateur préexistante ni de `pkill`, `killall` ou suppression par motif large.

**Après la QA**, une suppression permanente de copie complète, VM, simulateur, worktree, snapshot, cache historique partagé ou quarantaine demande une **autorisation humaine distincte et ciblée sur les chemins**, avec preuve de non-unicité et absence de travail en cours. Ne pas déduire une autorisation de suppression d'une QA PASS ou d'une clôture documentaire.

Les caches strictement régénérables peuvent être purgés seulement selon l'autorisation explicite du mandat et après contrôle d'inactivité ; des environnements inconnus restent protégés.

## 4. Copie ailleurs sur le Mac ou sur une autre machine

La recherche d'un clone extérieur au projet courant **n'est jamais automatique**. L'utilisateur doit autoriser explicitement les emplacements et le but de l'inventaire. Un simple nom ressemblant n'est pas une preuve d'appartenance : corroborer par une référence Git, un manifeste de création, une origine déclarée et/ou une correspondance de contenu pertinente, **sans consulter les projets voisins**. Ne pas suivre de liens symboliques hors racine, traverser des volumes/synchronisations non autorisés ou demander `sudo`.

Ne pas confondre deux projets parents et enfants, une copie du produit avec un dépôt wiki, une distribution signée et un cache de build, ou un profil de simulateur avec une simple ressource temporaire.

## 5. Clôture opérationnelle et espace disque

Le `90-BILAN.md` récapitule une fois : résultats de tests ; objets nettoyés ; objets en quarantaine ; objets protégés/incertains ; manifestes pour restauration ; **octets définitivement supprimés**, **espace disque disponible observé avant/après** et limites. Sur APFS, liens durs, clones et snapshots peuvent empêcher de déduire le gain réel de la seule taille logique. Déplacer dans la Corbeille sur le même volume ne libère pas l'espace à ce stade.

Aucun vidage global de Corbeille, suppression opportuniste de téléchargements/archives, ou purge générale de DerivedData, simulateurs, VMs ou snapshots. Préférer un lot consolidé d'actions qualifiées à des dizaines de micro-nettoyages. Le nettoyage doit être simple, mesuré et réversible chaque fois que possible.
