# Choisir une installation de lecture — v0.5.0 Pre-release

[Documentation](README.md) · [OpenTag3D](OPENTAG3D.md) · [Validation](validation/v0.5.0.md)

**L’imprimante, son lecteur et le logiciel doivent fonctionner ensemble.**
La présence d’un port USB ou d’une puce NFC ne suffit pas. La liste présente des
installations documentées, sans prétendre couvrir tous les modèles disponibles.
Ces choix sont disponibles dans la [préversion v0.5.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.5.0).
La version stable publique reste v0.3.5.

## Ce qui a été vérifié, et vos retours

Les tests automatisés vérifient le logiciel et les données exportées. La liste
ci-dessous repose sur les sources documentaires citées ; elle ne certifie pas une
recette sur chaque machine. Tester toutes les combinaisons exigerait de disposer
de toutes les imprimantes, de leurs lecteurs et des différentes versions de
firmware et de plugins. Aucune écriture NFC ni relecture physique sur imprimante
n’est revendiquée pour ces ajouts.

Les retours sont bienvenus, qu’il s’agisse d’un essai réussi ou d’un problème :
[ouvrir une Issue de compatibilité](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=printer_compatibility.yml).
Indiquez le modèle exact, le lecteur et sa connexion, les versions des logiciels,
le type de tag, le format exporté et le résultat observé. Ces informations permettront
de préciser la liste et d’ajuster l’application, sans généraliser un essai à toute
une gamme. N’incluez pas de données personnelles ou d’identifiants réseau.

## Un choix en trois étapes

1. **Imprimante** : choisissez le modèle, sans chercher une seconde entrée du même
   modèle portant le nom d’un lecteur externe.
2. **Composez votre installation** avec les boutons : lecteur intégré/USB/réseau,
   logiciel d’origine/modifié/ajouté, puis installation précise. Les choix se
   complètent ; un lecteur réseau ne confirme pas à lui seul que SpoolSense est
   installé. Même une seule possibilité restante doit être confirmée.
3. **Votre étiquette** : choisissez parmi les formats compatibles proposés par
   boutons, puis le tag acheté et, pour OpenTag3D, téléphone ou ordinateur.
   Le résultat reste visible sous la zone de choix, même pendant le défilement.

Les informations techniques sont regroupées sous **Prérequis et détails** :
versions, pilotes, connexions CAN/MQTT/UART, source documentaire et réglages NFC.
Le NDEF brut y reste réservé au parcours expert. Les listes techniques historiques
restent internes pour préserver les réglages et API ; elles ne sont plus montrées.

Exemple : **U1 → Lecteur intégré → Logiciel modifié → paxx12 / OpenRFID →
OpenTag3D → NTAG216 → Téléphone**. Le résumé indique l’identification dans
l’imprimante, le format du tag et le fichier NFC Tools à utiliser.

La fiche distingue **données transmises à l’imprimante**, **inventaire externe
uniquement** et **lecteur autonome**. Une installation expérimentale ou non vérifiée
est signalée. Le bouton de documentation ouvre la source au clic ; aucun service
personnel n’est contacté pour détecter automatiquement votre équipement.

## Les connexions ne sont pas interchangeables

| Installation | Ce qui est nécessaire | Ce que cela ne prouve pas |
| --- | --- | --- |
| Lecteur intégré | Décodeur du firmware compatible avec le format du tag | Installer un firmware communautaire ne garantit pas tous les modes ou formats |
| Lecteur USB sur l’imprimante ou son hôte | Lecteur compatible, pilote et logiciel d’intégration adaptés à ce système | Un ACR122U reconnu par macOS ne sera pas nécessairement reconnu par l’imprimante |
| Scanner réseau | Lecteur, réseau et API ou automatisations compatibles | Un câble USB d’alimentation n’est pas une liaison de données avec l’imprimante |
| Accessoire constructeur | Modèle, bus de connexion et version de firmware explicitement compatibles | L’accessoire Prusa OpenPrintTag sur CAN n’est pas un lecteur USB universel |
| Lecteur USB sur le Mac | Application d’écriture NFC et lecteur reconnus par macOS | Écrire un tag ne rend pas le firmware de l’imprimante capable de le lire |

