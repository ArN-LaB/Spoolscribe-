> **Archive historique.** Ce document décrit sa campagne datée, pas l’état actuel. [Documentation v0.3.5](../../README.md).

# Validation locale — ajustements UX et sources v0.3.0

Date : 31 octobre 2026. Branche : `feature/universal-catalogue`.
Base Git inchangée : `3c80d8299762a80078f96154396b45c75b9a3181`.
Travail local non commité, non poussé et non publié. Ce rapport complète, sans
le remplacer, [le rapport précédent](VALIDATION-v0.3.0-dev.md). Ses chiffres de
catalogue et de packaging décrivent un état antérieur.

## Réponses aux retours

Les treize points et leur fonctionnement sont décrits dans
[UX-v0.3.0.md](UX-v0.3.0.md) : tris dans les en-têtes, recherche et accès rapides
fabricants avec Polymaker par défaut, sources sélectionnables, colonnes
configurables, logos sans fond ajouté, export guidé par imprimante et étiquette,
réglages persistants/importables, recherche de mise à jour applicative,
vocabulaire clarifié, désélection et informations de base regroupées.

L'installateur ne contient plus de catalogue ni de profils Orca. Le premier
téléchargement constitue la base dans le dossier utilisateur. L'actualisation
des sources choisies est lancée à chaque ouverture après consentement réseau.
En cas de refus ou de panne, une base existante reste consultable ; une nouvelle
installation reste vide. Une restauration interdit l'actualisation automatique
dans la même session. Décocher une source ne supprime pas ses anciennes données.

Les fabricants ont priorité sur les données communautaires dont la provenance
est connue. Les corrections explicites de l'utilisateur restent prioritaires,
y compris une valeur inconnue volontaire ou une correction identique à la valeur
source. Les anciens champs sans provenance restent protégés par précaution.
Les identités incertaines ne sont pas fusionnées automatiquement. Les couleurs
transparentes, multiples ou volontairement inconnues ne sont pas inventées.

## Contrôles exécutés sur le code final

| Contrôle | Résultat |
|---|---|
| macOS ARM64, Python 3.10.20, PySide6/Shiboken 6.11.3 | 131 tests réussis, aucun ignoré, 7,249 s |
| macOS ARM64, Python 3.12.13, PySide6/Shiboken 6.11.3 | 131 tests réussis, aucun ignoré, 6,661 s |
| Contrat des 1 008 exports OpenSpool historiques | Identiques octet pour octet |
| Protections R1–R4 | Tests conservés et réussis : échecs/vides/partiels, restauration CLI/Qt, couleurs inconnues, concurrence |
| Données présentes au début de cette passe | 154 fichiers sous `data/` et 48 profils Orca identiques octet pour octet |
| Fichiers protégés historiques | 58 empreintes Git inchangées |
| Rapports antérieurs | Cinq rapports v0.2.2 et le rapport v0.3.0 précédent inchangés |
| Interface Qt hors écran | Rendus clair/sombre, choix Bambu et dialogue des sources inspectés ; interactions couvertes par tests Qt |
| PyInstaller 6.22.3, Python 3.12, macOS ARM64 | Compilation réussie |
| Ressources du binaire final | 173 fichiers identiques aux sources locales ; aucun catalogue, cache ou profil Orca embarqué |
| Exécutable : essai hors ligne de première installation | Base initiale vide ; une référence synthétique créée puis exportée sur NTAG215 et NTAG216 ; 137 logos vérifiés par empreinte |
| Exécutable : confiance TLS hors ligne | certifi 2026.10.23 ; 128 racines par défaut, 118 embarquées ; certificat et nom d'hôte vérifiés |
| ZIP macOS | Une seule racine `SpoolScribe.app` ; format Mach-O, version 0.3.0, permissions d'exécution et CRC vérifiés |
| Versions | `core.APP_VERSION`, `pyproject.toml`, `CHANGELOG.md` et Info.plist cohérents avec 0.3.0 |
| Git et inventaire | `git diff --check` réussi ; index vide ; aucun secret usuel, chemin personnel ou artefact de compilation détecté dans les fichiers candidats |

Commande des deux suites :

```sh
QT_QPA_PLATFORM=offscreen python -B -m unittest discover -s tests -t . -v
```

Les suites interdisent les connexions réseau. Les 22 nouveaux tests couvrent
notamment les rapprochements, la priorité des sources, les valeurs nulles
volontaires, le choix des sources, l'installation vide, la sélection NFC
automatique, les préférences, les interactions du tableau et la transparence.
Les assertions anciennes dépendant de l'affichage de toutes les marques ont été
adaptées au nouveau défaut Polymaker ; aucun test n'a été désactivé.

Les essais intermédiaires ont révélé des attentes devenues obsolètes, des ajouts
de métadonnées indésirables sur des fiches anciennes, une dépendance excessive
de l'archivage JSON à la capacité NFC et une sauvegarde des réglages susceptible
d'écraser le choix de sources d'un dialogue imbriqué. Ces points ont été corrigés
et sont couverts par les suites finales. Aucun échec ne subsiste dans ces suites.

