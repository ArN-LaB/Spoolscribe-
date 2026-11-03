# Visuels des imprimantes

SpoolScribe 0.4.0 — travail UX local, revue du 3 novembre 2026.

**15 photographies produit couvrent les 17 entrées désignant une machine ou une
famille précise.** Les vues isolées, de face ou de trois quarts, gardent leurs couleurs
et leur transparence native. Les photos sont communes au sélecteur, à la fiche
matérielle et au parcours d’export.

## Machines illustrées

| Entrée de SpoolScribe | Modèle réellement photographié | Provenance |
| --- | --- | --- |
| Snapmaker U1 | U1 | [Constructeur](https://www.snapmaker.com/snapmaker-u1) |
| Bambu Lab ; Bambu avec lecteur externe | X1 Carbon, exemple de la famille | [Bambu Studio](https://github.com/bambulab/BambuStudio/blob/master/resources/images/printer_thumbnail_x1c_png.png) |
| Prusa ; Prusa MK4/MK4S/MMU3 | Original Prusa MK4S, exemple de la famille | [IGO3D](https://www.igo3d.com/original-prusa-mk4s-3d-drucker-montiert) — version 680 px de la vue fournie par l’utilisateur |
| Prusa CORE One / CORE One L | CORE One, exemple de la famille | [Blog Prusa](https://blog.prusa3d.com/de/mehrfarbiges-drucken-mit-einem-prusa-einfuehrungs-anleitung_110590/), image produit publiée sur son stockage officiel |
| Anycubic Kobra S1 / Kobra 3 | Kobra S1, exemple de la famille | [AnycubicSlicerNext](https://github.com/ANYCUBIC-3D/AnycubicSlicerNext/blob/main/resources/profiles/Anycubic/Anycubic%20Kobra%20S1_cover.png) |
| QIDI Plus4 / Q2 / Max4 | Plus4, exemple de la famille | [Constructeur](https://qidi3d.com/products/plus4-3d-printer) |
| Creality K2 / K2 Plus / Hi | K2 Combo, exemple de la famille | [Fiche revendeur](https://3dcim.com/creality-k2-combo-3d-yazici), image hébergée par Creality |
| Creality K1 / K1 Max | K1 Max, exemple de la famille | [Site Creality](https://www.creality.com/ae/download), image du CDN constructeur |
| Flashforge AD5X | AD5X | [Boutique Flashforge](https://uk.flashforge.com/products/ad5x-3d-printer) |
| Flashforge Creator 5 | Creator 5, pas Creator 5 Pro | [Boutique Flashforge](https://uk.flashforge.com/products/flashforge-creator-5) |
| Elegoo Centauri Carbon 2 | Centauri Carbon 2 Combo | [Sync Innovation](https://www.sync-innovation.com/products/elegoo-centauri-carbon-2-combo) |
| UltiMaker 3 / S-series | S5, exemple de la famille | [Ultimate 3D Printing Store](https://ultimate3dprintingstore.com/products/ultimaker-s5) |
| Raise3D Pro3 HS | Pro3 HS | [参次元工房](https://3jigenkoubou.com/shopdetail/000000000323) |
| MakerBot METHOD | METHOD XL, exemple de la famille | [UltiMaker Cura](https://github.com/Ultimaker/Cura/blob/main/plugins/UM3NetworkPrinting/resources/png/MakerBot%20Method%20XL.png) |
| XYZprinting da Vinci | da Vinci 1.0 Pro, exemple de la famille | [3D Printer Superstore](https://3dprintersuperstore.com.au/products/da-vinci-1-0-pro) |

Une photo d’exemple ne représente pas tous les modèles d’une famille. La légende
nomme la machine illustrée ; ses dimensions ou équipements ne sont pas attribués aux
autres modèles. L’image Creator 5 Pro transmise comme exemple a servi à la recherche :
la fiche Creator 5 utilise le visuel du modèle correspondant.

## Intégration et qualité

- Les fichiers sont conservés octet pour octet, sans détourage automatique,
  génération d’image, recoloration, miroir ou suppression de marquage.
- Un canal RGBA ne suffit pas : les pixels transparents sont mesurés et le rendu est
  revu sur fonds clair et sombre. Les PNG opaques et bannières trouvés sont écartés.
- L’affichage retire seulement les marges entièrement transparentes, puis ajuste
  l’objet en conservant les proportions. Les originaux restent inchangés. Les petites
  tailles rendues sont mises en cache.
- Les images sont embarquées : aucun téléchargement à l’ouverture d’une fiche,
  aucune nouvelle source réseau dans l’application.
- URL de fichier et de page source, modèle, légende, dimensions, bornes alpha,
  octets et SHA-256 figurent dans le [manifeste](../data/printers/photos/manifest.json).
  Les tests contrôlent ces valeurs, la couverture et l’absence d’orphelins.

## Choix génériques

« Imprimante sous Klipper », « Prusa autre modèle » et « Imprimante sans lecteur »
ne désignent pas une machine précise. Ils gardent une illustration générique
explicitement nommée. Les lecteurs autonomes OpenSpool et OpenTag3D conservent
leur pictogramme de lecteur.

Les marques et photos restent la propriété de leurs ayants droit. L’origine peut
être le constructeur, son dépôt logiciel ou un revendeur identifié ; ces fichiers
ne sont pas relicenciés sous MIT et n’impliquent aucune affiliation. Voir
[TRADEMARKS.md](TRADEMARKS.md).

`printer_presentations.py` ne change aucun format, firmware ou drapeau de compatibilité
de `data/printers.json`. Une photo n’atteste ni la lecture RFID/NFC ni un essai matériel.
