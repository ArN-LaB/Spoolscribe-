# États dépliés et stabilité des mises en page — sixième passe

1er novembre 2026, suite aux captures de 11:32–11:35.
Suite de [la cinquième passe](VALIDATION-UX-RETOURS-5-v0.3.0.md).

**Corrections locales, 217 tests réussis sous Python 3.10 et 3.12,
archive macOS reconstruite et contrôlée. Aucune publication.**

## Défauts reproduits et corrections

- **Stockage** : une liste technique de 100 lignes faisait agrandir une fenêtre de 600 × 460 à **600 × 1 956**. Une page technique défilante de **140 px** remplace maintenant la liste des sources dans l’espace existant. « Retour aux sources » ramène à la liste ; Fermer reste accessible. Le rapport principal conserve ses compteurs et ses dates lisibles.
- **Recherche d’imprimante** : les widgets enfants accumulaient des hauteurs minimales lors des redimensionnements. Le rendu des lignes est désormais calculé directement selon la largeur, avec titre et description rapprochés en haut, photo de taille fixe et texte enveloppé. Contrôle sur une séquence 440 → 900 → 440 → 700 → 440 px ; hauteurs bornées et largeur contenue dans la liste.
- **Correction des caractéristiques** : une grille commune aligne les six champs ; boutons « Annuler » et « Enregistrer », hauteur standard. La portée sur toutes les références du produit reste explicitement indiquée. Aucun enregistrement réel n’est effectué pendant la recette.
- **Favoris** : titre sur une ligne propre, puis deux commandes de largeur égale, alignées sur la recherche fabricant. « Effacer » garde sa fonction de réinitialisation sans supprimer les favoris enregistrés.
- **Provenance** : encadré distinct, libellés et valeurs alignés en haut ; le dépliage amène les informations dans la partie visible. Les valeurs ne sont pas modifiées.
- **Bobine** : toutes les pièces dérivent d’une même projection de sections circulaires et d’un axe commun. Flasques, moyeu, ouvertures et enroulements partagent cette géométrie ; rayons moulés plus larges. HEX et transparence de l’illustration conservés. Ce dessin ne prétend pas reproduire la bobine commerciale exacte.
- **Pied de fenêtre** : marges du statut resserrées et poignée native retirée. Les trois commandes d’export restent directement accessibles ; export 48 px, commandes standard 32 px.

README, guide UX, changelog et roadmap mis à jour. La compatibilité imprimante,
les payloads NFC et les règles de protection/fusion du catalogue restent inchangés.

## Vérifications exécutées

| Contrôle | Résultat |
| --- | --- |
| Python 3.10.20, Qt/PySide6 6.11.3, macOS ARM64 | **217 tests**, 17,861 s, OK |
| Python 3.12.13, Qt/PySide6 6.11.3, macOS ARM64 | **217 tests**, 15,546 s, OK |
| Reproduction initiale | Cinq nouveaux tests, cinq échecs avant correction |
| Nouveau contrôle de contraste | Échec intermédiaire reproduit avant correction, puis inclus dans la suite finale |
| Contrats des 1 008 exports, R1–R4, préférences et correction locale | Tests existants conservés et exécutés |
| Captures natives du code | Cocoa + Fusion + police du démarrage ; fiche, provenance ouverte, édition, stockage ouvert, navigateur 440/620/900 px, clair/sombre, matériel, paramètres, menu et JSON |
| Paquet extrait | Rendu natif et assertions de géométrie ; recherche Prusa, provenance, stockage ouvert borné et formulaire français aligné |
| `git diff --check` | OK |

Les deux tests existants du navigateur ont été adaptés au rendu par delegate :
ils vérifient toujours les résultats, la sélection/annulation et le confinement
des lignes. Aucun test n’est retiré ou désactivé.

Un premier rendu du nouveau delegate utilisait un fond noir issu de la palette du
widget transparent. Le contrôle pixel l’a reproduit (luminosité 0), puis la surface
explicite clair/sombre l’a corrigé. Les captures finales ont été refaites. Les
avertissements habituels de plateforme offscreen et d’alias de police restent
présents ; aucun échec dans les suites finales. Les limites historiques des bindings
Qt ne sont pas considérées comme définitivement résolues par cette passe.

## Archive et préservation

Paquet local : `dist/test-ux-v0.3.0-r6/SpoolScribe-macos.zip`.

SHA-256 : `c8ca271e0561b3349bf98e2bf0c679a7758c2f8f45e5ff3ea3bd3a2abcc28041`.

- Build : Python 3.12.13, PyInstaller 6.22.3, PySide6/Shiboken6 6.11.3, certifi 2026.10.23.
- Archive : une seule `.app`, **582 entrées**, Mach-O/version/permissions/CRC/chemins vérifiés ; **191 ressources** identiques au dépôt. Catalogue et profils Orca absents de l’installateur.
- Probes gelés hors ligne : première installation vide, fixture écrite/relue, exports NTAG215/216, 147 chemins de logos, rendu des trois marques historiques, trois photos et bobines connue/inconnue.
- TLS : contrôle du certificat et du nom d’hôte actif ; 128 racines par défaut, 118 embarquées. Aucun téléchargement HTTPS réel revendiqué.
- Signature ad hoc vérifiée ; démarrage hors ligne de six secondes puis arrêt volontaire. Pas de signature Developer ID ni de notarisation.
- **220 fichiers protégés**, dont les **48 profils Orca**, comparés par SHA-256 : inchangés. Base et réglages personnels identiques aux copies initiales. Les captures utilisent une copie isolée ; aucun accès réseau réel pendant les tests.

HEAD `fba000b69048cf9e595274cdc253d5eb3ceacfce`, branche
`feature/universal-catalogue`, index vide. Tous les anciens rapports/paquets restent
accessibles. Application installée non remplacée ; aucun commit, push, tag, PR,
fusion ou release.

Restent à effectuer : acceptation humaine de cette nouvelle recette, CI distante et
builds Windows/Linux, NFC physique. Les dimensions contrôlées ne prouvent pas toutes
les combinaisons d’écrans, de polices et de réglages d’accessibilité.