## Collecte publique réelle, distincte des tests hors ligne

Une base vierge temporaire, distincte du catalogue et des réglages personnels,
a été constituée dans l'ordre fabricant puis compléments :

| Étape | Résultat réel |
|---|---|
| Polymaker officiel | Succès, code 0 ; 1 085 références |
| Open Filament Database | Succès, code 0 |
| SpoolmanDB | Succès, code 0 |
| Bambu Lab officiel | Succès, code 0 ; 40 familles rapprochées pour enrichissement |
| SUNLU officiel | Succès, code 0 ; 4 produits rapprochés pour enrichissement |

Résultat de cet essai : **24 388 références, 2 769 produits, 174 fabricants**.
Aucun doublon d'identité exacte détecté. Les différences de conditionnement,
diamètre, masse ou recharge sont conservées. Ce contrôle ne prouve pas l'absence
de tout doublon sémantique dans les données mondiales.

314 rapprochements OFD et 8 862 rapprochements SpoolmanDB restent en attente,
principalement faute d'identité suffisamment certaine. Ils ne sont pas ajoutés
comme variantes concurrentes. Le bilan de la base les signale ; aucun éditeur de
rapprochement manuel n'est livré dans cette passe. Les nombres sont ceux de
l'essai du 31 octobre, pas une promesse de couverture ou de stabilité des sources.

Cet essai réseau précède les derniers garde-fous sur les couleurs inconnues,
les anciens catalogues sans provenance et le repli des logos historiques. Les
parseurs réseau sont inchangés ; ces derniers garde-fous ont été vérifiés dans
les suites finales, sans répéter la collecte publique entière.

Les adaptateurs officiels ne généralisent pas une température dépendant de la
vitesse, du plateau ou de l'imprimante. Les valeurs manquantes restent inconnues.
Les nouvelles sources étudiées et les limites des adaptateurs sont détaillées
dans [DATA_SOURCES.md](../../DATA_SOURCES.md). Les recherches eSUN et Prusa n'ont pas
été présentées comme de nouveaux imports opérationnels. Aucun NAS, serveur
Spoolman personnel, firmware ou matériel RFID n'a été modifié.

## Livraison locale et preuves

Le paquet et les preuves de cette passe sont dans le répertoire local ignoré
`dist/preview-ux-v0.3.0/` : ZIP, empreinte, journaux des deux suites, captures Qt,
bilan de collecte et bilan d'intégrité. Ils ne font pas partie d'un commit.
Le ZIP contient uniquement l'application ; l'exécutable intermédiaire produit
par PyInstaller n'est pas ajouté à sa racine.

SHA-256 de `SpoolScribe-macos.zip` :

```text
595b15ee9e010bf7518a3bb416dcc8e7e4824d6f9acd2d6779009729789767ce
```

## Limites et vérifications non exécutées

- GitHub Actions n'a pas été lancé pour ces modifications locales. Le workflow
  conserve Linux/Python 3.10 et 3.12, Windows/3.12 et macOS/3.12 ; les trois builds
  dépendent des vérifications et des tests. Windows et Linux ne sont pas validés
  par le build macOS. Aucun nouveau binaire Windows/Linux n'est annoncé.
- Les rendus Qt hors écran et les tests automatisés ne remplacent pas une recette
  humaine sur un écran macOS, ni un essai de premier lancement après téléchargement.
- L'application macOS utilise une signature ad hoc, sans signature Developer ID
  ni notarisation. Les deux sondes natives ont émis l'avertissement macOS
  `sandbox_extension_issue_file_to_process ... Operation not permitted`, puis
  ont terminé avec code 0 et toutes les assertions réussies.
- PyInstaller avertit que l'association actuelle `onefile`/`.app` sera refusée
  dans sa version 7. La compilation a été faite avec 6.22.3 ; une migration du
  packaging sera nécessaire avant ce changement majeur.
- La vérification de version ouvre le téléchargement GitHub officiel. Le
  remplacement de l'application reste manuel ; aucun installateur automatique.
- Aucun essai physique SpoolFlux/NTAG215/NTAG216/U1 n'a été réalisé. L'enveloppe
  et la capacité calculées ne prédisent pas les données supplémentaires ajoutées
  par chaque logiciel d'écriture. Les exports historiques sont préservés ; la
  compatibilité exacte dépend du firmware et du lecteur réels.
- Bambu RFID et Prusa OpenPrintTag ne sont pas encodés par ce logiciel. Les choix
  d'imprimante expliquent les usages des champs et empêchent de présenter un
  export OpenSpool comme un tag propriétaire compatible.
- Les sources peuvent changer ou être indisponibles. Une source fabricant n'a
  pas systématiquement toutes les propriétés ; les données manquantes restent
  à compléter. Les logos sans visuel validé gardent un affichage textuel.
- La vérification de révision et la conservation des écritures concurrentes
  détectées ne garantissent pas une exclusion absolue d'un éditeur externe qui
  ignore le verrou.

Aucun commit, push, tag, PR, fusion ni publication n'a été effectué dans cette
passe. Les données personnelles et l'application installée n'ont pas été remplacées.