## Installations proposées

Lecture documentaire du 1er novembre 2026. **Aucune recette physique SpoolScribe
revendiquée** pour ces ajouts.

| Imprimante | Installation à choisir | Firmware de l’imprimante | Sorties SpoolScribe proposées | Résultat / limites |
| --- | --- | --- | --- | --- |
| U1 | Intégré, mode Snapmaker | paxx12 | OpenSpool | Identification par le lecteur intégré |
| U1 | Intégré, OpenRFID ou OpenRFID Generic | Le même paxx12 | OpenSpool et OpenTag3D | Generic modifie l’identification de la marque, pas les formats |
| U1 | Intégré, constructeur | Origine | Aucune | Tags Snapmaker natifs, non générés ici |
| U1 | SpoolSense réseau, mode External | paxx12 + API Moonraker ; scanner 1.7.5+ | OpenSpool et OpenTag3D | Transmission au canal configuré ; ne pas sélectionner le mode interne OpenRFID pour ce scanner |
| U1 | Lecteur distant ESP32/PN532 wasikuss ou baze | paxx12, mode External | OpenSpool | Pas de support OpenTag3D établi pour ces deux lecteurs précis |
| Flashforge AD5X / Creator 5 | ACR122U ou PN532 USB avec FF_NFC | Zmod | OpenSpool et OpenTag3D | Plugin obligatoire ; affectation de matière/couleur. Le projet rapporte des essais matériels sur ces lecteurs, pas notre recette OpenTag3D |
| Flashforge AD5X seulement | USB + FF_NFC | Kiln OS | OpenSpool et OpenTag3D | Intégration encore précoce ; parcours complet matériel non établi pour cette combinaison |
| Flashforge AD5X / Creator 5 | LaneTag Wi-Fi + FF_NFC | Zmod | OpenSpool et OpenTag3D | Liaison réseau, avec les modules et limites décrits par le projet |
| Bambu Lab | OpenSpool ESP32/PN532 via MQTT | Constructeur avec accès LAN permis | OpenSpool | Vérifier modèle et restrictions de firmware ; l’AMS ne décode pas directement ce tag |
| Bambu Lab | SpoolSense + Home Assistant | Constructeur, LAN Only + Developer Mode | OpenSpool et OpenTag3D | Scanner 1.7.0+, TFT, MQTT, intégration Bambu, automatisations et Spoolman nécessaires |
| Klipper / Moonraker | SpoolSense réseau + middleware | Klipper avec macros/configuration | OpenSpool et OpenTag3D | Transmission à la machine via le middleware ; Klipper ou Spoolman seuls ne suffisent pas |
| Klipper / Moonraker | nfc2klipper sur hôte, PN532 UART dans l’exemple documenté | Klipper + service nfc2klipper | Aucune pour ce parcours | Références Spoolman/UID et ancien OpenTag3D v0.12 expérimental ; prise en charge 2.004 non confirmée |
| Prusa CORE One / L | Accessoire officiel OpenPrintTag | Constructeur 8.0+ | Aucune | Bus CAN xBuddy ; format OpenPrintTag, non exporté ici. Exclusions INDX/MMU3 du constructeur |
| Prusa MK4 / MK4S / MMU3 | SpoolSense + PrusaLink / Home Assistant | Constructeur | OpenSpool et OpenTag3D pour le scanner | Inventaire et contrôles externes, expérimental ; pas de filament renseigné sur l’écran Prusa ni de slot écrit dans le firmware |
| Creality K1 / K1 Max | SpoolSense avec firmware d’origine | Constructeur | OpenSpool et OpenTag3D pour le scanner | Inventaire externe seulement, pas de données de bobine envoyées au firmware |
| Creality K1 / K1 Max | SpoolSense + root/Moonraker + middleware | Modifié | OpenSpool et OpenTag3D | Intégration à la machine après configuration ; aucun branchement USB d’origine promis |

