> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Navigation, caractéristiques et rapports — cinquième passe UX

1er novembre 2026, après les captures de 11:07–11:12.
Suite de [la quatrième passe](VALIDATION-UX-RETOURS-4-v0.3.0.md).

**Corrections locales ; 211 tests réussis sous Python 3.10 et 3.12.
Paquet macOS de recette reconstruit. Aucune publication.**

## Réponse aux retours

1. Le choix d’imprimante possède une flèche explicite, dessinée indépendamment du sous-contrôle natif masqué par les styles Qt. Les autres listes utilisent un chevron SVG embarqué.
2. Ce choix ouvre une fenêtre recherchable : cartes, titres en gras, descriptifs existants et photos officielles lorsqu’elles sont disponibles. Les modèles sans photo ont leurs initiales ; aucune image de modèle n’est inventée. « Choisir » confirme ; « Annuler » conserve le choix précédent.
3. La bobine devient courte, avec des flasques parallèles de même taille et un axe commun en projection orthographique. Les ellipses sont moins écrasées ; le HEX et l’état inconnu restent inchangés. C’est une illustration, pas la géométrie physique de la bobine achetée.
4. Les matières suivent l’alphabet, avec un champ de recherche dédié. Réinitialiser vide cette recherche aussi, sans supprimer les favoris.
5. Le défilement de la fiche apparaît seulement en cas de dépassement. Le pied d’export suit la largeur du viewport, barre présente ou absente.
6. « Impression » devient **Caractéristiques**. **Modifier…** et **Détails et sources** forment une paire de même hauteur et largeur sous les quatre valeurs. Les commandes d’export directes sont conservées.
7. **Paramètres → Bobines** contient masse et format préférés. **Export** contient les options du fichier, dont la priorité Orca. Les préférences existantes sont conservées, sans migration de clés.
8. État du catalogue et actualisation partagent des compteurs et des cartes de sources. Dates lisibles et statuts français remplacent le texte brut ; stockage et détails techniques sont dépliables. Une actualisation partielle reste explicitement partielle.
9. Règle de dimensions : commandes standard de **32 px logiques**, export principal de **48 px**, icônes de **26 px** dans leur groupe de 32 px. Les paires de fiche sont égales ; les menus partagent hauteur de contenu et marges. Ces règles visent l’alignement par rôle, pas une largeur identique pour tous les libellés.

README, guide UX, démarrage du wiki, changelog et roadmap sont actualisés.
Ni les données source ni les règles de fusion/NFC/compatibilité des imprimantes ne changent.

## Vérifications exécutées

| Vérification | Résultat |
| --- | --- |
| macOS ARM64, Python 3.10.20, PySide6 6.11.3 | 211 tests, 12,565 s, OK |
| macOS ARM64, Python 3.12.13, PySide6 6.11.3 | 211 tests, 11,418 s, OK |
| Répétition 3.10 avant le dernier ajustement de hauteur d’export | 211 tests, 11,422 s, OK |
| Nouveaux tests | Huit : choix/recherche/annulation d’imprimante, adaptation des cartes, recherche matières et favoris, défilement et bords d’export, actions de fiche et hauteurs, onglets Bobines/Export, rapport structuré, actualisation partielle |
| Reproduction initiale | Six cas avant correction : cinq échecs et une erreur (nouveau navigateur absent) |
| Contrats historiques | Tests des 1 008 exports, R1–R4, correction locale et préférences conservés et exécutés |
| Captures natives du code | Cocoa, Fusion et police réelle ; 1360 × 860 et 1000 × 720, clair/sombre, grille, matériel, navigateur et recherche, sources, rapports, paramètres, JSON |
| Paquet extrait | Capture native de la fiche à 1000 × 720 et du matériel, recherche Prusa et choix ; assertions des bords, actions 32 px, export 48 px et présence du chevron embarqué |
| `git diff --check` | OK |

Les suites et captures bloquent le réseau et utilisent des copies isolées.
Une première suite 3.10 s’est immobilisée dans la boucle Qt et a été interrompue ;
la cause précise n’a pas été établie. Les fixtures GUI refusent maintenant
explicitement le réseau, pour empêcher une demande de consentement différée au
milieu d’un test. Le test réel de restauration/démarrage conserve son propre
consentement et son timer réel. Les suites complètes ci-dessus passent ; aucun
test n’est retiré. Les risques historiques Qt restent documentés dans les rapports précédents.

Des essais intermédiaires du harnais gelé ont été invalidés : dépendance de test
`unittest` absente du binaire, puis réutilisation d’une fixture déjà peuplée et
d’une extraction précédente. Le harnais final ne dépend pas de `unittest` et
vérifie la nouvelle archive sur une fixture vierge et une nouvelle extraction.
Ces essais intermédiaires ne sont pas comptés comme des validations réussies.

## Archive et intégrité

Paquet : `dist/test-ux-v0.3.0-r5/SpoolScribe-macos.zip`.

SHA-256 : `9ba19e2718f4264231d1132efffaca6f209f2f17fa7f0716e6ae7e1049a7f6ef`.

- Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Une seule `.app` à la racine ; version 0.3.0, Mach-O, permissions, chemins et CRC vérifiés : **582 entrées**.
- **191 ressources** comparées au dépôt ; catalogue et profils Orca exclus de l’installateur.
- Probes gelés hors ligne : première installation vide, fixture écrite/relue, exports NTAG215/216, 147 chemins de logos, rendu des trois marques historiques, trois photos et bobine connue/inconnue.
- TLS : vérification des certificats et du nom d’hôte active ; 128 racines par défaut, 118 racines embarquées. Aucun téléchargement HTTPS réel n’est revendiqué.
- Signature ad hoc vérifiée et démarrage hors ligne de six secondes, arrêté volontairement. Pas de signature Developer ID ni de notarisation.
- Les **219 fichiers protégés** du début de passe, dont **48 profils Orca**, sont identiques par SHA-256. Le chevron est un nouvel asset d’interface ; aucun catalogue n’est modifié.
- Base et réglages personnels identiques aux copies initiales. Les captures utilisent une copie de la base actuelle ; les données d’échec du rapport partiel sont une simulation hors ligne explicitement construite.

Les logs contiennent les avertissements Qt de plateforme offscreen et d’alias de
police. Le lancement natif gelé peut émettre un avertissement macOS
`sandbox_extension_issue_file_to_process`; les contrôles de rendu et de géométrie
terminent néanmoins avec le code 0.

Branche `feature/universal-catalogue`, HEAD
`fba000b69048cf9e595274cdc253d5eb3ceacfce`, index vide. Anciens paquets conservés.
Aucun commit, push, tag, PR, fusion ou release ; application installée non remplacée.

Restent non exécutés : acceptation humaine de ce paquet, CI distante Windows/Linux
et tests physiques NFC. Les dimensions testées ne couvrent pas tous les écrans,
facteurs d’accessibilité et longueurs de texte possibles.
