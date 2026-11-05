# Utiliser SpoolScribe v0.8.0 · stable

[Accueil](../README.md) · [Documentation](README.md) · [Version stable v0.8.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.8.0) · [Politique de versions](RELEASE_POLICY.md)

[Parcours visuel de v0.8.0 : catalogue, ΔE, imprimantes et QR](wiki/Visual-Tour.md).
Les captures sont réelles, en anglais ; le même parcours existe dans les quatre langues.

## Langue de l’interface

Anglais, français, espagnol et chinois simplifié. La langue du système est utilisée lorsqu’elle est disponible ; sinon l’anglais est choisi. **Paramètres → Interface** permet de choisir une langue. Enregistrez puis choisissez **Redémarrer maintenant** ou **Plus tard**. Les favoris, données et réglages sont conservés. Les noms des filaments et les diagnostics techniques externes ne sont pas traduits.

## Trouver et mémoriser un filament

- La recherche principale porte sur les fabricants, produits, matières et couleurs.
  Les recherches latérales réduisent les listes de fabricants et de matières. Les matières sont classées par ordre alphabétique, sans déplacer les éléments selon leur effectif.
- Survolez un fabricant pour faire apparaître le bouton de favori à droite, puis cliquez pour le
  mémoriser. Une étoile reste visible pour les favoris ; le clic droit propose
  aussi cette action. Le nom sélectionne le fabricant. Parcourir la liste ne change pas les favoris.
- La fiche et les cartes de grille utilisent la même étoile pour les filaments.
- Les boutons **Fabricants** et **Filaments**, sous le titre Favoris, limitent les résultats aux
  favoris correspondants. Ils se combinent avec les autres filtres et restent
  mémorisés. Ce sont des filtres, pas des commandes de suppression des favoris.
- **Effacer** vide les trois recherches, les filtres et la sélection. Les favoris
  enregistrés restent intacts. Polymaker est le choix initial d’une première session.
- Les sections **Fabricants**, **Matières** et **État des données** se replient
  indépendamment (clic ou touche Espace sur leur titre). Une section fermée affiche
  son choix actif sous son titre ; le menu **Filtres** indique le nombre et le détail des
  critères. Replier ne change ni les filtres, ni la page, ni le tri, ni la sélection,
  et l’état ouvert/fermé est mémorisé. Les compteurs de fabricants et de matières
  tiennent compte des autres filtres ; ceux de l’état des données portent sur tout le catalogue.

Le menu **Filtres**, en haut de la colonne gauche, propose **Tout replier** et
**Tout déplier**. Ces actions changent seulement la présentation : les critères,
la sélection, les tris et les favoris restent conservés. Les listes gardent une
hauteur contenue ; leurs sélections utilisent le même accent discret que les
autres contrôles de filtrage.


Les commandes **liste/grille** sont près des résultats. En liste, cliquez sur un
intitulé pour trier ; recliquez pour inverser. Le clic droit choisit le tri principal,
le tri secondaire ou les colonnes. En grille, chaque carte nomme le produit et la
couleur, rappelle le diamètre et montre une bobine. Le nom de couleur est mis en avant ;
le produit et le fabricant restent lisibles, plus discrets (le fabricant l’est davantage
lorsqu’un filtre le fixe déjà). L’état « à compléter » ou « à vérifier » est écrit sur la carte.
Le focus clavier est un cadre pointillé, distinct de la sélection. Les cartes restent sélectionnables
et leur étoile se clique directement. Recliquer une sélection, cliquer dans le vide
ou appuyer sur Échap désélectionne. La pagination apparaît si nécessaire.

## Lire la fiche

Le bloc filament rassemble une seule fois le logo, le produit, la matière et la
couleur. L’aperçu de bobine en projection parallèle montre deux flasques, des rayons et un enroulement
reprenant le HEX de la référence sélectionnée. Une couleur
absente ou encore ambiguë reste neutre avec un point d’interrogation : cette image
n’ajoute aucune valeur au catalogue et ne remplace pas un choix explicite.

