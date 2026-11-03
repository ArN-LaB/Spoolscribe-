# Documentation SpoolScribe v0.6.0 · Pre-release

**[Télécharger la préversion v0.6.0](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.6.0)** · **[Version stable v0.3.5](https://github.com/ArN-LaB/Spoolscribe-/releases/tag/v0.3.5)** · [Présentation](../README.md) · [Wiki](wiki/Home.md)

## Utiliser l’application

| Besoin | Guide |
| --- | --- |
| Découvrir le catalogue, ΔE, les imprimantes et le QR en images | [Parcours visuel v0.6.0](wiki/Visual-Tour.md) |
| Installer et préparer une première étiquette | [Démarrage](wiki/Getting-Started.md) |
| Langue, filtres croisés, favoris, bobines et copies personnelles | [Guide de l’interface](USER_GUIDE.md) |
| Choisir une imprimante ou un lecteur | [Compatibilité](wiki/Printers-and-Readers.md) |
| Écrire et relire une étiquette | [Guide NFC](wiki/Writing-RFID-Tags.md) · [Formats](FORMATS-NFC.md) |
| Actualiser le catalogue et comprendre ses limites | [Actualisation](wiki/Updating-the-Database.md) · [Sources](DATA_SOURCES.md) |
| Résoudre un problème | [FAQ](wiki/FAQ.md) |

## Comprendre et contribuer

- [Développement, commandes et compilation](DEVELOPMENT.md).
- [Structure du dépôt et maintenance](REPOSITORY.md).
- [Contrat des données et de l’export](DATA_FORMAT.md) · [QR numérique autonome SSQR1 du message NFC](QR_FORMAT.md).
- [Ressources de l’application](../data/README.md) · [Jeux de référence](../tests/fixtures/README.md).
- [Langues de l’interface](../data/translations/README.md).
- [Captures et logo animé : provenance et régénération](images/README.md).
- [Validation de la préversion v0.6.0](validation/v0.6.0.md) · [Stable v0.3.5](validation/v0.3.5.md).
- [Installation personnelle macOS](LOCAL_MACOS_INSTALL.md).
- [Roadmap](ROADMAP.md) · [Changelog](../CHANGELOG.md) · [Contribuer](../.github/CONTRIBUTING.md).
- [Confidentialité](PRIVACY.md) · [Marques](TRADEMARKS.md) · [Visuels des imprimantes](PRINTER_VISUALS.md) · [Licence](../LICENSE) · [Attributions](../NOTICE).

La v0.6.0 ajoute le QR numérique SSQR1 (PNG/SVG) pour le futur Companion ;
l’impression et les essais matériels restent différés. [Contrat](QR_FORMAT.md).

## Historique

La [validation v0.5.0](validation/v0.5.0.md) est conservée.
L’[index historique](archive/README.md) donne accès aux audits, retours UX et journaux des
versions précédentes dans leurs commits Git immuables. Leurs nombres de tests et états de publication sont datés ;
ils ne décrivent pas la version actuelle.

Les tests automatisés et les sondes des exécutables ne remplacent pas une recette
visuelle humaine ni une écriture/relecture NFC sur une imprimante réelle.

## Préversion v0.6.0

[Reader setup guide](PRINTER-CONFIGURATIONS.md) · [OpenTag3D export guide](OPENTAG3D.md) · [Validation status](validation/v0.6.0.md).
La préversion propose trois ZIP et leurs SHA-256. La stable reste v0.3.5.
Les tests logiciels ne certifient pas toutes les combinaisons imprimante/lecteur ;
[retours de compatibilité bienvenus](https://github.com/ArN-LaB/Spoolscribe-/issues/new?template=printer_compatibility.yml).
