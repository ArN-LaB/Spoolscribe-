# Visuels et descriptions des imprimantes

Version de développement 0.3.0, vérification du 1er novembre 2026.

Les images sont des fichiers originaux provenant du fabricant, sans retouche.
Leur affichage les redimensionne en conservant les proportions. Elles sont
embarquées pour éviter tout chargement réseau à l’ouverture de la fiche.

| Entrée | Modèle illustré | Provenance | Description factuelle utilisée |
| --- | --- | --- | --- |
| Snapmaker U1 | U1 | [Page constructeur](https://www.snapmaker.com/snapmaker-u1), visuel CDN référencé par cette page | Quatre têtes indépendantes, volume 270 × 270 × 270 mm ; la compatibilité OpenSpool reste conditionnée au logiciel déjà documenté. |
| Bambu Lab et lecteur externe Bambu | X1 Carbon, exemple de machine de la famille | [Image officielle Bambu Studio](https://github.com/bambulab/BambuStudio/blob/master/resources/images/printer_thumbnail_x1c_png.png), [identité du modèle](https://github.com/bambulab/BambuStudio/blob/master/resources/printers/BL-P001.json) | Le volume 256 × 256 × 256 mm concerne exclusivement la X1 Carbon, selon [sa fiche technique](https://public-cdn.bambulab.com/store/X1-Carbon%20tech%20specs.pdf). Le fonctionnement du lecteur externe est décrit par [OpenSpool](https://github.com/spuder/OpenSpool). |
| Anycubic Kobra S1 / Kobra 3 | Kobra S1, exemple de machine de la famille | [PNG officiel AnycubicSlicerNext](https://github.com/ANYCUBIC-3D/AnycubicSlicerNext/blob/main/resources/profiles/Anycubic/Anycubic%20Kobra%20S1_cover.png) | Aucune caractéristique de la S1 n’est généralisée à la Kobra 3. |
| QIDI Plus4 / Q2 / Max4 | Plus4, explicitement indiquée comme exemple | [Page QIDI Plus4](https://qidi3d.com/products/plus4-3d-printer) et son image produit | Aucun volume ou équipement de la Plus4 n’est généralisé à toute la famille. |

Les fichiers, URL exactes, SHA-256 et noms illustrés sont consignés dans
[data/printer_photos/manifest.json](../data/printer_photos/manifest.json).
Les marques et visuels restent la propriété de leurs ayants droit ; leur présence
sert à identifier les machines et ne signifie aucune affiliation. La licence du
code de SpoolScribe ne transforme pas ces visuels en créations sous licence MIT.

Les quatre visuels actuellement référencés disposent d’un canal alpha natif, vérifié sur les fichiers. Le PNG X1 Carbon de 320 × 320 remplace une miniature de 181 × 180 dans le manifeste ; l’ancien fichier est conservé. Le PNG Anycubic de 180 × 180 est ajouté sans retouche ni suppression de fond.

Les autres entrées restent textuelles tant qu’un visuel adapté n’a pas été revu. Les images promotionnelles Prusa et Anycubic des passes antérieures avaient été écartées. La nouvelle recherche Prusa, sur sa page officielle de ressources médias, a fourni des photographies JPEG opaques ; elles ne sont pas présentées comme des détourages transparents. Le dessin générique de l’ancienne
passe a été retiré.

Pour Prusa, le descriptif distingue les architectures CORE One, MK4S et XL à partir
du [catalogue constructeur](https://www.prusa3d.com/) et de la
[documentation des configurations XL](https://help.prusa3d.com/article/prusa-printer-upgrades_796284?product=xl).
Pour Kobra S1, le volume cité est limité à ce modèle selon
[la page Anycubic](https://store.anycubic.com/products/kobra-s1-combo).
Les autres résumés reprennent le périmètre fonctionnel déjà décrit par le catalogue
matériel et évitent d’inventer des caractéristiques communes à plusieurs modèles.

`printer_presentations.py` ne modifie aucun drapeau de compatibilité : les données
sur les firmwares et les formats lisibles restent dans `data/printers.json`.
Une photo ou un résumé ne vaut pas validation physique du lecteur.


Les autres descriptifs techniques sont limités à des faits documentés :
[CoreXY et CANVAS Elegoo](https://us.elegoo.com/collections/3d-printing/products/centauri-carbon-2),
[double extrusion et filaments 2,85 mm UltiMaker](https://support.ultimaker.com/s/article/1667410778895),
[double tête et filaments 1,75 mm Raise3D Pro3 HS](https://s1.raise3d.com/2024/06/Raise3D_Pro3-HS-Series-Technical-Specifications_V1.5.pdf),
[exemple METHOD XL, sans généralisation à la famille](https://um-support-files.ultimaker.com/manuals/user-manual/Method-XL/METHOD%20XL%20User%20Manual%20%28English%29_JUN142023.pdf).
L’entrée historique da Vinci indique explicitement que ses caractéristiques restent
à confirmer, plutôt que d’attribuer une fiche technique unique à toute la famille.
