# Jeux de référence — SpoolScribe v0.6.0

[Ressources de l’application](../../data/README.md) · [Développement](../../docs/DEVELOPMENT.md)

| Dossier | Rôle |
| --- | --- |
| `catalogues/` | Catalogue historique Polymaker/Prusament/ROSA3D et instantanés OFD/SpoolmanDB |
| `catalogues/audits/` | Rapports de provenance et de couverture associés aux instantanés |
| `orca/` | 48 profils officiels utilisés pour les tests de non-régression |
| `legacy/` | Instantané TheFilamentDB, réservé au développement et à l’enrichissement historique optionnel |
| `qr/ssqr1_vectors.json` | Vecteurs normatifs SSQR1, message NDEF exact pour les deux formats, sans données personnelles |
| `manifest.json` | Ancien emplacement et SHA-256 des 54 fichiers déplacés sans modification de contenu |

Les fixtures JSON synthétiques, exceptions et le contrat des 1 008 exports restent
ici, à côté de ce guide. Les tests travaillent sur des copies temporaires et
interdisent les connexions réseau. Aucun de ces fichiers n’est embarqué dans les
exécutables, ni copié dans une nouvelle installation utilisateur.

Le manifeste historique reste celui des 54 fichiers déplacés en v0.3.5 ;
les nouveaux vecteurs QR ne modifient ni ce manifeste ni les 48 profils Orca.

Les anciens chemins de logos présents dans ces instantanés restent volontairement
inchangés : les alias de ressources assurent leur lecture. Cela conserve les
empreintes des catalogues et prouve la compatibilité des installations existantes.
