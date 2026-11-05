# OpenTag3D — SpoolScribe v0.8.0 Pre-release

[Documentation](README.md) · [Installations de lecture](PRINTER-CONFIGURATIONS.md) · [Formats NFC](FORMATS-NFC.md) · [Validation](validation/v0.8.0.md)

**Disponible dans la [préversion v0.8.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0).**
La version stable v0.3.5 continue à exporter OpenSpool uniquement. Cette préversion
ajoute OpenTag3D **2.004** ;
elle ne remplace pas OpenSpool et n’ajoute pas OpenPrintTag.

## Choisir le matériel avant le format

Dans **Mon matériel**, choisissez le lecteur et le logiciel effectivement installé.
La liste des formats se limite à ceux déclarés pour cette configuration.

| Configuration choisie | Formats proposés |
| --- | --- |
| U1, paxx12 avec détection par défaut | OpenSpool 1.0 |
| U1, paxx12 avec détection OpenRFID | OpenSpool 1.0 ou OpenTag3D 2.004 |
| Lecteur OpenTag3D explicitement compatible | OpenTag3D 2.004 |
| Bambu AMS, Prusa OpenPrintTag et autres formats natifs non pris en charge | Consultation de la fiche ; aucun nouvel export activé |

OpenRFID est un système de lecture ; OpenSpool et OpenTag3D sont des formats. Les modes OpenRFID et OpenRFID Generic de paxx12 lisent les deux.

Le support OpenTag3D de la U1 est décrit pour **OpenRFID**, pas pour le système de
détection par défaut. Vérifiez la version installée et la documentation de ce
lecteur. Aucun firmware ou réglage d’imprimante n’est modifié par SpoolScribe.

## Préparer une étiquette

1. Sélectionnez le filament, sa teinte et son conditionnement réel.
2. Dans **Mon matériel**, choisissez **OpenTag3D 2.004**, votre NTAG215/216 et
   le type de fichier accepté par le logiciel d’écriture.
3. Cliquez **Préparer l’étiquette…**. Confirmez la masse et les températures
   cibles ; adaptez explicitement les libellés trop longs.
4. Vérifiez l’aperçu, puis exportez vers le dossier choisi. Une confirmation
   indique le fichier enregistré.
5. Importez le fichier dans le logiciel d’écriture correspondant, écrivez le tag,
   relisez-le, puis contrôlez les valeurs détectées par le lecteur.

Les paramètres confirmés sont mémorisés **par référence de bobine**, dans les
réglages utilisateur. Le catalogue source reste intact ; une actualisation ne
remplace pas ces paramètres. Exporter/importer les réglages conserve également
le logiciel du lecteur, le format et le type de fichier.

## Informations à confirmer

| Information | Règle |
| --- | --- |
| Température cible de buse et de plateau | Pas de milieu de plage choisi automatiquement. Valeurs explicites, dans les bornes renseignées. |
| Température d’enceinte | Aucune valeur inventée ; `0` signifie absence de chauffage, à confirmer. |
| Masse | Masse de filament, hors bobine vide ; pas une masse restante mesurée. |
| Températures encodées | Multiples de 5 °C. Une valeur non représentable est refusée, jamais arrondie silencieusement. |
| Noms | Longueurs UTF-8 contrôlées ; aucune troncature automatique. Fabricant : 16 octets ; matière et variante : 5 chacun. |
| Couleurs | Quatre RGBA au total. Une couleur inconnue doit être confirmée ; aucune couleur supplémentaire n’est supprimée pour faire tenir le tag. |
| Référence fabricant | Utilisée seulement si fournie ; un identifiant OFD/Spoolman n’est pas transformé en référence fabricant. |

Les bornes de températures sont facultatives dans OpenTag3D : une borne inconnue
reste absente. Diamètre et densité doivent être connus. Les champs optionnels non
pris en charge dans cette première intégration restent non renseignés.

## Fichier à utiliser

| Choix | Contenu | Destination |
| --- | --- | --- |
| **NFC Tools mobile (.json)** | Profil d’import contenant le message binaire dans son enveloppe base64 | Import de profils de l’application mobile ; recette réelle à effectuer |
| **NFC Tools Desktop (.json)** | Profil d’import avec le type MIME et les octets du payload | Ouverture du fichier par NFC Tools Desktop ; recette réelle à effectuer |
| **Message NDEF brut (.ndef)** | Un message NDEF binaire complet | Logiciel capable d’importer ce type de fichier, à vérifier |

Un profil `.json` NFC Tools n’est **pas** un JSON OpenSpool. Il doit être importé
comme profil, pas écrit comme un simple enregistrement texte. La compatibilité
avec l’import de fichiers SpoolFlux n’est pas établie par cette intégration.

