# Seconde passe UX — SpoolScribe 0.3.0

1er novembre 2026, suite des captures utilisateur de 09:27 à 09:32.
Complément de [VALIDATION-RETOURS-v0.3.0.md](VALIDATION-RETOURS-v0.3.0.md).

**Résultat : correctifs locaux, 186 tests réussis sur les deux versions de Python, paquet macOS reconstruit. Aucune publication.**

## Défauts corrigés

| Retour | Cause et correction |
| --- | --- |
| Logos remplacés par un nom | Dans le bundle macOS, `Frameworks/data` est un lien vers `Resources/data`. Le contrôle comparait un fichier résolu à un répertoire non résolu et rejetait le chemin. Les deux sont désormais résolus. Un test autorise ce montage tout en rejetant un lien sortant du dossier de données. Le même défaut du logo de l’application est corrigé. |
| ROSA3D après un téléchargement neuf | Le logo historique dépendait des métadonnées de l’ancienne base. Les trois logos historiques ont désormais un repli vers leurs fichiers déjà embarqués. Aucun artwork, manifeste ni catalogue n’est modifié. |
| Remise à zéro incomplète | **Tout effacer**, en haut de la barre latérale, vide les deux recherches, le fabricant, la matière, l’état des données, le filtre favoris et la sélection. Les favoris enregistrés restent intacts. Polymaker demeure le choix du premier lancement ; la remise à zéro affiche tous les fabricants. |
| Position et aspect des boutons | Étoile filament près du titre, remise à zéro près des filtres, boutons secondaires arrondis et états survol/sélection visibles. Les actions d’export restent en pied de fiche. Le texte de progression est placé au-dessus de la barre et dispose de sa propre hauteur. |
| Plusieurs conditionnements et plusieurs HEX mélangés | Les teintes divergentes sont présentées par des pastilles cliquables. Après choix de la teinte, la liste des conditionnements contient uniquement les références correspondantes, avec des masses lisibles en kg. Le HEX reste en infobulle ; aucune couleur n’est fusionnée arbitrairement. La couleur affichée ne répète plus le préfixe fabricant. |
| Choix imprimante peu lisible et texte Prusa coupé | Carte avec schéma indicatif original, nom, statut OpenSpool et description du lecteur. Les libellés réservent la hauteur de leur texte après changement de largeur ou de modèle. Les contrôles NFC se masquent pour une configuration incompatible. La carte suit le thème clair/sombre. |
| Erreur d’actualisation de la liste d’imprimantes | Le fichier `main/data/printers.json` est absent de la branche publiée, vérifié par le connecteur GitHub : HTTP 404. Ce cas conserve la liste fournie avec cette version de développement et affiche « Aucune nouvelle liste publiée ». Les autres erreurs restent affichées en ligne ; elles ne deviennent pas un succès. Aucun basculement vers une branche de développement distante n’est ajouté. |
| Sources présentées comme exhaustives | Le sélecteur indique **Catalogue ouvert, non exhaustif**, le rôle des sources et leurs derniers compteurs d’analyse disponibles. Bambu Studio enrichit des caractéristiques ; SUNLU couvre actuellement le PLA de fiches existantes. Le rapport distingue **Sources actualisées** et les références non rapprochées. |

Le schéma de l’imprimante est une illustration générique, pas une photo du modèle. Une sélection de teinte sur écran n’est pas une mesure colorimétrique de la bobine. La compatibilité matérielle documentée n’a pas été élargie.

## Validation exécutée

| Contrôle | Résultat final |
| --- | --- |
| Python 3.10.20, macOS ARM64, Qt/PySide6 6.11.3 | 186 tests, 9,418 s, OK |
| Python 3.12.13, macOS ARM64, Qt/PySide6 6.11.3 | 186 tests, 8,728 s, OK |
| Contrat catalogue et 1 008 exports compacts | OK dans les deux suites |
| Régressions R1–R4 et première passe UX | Conservées et exécutées ; aucun test désactivé |
| Rendu natif macOS Cocoa | Captures inspectées : fenêtre 1360 × 860, 1000 × 720, teinte sélectionnée, imprimantes U1/Prusa, petite fenêtre avancée, sources et thème sombre |
| Changement d’imprimante dans un dialogue 510 × 360 | U1, Prusa, Bambu, sans lecteur, puis U1 ; textes et carte vérifiés par test |
| Réinitialisation et favoris | Recherches vides, filtres désactivés, aucune sélection, deux listes de favoris inchangées |
| Rafraîchissement imprimantes | 404 conserve la liste, sans avertissement d’échec ; 503 reste une erreur dans le test de service |
| `git diff --check` | OK |

