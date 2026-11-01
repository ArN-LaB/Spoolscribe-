# OpenSpool 1.0 est-il le seul format RFID/NFC pour imprimante 3D ?

**Non.** OpenSpool est un format de données parmi plusieurs. Une puce NFC,
un encodage et un logiciel de lecteur compatibles sont trois conditions distinctes.
SpoolScribe 0.3.0 prépare actuellement **OpenSpool 1.0** uniquement ; il n’écrit pas
physiquement le tag. Vérification documentaire : 1er novembre 2026.

| Format | Encodage et support documentés | Export dans SpoolScribe |
| --- | --- | --- |
| OpenSpool 1.0 | JSON, enregistrement NDEF `application/json`, NTAG215/216. Le champ `version` vaut `1.0` dans les exemples du projet | Oui, compact pour NFC et archive complète ; mêmes règles existantes |
| OpenTag3D | Standard distinct, version publiée 2.003 à la consultation ; structure binaire, NDEF `application/opentag3d`, NTAG215/216 selon sa spécification | Non |
| OpenPrintTag | NDEF `application/vnd.openprinttag`, sections CBOR ; la spécification décrit ISO/IEC 15693-3/NFC-V | Non |
| Formats des fabricants | Encodages et conditions de lecture propres aux équipements ; certains demandent des clés. La présence de RFID/NFC ne signifie pas que le lecteur accepte OpenSpool | Non, sauf lecture OpenSpool par une configuration explicitement documentée |

Sources primaires : [OpenSpool, protocole et exemple 1.0](https://github.com/spuder/OpenSpool#-openspool-protocol),
[spécification OpenTag3D](https://opentag3d.info/spec.html),
[format des données OpenPrintTag](https://github.com/OpenPrintTag/openprinttag-specification/blob/main/docs_src/nfc_data_format.md).
Les numéros 1.0 d’OpenSpool et 2.003 d’OpenTag3D ne désignent pas deux versions d’un
même format. Remplacer simplement `version` dans un JSON ne convertit pas le tag.

## Cas du Snapmaker U1

La [documentation OpenSpool du firmware étendu](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/openspool.md)
décrit le JSON OpenSpool 1.0, ses champs et des extensions U1. Sa
[matrice lecteurs RFID](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md)
documente aussi OpenRFID et d’autres formats/lecteurs : OpenSpool n’est donc pas
le seul format décrit pour cet écosystème. Il s’agit de la branche **develop**,
pas d’une vérification du firmware effectivement installé sur votre machine.

La recette doit contrôler le firmware, le système de détection choisi et le tag
réel. Cette recherche ne valide aucun nouveau format dans SpoolScribe, ne modifie
pas Paxx12 et ne remplace pas un essai NFC physique. Les profils de l’application
restent ceux déjà documentés dans [Imprimantes et lecteurs](wiki/Printers-and-Readers.md).

## Conséquence pour l’interface

« Compatible SpoolScribe » indique ici la possibilité de lire son **export
OpenSpool**, selon la configuration. Une imprimante peut lire son propre RFID ou
OpenPrintTag sans accepter un export OpenSpool de SpoolScribe. Consulter les fiches
de filament reste possible dans les autres catégories.
