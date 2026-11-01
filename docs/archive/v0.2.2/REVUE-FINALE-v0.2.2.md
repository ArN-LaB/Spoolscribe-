> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# SpoolScribe v0.2.2 — revue finale de non-régression

Date : 31 octobre 2026. Référence : `main`, HEAD
`5197234c68885618492039061d4228f6848d024c`. Version locale, non publiée.

**Avis : corrections nécessaires avant validation de release.** Les 59 tests
existants passent, mais les sondes complémentaires révèlent trois anomalies
fonctionnelles et une limite de concurrence. Ce rapport complète et nuance
`VALIDATION-v0.2.2.md` ; il ne constitue aucune autorisation de publication.

## 1. Périmètre et méthode

Relecture du diff complet des 29 fichiers suivis modifiés et des 16 nouveaux
fichiers d'implémentation, tests, fixtures et documentation. Attention portée
aux 13 scripts d'acquisition, à `scripts/db_io.py`, aux parcours CLI/GUI, au
packaging et au workflow CI. Comparaison des exports avec le code de `v0.2.1`.

Les essais supplémentaires utilisent des copies temporaires du catalogue et
des profils, avec sources réseau simulées. Aucun catalogue utilisateur, NAS,
serveur Spoolman, programmateur ou imprimante n'a été modifié. Les sondes
exploratoires ne sont pas ajoutées à la suite de tests dans cette revue.

## 2. Anomalies et corrections indispensables

### R1 — Une source vide peut être déclarée vérifiée avec succès

**Priorité haute.** Une réponse Spoolman `{"filaments":[]}` est non vide au sens
Python, mais ne contient aucun filament. Le véritable script Polymaker retourne
alors `unchanged`, code 0. Un index TheFilamentDB vide est également accepté
par le script multimarque. Dans une sonde du pipeline où les autres étapes
réussissent sans changement, cela produit `complete` et avance `_last_updated`,
alors que la source n'a pas été vérifiée utilement.

Points concernés : `scrape_spoolman_hex.py:205–209`,
`scrape_spoolman_multibrand_hex.py:160–167`,
`scrape_thefilamentdb_hex.py:224`,
`scrape_thefilamentdb_multibrand_hex.py:146–154`, puis `core.py:797–814`.
Autre incohérence reproduite : `sync_multibrand_assets.py:127–128` renvoie
`partial` même lorsque ses deux sources distantes échouent toutes les deux.

**À corriger :** contrôler structure et données exploitables de chaque source
avant de conclure `unchanged` ; distinguer une source valide sans nouveauté
d'une source vide/inexploitable ; distinguer échec total et résultat partiel.
Ajouter des tests avec réponses vides et index vides vérifiant le statut global
et le maintien de la date du dernier contrôle complet.

### R2 — Une restauration peut déclencher immédiatement une mise à jour

**Priorité moyenne.** En CLI, avec consentement réseau et mise à jour automatique
déjà activés, restaurer une sauvegarde ancienne appelle ensuite le contrôle
automatique de démarrage (`convert_profile.py:272–278`). Sonde reproduite avec
le vrai parcours CLI et un pipeline simulé : un appel automatique, ajout d'une
entrée après restauration, fichier final différent de la sauvegarde choisie.

La GUI présente le même enchaînement potentiel à la lecture : reconstruction
de `MainWindow` après restauration, programmation du contrôle automatique à
400 ms (`app_gui.py:464`, `:1373`, `:1549–1563`). Ce parcours GUI particulier
n'a pas fait l'objet d'une reproduction visuelle.

**À corriger :** suspendre l'actualisation automatique pendant la session de
restauration CLI et GUI, ou demander un choix explicite après restauration.
Les préférences peuvent rester enregistrées. Tester que les octets restaurés
restent ceux de la sauvegarde même si l'actualisation était activée auparavant.
Le fichier remplacé est bien conservé ; l'anomalie concerne la stabilité du
retour arrière, pas un contournement du consentement réseau.

### R3 — Les deux scripts de seed ignorent le choix de couleur manuel

