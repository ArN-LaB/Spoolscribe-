# Utiliser SpoolScribe v0.3.0 — version de développement

Cette interface locale est décrite dans
[VALIDATION-UX-RETOURS-6-v0.3.0.md](VALIDATION-UX-RETOURS-6-v0.3.0.md).
Les passes précédentes restent accessibles depuis
[VALIDATION-AUDIT-v0.3.0.md](VALIDATION-AUDIT-v0.3.0.md).

## Trouver et mémoriser un filament

- La recherche principale porte sur les fabricants, produits, matières et couleurs.
  Les recherches latérales réduisent les listes de fabricants et de matières. Les matières sont classées par ordre alphabétique, sans déplacer les éléments selon leur effectif.
- Survolez un fabricant pour faire apparaître **☆** à droite, puis cliquez pour le
  mémoriser. Une étoile **★** reste visible pour les favoris ; le clic droit propose
  aussi cette action. Le nom sélectionne le fabricant. Parcourir la liste ne change pas les favoris.
- La fiche et les cartes de grille utilisent la même étoile pour les filaments.
- Les boutons **Fabricants** et **Filaments**, sous le titre Favoris, limitent les résultats aux
  favoris correspondants. Ils se combinent avec les autres filtres et restent
  mémorisés. Ce sont des filtres, pas des commandes de suppression des favoris.
- **Effacer** vide les trois recherches, les filtres et la sélection. Les favoris
  enregistrés restent intacts. Polymaker est le choix initial d’une première session.

Les commandes **liste/grille** sont près des résultats. En liste, cliquez sur un
intitulé pour trier ; recliquez pour inverser. Le clic droit choisit le tri principal,
le tri secondaire ou les colonnes. En grille, chaque carte nomme le produit et la
couleur, rappelle le diamètre et montre une bobine. Les cartes restent sélectionnables
et leur étoile se clique directement. Recliquer une sélection, cliquer dans le vide
ou appuyer sur Échap désélectionne. La pagination apparaît si nécessaire.

## Lire la fiche

Le bloc filament rassemble une seule fois le logo, le produit, la matière et la
couleur. L’aperçu de bobine en projection parallèle montre deux flasques, des rayons et un enroulement
reprenant le HEX de la référence sélectionnée. Une couleur
absente ou encore ambiguë reste neutre avec un point d’interrogation : cette image
n’ajoute aucune valeur au catalogue et ne remplace pas un choix explicite.

Les paramètres d’impression sont regroupés en quatre blocs : **buse**, **plateau**,
**diamètre**, **densité**. « Modifier… » conserve l’édition locale existante. Cette commande et « Détails et sources » sont alignées sous les quatre caractéristiques. Survolez
un paramètre pour connaître son usage pour l’imprimante choisie. Les températures
restent à adapter au trancheur et au plateau ; leur présence dans le JSON ne signifie
pas qu’elles seront automatiquement appliquées par l’imprimante.

**Détails et sources** déplie les références et la provenance dans un encadré, puis les fait défiler dans la zone visible. Les identifiants
OFD/SMDB restent des identifiants de source, pas des références commerciales.
Le filtre « État des données » décrit les informations disponibles ; il ne note pas
la qualité physique du filament.

## Choisir le conditionnement

Dans **⚙ → Paramètres → Bobines**, choisissez le poids préféré et, si souhaité,
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

Le pied de fiche affiche le matériel choisi et le résultat du calcul de capacité.
**Exporter pour NFC** occupe la largeur de la fiche. Les commandes **Voir le JSON**
et **Dossier d’export** restent visibles dessous, alignées sur les mêmes bords.
L’inspection défile vers le fichier lorsqu’elle s’ouvre. Le menu général contient
les réglages matériels et les paramètres du conditionnement.

Le fichier inspecté est identique à celui exporté avec les mêmes options. Les
formats compact/complet et les réserves d’écriture restent dans les réglages
matériels avancés. SpoolScribe prépare le fichier ; une autre application écrit
l’étiquette. L’archive JSON complète reste disponible dans le menu général.

## Configurer l’imprimante

Ouvrez **⚙ → Mon matériel** depuis le menu général. Cliquez le choix avec sa flèche visible pour ouvrir une fenêtre de recherche par marque ou modèle, avec des cartes, une description courte et des photographies lorsqu’elles sont disponibles. La sélection est confirmée par « Choisir » ; « Annuler » conserve le matériel précédent. La fiche distingue la description de la machine et son statut OpenSpool.
Des visuels officiels sont embarqués pour la U1, la X1 Carbon illustrant les familles
Bambu et la Plus4 illustrant les familles QIDI. Le modèle illustré est précisé si
nécessaire. Les autres entrées restent textuelles : aucune icône générique n’est
présentée comme une photographie de leur modèle.

Choisissez le logiciel installé lorsque sa compatibilité en dépend. Une nouvelle
installation ne suppose pas qu’un U1 utilise paxx12. Lorsque la lecture est possible,
choisissez NTAG215 ou NTAG216, selon vos étiquettes. Les formats propriétaires Bambu,
Creality, Prusa OpenPrintTag et autres ne deviennent pas compatibles du fait de la
présence d’une photo ou d’un descriptif. Aucun firmware n’est modifié par ce réglage.

La liste embarquée reste disponible si sa copie distante n’est pas publiée. Les
autres erreurs de mise à jour sont signalées. Les sources des visuels et descriptifs
figurent dans [PRINTER_VISUALS.md](PRINTER_VISUALS.md).

## Synchroniser et conserver ses réglages

**Synchroniser** utilise directement les sources déjà enregistrées après consentement.
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

Les cartes de recherche d’imprimante calculent leur hauteur sur la largeur disponible, y compris après plusieurs redimensionnements. Elles ne répartissent pas le texte sur la hauteur restante. Le formulaire « Modifier » utilise une grille unique, avec ses six champs alignés et les commandes « Annuler » / « Enregistrer ».
