# Printer photographs

SpoolScribe 0.6.0 photographs retained; documentation updated 3 November 2026.

**15 product photographs cover the 17 entries naming a specific machine or
family.** Isolated front/three-quarter views retain their original colours and
transparency. The same photographs appear in the selector, hardware details
and export workflow.

| SpoolScribe entry | Model actually shown | Source |
| --- | --- | --- |
| Snapmaker U1 | U1 | [Manufacturer](https://www.snapmaker.com/snapmaker-u1) |
| Bambu Lab; Bambu with external reader | X1 Carbon, family example | [Bambu Studio](https://github.com/bambulab/BambuStudio/blob/master/resources/images/printer_thumbnail_x1c_png.png) |
| Prusa; Prusa MK4/MK4S/MMU3 | Original Prusa MK4S, family example | [IGO3D](https://www.igo3d.com/original-prusa-mk4s-3d-drucker-montiert), 680 px version of the user-supplied view |
| Prusa CORE One / CORE One L | CORE One, family example | [Prusa blog](https://blog.prusa3d.com/de/mehrfarbiges-drucken-mit-einem-prusa-einfuehrungs-anleitung_110590/), product image on official storage |
| Anycubic Kobra S1 / Kobra 3 | Kobra S1, family example | [AnycubicSlicerNext](https://github.com/ANYCUBIC-3D/AnycubicSlicerNext/blob/main/resources/profiles/Anycubic/Anycubic%20Kobra%20S1_cover.png) |
| QIDI Plus4 / Q2 / Max4 | Plus4, family example | [Manufacturer](https://qidi3d.com/products/plus4-3d-printer) |
| Creality K2 / K2 Plus / Hi | K2 Combo, family example | [Retailer](https://3dcim.com/creality-k2-combo-3d-yazici), image hosted by Creality |
| Creality K1 / K1 Max | K1 Max, family example | [Creality](https://www.creality.com/ae/download), manufacturer CDN image |
| Flashforge AD5X | AD5X | [Flashforge store](https://uk.flashforge.com/products/ad5x-3d-printer) |
| Flashforge Creator 5 | Creator 5, not Creator 5 Pro | [Flashforge store](https://uk.flashforge.com/products/flashforge-creator-5) |
| Elegoo Centauri Carbon 2 | Centauri Carbon 2 Combo | [Sync Innovation](https://www.sync-innovation.com/products/elegoo-centauri-carbon-2-combo) |
| UltiMaker 3 / S-series | S5, family example | [Ultimate 3D Printing Store](https://ultimate3dprintingstore.com/products/ultimaker-s5) |
| Raise3D Pro3 HS | Pro3 HS | [3jigen Koubou](https://3jigenkoubou.com/shopdetail/000000000323) |
| MakerBot METHOD | METHOD XL, family example | [UltiMaker Cura](https://github.com/Ultimaker/Cura/blob/main/plugins/UM3NetworkPrinting/resources/png/MakerBot%20Method%20XL.png) |
| XYZprinting da Vinci | da Vinci 1.0 Pro, family example | [3D Printer Superstore](https://3dprintersuperstore.com.au/products/da-vinci-1-0-pro) |

A family example does not represent every model. Captions identify the pictured
machine without attributing its dimensions/equipment to other models. The
user-supplied Creator 5 Pro example informed the search; the Creator 5 entry uses
the matching model's photograph.

## Integration and quality

Original files are retained byte for byte: no automatic cutout, generated image,
recolouring, mirroring or removal of markings. An RGBA channel alone is not enough:
transparent pixels are measured and rendering reviewed on light/dark backgrounds.
Opaque PNGs and banners found during selection are excluded.

Display trims only completely transparent margins, scales proportionally and
caches small rendered sizes. Originals remain unchanged. Images are bundled:
opening hardware details downloads nothing and adds no application network source.
The [manifest](../data/printers/photos/manifest.json) records file/source-page URLs,
model, caption, dimensions, alpha bounds, bytes and SHA-256. Tests check those
values, coverage and orphan-free resources.

## Generic choices and rights

Klipper printer, other Prusa model and printer without reader are not specific
machines. They retain an explicitly named generic illustration. Standalone
OpenSpool/OpenTag3D readers retain a reader icon.

Marks and photographs belong to their rights holders. Sources may be the
manufacturer, its software repository or an identified retailer. Files are not
relicensed under MIT and imply no affiliation; see [trademarks](TRADEMARKS.md).
`printer_presentations.py` changes no format, firmware or compatibility flag in
`data/printers.json`. A photograph proves neither RFID/NFC support nor a hardware test.