Les autres configurations d’origine déjà présentes (Anycubic, Creality CFS,
Elegoo, QIDI, UltiMaker, Raise3D, MakerBot, XYZprinting) restent consultables.
Leur liste n’a pas été transformée en promesse d’extension USB : les informations
non vérifiées sont signalées et n’activent aucun export. Les lecteurs OpenSpool
et OpenTag3D génériques servent à préparer un tag pour un lecteur explicitement
compatible ; ils ne garantissent aucune liaison à une imprimante particulière.

## Limites de version importantes

Le décodeur SpoolSense audité à la révision
`6070713488b45e51d2dc81124882775253dee2f0` annonce OpenTag3D **2.003**.
Il relit correctement 100 payloads SpoolScribe **2.004**, avec un avertissement de
version mineure sur chacun. Cela valide le décodage logiciel des champs vérifiés,
pas la radio, l’affectation de slot ou la réécriture complète du tag par le lecteur.
Le document général SpoolSense parlant de CBOR pour OpenTag3D est contredit par
son décodeur binaire v2 ; la vérification a porté sur ce code, sans le distribuer.

FF_NFC annonce OpenTag3D 2.x ; ses essais matériels publiés restent distincts de
nos tests logiciels. BambuTagger et les variantes de firmware OpenSpool limitées
à OpenTag3D v1 ne sont pas activés sur la seule base d’une mention du standard.
Aucun encodeur OpenPrintTag ou format constructeur n’est ajouté.

## Réglages conservés et données structurées

Le champ historique `firmwares` de `data/printers.json` reste lisible par les
anciens clients. Ses entrées décrivent maintenant une installation complète :
`connection`, `firmware_kind`, `reader`, `reader_formats`, `formats`, `effect`,
`evidence`, `url`, `choice_label` et date documentaire. `formats` est limité aux encodeurs présents.
Une installation non vérifiée ne peut pas activer d’export dans ce schéma.

- Les anciens choix U1/paxx12 et U1 constructeur sont conservés.
- L’ancienne entrée séparée Bambu + lecteur OpenSpool est ramenée à **Bambu →
  lecteur réseau OpenSpool**, sans perdre le lecteur choisi.
- L’ancienne entrée regroupant plusieurs Prusa devient **modèle à préciser** ;
  elle n’est pas convertie automatiquement en CORE One avec accessoire CAN.
- Le choix Klipper générique ne prétend plus décoder OpenSpool sans intégration
  identifiée. La liaison nfc2klipper par référence et son ancien décodeur v0.12 restent distincts de la lecture 2.004.
- Le catalogue des filaments, les corrections personnelles et les profils Orca
  ne sont pas modifiés par cette réorganisation.

## Sources primaires

- [paxx12 : modes et formats RFID](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/rfid.md).
- [FF_NFC : lecteurs, plateformes et limites](https://github.com/DIEHARDave/FF_NFC),
  révision `fea14b226f09ab3537c326a6cbbc4c97954ba8a0` ; le projet remplace zmod_nfc.
- [SpoolSense : matrice de compatibilité](https://spoolsense.org/resources/compatibility/),
  [U1](https://spoolsense.org/installation/snapmaker-u1/),
  [Bambu](https://spoolsense.org/installation/bambu-ams/),
  [Prusa et ses limites](https://spoolsense.org/installation/prusa/),
  [middleware Klipper](https://spoolsense.org/installation/middleware/).
- [Décodeur binaire SpoolSense épinglé](https://github.com/SpoolSense/spoolsense_scanner/blob/6070713488b45e51d2dc81124882775253dee2f0/lib/opentag3d/opentag3d_lib.c).
- [OpenSpool : lecteur externe et MQTT](https://github.com/spuder/OpenSpool).
- [nfc2klipper : références Spoolman](https://github.com/bofh69/nfc2klipper).
- [Prusa : accessoire, modèles, CAN et exclusions](https://www.prusa3d.com/product/openprinttag-upgrade/),
  [firmware requis](https://help.prusa3d.com/article/prusa-openprinttag-upgrade-for-core-one-l_1246289).