**Voir l’export** affiche exactement le JSON du profil généré. Pour le fichier
binaire `.ndef`, l’aperçu montre les champs décodés et les octets hexadécimaux.
Le fichier brut ne contient ni UID, ni mémoire constructeur, ni Capability Container.
SpoolScribe n’écrit pas directement le tag.

Le payload fait 224 octets, le message NDEF 248 et l’occupation avec TLV/terminateur
251 octets, avant les ajouts éventuels du logiciel d’écriture :

| Tag | Zone NDEF standard | Marge avant réserve utilisateur |
| --- | --- | --- |
| NTAG215 | 496 octets | 245 octets |
| NTAG216 | 872 octets | 621 octets |

Le contrôle refuse une réserve qui fait dépasser cette capacité. La taille du
fichier JSON/base64 sur disque n’est pas l’occupation mémoire du tag.

<details>
<summary><strong>Terminal et paramètres explicites</strong></summary>

Créez un fichier local, par exemple `etiquette.json` :

```json
{"print_temp": 210, "bed_temp": 60, "chamber_temp": 0, "weight": 1000}
```

Ces nombres sont un exemple de saisie, pas des recommandations universelles.
Depuis une installation source :

```sh
python -m spoolscribe.convert_profile --nfc-format opentag3d \
  --printer opentag3d --firmware any --tag-type NTAG215 \
  --opentag-output nfctools-mobile --opentag-settings etiquette.json
```

Saisissez la référence du catalogue, puis confirmez l’export. Les températures
cibles et la masse manquantes sont demandées lorsqu’elles n’ont pas été fournies.
Pour la U1/OpenRFID : `--printer u1 --firmware paxx12_openrfid`.
`--opentag-output nfctools-desktop` et `ndef` sélectionnent les deux autres sorties.
L’archive historique reste OpenSpool ; la combinaison OpenTag3D/archive est refusée.

</details>

## Spécification et portée de la validation

- [Spécification OpenTag3D](https://opentag3d.info/spec.html) et
  [schéma machine](https://opentag3d.info/spec.json), version 2.004, révision
  `5e5069cf5696e03bdd328e7bc3d15ee2fde97909`. Les mises à jour nécessitent une revue ;
  aucun téléchargement de schéma ne se produit à l’exécution.
- [Outil officiel de création et fichiers d’écriture](https://opentag3d.info/make).
- [Détection RFID U1](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md) ;
  la branche de développement documente les capacités, sans prouver le firmware installé.
- [Décodeur OpenRFID épinglé](https://github.com/suchmememanyskill/OpenRFID/tree/a13bc9e181374e182f61db4e69abf9fa1786cc29/src/tag/opentag3d).

L’encodeur SpoolScribe est une implémentation indépendante fondée sur les champs
et unités du standard. Aucun code du site OpenTag3D ou d’OpenRFID n’est embarqué.
Les essais logiciels et leurs limites sont détaillés dans le
[rapport de validation](validation/v0.8.0.md). La validation physique des imports,
des tags et des imprimantes reste à réaliser avant de revendiquer leur recette.

## Températures proposées et confirmation

Disponible dans les téléchargements v0.8.0.
L’ouverture du formulaire propose, pour les cibles manquantes, une valeur unique
explicite du profil Orca U1 correspondant, uniquement si une U1 est sélectionnée.
À défaut, une plage connue permet une estimation de son milieu, arrondie à un
multiple de 5 °C dans les bornes. Son origine est indiquée : ce n’est pas une
nouvelle recommandation fabricant. Un plateau avec plusieurs valeurs de profil
différentes ne donne pas de cible documentée unique.

Sans plage exploitable, le champ reste vide. L’enceinte n’est pas estimée à partir
de la matière : choisissez explicitement « Sans chauffage » si cela correspond à
votre installation, ou indiquez la valeur. Les valeurs déjà confirmées ne sont
pas remplacées. Toute édition retire la confirmation ; « Enregistrer » reste bloqué tant que
le bouton « Valider les températures », placé juste à côté, n’a pas été activé. Annuler n’enregistre
aucune suggestion. Le catalogue et les encodeurs restent inchangés.

Le parcours matériel ne demande plus de choisir NFC Tools téléphone/ordinateur.
Le fichier OpenTag3D produit par défaut par l’interface est un message NDEF brut ;
les conteneurs historiques restent disponibles dans les commandes CLI/API et
les réglages importés. Le QR transmet toujours exactement le même message NDEF.

Une fois les valeurs enregistrées et l’étiquette valide, l’export NFC et l’aperçu
réutilisent ces réglages sans rouvrir le formulaire. La validité du message complet
est contrôlée à chaque action. Des valeurs manquantes ou devenues incompatibles
ramènent à la préparation ; « Modifier les valeurs de l’étiquette… » ouvre toujours
le formulaire et demande une nouvelle confirmation avant tout enregistrement.
