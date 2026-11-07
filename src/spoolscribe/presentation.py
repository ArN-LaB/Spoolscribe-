"""Shared presentation metadata of Desktop (About dialog, docs checks): formats, links, credits.

Values come from the modules that implement them, so a format version change
cannot silently drift from what « À propos » announces. No Qt import here.
"""
from __future__ import annotations

from . import opentag3d, qr_transfer

OPENSPOOL_VERSION = "1.0"   # checked against core.build_openspool/validate_openspool by tests
FORMATS = (
    ("openspool", f"OpenSpool {OPENSPOOL_VERSION}"),
    ("opentag3d", f"OpenTag3D {opentag3d.VERSION}"),
    ("ssqr1", qr_transfer.PREFIX.rstrip(":")),
)
FORMAT_NAMES = dict(FORMATS)

REPOSITORY = "https://github.com/ArN-LaB/Spoolscribe-"
# (object name, French label for tr(), URL). Desktop privacy is docs/PRIVACY.md;
# docs/privacy/ belongs to Companion and is never presented as the Desktop policy.
LINKS = (
    ("projectGithub", "GitHub", REPOSITORY),
    ("projectDocumentation", "Documentation", REPOSITORY + "/wiki"),
    ("projectPrivacy", "Confidentialité (Desktop)", REPOSITORY + "/blob/main/docs/PRIVACY.md"),
    ("projectSupport", "Assistance · signaler un problème", REPOSITORY + "/issues/new/choose"),
    ("projectCompanion", "Companion : disponibilité", REPOSITORY + "/blob/main/docs/COMPANION.md"),
)
DONATION = ("supportProject", "Soutenir le projet (facultatif)", "https://buymeacoffee.com/arn_lab")

# French source texts (translated through messages.json); placeholders are the format names.
ABOUT_SUMMARY = ("Catalogue local de filaments, comparaison de couleurs déclarées, copies personnelles et références "
                 "couleur saisies ou importées. Prépare des fichiers {v0} et {v1} et un QR {v2} pour transférer le "
                 "message NFC, notamment vers Companion. L’écriture physique nécessite une application et un matériel "
                 "compatibles.")
ABOUT_INDEPENDENCE = ("Projet indépendant des fabricants. Code SpoolScribe sous licence MIT ; données et composants "
                      "tiers selon leurs propres licences.")
# Short credits (details shown on demand). Not an MIT grant for third-party parts.
CREDITS = (
    "Open Filament Database et SpoolmanDB : MIT.",
    "TheFilamentDB : CC-BY 4.0, pour les couleurs qui en proviennent.",
    "Données publiques des fabricants ; marques et logos affichés à titre d’identification seulement.",
    "QR générés avec Segno (BSD 3-Clause).",
    "Interface Qt et PySide6 de The Qt Company, sous leurs propres licences (LGPLv3), distinctes du code MIT du projet.",
)


def format_arguments() -> dict:
    """Placeholders of :data:`ABOUT_SUMMARY`, in its order."""
    return dict(v0=FORMAT_NAMES["openspool"], v1=FORMAT_NAMES["opentag3d"], v2=FORMAT_NAMES["ssqr1"])