Les paramètres d’impression sont regroupés en quatre blocs : **buse**, **plateau**,
**diamètre**, **densité**. « Modifier… » ouvre un brouillon dans la fiche, sans fenêtre
séparée : l’identité du filament reste affichée, les tuiles gardent les valeurs enregistrées
et les champs modifiés sont signalés. **Enregistrer une copie** crée la copie personnelle
nommée « Produit @Personnel » (suffixe modifiable, par exemple @U1) ; **Annuler** n’écrit rien.
Seuls les champs modifiés deviennent des corrections confirmées ; un champ vidé signifie « inconnu ».
La couleur HEX peut aussi être corrigée dans la copie ; pour une couleur signalée « à vérifier »,
la case **Confirmer ce HEX tel quel** confirme explicitement la valeur affichée, sans la modifier. La source reste intacte et les valeurs de
la copie sont protégées lors des actualisations. Enregistrer le même suffixe pour la même
référence met à jour sa copie existante. Avant de changer de fiche, de variante, de filtre
effaçant la sélection, de réglages importés ou de fermer, SpoolScribe demande d’enregistrer,
d’abandonner ou de continuer l’édition ; un brouillon modifié bloque l’export et l’aperçu.
Cette commande et « Détails et sources » sont alignées sous les quatre caractéristiques. Survolez
un paramètre pour connaître son usage pour l’imprimante choisie. Les températures
restent à adapter au trancheur et au plateau ; leur présence dans le JSON ne signifie
pas qu’elles seront automatiquement appliquées par l’imprimante.

**Détails et sources** déplie les références et la provenance dans un encadré, puis les fait défiler dans la zone visible.

Le panneau **Paramètres de l’étiquette**, aussi affiché pendant l’édition, regroupe
les valeurs en cinq blocs : buse, plateau, diamètre, densité et couleur. Les plages
minimale/maximale restent distinctes. Les valeurs retenues sont mises en avant ;
les valeurs ajustées, inconnues ou à vérifier sont nommées explicitement. La source
commune n’est indiquée qu’une fois. **Origine des valeurs** déplie les références,
le profil Orca s’il s’applique et la copie personnelle. Chaque provenance reste
accessible par champ, avec la valeur effectivement retenue dans le format choisi. Une valeur
inconnue n’est jamais présentée comme un écart. Le bouton ↺ rétablit la valeur de référence
dans la copie personnelle seulement ; une référence à vérifier ne se rétablit pas automatiquement.
Le HEX reste une couleur déclarée, pas une mesure. Les identifiants
OFD/SMDB restent des identifiants de source, pas des références commerciales.
Le filtre « État des données » décrit les informations disponibles ; il ne note pas
la qualité physique du filament.

La zone imprimante et les détails du filament fonctionnent de façon exclusive :
ouvrir **Détails et sources** ou **Modifier…** replie la zone imprimante. La
flèche près de **Configurer** permet de l’ouvrir ; les détails de la fiche se
ferment alors. Fermer une zone ne rouvre pas automatiquement l’autre. Si un
brouillon contient des modifications, les choix habituels d’enregistrement,
d’abandon ou de poursuite de l’édition restent proposés avant de le fermer.
L’état de préparation et l’action d’export restent visibles. Le panneau matériel
et la fiche partagent les mêmes bords ; leurs hauteurs s’adaptent à leur contenu.


## Teintes proches

Les catégories de la colonne de gauche partagent le même cadre repliable. Le bouton
**Filtres** ouvre le détail des critères et les commandes de repli ; les choix actifs restent aussi lisibles
dans les en-têtes repliés. Fabricants, matières et état conservent leurs listes à parcourir.

La section **Teintes**, sous **Matières** à gauche, rassemble le choix de couleur :
cliquez sur la pastille pour choisir une couleur, ou saisissez un code puis **Comparer**.
Elle fonctionne sans filament sélectionné et ne modifie aucune fiche.
**Teintes**, dans la fiche, ouvre cette même section avec la couleur du filament.
En grille, le badge compact **ΔE**, à côté du diamètre, affiche l’écart sur chaque tuile : plus le nombre est petit,
plus la couleur déclarée est proche. **Écart maximal**, dans cette section, ouvre
**Paramètres > Teintes**. La limite initiale est **10** ; les choix **3**, **10**, **20**,
**Toutes les couleurs** ou une valeur personnelle de **0 à 200** sont mémorisés et
inclus dans l’enregistrement des réglages. Il s’agit de plages d’exploration, pas de
seuils certifiant une correspondance après impression. Les résultats trop éloignés
sont masqués ; l’aide les compte séparément des fiches non comparables.

