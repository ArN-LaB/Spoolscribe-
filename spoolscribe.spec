# -*- mode: python ; coding: utf-8 -*-
"""
spoolscribe.spec — Build PyInstaller multiplateforme (win/mac/linux).

Mode **onefile** : produit un exécutable unique, sans dossier `_internal`.
  - Windows : dist/SpoolScribe.exe
  - macOS   : dist/SpoolScribe.app
  - Linux   : dist/SpoolScribe

Sur Windows, des métadonnées de version sont embarquées pour que l'OS affiche
le nom de l'app et l'auteur (au lieu de « Éditeur inconnu » vide) dans les
propriétés du fichier et la boîte SmartScreen/UAC.

Build :
    pyinstaller spoolscribe.spec --noconfirm
"""
import os
import sys

block_cipher = None

# ─── Métadonnées : source unique de vérité = core.py ──────────────────────
# La version n'est définie qu'une seule fois (core.APP_VERSION). Le .spec et
# pyproject.toml la lisent depuis là pour éviter toute désynchronisation (cf.
# l'ancienne release "sync version" inutile dans l'historique).
def _read_core_metadata():
    meta = {"APP_NAME": "SpoolScribe", "APP_VERSION": "0.0.0", "APP_AUTHOR": "ArN-LaB"}
    try:
        with open("core.py", "r", encoding="utf-8") as fh:
            src = fh.read()
        import re as _re
        for key in meta:
            m = _re.search(rf'^{key}\s*=\s*["\']([^"\']+)["\']', src, _re.M)
            if m:
                meta[key] = m.group(1)
    except OSError:
        pass
    return meta

_meta = _read_core_metadata()
APP_NAME = _meta["APP_NAME"]
APP_VERSION = _meta["APP_VERSION"]
APP_AUTHOR = _meta["APP_AUTHOR"]
APP_DESC = "Write OpenSpool / NFC spool tags for the Snapmaker U1"
_v = tuple(int(p) for p in (APP_VERSION.split(".") + ["0", "0", "0", "0"])[:4])

# ─── Icône optionnelle (par plateforme) ───────────────────────────────────
# Windows veut un .ico, macOS un .icns ; Linux n'utilise pas d'icône d'exe.
_icon = None
if sys.platform == "win32":
    _cands = ("data/app.ico",)
elif sys.platform == "darwin":
    _cands = ("data/app.icns",)
else:
    _cands = ()
for _candidate in _cands:
    if os.path.isfile(_candidate):
        _icon = _candidate
        break

# Données embarquées : (source, destination_relative_dans_le_bundle)
datas = [
    ("data", "data"),
    ("scripts", "scripts"),
    ("orca_profiles", "orca_profiles"),
]
# Filtre les dossiers absents pour éviter les erreurs de build.
datas = [(src, dst) for src, dst in datas if os.path.isdir(src)]

# ─── Métadonnées de version Windows (réduit l'effet « Éditeur inconnu ») ──
version_info = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable,
        StringStruct, VarFileInfo, VarStruct,
    )
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=_v, prodvers=_v, mask=0x3F, flags=0x0,
            OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0),
        ),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", APP_AUTHOR),
                StringStruct("FileDescription", APP_DESC),
                StringStruct("FileVersion", APP_VERSION),
                StringStruct("InternalName", APP_NAME),
                StringStruct("LegalCopyright", f"(c) {APP_AUTHOR}. MIT License."),
                StringStruct("OriginalFilename", f"{APP_NAME}.exe"),
                StringStruct("ProductName", APP_NAME),
                StringStruct("ProductVersion", APP_VERSION),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x0409, 1200])]),
        ],
    )

a = Analysis(
    ["app_gui.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "core",
        # Les scrapers dans scripts/ sont lancés via runpy depuis l'exe gelé ;
        # PyInstaller n'analyse pas leurs imports, on les déclare donc ici.
        "urllib", "urllib.request", "urllib.error", "urllib.parse",
        "http", "http.client", "ssl", "gzip", "bz2", "lzma", "zlib",
        "email", "json", "csv", "re", "difflib", "unicodedata",
        "argparse", "collections", "datetime", "time",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Allège le bundle : modules Qt inutilisés.
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets", "PySide6.QtCharts",
        "tkinter", "pdfplumber",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# ─── Onefile : un seul exécutable autonome (pas de dossier _internal) ─────
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,            # pas de console : app GUI pure
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
    version=version_info,      # None hors Windows
)

# ─── macOS : .app pour une expérience native ──────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=_icon,
        bundle_identifier=f"com.github.{APP_AUTHOR.lower()}.spoolscribe",
        info_plist={
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.utilities",
        },
    )
