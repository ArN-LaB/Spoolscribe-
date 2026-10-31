# Prise en main — révision UX v0.3.0

Cette version est en développement. La version publiée reste v0.2.2.
Les comportements ci-dessous intègrent les correctifs de l'audit du 31 octobre 2026.

| Retour | Fonctionnement retenu |
|---|---|
| 1. Tris | Clic sur un en-tête : tri principal (1) croissant, second clic : décroissant. Maj + clic, ou clic droit : tri secondaire (2), retrait du secondaire. Les flèches numérotées indiquent l'ordre. Aucune liste de tri visible. |
| 2. Fabricant | Polymaker est sélectionné à la première utilisation. Tapez quelques lettres dans le sélecteur : les correspondances sont proposées et une correspondance unique filtre aussitôt, sans réécrire votre saisie. Les accès rapides (pastilles) combinent Polymaker et les fabricants récemment choisis. Le dernier filtre personnel est mémorisé. |
| 3. Sources et base | Premier téléchargement nécessaire ; aucun catalogue ni profil Orca dans l'installateur. Actualisation au lancement selon la cadence choisie dans Paramètres (à chaque lancement, quotidienne par défaut, hebdomadaire, manuelle) ; « Mettre à jour » force. Une source inchangée répond « non modifiée » (ETag) sans nouveau téléchargement. Synchro annulable ; fermeture possible après confirmation ; hors ligne, la base locale est conservée sans réécriture. Priorité fabricant, complément communautaire, correction personnelle prioritaire. Rapprochements incertains mis à part. Pagination sous la liste qu'elle contrôle. |
| 4. Menu mise à jour | Choisir/décocher les sources puis enregistrer ou télécharger. Une source décochée n'est plus contactée ; ses anciennes données ne sont pas effacées. Une seule instance de l'application par dossier de données. |
| 5. Colonnes | Bouton « Colonnes » en haut à droite du tableau, ou clic droit sur un en-tête. La colonne Référence affiche le numéro fabricant quand il est connu, sinon l'identifiant interne (infobulle). Largeur, déplacement et visibilité mémorisés. Au moins une colonne textuelle reste visible. |
| 6. Logos/icônes | Pas de fond rectangulaire ajouté ; proportions et transparence conservées, contour discret pour la lisibilité, taille réelle sur écran Retina. Les marges raster uniformes blanches/noires reliées au bord sont rendues transparentes ; les couleurs du dessin et les fichiers source sont conservés. Un bitmap de moins de 24 px est remplacé par le nom du fabricant. |
| 7. NFC | Choisissez l'imprimante/lecteur et l'étiquette réellement achetée. Le profil recommandé est l'essentiel : matière, couleurs, températures, diamètre, densité — tout ce que l'imprimante lit — et il tient sur NTAG215 pour toutes les références. « Complet » (descriptifs, métadonnées de marque) est un choix explicite dans « Réglages avancés », avec le profil manuel et la réserve d'écriture. La marge restante est affichée à titre indicatif. Pour Bambu Lab et Prusa, les réglages d'étiquette sont masqués : aucun tag propriétaire n'est produit. |
| 8. Caractéristiques | Le choix d'imprimante fournit un résumé de compatibilité. Les champs marqués * servent à l'identification U1 ; leur survol explique l'usage. Les températures du fichier ne remplacent pas un profil de trancheur. Références/provenance/masse sont affichables à la demande. |
| 9. Réglages | Filtres, tris, colonnes, vue, géométrie, séparation des panneaux, imprimante, tag/profil/réserve, sources, cadence, affichage détaillé et fabricants récents sont mémorisés. Menu ⋯ : enregistrer/charger un fichier de réglages. Le consentement réseau ne s'importe pas. |
| 10. Application | Menu ⋯ : vérifier la version stable GitHub, sur clic seulement. Si elle est plus récente, ouvrir le téléchargement officiel. Remplacement manuel du binaire ; aucune exécution automatique d'un installateur téléchargé. Données et configuration restent dans le dossier utilisateur. |
| 11. « Qualité » | Renommé « État des données ». « Export possible » signifie que les champs OpenSpool sont renseignés, pas que le filament est meilleur ou que toutes les imprimantes reconnaissent son tag. Capacité et compatibilité sont vérifiées séparément. |
| 12. Désélection | Recliquer sur la ligne ou la carte sélectionnée, cliquer dans la zone vide, ou appuyer sur Échap, dans la liste comme dans la grille. Le panneau revient à son état sans sélection. La sélection et sa page sont conservées après un tri, un filtre ou une synchronisation. |
| 13. Informations base | En bas de fenêtre : nombre de références et statut. Un clic ouvre la date de la dernière tentative (conservée dans les réglages, pas dans la base), la dernière synchronisation complète, le résultat de chaque source, les corrections conservées et le nombre de rapprochements en attente. Le compteur au-dessus du tableau décrit uniquement les résultats filtrés. |
| 14. « À vérifier » | Une valeur source qui se contredit (HEX noir pour « White », HEX blanc pour un nom sombre, buse hors 120–500 °C, plateau hors 0–200 °C ou maximum à 0, densité hors 0,5–4,0, diamètre hors 1,0–3,2 mm) est signalée dans « État des données » et bloque l'export jusqu'à correction explicite dans la fiche. Vos corrections et les fiches historiques ne sont jamais remises en cause. |
| 15. Raccourcis | Ctrl+F : recherche ; Ctrl+E : exporter pour NFC ; Ctrl+U : sources et mise à jour ; Échap : désélection. L'export affiche un message de statut ; « Dossier d'export » ouvre le dossier. |

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
sont de la même matière ou couleur. Une référence fabricant **et** une couleur
compatible (même nom, ou même HEX sous un autre nom), ou un rapprochement exact
du produit/couleur, avec un conditionnement compatible, sont nécessaires. Les
grades restent distincts (« PLA+ » n'est pas « PLA »). Les renommages historiques
Polymaker sont explicites. En cas d'ambiguïté, aucune fusion arbitraire ni
référence supplémentaire n'est ajoutée au tableau ; chaque fiche source absorbée
reste tracée dans la fiche qui l'a conservée.

Les valeurs source gardent leur provenance. Une source constructeur peut remplacer
une valeur communautaire non modifiée. Une valeur source inconnue peut recevoir
un complément factuel. Une source qui cesse de publier une valeur ne vide jamais
la valeur locale ; une source qui renvoie moins de la moitié de ses références
précédentes est refusée. Dès qu'un champ est corrigé explicitement, il est protégé,
même si la nouvelle valeur est `null` ou identique à celle de la source. Les anciens
champs sans provenance restent protégés par précaution. Les données mises à part
sont signalées dans le bilan ; cette version ne fournit pas encore d'éditeur de
rapprochement manuel.
