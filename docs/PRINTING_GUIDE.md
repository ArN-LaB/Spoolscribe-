# QR à l’écran, puis impression facultative

[Guide utilisateur](USER_GUIDE.md) · [Contrat SSQR1](QR_FORMAT.md)

**v0.8.0 Pre-release.** Le transfert numérique est le parcours
par défaut : aucun support ni imprimante à choisir. Le Companion devra
savoir décoder SSQR1 et écrire le message NFC. Les téléchargements officiels seront
annoncés sur la [page Companion](COMPANION.md).

## Choisir selon l’usage

| Usage | Choix dans SpoolScribe | À vérifier |
| --- | --- | --- |
| Afficher le code ou partager un fichier numérique | **Aucun — QR à l’écran**, PNG/SVG | Pas d’imprimante nécessaire. Un lecteur ordinaire affiche le texte SSQR1. |
| Coller une étiquette sur une bobine | Une étiquette assez large, ou **Support personnalisé** | Largeur réellement imprimable, résolution du pilote, marge blanche, lecture du résultat. |
| Imprimante de bureau laser/jet d’encre | A4 ou dimensions personnalisées | Feuille adaptée à cette technologie, impression à taille réelle ; pas de mise à l’échelle automatique. Le mode A4 ne fournit pas un gabarit de planche multi-étiquettes. |

Les dimensions des étiquettes commerciales ne forment pas une norme universelle
pour le QR. Par exemple, les [étiquettes carrées Avery](https://www.avery.com/products/labels/shape/square-labels)
comprennent du 2 × 2 pouces, soit **50,8 × 50,8 mm**, différent du préréglage générique
50 × 50 mm. Saisissez les dimensions exactes et les marges de votre support.

Le choix **62 × 100 mm** affiche en italique l’exemple **Brother DK-11202**,
avec une invitation à vérifier la compatibilité de l’imprimante. C’est une
référence commerciale documentée, pas un code universel déduit des dimensions.
Aucune référence précise n’est attribuée automatiquement aux formats génériques
50 × 50 mm ou 100 × 150 mm. [Brochure Brother](https://www.brother.eu/-/media/product-downloads/uk/ql1100-ql110nwb-brochure.pdf), consultée le 5 novembre 2026.

## Planche A4 : reprendre la référence de la boîte

Dans le QR, **Formats et références d’étiquettes… → Références papier** donne
ces exemples informatifs. Une dimension ne détermine pas un code universel :
la matière, le nombre d’étiquettes, les marges et le pays de vente interviennent.
Aucune donnée comparative ne permet ici de les présenter comme les plus vendues.

| Exemple | Technologie | Dimensions commerciales / disposition | Gabarit ou fiche officielle |
| --- | --- | --- | --- |
| Avery L7165 | Laser | 99,1 × 67,7 mm ; 8 par A4 | [Gabarit L7165](https://www.avery.co.uk/template-l7165) : géométrie précise 99,06 × 67,73 mm. |
| Avery J8165 | Jet d’encre | 99,1 × 67,7 mm ; 8 par A4 | [Fiche J8165-100](https://www.avery.fr/produit/etiquettes-dexpedition-j8165-100) et code logiciel J8165. |
| Brother DK-11202 | Étiqueteuse compatible | 62 × 100 mm en rouleau | [Fiche Brother](https://store.brother.co.uk/supplies/label-printers/labels/dk/dk11202). Ce n’est pas une planche A4. |

**Parcours simple :** enregistrez le QR en PNG ou SVG, ouvrez le gabarit exact
indiqué sur votre boîte dans votre logiciel habituel, placez l’image et imprimez
à taille réelle. Faites un essai sur papier ordinaire pour vérifier l’alignement.
Le mode **Page A4** de SpoolScribe imprime un QR sur une page, **pas une planche
prépositionnée**. La gestion du gabarit, du pilote et du bac reste extérieure à l’app.
Ne supprimez pas la marge blanche du QR. Un code trop dense peut exiger un support
plus grand, même si la référence commerciale est correcte. Sources consultées le
5 novembre 2026 ; aucune impression physique revendiquée.

## Exemples documentés de familles d’imprimantes

Ces exemples ont des caractéristiques adaptées aux QR larges. Ils ne sont pas
une certification SSQR1 de SpoolScribe, ni une mesure de popularité, ni une recette
physique. Le pilote de votre système et la densité du QR restent déterminants.

| Famille | Caractéristiques constructeur utiles | Support à examiner |
| --- | --- | --- |
| Brother QL-800 / QL-810W / QL-820NWB | 300 × 300 ppp en mode standard, largeur de rouleau jusqu’à 62 mm et largeur d’impression annoncée de 58 mm | DK-11202 62 × 100 mm, ou rouleau continu adapté. Vérifier les marges acceptées par le pilote. |
| Zebra ZD421 | Résolution 203 ppp ou option 300 ppp ; version et largeur utile à vérifier | Supports larges, par exemple environ 100 × 150 mm ; renseigner leurs dimensions réelles. |
| Laser / jet d’encre | Selon le modèle et son pilote | Feuille adhésive compatible ; aucun matériel RFID spécifique requis pour imprimer le QR. |

Sources primaires : [fiche Brother QL](https://www.brother.eu/-/media/product-downloads/devices/nordics/eu_en/labelling-machines/ql_800_leaflet_english_single_pages.pdf),
[rouleau Brother DK-11202](https://store.brother.co.uk/supplies/label-printers/labels/dk/dk11202),
[caractéristiques Zebra ZD421](https://www.zebra.com/us/en/products/printers/desktop/zd400-series/zd421.html).
Consultées le 4 novembre 2026. Aucun pilote propriétaire ou Bluetooth direct ajouté.
L’application utilise les imprimantes déjà installées, via le dialogue du système.

## Pourquoi la taille dépend du message

Le calcul porte sur le QR produit, pas sur la marque de l’imprimante. Il garde
quatre modules blancs de chaque côté et des points d’imprimante entiers.
[DENSO WAVE](https://www.qrcode.com/en/howto/cell.html) préconise au moins quatre
points par module pour une utilisation stable. Le mode réduit à trois points
reste un choix explicite, avec essai de lecture requis.

Exemple géométrique : un QR version 15 possède 77 modules par côté, soit 85 avec
les marges blanches. À quatre points par module, il demande environ **42,5 mm à
203 ppp** ou **28,8 mm à 300 ppp**. Ce sont des minima géométriques, pas une garantie
de lecture. Le pilote est contrôlé de nouveau après le dialogue d’impression.

## Protection et vérification

**Standard (M)** convient au parcours normal. **Renforcée (Q)** ajoute de la
redondance et peut produire un code plus dense ou plus grand. Cela ne correspond
pas à un pourcentage garanti de surface que l’on pourrait masquer : la
[correction d’erreur](https://www.qrcode.com/en/about/error_correction.html) concerne
les données du code et dépend des dommages. Gardez le code net, contrasté et entier.

Ne collez une étiquette qu’après avoir vérifié sa lecture. Aucun essai physique
d’imprimante, scanner, téléphone ou écriture RFID n’est revendiqué ici.