**Priorité moyenne.** Les autres scripts d'enrichissement utilisent
`requires_manual_color`, mais les branches existantes des seeds Prusament et
ROSA3D remplissent tout HEX vide (`seed_prusament.py:214–215`,
`seed_rosa3d.py:265–266`). Sur copies temporaires, les SKU existants
`PM-PLA-JETBLACK` et `R3-PETG-BLACK`, avec `hex: null` et `alpha: "00"`, sont
reconnus comme exigeant une couleur manuelle par le garde commun ; les seeds
leur attribuent pourtant automatiquement `1A1A1A`.

**À corriger :** appliquer le même garde aux seeds avant de compléter une
entrée existante. Tester les couleurs volontairement inconnues avec alpha,
couleurs supplémentaires et noms signalant transparence/multicolore. Aucun
écrasement d'un HEX non vide n'a été observé lors des essais des 13 scripts.

### R4 — Le verrou ne protège pas contre un éditeur externe simultané

**Limite conditionnelle reproduite, risque de perte de correction.**
`save_db` contrôle la révision, écrit `.bak`, puis publie le nouveau fichier
(`scripts/db_io.py:195–202`). Une sonde injectant une écriture directe externe
pendant l'écriture de `.bak`, après le contrôle de révision, perd cette
correction dans le fichier final et dans `.bak`.

Le refus des écritures obsolètes fonctionne pour les écrivains utilisant le
module et son verrou. Il ne constitue pas une exclusion d'un éditeur JSON,
d'une autre ancienne version ou d'un outil de synchronisation ignorant ce verrou.

**À traiter :** préciser cette limite et éviter les éditions simultanées hors
verrou ; renforcer la détection juste avant publication et conserver une
version concurrente détectée. Une seconde vérification réduit la fenêtre, sans
garantir à elle seule une exclusion absolue des écrivains non coopératifs.
Toute promesse générale de protection des modifications concurrentes doit être
restreinte ou accompagnée d'un mécanisme adapté et de tests dédiés.

## 3. Compatibilité exacte des exports OpenSpool

Comparaison des fonctions d'export de `v0.2.1` avec la version locale, sur le
même catalogue et les mêmes 48 profils Orca, sans écriture de l'ancien code :

| Contrôle sur les 1 008 SKU à couleur connue | Résultat |
|---|---|
| Objets JSON, champs, types et valeurs | Identiques pour 1 008/1 008 |
| Ordre des champs | Identique pour 1 008/1 008 |
| Nouvelle archive lisible / ancien export lisible | Octets identiques pour 1 008/1 008 |
| Nouveau compact / ancien export lisible | Octets différents, seules les espaces de sérialisation changent sur ces données |
| Noms de fichiers | Identiques ; aucune collision parmi ces 1 008 références |

Cette équivalence ne s'étend pas aveuglément à toutes les bases personnalisées :
une densité locale de `1.2711` pour `PB05001` était remplacée par `1.3` via
Orca auparavant ; elle reste `1.2711` par défaut désormais. Le choix explicite
`--orca-overrides` restitue `1.3`. Ce changement de priorité est intentionnel.

Les 74 SKU résolubles sans HEX sont désormais refusés jusqu'au choix explicite
d'une couleur ; l'ancien code émettait `000000`. Les deux orphelins `FM01001`
et `FM01002` restent non exportables. Les validations plus strictes peuvent
aussi refuser des données personnalisées invalides auparavant sérialisables.
La compatibilité mesurée porte sur les exports ; il n'existe pas de parcours
d'import des anciens fichiers OpenSpool à valider ici. Le compact reste du JSON,
avec les mêmes métadonnées, et non un autre schéma OpenSpool.

## 4. NDEF : plus gros fichiers et marge pour SpoolFlux

