# OpenSpool 1.0 est-il le seul format RFID/NFC pour imprimante 3D ?

**Non.** OpenSpool est un format de données parmi plusieurs. Une puce NFC,
un encodage et un logiciel de lecteur compatibles sont trois conditions distinctes.
La [version stable v0.8.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0) prépare **OpenSpool 1.0** et **OpenTag3D 2.004**, sans écrire physiquement le tag.
Les descriptions de formats ci-dessous sont des vérifications documentaires, pas
une certification de toutes les imprimantes.

| Format | Encodage et support documentés | Export dans SpoolScribe |
| --- | --- | --- |
| OpenSpool 1.0 | JSON, enregistrement NDEF `application/json`, NTAG215/216. Le champ `version` vaut `1.0` dans les exemples du projet | Oui, compact pour NFC et archive complète ; mêmes règles existantes |
| OpenTag3D | Standard distinct, version publiée 2.004 à la consultation ; structure binaire, NDEF `application/opentag3d`, NTAG215/216 selon sa spécification | Non en v0.3.5 ; [disponible en version stable v0.8.0](OPENTAG3D.md) |
| OpenPrintTag | NDEF `application/vnd.openprinttag`, sections CBOR ; la spécification décrit ISO/IEC 15693-3/NFC-V | Non |
| Formats des fabricants | Encodages et conditions de lecture propres aux équipements ; certains demandent des clés. La présence de RFID/NFC ne signifie pas que le lecteur accepte OpenSpool | Non, sauf lecture OpenSpool par une configuration explicitement documentée |

Sources primaires : [OpenSpool, protocole et exemple 1.0](https://github.com/spuder/OpenSpool#-openspool-protocol),
[spécification OpenTag3D](https://opentag3d.info/spec.html),
[format des données OpenPrintTag](https://github.com/OpenPrintTag/openprinttag-specification/blob/main/docs_src/nfc_data_format.md).
Les numéros 1.0 d’OpenSpool et 2.004 d’OpenTag3D ne désignent pas deux versions d’un
même format. Remplacer simplement `version` dans un JSON ne convertit pas le tag.

## Cas du Snapmaker U1

La [documentation OpenSpool du firmware étendu](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/openspool.md)
décrit le JSON OpenSpool 1.0, ses champs et des extensions U1. Sa
[matrice lecteurs RFID](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md)
documente aussi OpenRFID et d’autres formats/lecteurs : OpenSpool n’est donc pas
le seul format décrit pour cet écosystème. Il s’agit de la branche **develop**,
pas d’une vérification du firmware effectivement installé sur votre machine.

La recette doit contrôler le firmware, le système de détection choisi et le tag
réel. L’ajout de l’encodeur OpenTag3D ne modifie pas Paxx12 et ne remplace pas un
essai NFC physique. Les installations et leurs prérequis sont décrits dans [Imprimantes et lecteurs](wiki/Printers-and-Readers.md).

## Conséquence pour l’interface

« Compatible SpoolScribe » indique ici la possibilité de lire son **export
OpenSpool ou OpenTag3D**, selon la configuration. Une imprimante peut lire son propre RFID ou
OpenPrintTag sans accepter un export OpenSpool de SpoolScribe. Consulter les fiches
de filament reste possible dans les autres catégories.

## Version stable v0.8.0

L’[export OpenTag3D 2.004](OPENTAG3D.md) ajoute un encodage indépendant et des profils NFC Tools. Il ne transforme pas les tags OpenSpool existants et ne fournit pas d’encodeur OpenPrintTag. La recette physique reste distincte des tests logiciels.

## Le QR SSQR1 transporte le format choisi

SSQR1 n’est pas un troisième format NFC : il transporte **le message NDEF entier**
OpenSpool ou OpenTag3D, sans le convertir. Le QR reste numérique, affichable et
enregistrable en PNG/SVG. Le futur Companion devra le décoder avant d’écrire la
puce ; un lecteur QR ordinaire n’effectue pas cette écriture.
[Contrat numérique](QR_FORMAT.md) · [Exemple visuel](wiki/Companion-and-QR.md).
