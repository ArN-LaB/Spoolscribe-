# Prise en main — révision UX v0.3.0

Cette version est en développement. La version publiée reste v0.2.2.

| Retour | Fonctionnement retenu |
|---|---|
| 1. Tris | Clic sur un en-tête : croissant, puis décroissant. Clic droit : tri principal (1), secondaire (2), retrait du secondaire. Les flèches numérotées indiquent l'ordre. Aucune liste de tri visible. |
| 2. Fabricant | Polymaker est sélectionné à la première utilisation. Tapez quelques lettres dans le sélecteur ; les correspondances sont proposées. Les accès rapides combinent Polymaker et les fabricants récemment choisis. Le dernier filtre personnel est mémorisé. |
| 3. Sources et base | Premier téléchargement nécessaire ; aucun catalogue ni profil Orca dans l'installateur. Actualisation des sources choisies à chaque démarrage autorisé ; conservation du cache lors d'un échec. Priorité fabricant, complément communautaire, correction personnelle prioritaire. Rapprochements incertains mis à part. Pagination sous la liste qu'elle contrôle. |
| 4. Menu mise à jour | Choisir/décocher les sources puis enregistrer ou télécharger. Une source décochée n'est plus contactée ; ses anciennes données ne sont pas effacées. |
| 5. Colonnes | Bouton ▥ en haut à droite du tableau, ou clic droit sur un en-tête. Largeur, déplacement et visibilité mémorisés. Au moins une colonne textuelle reste visible. |
| 6. Logos/icônes | Pas de fond rectangulaire ajouté ; proportions et transparence conservées, contour discret pour la lisibilité. Les marges raster uniformes blanches/noires reliées au bord sont rendues transparentes ; les couleurs du dessin et les fichiers source sont conservés. |
| 7. NFC | Choisissez l'imprimante/lecteur et l'étiquette réellement achetée. Le mode automatique conserve le profil complet s'il tient, sinon le profil essentiel en expliquant les champs omis. Aucun calcul d'octets nécessaire au quotidien. Profil manuel et réserve restent dans « Réglages avancés ». |
| 8. Caractéristiques | Le choix d'imprimante fournit un résumé de compatibilité. Les champs marqués * servent à l'identification U1 ; leur survol explique l'usage. Les températures du fichier ne remplacent pas un profil de trancheur. Références/provenance/masse sont affichables à la demande. |
| 9. Réglages | Filtres, tris, colonnes, vue, géométrie, séparation des panneaux, imprimante, tag/profil/réserve, sources, affichage détaillé et fabricants récents sont mémorisés. Menu ⋯ : enregistrer/charger un fichier de réglages. Le consentement réseau ne s'importe pas. |
| 10. Application | Menu ⋯ : vérifier la version stable GitHub. Si elle est plus récente, ouvrir le téléchargement officiel. Remplacement manuel du binaire ; aucune exécution automatique d'un installateur téléchargé. Données et configuration restent dans le dossier utilisateur. |
| 11. « Qualité » | Renommé « État des données ». « Export possible » signifie que les champs OpenSpool sont renseignés, pas que le filament est meilleur ou que toutes les imprimantes reconnaissent son tag. Capacité et compatibilité sont vérifiées séparément. |
| 12. Désélection | Recliquer sur la ligne sélectionnée, cliquer dans la zone vide du tableau ou appuyer sur Échap. Le panneau revient à son état sans sélection. |
| 13. Informations base | En bas de fenêtre : nombre de références et statut. Un clic ouvre les dates, le résultat de chaque source, les corrections conservées et le nombre de rapprochements en attente. Le compteur au-dessus du tableau décrit uniquement les résultats filtrés. |

## Imprimantes et protocoles : distinction nécessaire

| Choix | Usage des informations | Export NFC produit ici |
|---|---|---|
| U1 avec firmware OpenSpool compatible | Matière/couleur identifient le filament ; marque facultative. Dans le mapping documenté consulté, les températures sont stockées, pas transmises comme températures d'impression ; diamètre/masse ne sont pas mappés. | OpenSpool, après validation conservatrice des paramètres par SpoolScribe. |
| U1 constructeur | Fiche de référence ; ne suppose pas l'installation du firmware compatible. | Non. |
| Bambu Lab / AMS | Matière/couleur et profil filament dans Bambu Studio ; température plateau dépendant du plateau. Densité pour les calculs du trancheur, masse pour l'inventaire. | Aucun tag RFID propriétaire Bambu n'est généré. |
| Prusa / PrusaSlicer | Choix et paramètres du profil filament ; identification/aperçu et calculs du trancheur. | Aucun encodeur OpenPrintTag dans cette passe. Un JSON OpenSpool NTAG215/216 ne remplace pas le format OpenPrintTag. |
| Autre lecteur OpenSpool | Utilisation à vérifier dans la documentation de ce lecteur. | OpenSpool conservateur. |

Sources techniques consultées le 31 octobre 2026 :
[mapping U1 du firmware](https://github.com/paxx12-snapmaker-u1/SnapmakerU1-Extended-Firmware/blob/develop/docs/design/filament_detect.md),
[OpenPrintTag](https://openprinttag.org/),
[champs OpenPrintTag](https://github.com/OpenPrintTag/openprinttag-specification/blob/main/data/main_fields.yaml),
[matériel Prusa compatible](https://www.prusa3d.com/product/openprinttag-upgrade/),
[profils Bambu Studio](https://github.com/bambulab/BambuStudio/tree/master/resources/profiles/BBL/filament).
Le firmware installé, le lecteur et le logiciel d'écriture doivent être vérifiés
sur le matériel réel. Aucune recette physique n'est revendiquée.

## Identités et corrections

L'application ne considère pas deux filaments identiques simplement parce qu'ils
sont de la même matière ou couleur. Une référence fabricant, ou un rapprochement
exact du produit/couleur avec conditionnement compatible, est nécessaire. Les
renommages historiques Polymaker sont explicites. En cas d'ambiguïté, aucune
fusion arbitraire ni référence supplémentaire n'est ajoutée au tableau.

Les valeurs source gardent leur provenance. Une source constructeur peut remplacer
une valeur communautaire non modifiée. Une valeur source inconnue peut recevoir
un complément factuel. Dès qu'un champ est corrigé explicitement, il est protégé,
même si la nouvelle valeur est `null` ou identique à celle de la source. Les anciens
champs sans provenance restent protégés par précaution. Les données mises à part
sont signalées dans le bilan ; cette version ne prétend pas résoudre tous les
rapprochements et ne fournit pas encore d'éditeur de rapprochement manuel.