Hypothèse exacte : NTAG216 avec zone disponible de **872 octets**, un seul
enregistrement MIME `application/json`, sans identifiant NDEF, TLV Type 2 et
terminateur inclus ; CC exclu. La capacité doit correspondre à celle réellement
annoncée et disponible sur l'étiquette. Voir la
[fiche NXP NTAG213/215/216](https://www.nxp.com/docs/en/data-sheet/NTAG213_215_216.pdf).

Pour les gros exports, payload JSON `L ≥ 256` : en-tête NDEF 6 + type MIME 16,
donc NDEF = `L + 22` ; TLV long 4 + terminateur 1, donc total = **`L + 27`**.
Un encodeur binaire indépendant confirme les 829 octets du maximum. Les seuils
des en-têtes courts/longs et l'UTF-8 sont couverts par les tests existants.

| SKU | Ancien JSON lisible | Compact UTF-8 | NDEF | Total Type 2 | Marge / 872 |
|---|---:|---:|---:|---:|---:|
| CA02027 — Panchroma PLA Galaxy | 908 | 802 | 824 | 829 | **43** |
| PA05007 — PolyLite CosPLA Version A | 907 | 801 | 823 | 828 | 44 |
| PA07046 — PolyLite CosPLA Version B | 907 | 801 | 823 | 828 | 44 |
| CA09003 — Panchroma PLA Glow | 903 | 797 | 819 | 824 | 48 |
| CA09020 / CA09008 / CA09009 | 901 | 795 | 817 | 822 | 50 |

Tous les 1 008 exports compacts tiennent dans cette hypothèse : JSON 389–802,
total 416–829 octets. Le plus gros ancien export lisible occuperait 935 octets
avec cet encapsulage : l'archive n'est donc pas un substitut à l'export NFC.

La marge minimale de **43 octets comprend tous les ajouts du programmateur**.
Exemples calculés indépendamment sur CA02027 :

| Ajout au fichier ou message de base | Total final | Marge |
|---|---:|---:|
| Propriété JSON `"spool_id":123` | 844 | 28 |
| Propriété JSON `"alpha":"00"` | 842 | 30 |
| Propriétés JSON `spool_id:123`, `weight:1000`, `alpha:"00"` | 871 | 1 |
| Tableau JSON de quatre couleurs supplémentaires à 6 chiffres | 892 | **Dépassement de 20** |
| Second enregistrement MIME application/json, payload de 24 octets | 872 | 0 |

Les propriétés JSON des exemples incluent leur ponctuation compacte et leurs
guillemets ; le tableau de couleurs ajoute 63 octets. Avec un second
enregistrement MIME court sans ID, 19 octets sont consommés par son en-tête
et son type : seuls 24 octets de payload restent. Un second enregistrement
Text de langue `en` peut contenir 36 octets de texte ; un URI avec un octet
de préfixe peut contenir 38 octets supplémentaires. Ces budgets ne se cumulent
pas et les caractères non ASCII peuvent occuper plusieurs octets.

Le [site officiel SpoolFlux](https://spoolflux.dingdongclick.de/) annonce
l'écriture NDEF, la relecture automatique octet pour octet et des champs
optionnels, notamment poids, diamètre et identifiant de bobine compatible
Spoolman. Il ne permet pas d'établir ici l'encapsulage exact de chaque écriture
ni le coût de tous ses ajouts. Les exemples ci-dessus sont des budgets, pas
une mesure de ce que SpoolFlux ajoute effectivement. La garantie reste donc
conditionnelle jusqu'à la relecture du message réellement écrit et l'essai U1.

## 5. Protection des corrections et intégrité après migration

Matrice exécutée sur les 13 véritables fonctions de scripts, sources simulées,
copies du catalogue et des profils. Les corrections injectées portent sur trois
marques : HEX, nom de couleur, densité, métadonnées de marque, champs libres,
notes et SKU local supplémentaire, soit 1 085 SKU.

| Scripts | Résultat sur les valeurs existantes non vides injectées |
|---|---|
| scrape_wholesale, scrape_wiki_hex, scrape_spoolman_hex, scrape_thefilamentdb_hex, scrape_internal_exact_hex | Conservées |
| sync_polymaker_brand_assets, sync_multibrand_assets | Conservées |
| seed_prusament, seed_rosa3d | Conservées ; exception des nulls intentionnels détaillée en R3 |
| scrape_spoolman_multibrand_hex, scrape_thefilamentdb_multibrand_hex | Conservées |
| download_orca_profiles, import_orca_profiles | Profils existants et corrections physiques conservés |

Douze étapes sont inchangées dans cette matrice. `sync_multibrand_assets`
complète uniquement deux chemins de logos jusque-là vides. Aucun retrait de
SKU ou perte de valeur non vide injectée n'a été constaté.

Une séquence complète migration → mise à jour partielle → restauration a aussi
été exécutée sur copies :

- Migration du bundle : aucune perte des champs locaux, y compris notes et
  couleurs nulles ; conflits consignés ; `.bak` identique à l'état précédent.
- Une étape ajoute un SKU valide, douze sources sont indisponibles : statut
  `partial`, corrections conservées, `_last_updated` ancien inchangé,
  `.pre-update.bak` identique à l'état précédant le pipeline.
- Restauration explicite de cet état puis rechargement : octets identiques à
  la sauvegarde ; état remplacé conservé dans `.before-restore-*`.
  Cet essai du stockage exclut le déclenchement automatique décrit en R2.

Les écritures atomiques, refus d'une base corrompue, d'une suppression de clés,
de nouveaux orphelins et d'une révision obsolète sont couverts par la suite.
La fusion du bundle préserve les valeurs locales existantes, même nulles.
La migration n'invente pas de produit pour les deux orphelins historiques.
Les mises à jour partielles restent volontairement appliquées : il n'existe
pas de transaction globale couvrant catalogue, logos et profils. `.bak`
conserve la révision précédente et `.pre-update.bak` le début du dernier
pipeline ; ce ne sont pas des historiques immuables de toutes les versions.

## 6. Vérifications, risques résiduels et état du dépôt

- Suite relancée : **59/59 tests réussis** sur Python 3.12.13 et **59/59** sur
  Python 3.10.20, macOS ARM64 avec PySide6 6.12.0, GUI offscreen.
  Commande : `python -B -m unittest discover -s tests -t . -v`.
- Les nouvelles sondes R1–R4 montrent les limites de cette couverture : les
  résultats PASS existants ne lèvent pas ces anomalies.
- Relecture CI/packaging : tests requis avant les builds, dépendances de build
  contraintes et module de stockage embarqué. Aucun workflow distant lancé.
  Le build local relaté dans `VALIDATION-v0.2.2.md` n'a pas été reconstruit ici.
- GitHub Actions, binaires Windows/Linux, essai visuel humain macOS et recette
  SpoolFlux/NTAG216/Snapmaker U1 : **NON MESURÉS dans cette revue**, différés
  conformément à la demande. Aucun résultat matériel ne se déduit du calcul.
- Sources réseau réelles : non actualisées pendant la revue. Les garanties
  après panne matérielle ou coupure d'alimentation ne sont pas mesurées par
  les simulations d'interruption logicielle.

Catalogue réel inchangé : **1 084 SKU, 91 produits, 48 profils Orca** ; 76 HEX
manquants dont les deux SKU orphelins. SHA-256 de `data/polymaker_db.json` :

```
ddf48fbbaf9addf3c8751e6d69ea2daae0d061d8bb2a595f4b62d1fcb164cc35
```

État Git : branche `main`, HEAD inchangé ; aucune divergence avec la référence
locale `origin/main` (sans nouvelle interrogation distante). Index vide.
Les 29 fichiers suivis modifiés et 16 nouveaux fichiers d'implémentation
préexistants restent non commités ; ce rapport est le 17e fichier nouveau.
Le contrôle des empreintes confirme qu'aucun de ces fichiers ni le catalogue
n'a été modifié pendant cette revue. `git diff --check` ne signale pas d'erreur.

**Aucune correction appliquée, aucun commit, push, tag, release ou publication.
STOP : revue terminée, attente de validation humaine avant toute suite.**