Les tests refusent les connexions réseau et isolent base/configuration. Les sept premiers tests de cette seconde passe ont échoué avant correction (trois échecs et quatre erreurs), puis deux tests supplémentaires ont couvert le repli ROSA3D et le thème de la carte. Le contrôle initial du rendu gelé a révélé que l’entrée PyInstaller n’était pas importable comme un module `app_gui` ; le probe utilise maintenant Qt directement sur les chemins résolus. Il a ensuite détecté le repli ROSA3D absent, corrigé dans le code. Les vérifications finales passent toutes.

## Paquet macOS de recette

Emplacement : `dist/test-ux-v0.3.0-r2/SpoolScribe-macos.zip` et fichier `.sha256` associé.

SHA-256 : `751d6d48a9f507472c396d2e253935af46bd45b99542ea541678e5b4acf0af21`.

- Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Une seule racine `SpoolScribe.app`, exécutable Mach-O, version 0.3.0, permissions et CRC vérifiés ; 576 entrées ZIP.
- 186 ressources attendues identiques aux fichiers du dépôt ; catalogue et profils Orca absents de l’installateur.
- Les chemins des **147 logos du manifeste** sont vérifiés dans le véritable bundle. Polymaker, Prusament et ROSA3D sont décodés/rendus avec Qt, avec des pixels non transparents et un rendu HiDPI borné.
- TLS : vérification du certificat et du nom d’hôte active ; 128 racines par défaut, 118 racines embarquées. Ce contrôle n’est pas un téléchargement HTTPS complet de catalogue par le binaire.
- Probe catalogue hors ligne : première installation vide, fixture écrite puis relue, exports NTAG215/216.
- Signature ad hoc contrôlée avec `codesign --verify --deep --strict` après extraction ; application lancée hors ligne pendant six secondes puis arrêtée volontairement.

L’application installée n’a pas été remplacée. Le paquet n’est pas signé Developer ID ni notarié.

## Données, couverture et dépôt

Les **215 fichiers protégés** présents au début de cette seconde passe, dont les **48 profils Orca**, sont identiques par SHA-256. La base personnelle et la configuration personnelle sont identiques aux copies prises au début de la passe. Aucune suppression ni réécriture du catalogue réel n’a servi à résoudre les défauts d’affichage.

Cette passe ne relance pas les cinq téléchargements complets : leur exécution réelle de la première passe est documentée dans le rapport précédent. Les captures utilisent une copie isolée de cette base analysée : 24 649 références, 16 708 groupes et 165 fabricants ; 157 groupes avec des divergences de teinte et 876 rapprochements en attente. Ces chiffres ne sont pas une nouvelle mesure réseau ni une preuve d’exhaustivité. Les neuf tests supplémentaires ne résolvent pas ces ambiguïtés de données.

README, guide UX, sources, guide des imprimantes, changelog et roadmap sont actualisés. Les rapports précédents et leurs artefacts restent disponibles.

Branche `feature/universal-catalogue`, HEAD `fba000b69048cf9e595274cdc253d5eb3ceacfce`, index vide. Les changements des deux passes restent locaux. Aucun commit, push, tag, PR, fusion ou release n’a été créé dans cette passe.

Restent non exécutés : recette interactive humaine de ce nouveau paquet, CI distante et builds Windows/Linux pour ces changements, écriture puis relecture NFC sur le matériel réel. Les captures natives et probes automatiques ne valent pas acceptation humaine. Aucun service personnel Spoolman, firmware, NAS ni association RFID n’a été modifié.


## Passe visuelle suivante

Les retours de 09:55–09:58 sont traités dans
[VALIDATION-UX-RETOURS-3-v0.3.0.md](VALIDATION-UX-RETOURS-3-v0.3.0.md).
Les mesures ci-dessus restent celles de la seconde passe.
