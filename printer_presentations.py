"""Presentation only: documented product summaries, no firmware compatibility changes."""
from i18n import tr
import json
from pathlib import Path
import printer_profiles

# Specs that differ between models are explicitly scoped to the illustrated model.
DESCRIPTIONS = {
 'u1': ('Snapmaker U1','4 têtes indépendantes · volume 270 × 270 × 270 mm. Changement d’outil pour l’impression multicolore.','https://www.snapmaker.com/snapmaker-u1'),
 'bambu': ('Bambu Lab · X1 / P1 / A1 / H2','Imprimantes à filament, avec AMS selon modèle. Exemple illustré : X1 Carbon, volume 256 × 256 × 256 mm.','https://public-cdn.bambulab.com/store/X1-Carbon%20tech%20specs.pdf'),
 'bambu_openspool': ('Bambu Lab + lecteur externe','Votre imprimante Bambu reste la même. Un lecteur ESP32 + PN532 lit l’étiquette puis transmet les informations par MQTT ; l’AMS ne lit pas cette étiquette.','https://github.com/spuder/OpenSpool'),
 'prusa': ('Prusa · CORE One / MK4S / XL','CORE One : enceinte fermée ; MK4S : portique ouvert ; XL : changement d’outils selon équipement. Préparation avec PrusaSlicer.','https://www.prusa3d.com/'),
 'anycubic_ace': ('Anycubic · Kobra S1 / Kobra 3','Impression multicolore avec ACE Pro selon équipement. Kobra S1 : enceinte fermée, volume 250 × 250 × 250 mm.','https://store.anycubic.com/products/kobra-s1-combo'),
 'creality_k2': ('Creality · K2 / K2 Plus / Hi','Imprimantes à filament associées au système CFS selon équipement. Les volumes et matériaux acceptés varient selon le modèle.','https://www.creality.com/'),
 'qidi_box': ('QIDI · Plus4 / Q2 / Max4','Imprimantes à filament, système QIDI Box selon équipement. Le profil d’impression et les capacités dépendent du modèle.','https://qidi3d.com/products/plus4-3d-printer'),
 'flashforge_ad5x': ('Flashforge · AD5X / Creator 5','Impression à filament multicolore. Le lecteur FF_NFC et le logiciel communautaire sont des équipements supplémentaires.','https://github.com/ghzserg/zmod'),
 'klipper_diy': ('Imprimante sous Klipper','Voron, Sovol SV08, RatRig et autres montages. Les capacités viennent de votre machine ; le lecteur et son intégration Spoolman sont à configurer séparément.','https://www.klipper3d.org/'),
 'openspool': ('Lecteur OpenSpool','Un lecteur externe identifie la bobine. La prise en charge des champs du fichier dépend du lecteur et de son logiciel.','https://github.com/spuder/OpenSpool'),
 'no_reader': ('Imprimante sans lecteur de bobine','Utilisez la fiche pour retrouver la matière, la couleur et les paramètres à reporter dans votre trancheur. Le modèle reste à choisir dans ce dernier.',''),
 'elegoo_cc2': ('Elegoo Centauri Carbon 2','Architecture CoreXY · impression à filament · système multicolore CANVAS selon équipement.','https://us.elegoo.com/collections/3d-printing/products/centauri-carbon-2'),
 'ultimaker_s': ('UltiMaker · 3 / S-series','Double extrusion · filaments 2,85 mm. La Material Station gère plusieurs bobines sur les modèles S compatibles ; elle ne convient pas à toutes les machines de la gamme.','https://support.ultimaker.com/s/article/1667410778895'),
 'raise3d_pro3': ('Raise3D Pro3 HS','Impression FFF · double tête à relevage électronique · filaments 1,75 mm. Les paramètres du matériau restent à préparer dans le trancheur.','https://s1.raise3d.com/2024/06/Raise3D_Pro3-HS-Series-Technical-Specifications_V1.5.pdf'),
 'makerbot_method': ('MakerBot METHOD','Gamme d’imprimantes à filament. Exemple METHOD XL : double extrusion ; les capacités et équipements diffèrent selon la version exacte.','https://um-support-files.ultimaker.com/manuals/user-manual/Method-XL/METHOD%20XL%20User%20Manual%20%28English%29_JUN142023.pdf'),
 'xyz_davinci': ('XYZprinting da Vinci','Famille da Vinci : capacités et consommables variables selon le modèle. Les caractéristiques techniques de votre version restent à confirmer.',''),
}


def presentation(profile):
    key=next((k for k,p in printer_profiles.PROFILES.items() if p['label']==profile['label']),None)
    title,description,source=DESCRIPTIONS.get(key,(profile['label'],profile.get('help','Consultez le profil de votre modèle dans le trancheur.'),''))
    result=dict(title=tr(title),description=tr(description),source=source)
    root=printer_profiles.bundled_path().parent
    try:
        manifest=json.loads((root/'printer_photos/manifest.json').read_text())
        item=manifest.get('bambu' if key=='bambu_openspool' else key,{})
        if item:
            path=(root/'printer_photos'/item['file']).resolve()
            if path.is_relative_to((root/'printer_photos').resolve()) and path.is_file():
                result.update(photo=str(path),caption=tr(item['caption']))
    except (OSError,ValueError,KeyError):pass
    return result
