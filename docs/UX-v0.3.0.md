# Prise en main — révision UX v0.3.0

Cette version est en développement. La version publiée reste v0.2.2.
Les comportements ci-dessous intègrent les correctifs de l'audit du 31 octobre 2026
et de la seconde revue, sur données réelles, du 1er novembre 2026 (voir la fin).

| Retour | Fonctionnement retenu |
|---|---|
| 1. Tris | Clic sur un en-tête : tri principal (1) croissant, second clic : décroissant. Maj + clic, ou clic droit : tri secondaire (2), retrait du secondaire. Les flèches numérotées indiquent l'ordre. Aucune liste de tri visible. |
| 2. Fabricant | Barre latérale « Fabricants » : « Tous les fabricants », puis les fabricants récemment choisis épinglés (★), puis la liste alphabétique avec le nombre de filaments ; un champ filtre la liste. Les lignes de produits que certaines sources listent comme marques (PolyLite, Panchroma, Fiberon, PrimaSelect…) sont rangées sous leur fabricant ; la fiche affiche « Marque · ligne ». Polymaker est sélectionné à la première utilisation ; le dernier filtre est mémorisé. |
| 3. Sources et base | Premier téléchargement nécessaire ; aucun catalogue ni profil Orca dans l'installateur. Actualisation au lancement selon la cadence choisie dans Paramètres (à chaque lancement, quotidienne par défaut, hebdomadaire, manuelle) ; « Synchroniser » force. Une source inchangée répond « non modifiée » (ETag) sans nouveau téléchargement. Synchro annulable ; fermeture possible après confirmation ; hors ligne, la base locale est conservée sans réécriture. Priorité fabricant, complément communautaire, correction personnelle prioritaire. Rapprochements incertains mis à part. Pagination sous la liste qu'elle contrôle. |
| 4. Synchroniser | Le bouton « Synchroniser » (Ctrl+U) ouvre les sources : case, détail, dernier résultat de chacune, « Voir le rapport de la dernière synchronisation », puis « Synchroniser maintenant », « Enregistrer seulement » ou Annuler. Une source décochée n'est plus contactée ; ses anciennes données ne sont pas effacées. Pendant la synchro : barre de progression et bouton Annuler. Après une synchro manuelle, ou dès qu'une source échoue : rapport (complète / partielle / échec / annulée ; références, filaments prêts et fabricants avec écarts ; valeurs conservées ; rapprochements en attente ; ordre de priorité ; tableau Source · Résultat · Références · Détail). Au lancement hors ligne : une ligne de statut, rien d'autre. Une seule instance par dossier de données. |
| 5. Colonnes et lignes | Une ligne par filament (fabricant + produit + couleur) : les conditionnements (masse, recharge, diamètre) sont regroupés et listés dans la fiche. Colonnes par défaut : pastille, Produit, Couleur, Fabricant, Matière, État des données ; « Colonnes » (bouton en haut à droite ou clic droit sur un en-tête) ajoute Référence (numéro fabricant « +n », ou « n cond. » quand la source n'en donne pas), Ø mm et Masse. Largeur, déplacement et visibilité mémorisés ; au moins une colonne textuelle reste visible. |
| 6. Logos/icônes | Pas de fond rectangulaire ajouté ; proportions et transparence conservées, contour discret pour la lisibilité, taille réelle sur écran Retina. Les marges raster uniformes blanches/noires reliées au bord sont rendues transparentes ; les couleurs du dessin et les fichiers source sont conservés. Un bitmap de moins de 24 px est remplacé par le nom du fabricant. |
| 7. NFC | Menu ⚙ → « Mon matériel » (ou « Modifier… » dans la fiche) : imprimante ou lecteur, firmware quand plusieurs existent, étiquette réellement achetée. La fiche résume le choix (« Pour : imprimante — firmware · étiquette · profil »). Le profil recommandé est l'essentiel : matière, couleurs, températures, diamètre, densité — tout ce que l'imprimante lit — et il tient sur NTAG215 pour toutes les références. « Complet » (descriptifs, métadonnées de marque) est un choix explicite dans « Réglages avancés », avec le profil manuel et la réserve d'écriture. La marge restante est affichée à titre indicatif. L'étiquette, le profil et la réserve choisis valent pour la session ; le bouton « Définir par défaut » à côté de l'étiquette les conserve pour les exports et lancements suivants (« Par défaut ✓ » quand le choix courant est déjà le défaut ; CLI : `--save-nfc-default`). Quand le matériel choisi ne lit pas OpenSpool (Bambu AMS, Prusa OpenPrintTag, Creality CFS, firmware constructeur du U1…), les réglages d'étiquette sont masqués et l'export indisponible : aucun tag propriétaire n'est produit. |
| 8. Caractéristiques et imprimantes | La liste des imprimantes et lecteurs est une donnée (`data/printers.json`, embarquée, actualisable depuis le dépôt par « Mettre à jour la liste des imprimantes… » avec l'accord réseau) : groupe (lecteur intégré lisant OpenSpool / via un lecteur externe / lecteur propriétaire / sans lecteur), technologie du lecteur, firmwares avec le drapeau « lit OpenSpool », aide et usage des champs. Les champs marqués * servent à l'identification ; leur survol explique l'usage. Les températures du fichier ne remplacent pas un profil de trancheur. La fiche affiche toujours « Caractéristiques » (+ « Corriger… »), les références de chaque conditionnement (référence · masse · Ø · état ; « source OFD » sans numéro fabricant ; ⚠ quand les sources donnent des teintes différentes) et la provenance. |
| 9. Réglages | Filtres, tris, colonnes, regroupement, vue, géométrie, séparation des panneaux, imprimante et firmware, tag/profil/réserve par défaut, sources, cadence et fabricants récents sont mémorisés. Menu ⚙ : Mon matériel, Paramètres, Exporter en archive JSON, Sources de la base, Enregistrer/Charger des réglages, Vérifier une mise à jour, À propos. Le consentement réseau ne s'importe pas. |
| 10. Application | Menu ⚙ : vérifier la version stable GitHub, sur clic seulement. Si elle est plus récente, ouvrir le téléchargement officiel. Remplacement manuel du binaire ; aucune exécution automatique d'un installateur téléchargé. Données et configuration restent dans le dossier utilisateur. |
| 11. « Qualité » | Renommé « État des données », dans la barre latérale : Toutes les fiches / Prêtes à exporter / À compléter / À vérifier, avec les comptes. « Export possible » signifie que les champs OpenSpool sont renseignés, pas que le filament est meilleur ou que toutes les imprimantes reconnaissent son tag. Capacité et compatibilité sont vérifiées séparément. |
| 12. Désélection | Recliquer sur la ligne ou la carte sélectionnée, cliquer dans la zone vide, ou appuyer sur Échap, dans la liste comme dans la grille. Le panneau revient à son état sans sélection. La sélection et sa page sont conservées après un tri, un filtre ou une synchronisation. |
| 13. Informations base | En bas de fenêtre : « Base : n références · m filaments · état ⓘ ». Un clic ouvre la date de la dernière tentative (conservée dans les réglages, pas dans la base), la dernière synchronisation complète, le résultat de chaque source, les corrections conservées et le nombre de rapprochements en attente. Le compteur au-dessus du tableau décrit uniquement les résultats filtrés. |
| 14. « À vérifier » | Une valeur source qui se contredit (HEX noir pour « White », HEX blanc pour un nom sombre, buse hors 120–500 °C, plateau hors 0–200 °C ou maximum à 0, densité hors 0,5–4,0, diamètre hors 1,0–3,2 mm) est signalée dans « État des données » et bloque l'export jusqu'à correction explicite dans la fiche. Vos corrections (provenance « Utilisateur ») ne sont jamais remises en cause ; un champ sans provenance est vérifié comme une donnée source. |
| 15. Raccourcis | Ctrl+F : recherche ; Ctrl+E : exporter pour NFC ; Ctrl+U : synchroniser ; Échap : désélection. L'export affiche un message de statut ; « Dossier d'export » ouvre le dossier. |
| 16. Recherche et filtres | Une seule barre de recherche (produit, couleur, référence, fabricant, matière) et la barre latérale ; plus de listes déroulantes ni d'accès rapides redondants. « Réinitialiser les filtres » revient à Polymaker, toutes matières, toutes fiches. |

## Imprimantes et protocoles : distinction nécessaire

La liste complète est dans `data/printers.json` (version du 2026-11-01) et dans le
wiki ([Printers and Readers](wiki/Printers-and-Readers.md)). Résumé par groupe :

| Groupe | Matériel | Lecteur et firmware | Export NFC produit ici |
|---|---|---|---|
| Lecteur intégré lisant OpenSpool | Snapmaker U1 | NFC ISO 14443-A intégré. Firmware ouvert paxx12 : lit OpenSpool depuis la 0.9.4 ; matière et couleur identifient le filament, marque facultative. Firmware constructeur : ne lit que les tags Snapmaker (MIFARE Classic 1K). | OpenSpool, avec le firmware paxx12 seulement, après validation conservatrice des paramètres. |
| Via un lecteur externe | Flashforge AD5X / Creator 5 sous Zmod/Kiln OS + FF_NFC ; Klipper + Spoolman (Voron, Sovol SV08, RatRig…) avec SpoolSense, nfc2klipper ou Happy Hare ; Bambu Lab + lecteur OpenSpool externe (ESP32 + PN532, MQTT en mode développeur) ; autre lecteur OpenSpool | Le lecteur externe lit le tag ; l'imprimante ne le lit pas elle-même. | OpenSpool conservateur ; l'usage des champs dépend du lecteur. |
| Lecteur intégré, protocole propriétaire | Bambu Lab X1/P1/A1/H2 (AMS : MIFARE Classic chiffré et signé ; X1Plus ne change rien) ; Prusa CORE One / MK4S / XL (OpenPrintTag : tags ISO 15693 + CBOR, lecteur optionnel CORE One) ; Creality K2 / K2 Plus / Hi (CFS, MIFARE Classic) ; Anycubic Kobra S1 / Kobra 3 (ACE Pro, NTAG213 au format Anycubic) ; Elegoo Centauri Carbon 2 (CANVAS, NTAG213 format Elegoo) ; QIDI Plus4 / Q2 / Max4 (QIDI Box, MIFARE Classic) ; UltiMaker 3 / S-series (NTAG216 format UltiMaker) ; Raise3D Pro3 HS ; MakerBot METHOD ; XYZprinting da Vinci | Un NTAG215/216 OpenSpool n'est pas lu. | Non : fiche de référence pour le trancheur. Aucun tag propriétaire n'est généré. |
| Pas de lecteur | Snapmaker Artisan/J1, Flashforge AD5M, Phrozen Arco, Zortrax, Kingroon… | Aucun ; un lecteur externe reste possible. | Non. |

Points non confirmés par une source primaire (listés dans le fichier) : le
comportement des Bambu Lab X2D / P2S / H2C et de l'ACE 2 Pro, la disponibilité
du lecteur OpenPrintTag Prusa hors famille CORE One, les formats décodés par
Happy Hare, nfc2klipper et SpoolSense selon leurs versions.

Sources techniques consultées les 31 octobre et 1er novembre 2026 :
[mapping U1 du firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/filament_detect.md),
[OpenPrintTag](https://openprinttag.org/),
[champs OpenPrintTag](https://github.com/OpenPrintTag/openprinttag-specification/blob/main/data/main_fields.yaml),
[matériel Prusa compatible](https://www.prusa3d.com/product/openprinttag-upgrade/),
[profils Bambu Studio](https://github.com/bambulab/BambuStudio/tree/master/resources/profiles/BBL/filament).
Le firmware installé, le lecteur et le logiciel d'écriture doivent être vérifiés
sur le matériel réel. Aucune recette physique n'est revendiquée.

## Identités et corrections

L'application ne considère pas deux filaments identiques simplement parce qu'ils
sont de la même matière ou couleur. Une référence fabricant **et** une couleur
compatible (même nom, ou même HEX sous un autre nom), ou un rapprochement exact
du produit/couleur, avec un conditionnement compatible, sont nécessaires. Les
grades restent distincts (« PLA+ » n'est pas « PLA »). Les renommages historiques
Polymaker sont explicites. En cas d'ambiguïté, aucune fusion arbitraire ni
référence supplémentaire n'est ajoutée au tableau ; chaque fiche source absorbée
reste tracée dans la fiche qui l'a conservée.

Les valeurs source gardent leur provenance. Une source constructeur (rang 100)
peut remplacer une valeur communautaire non modifiée et une valeur sans
provenance (catalogue historique, base créée par un ancien build). Une valeur
inconnue peut recevoir un complément factuel de n'importe quelle source. Une
source qui cesse de publier une valeur ne vide jamais la valeur locale ; une
source qui renvoie moins de la moitié de ses références précédentes est refusée.
Dès qu'un champ est corrigé explicitement, il porte la provenance « Utilisateur »
(rang 1000) et n'est plus jamais remplacé, même si la nouvelle valeur est `null`
ou identique à celle de la source. Les données mises à part sont signalées dans
le rapport ; cette version ne fournit pas encore d'éditeur de rapprochement manuel.

## Seconde revue (1er novembre 2026), sur l'application installée

| Remarque | Réponse |
|---|---|
| 1. Interface confuse, actions mal placées | Barre latérale de facettes ; barre du haut réduite à la recherche, la vue, « Synchroniser » et le menu ⚙ ; réglages de matériel regroupés dans « Mon matériel » (fiche : résumé + « Modifier… ») ; fiche réorganisée (caractéristiques + « Corriger… », références, provenance) ; barre d'état avec références et filaments. |
| 2. Listes incohérentes (PolyLite, Panchroma… à côté de Polymaker) et couleurs différentes pour un même filament | Lignes de produits rattachées à leur fabricant ; une ligne par filament dont le HEX est celui de meilleure provenance ; les sources fabricant corrigent désormais les fiches sans provenance (la base installée, créée par un ancien build, n'avait aucune provenance et était figée). |
| 3. Doublons ; la mise à jour doit fusionner, croiser et compléter avec priorité aux constructeurs ; interface et rapport à reconstruire | Regroupement des conditionnements ; fiche orpheline réparée au lieu de faire échouer la synchro ; dialogue des sources avec le dernier résultat de chacune ; rapport de synchronisation détaillé ; sources saturées (HTTP 429) attendues puis signalées ; délais allongés (une liaison lente mettait plus de deux minutes pour 2 Mo). |
| 4. Choix de l'imprimante : liste exhaustive, lecteur externe, firmware, liste actualisable | `data/printers.json` par groupe, lecteur, firmwares et drapeau « lit OpenSpool » ; « Mettre à jour la liste des imprimantes… ». |
| 5. Logos pas à jour, fond transparent obligatoire | Fond uniforme rendu transparent sur tous les logos raster (test automatisé), outil d'import avec provenance, manifeste prioritaire ; sourcing des logos officiels en cours, marque par marque. |
| 6. Barre de recherche + trois listes déroulantes : redondance | Une recherche, une barre latérale ; plus d'accès rapides ni de listes déroulantes. |