Le classement se fait dans la
zone de résultats, en liste ou en grille, et respecte les filtres de la colonne de gauche.
Les égalités sont départagées par fabricant, produit, couleur et référence. Les couleurs
inconnues, les teintes en conflit, les multicolores et les translucides sont exclus et
comptés ; les effets (soie, métal, lueur…) restent classés mais signalés. ΔE00 compare des
couleurs d’écran déclarées par les sources : il ne prédit pas le rendu imprimé. **Retirer**
désactive seulement la comparaison ; **Effacer** réinitialise tous les filtres, sans supprimer les favoris.
**Retirer** efface aussi une saisie non appliquée et devient inactif quand il n’y a rien
à retirer. Le champ vide indique « Code couleur », sans réafficher une fausse couleur d’exemple.
Replier la section ne désactive pas la couleur choisie : son code reste dans le titre et le résumé des filtres.
Le titre des résultats affiche **couleurs comparables**. **Aide**, dans la section Teintes,
ouvre une fenêtre organisée : **Les résultats** présente la couleur, les effectifs et quatre
cartes expliquant les exclusions ; **La méthode** explique le classement et ses limites.
Sans couleur choisie, seule la méthode est proposée, sans résultat fictif.

### Lab, RGB ou fichier : saisir des valeurs couleur

Dans **Teintes**, « Lab, RGB ou fichier… » ouvre une fenêtre à trois
entrées : **Saisir** (HEX, RGB ou L*a*b*), **Coller** (texte copié depuis
l’application de votre appareil ; seules les valeurs étiquetées sont reconnues
et vous confirmez le jeu principal) et **Importer** (CSV/TSV : encodage,
séparateur, décimales et colonnes confirmés, bilan « N valides / M à corriger /
K doublons » avant enregistrement). La mesure peut être enregistrée dans un
registre local distinct du catalogue, réutilisée comme cible, liée à une
référence exacte ou détachée, sans jamais modifier la couleur du catalogue.

Pour une mesure L*a*b*, indiquez l’éclairage et l’observateur lus sur votre
appareil : D65 et 2° permettent une **proximité indicative** avec les codes
déclarés du catalogue ; D50, 10° ou « Je ne sais pas » conservent la mesure sans
la comparer. Les conditions documentées (géométrie, SCI/SCE, ouverture,
calibration) et la description de l’échantillon (matériau, finition, épaisseur,
fond) sont facultatives, inconnues par défaut, et se renseignent dans « Plus de
détails » ou par les colonnes du fichier. Chaque entrée garde son propre
brouillon : les boutons agissent sur l’entrée affichée ; modifier un texte collé
retire la proposition jusqu’à une nouvelle interprétation ; si un fichier mappe
à la fois Lab, HEX ou RGB, vous choisissez le jeu principal. Un petit écart ne
garantit pas le rendu imprimé. Saisie de couleurs disponible depuis v0.7.0 ; parcours guidé et profils d’appareil affinés en v0.8.0.

## Choisir le conditionnement

Dans **Paramètres → Bobines**, choisissez le poids préféré et, si souhaité,
« Avec bobine » ou « Recharge ». Le choix initial est **1 kg, indifférent**.
« Selon la fiche » conserve la référence proposée par le catalogue.

La préférence présélectionne uniquement une référence réellement disponible. Une
préférence de forme s’applique lorsque la source renseigne cette forme. Si le poids
n’existe pas, la référence réelle est conservée et la fiche l’indique. Aucun poids
ni aucune recharge n’est inventé. Vous pouvez changer le choix dans la fiche ; votre
choix manuel reste prioritaire pour ce groupe pendant la session.

Si les sources donnent plusieurs teintes, comparez les pastilles et choisissez
celle de votre bobine. La préférence de poids ne tranche jamais cette divergence.
Le conditionnement est ensuite choisi parmi les références de la teinte confirmée.
Un écran n’est pas une mesure colorimétrique. Matières, grades, diamètres,
transparences et variantes multicolores restent distincts selon leurs données.

## Exporter

Le pied de fiche relie deux étapes dans un même encadré : **1. l’imprimante et son lecteur**,
avec la photo disponible et **Configurer**, puis **2. l’étiquette et le format de fichier**.
Les entrées nommant une machine ou une famille disposent d’une vraie photo produit
à fond transparent. Pour une famille, la légende indique le modèle illustré comme
exemple. Seuls les choix génériques sans modèle précis et les lecteurs autonomes
gardent un pictogramme clairement identifié. Ces repères sont communs au choix
d’imprimante, à sa fiche et au parcours d’export. [Origine des photos](PRINTER_VISUALS.md).
Il affiche une conclusion simple :
**Le fichier tient sur votre étiquette**, avec une jauge de **place disponible**, ou la
raison d’un blocage, formulée avec les termes de l’utilisateur (par exemple « Indiquez
la température de buse »). **Détails**, à côté de l’étiquette, ouvre une fenêtre :
**Votre parcours** explique préparer, écrire et relire ; **Informations techniques**
regroupe les tailles dans des cartes séparées et conserve le diagnostic exact du moteur.
La jauge indique l’espace disponible
après la réserve choisie ; elle ne confirme ni l’écriture ni la lecture réelle de l’étiquette.
L’action principale suit cet état :
**Exporter pour NFC** lorsque tout est prêt, **Corriger les caractéristiques…**,
**Préciser la couleur…**, **Confirmer la couleur…** ou **Ajuster l’étiquette…** sinon.
Les commandes **Voir le JSON** et **Afficher le fichier** restent visibles dessous, alignées
sur les mêmes bords. **Afficher le fichier** n’est disponible qu’après une écriture réussie
pendant la session, si le fichier existe encore ; la ligne du dernier export indique s’il
correspond à la fiche et aux réglages actuels. Un fichier exporté n’est ni une étiquette
écrite, ni une étiquette relue, ni une validation de l’imprimante.
L’inspection défile vers le fichier lorsqu’elle s’ouvre, sans changer la taille de la fenêtre. Chaque export propose un dossier de destination, mémorise le dernier choix et confirme le chemin du fichier après son écriture. Annuler le choix de dossier ne crée rien. Le dossier proposé se règle aussi dans **Paramètres → Export**. Le menu général contient
les réglages matériels et les paramètres du conditionnement.

Les accents sont discrets : violet pour la recherche de teintes, bleu pour le parcours
matériel, vert lorsque le fichier tient et ambre pour une étape à compléter. Les libellés
et actions donnent toujours le sens de l’état ; la couleur seule ne porte aucune instruction.

Pour OpenTag3D, **Voir l’export** affiche le profil NFC Tools ; le NDEF brut affiche
ses champs décodés et octets. **Préparer l’étiquette…**, proposé comme action principale
si des valeurs manquent, demande les cibles et la masse explicites. Pour les modifier
ensuite : **Détails → Votre parcours → Modifier les valeurs de l’étiquette…**.
Un seul bouton de préparation apparaît dans la fiche. [Guide OpenTag3D](OPENTAG3D.md).

Le fichier inspecté est identique à celui exporté avec les mêmes options. Les
profils OpenSpool compact/complet et les réserves d’écriture restent dans les réglages
matériels avancés. SpoolScribe prépare le fichier ; une autre application écrit
l’étiquette. L’archive JSON complète reste disponible dans le menu général.

### QR numérique SSQR1 et Companion

Le contrat numérique SSQR1 est validé pour OpenSpool 1.0 et OpenTag3D 2.004.
L’impression et les essais physiques sont différés ; les commandes
d’impression déjà présentes ne font pas partie de cette validation.

**Afficher le QR Code — SpoolScribe Companion**, à côté de **Exporter pour NFC**,
n’est actif que si l’export NFC est possible : mêmes blocages (couleur, brouillon, configuration,
capacité, valeurs OpenTag3D). Le QR contient **tout le message NFC** de l’export, sans
serveur ni lien ; un lecteur QR ordinaire n’affiche qu’un texte de transfert. Écrire une
puce depuis ce QR demandera la future application SpoolScribe Companion, encore en développement, sans lien de téléchargement public.

La fenêtre garde les données du moment de son ouverture (heure indiquée) : changer de
fiche, de teinte ou d’étiquette dans la fenêtre principale ne modifie ni ce qui est
enregistré ni ce qui est imprimé. Rouvrez le QR pour prendre en compte un changement.
Le code reste entier, noir sur blanc, dans les deux thèmes et à toutes les tailles de fenêtre :
la fenêtre ne descend pas sous la taille qui le garde lisible. **Aperçu de l’étiquette** montre
le gabarit avec ses dimensions, à un zoom indicatif (l’écran n’est pas calibré).

**Enregistrer en PNG…** et **Enregistrer en SVG…**, juste sous le code, utilisent le dialogue
du système ; annuler n’écrit rien. Si l’extension ajoutée désigne un fichier existant, une
confirmation est demandée. Le support, **Imprimer…** et les **Détails techniques** sont dans
la partie basse, qui défile sans réduire le code. **Imprimer…** passe par le dialogue
d’impression du système, relit le format et la résolution acceptés par le pilote, puis refuse
d’envoyer une page trop dense.
« Tâche transmise au système » ne prouve pas qu’une étiquette est sortie ni qu’elle se lit :
faites un essai de lecture.

**Dans v0.8.0 :** chaque ouverture commence avec
**Aucun — QR à l’écran**. Choisir une étiquette est facultatif ; les dimensions
précédentes restent mémorisées pour un usage ultérieur. Les supports proposés sont
50 × 50, 62 × 100, 100 × 150 mm, A4 et un format personnalisé. Le pilote fournit
la zone réellement imprimable ; une géométrie trop dense reste refusée.

**Protection du QR** se trouve avant les options d’impression : Standard (M) ou
Renforcée (Q). La protection ajoute de la redondance pour aider à lire un code
abîmé ; elle peut le rendre plus grand. Ce n’est pas une promesse de lecture.
Les **Détails techniques** regroupent message, structure du QR, étiquette NFC
et papier éventuel ; l’empreinte de contrôle peut être copiée séparément.
[Choisir un support et une imprimante](PRINTING_GUIDE.md).

## Configurer l’imprimante

Ouvrez **Mon matériel** depuis le menu général. La flèche ouvre une recherche par
marque ou modèle avec descriptions et photographies disponibles. Confirmez par
« Choisir » ; « Annuler » conserve le matériel précédent.

Composez ensuite votre installation par boutons : **lecteur**, **logiciel**, puis
**solution installée**. Choisir USB ou réseau ne confirme pas automatiquement un
plugin. Le résumé fixé sous les choix distingue identification dans l’imprimante,
inventaire externe et lecteur autonome. Les versions, pilotes et connexions sont
regroupés sous **Prérequis et détails**.

Le sélecteur de catégorie ouvre des cartes illustrées : installations exportables,
lecteurs USB ou réseau, logiciel d’origine ou modifié, autre format RFID et
intégration à vérifier. Chaque carte explique son rôle et compte les choix qui
correspondent à la recherche en cours. Cliquer sur une carte applique le filtre ;
Annuler ne change rien. Un même modèle peut relever de plusieurs catégories,
sans que ce filtre confirme la présence réelle d’un lecteur ou d’un logiciel.
Choisissez un format proposé, votre NTAG215/216 et, pour OpenTag3D, le logiciel
qui importera le fichier. [Installations et limites](PRINTER-CONFIGURATIONS.md).

Les choix nommant une machine ou une famille précise utilisent les photographies
produit embarquées ; le modèle réellement illustré est précisé si le choix regroupe
plusieurs machines. Les lecteurs et installations génériques gardent un symbole
explicite. Les symboles des cartes de catégories désignent une fonction, pas un
modèle d’imprimante. [Visuels et provenances](PRINTER_VISUALS.md).

Choisissez le logiciel installé lorsque sa compatibilité en dépend. Une nouvelle
installation ne suppose pas qu’un U1 utilise paxx12. Lorsque la lecture est possible,
choisissez NTAG215 ou NTAG216, selon vos étiquettes. Les formats propriétaires Bambu,
Creality, Prusa OpenPrintTag et autres ne deviennent pas compatibles du fait de la
présence d’une photo ou d’un descriptif. Aucun firmware n’est modifié par ce réglage.

La liste embarquée reste disponible si sa copie distante n’est pas publiée. Les
autres erreurs de mise à jour sont signalées. Les sources des visuels et descriptifs
figurent dans [PRINTER_VISUALS.md](PRINTER_VISUALS.md).

## Actualiser le catalogue et conserver ses réglages

**Actualiser le catalogue** utilise directement les sources déjà enregistrées après consentement.
Au premier téléchargement, le choix des sources est proposé. Pour modifier ces
choix, ouvrez **Paramètres → Catalogue → Sources du catalogue**. La présentation est
compacte ; **i** déplie la portée, les compteurs et les limites d’une source.

Le catalogue est non exhaustif. Les données officielles sont prioritaires sur les
sources communautaires et vos corrections restent prioritaires. Décocher une source
conserve ses anciennes fiches. Le rapport présente des compteurs, des états en français et des détails techniques dépliables. Le bouton de base ouvre la même présentation, avec des dates lisibles. « Stockage et valeurs conservées » remplace la liste des sources par une zone technique de 140 pixels défilante, sans agrandir la fenêtre ; « Retour aux sources » restaure la liste. Un succès décrit le traitement des sources ; il ne certifie pas toutes leurs couleurs et ne résout pas tous les rapprochements.

L’installateur ne contient ni catalogue ni profils Orca. Le premier téléchargement
constitue la base. Les suivants suivent la cadence choisie ; le cache reste disponible
en cas d’échec. Une restauration inhibe l’actualisation automatique pendant la session.
Les filtres, favoris, tris, colonnes, disposition et préférences d’export sont
mémorisés et inclus dans les fichiers de réglages. Le consentement réseau ne
s’importe pas. La mise à jour de l’application propose le téléchargement officiel ;
son remplacement demeure manuel.

## Rythme visuel

Les commandes standard utilisent une hauteur de 32 pixels logiques. L’export principal mesure 48 pixels ; les icônes liste/grille sont placées dans un groupe de 32 pixels. Les boutons d’une même ligne partagent la même hauteur et, pour les paires de la fiche, la même largeur. Les menus utilisent une hauteur de contenu et des marges communes. La barre de défilement de la fiche apparaît uniquement en cas de dépassement ; le pied d’export suit la largeur visible. Les dimensions sont vérifiées aux tailles documentées dans le rapport de recette.

Les cartes de recherche d’imprimante calculent leur hauteur sur la largeur disponible, y compris après plusieurs redimensionnements. Elles ne répartissent pas le texte sur la hauteur restante. Le formulaire « Modifier » utilise une grille unique, avec son suffixe et ses six caractéristiques alignés et les commandes « Annuler » / « Enregistrer ».

Dans **À propos**, le bouton « Soutenir le projet · Buy Me a Coffee » ouvre [arn_lab](https://buymeacoffee.com/arn_lab) dans le navigateur au clic seulement. Aucun widget JavaScript distant n’est chargé par l’application. Le lien correspond au fichier [FUNDING.yml](../.github/FUNDING.yml).

La vérification de version efface son message d’attente lorsqu’elle se termine. Dans À propos, GitHub et Buy Me a Coffee sont deux boutons de dimensions communes. Les autres formats RFID/NFC sont expliqués dans [Formats NFC](FORMATS-NFC.md) ; l’application conserve son export OpenSpool 1.0.

La poignée entre les colonnes permet de redimensionner les panneaux. La largeur
choisie est conservée, dans les limites nécessaires à la lisibilité. Une flèche vers
le bas indique une section ouverte ; vers la droite, une section repliée, y compris
pour la zone imprimante. Pendant une actualisation, la carte de progression indique
la source en cours et son numéro d’étape ; la barre ne certifie pas le succès des sources.


Les fenêtres de paramètres et d’aide privilégient la place utile au contenu et
restent dans l’écran où elles s’ouvrent. Les pages longues défilent sans masquer
les actions de fermeture. Les onglets tiennent sur une ligne lorsque la place le
permet ; sinon, des flèches visibles et une coupure ondulée à chaque bord masqué
signalent la suite. Leurs titres complets restent disponibles en infobulle.
Les logos de fabricants reçoivent un halo léger en thème sombre : leur fichier et
leurs couleurs d’origine ne sont pas modifiés ; le halo disparaît en thème clair.


Modifier et Détails sont deux vues distinctes : l’une ferme l’autre. Si un brouillon
a changé, le passage aux détails demande quoi en faire. Le résumé des caractéristiques
est remplacé par la vue ouverte, afin de ne pas afficher deux fois les mêmes données.
Les détails regroupent les plages de température sur une ligne et les autres valeurs
avec leur unité. L’origine commune est indiquée une seule fois ; les références
chiffrées identiques ne sont pas répétées. Les différences Orca/personnelles restent
consultables dans Origine des valeurs, sans changer ce qui sera réellement exporté.

**Maximum 3** signifie **ΔE ≤ 3**, sans pourcentage ni marge supplémentaire.
Exemple : l’écart entre `C8E6A0` et `D8EEA3` est **3,035999** dans le calcul existant :
il est exclu à 3, inclus à 10. Le score affiché devient **3,04**. Les scores sont
arrondis à l’écran au centième supérieur pour ne pas masquer un dépassement ; le
filtre conserve le score calculé à six décimales. L’infobulle donne cette valeur précise.
Aucun de ces nombres ne certifie une correspondance de couleur après impression.

Après ouverture ou remise en page native, une fenêtre peut encore gagner en hauteur
si son contenu défile alors qu’il reste de la place sur son écran. La limite de l’écran
et les boutons restent respectés ; les contenus trop longs continuent à défiler.

Les liens de téléchargement mobile seront regroupés sur la [page Companion](COMPANION.md), accessible depuis la fenêtre QR. Les [références papier et gabarits](PRINTING_GUIDE.md) sont informatifs ; aucune planche multi-étiquettes n’est créée automatiquement.
