#!/usr/bin/env python3
"""Procédure locale macOS : préparer, signer (Developer ID), notariser, stapler et empaqueter.

Bibliothèque standard uniquement. Chaque sous-commande fait une seule étape :

    preflight      lecture seule : outils Apple, interpréteur, types d'identités
    prepare        crée un espace privé neuf, exporte un commit, crée la venv de build
    build          PyInstaller avec la spec inchangée, dans l'export privé
    inspect        inventaire Mach-O, liens, architectures, otool, ressources, plan de signature
    probes         quatre sondes gelées (oracles installés après PyInstaller), candidat inchangé
    sanitize       retire FinderInfo/ResourceFork de la copie neuve seulement
    sign           signature explicite de l'intérieur vers l'extérieur (--confirm-signing)
    notarize       ZIP de soumission privé puis notarytool (--confirm-submission)
    notary-status  reprise d'une soumission existante, sans nouvel envoi (--confirm-apple-query)
    staple         stapler + validation, seulement après Accepted et journal examiné
    package        SpoolScribe-macos.zip + .sha256, vérification d'une extraction neuve
    assess         spctl sur une nouvelle extraction (--confirm-assessment)
    status         état de l'espace de travail, sans action

Aucune identité, aucun profil et aucun secret ne sont inscrits dans ce fichier.
Voir docs/MACOS_NOTARIZATION.md.
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import hashlib
import importlib.util
import json
import os
import platform as _platform
import plistlib
import re
import secrets
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
from pathlib import Path, PurePosixPath

TOOL_PATH = Path(__file__).resolve()
DEFAULT_CHECKOUT = TOOL_PATH.parents[1]

APP_NAME = "SpoolScribe"
APP_DIR = APP_NAME + ".app"
BUNDLE_ID = "com.github.arn-lab.spoolscribe"
FINAL_ZIP = "SpoolScribe-macos.zip"
SUBMISSION_ZIP = "SpoolScribe-submission.zip"
STATE_FILE = ".spoolscribe-notarize.json"
MARKER = "spoolscribe-macos-notarize/1"
REQUIRED_PYTHON = (3, 12)
PILOT_ARCHS = ("arm64",)
DEVELOPER_ID_APPLICATION = "Developer ID Application"
# Types de certificats Apple affichables ; tout autre préfixe de libellé reste privé (« autre type »).
KNOWN_IDENTITY_TYPES = ("Apple Development", "Apple Distribution", "Developer ID Application",
                        "Developer ID Installer", "Mac Developer", "Mac App Distribution",
                        "Mac Installer Distribution", "3rd Party Mac Developer Application",
                        "3rd Party Mac Developer Installer", "iPhone Developer", "iPhone Distribution")
FORBIDDEN_XATTRS = ("com.apple.FinderInfo", "com.apple.ResourceFork")
FORBIDDEN_ENTITLEMENTS = ("com.apple.security.get-task-allow",)
# Exceptions possibles, jamais appliquées par défaut : chacune exige une validation humaine préalable.
REVIEWABLE_ENTITLEMENTS = (
    "com.apple.security.cs.allow-jit",
    "com.apple.security.cs.allow-unsigned-executable-memory",
    "com.apple.security.cs.disable-library-validation",
)
BUNDLE_SUFFIXES = (".app", ".bundle", ".plugin", ".appex", ".xpc")
SYSTEM_PREFIXES = ("/usr/lib/", "/System/Library/")
SYNCED_MARKERS = ("/library/cloudstorage/", "/library/mobile documents/")
QML_PREFIXES = ("QtQml", "QtQuick", "QtVirtualKeyboard")
CI_ORACLES = ("Pillow>=10.0", "zxing-cpp==2.3.0")
FROZEN_PROBES = ("check_frozen_tls.py", "check_frozen_catalogue.py",
                 "check_frozen_measurements.py", "check_frozen_ssqr1.py")
MAX_LINK_HOPS = 40

EXIT_OK, EXIT_BLOCKED, EXIT_READY_MISSING, EXIT_PENDING = 0, 1, 3, 4
VERDICT_READY = "READY TO NOTARIZE — PRÉREQUIS HUMAINS MANQUANTS"

TOOLS = {
    "xcode-select": "/usr/bin/xcode-select", "xcrun": "/usr/bin/xcrun", "codesign": "/usr/bin/codesign",
    "ditto": "/usr/bin/ditto", "lipo": "/usr/bin/lipo", "otool": "/usr/bin/otool",
    "spctl": "/usr/sbin/spctl", "security": "/usr/bin/security", "xcodebuild": "/usr/bin/xcodebuild",
}

SHA1_RE = re.compile(r"^[0-9A-Fa-f]{40}$")
COMMIT_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TIMEOUT_RE = re.compile(r"^([1-9][0-9]{0,3})([smh])$")
IDENTITY_LINE = re.compile(r'^\s*\d+\)\s+([0-9A-Fa-f]{40})\s+"([^"]*)"\s*(.*)$')


class ProcedureError(Exception):
    """Refus ou blocage : la procédure s'arrête sans étape suivante.

    Seul un libellé du catalogue fermé PUBLIC_REFUSALS est publiable (str, args, repr). Tout autre
    texte (`raw`) et le détail éventuel (`detail` : chemin, valeur, diagnostic) ne vont que dans la
    trace privée de l'espace de travail. Les libellés ne contiennent jamais de donnée interpolée.
    """

    def __init__(self, message, detail=None):
        self.raw = message
        self.detail = detail
        self.public = message if isinstance(message, str) and message in PUBLIC_REFUSALS else None
        super().__init__(self.public or UNLISTED_REFUSAL)

    def __str__(self):
        return self.public or UNLISTED_REFUSAL


UNLISTED_REFUSAL = "refus non catalogué"
# Catalogue fermé : exactement les littéraux passés à ProcedureError dans ce fichier (vérifié par test).
PUBLIC_REFUSALS = frozenset((
    'espace privé altéré : dossiers logs/ et private/ requis',
    "--commit doit être l'empreinte complète du commit approuvé",
    '--workspace est requis',
    'Hardened Runtime absent',
    'Python 3.12 requis',
    'archive finale déjà produite dans cet espace',
    'archive finale modifiée',
    'archive modifiée pendant les vérifications',
    'attributs FinderInfo/ResourceFork présents : signature refusée',
    'attributs interdits encore présents',
    'attributs étendus non pris en charge sur cette plateforme',
    'aucun identifiant de soumission conservé : aucune reprise possible ici',
    'aucune reprise automatique pour ce statut de soumission',
    'autorité de signature inattendue',
    'avertissements du journal à relire : relancer avec --acknowledge-log-warnings',
    'build PyInstaller en échec (voir logs privés)',
    'build manquant',
    'candidat absent : lancer build',
    'candidat différent du build et de la signature enregistrés',
    'candidat déjà signé',
    'candidat déjà staplé',
    'candidat déjà staplé : sondes à relancer sur une extraction, pas sur le candidat',
    "candidat modifié depuis l'étape enregistrée : reconstruire dans un nouvel espace",
    'chaîne de certificats inattendue',
    'chemin absolu requis',
    "cible de lien différente dans l'export",
    'codesign --verify --deep --strict en échec',
    'commit approuvé introuvable dans le checkout',
    'contenu du candidat modifié pendant le nettoyage',
    'contenu exporté différent du commit',
    "contrôles de l'extraction en échec",
    'création de la venv privée impossible',
    'création du ZIP de soumission impossible',
    'création du ZIP final impossible',
    'destination préexistante : choisir un dossier neuf',
    'dossier de sortie préexistant',
    'dossier de soumission préexistant',
    'dossier non créé par cette procédure (marqueur absent)',
    'dossier parent : lien cassé',
    'délai invalide : utiliser par exemple 30m, 2h, 900s',
    'entitlement interdit',
    'entitlement non prévu par la procédure',
    'entitlements de type inattendu',
    'entitlements embarqués différents des entitlements approuvés',
    'envoi Apple non autorisé : ajouter --confirm-submission après accord explicite',
    "envoi notarytool en échec (authentification, réseau ou refus) ; voir logs privés. Ne pas renvoyer automatiquement : vérifier l'historique en privé.",
    'espace privé introuvable',
    'export différent du commit',
    'export git archive impossible',
    'extraction différente du candidat staplé',
    'extraction ditto impossible',
    "exécutable principal de l'app introuvable pour la vérification",
    "fichier d'entitlements illisible",
    "fichier d'entitlements vide ou invalide",
    'get-task-allow=true embarqué',
    'identifiant de soumission inattendu',
    'identité ambiguë : même empreinte présente plusieurs fois',
    'identité de signature non fournie (--identity, empreinte SHA-1)',
    'identité introuvable parmi les identités de signature valides',
    'inspection en échec : signature refusée',
    'installation des oracles QA impossible (après PyInstaller)',
    'installation du snapshot de build impossible (voir logs privés)',
    'interpréteur arm64 requis pour ce pilote',
    'interpréteur introuvable',
    'interpréteur inutilisable',
    'interpréteur non fourni (--python)',
    "interpréteur sans extraction tar sûre (filtre 'data')",
    "journal notarial indisponible : rien n'est validé sans journal lu",
    "l'archive ne contient pas uniquement SpoolScribe.app",
    "l'espace privé doit être en mode 0700",
    "l'espace privé doit être hors du checkout",
    "l'espace privé doit être hors stockage synchronisé",
    "l'espace privé doit être un dossier réel, pas un lien",
    "l'espace privé est géré par un File Provider (stockage synchronisé)",
    "l'espace privé n'appartient pas à l'utilisateur courant",
    'la soumission ne correspond pas au candidat signé',
    "le chemin de l'espace privé doit être absolu",
    'le dossier parent doit exister',
    'le stapling a modifié autre chose que Contents/CodeResources',
    'lecture de la signature en échec',
    'lecture des entitlements en échec',
    'lecture des versions installées impossible (voir logs privés)',
    'les sondes ont modifié le candidat',
    "lien attendu dans l'export",
    'ls-tree impossible',
    "marqueur de l'espace privé illisible",
    "marqueur de l'espace privé incohérent (copie ou déplacement ?)",
    "marqueur de l'espace privé invalide",
    'nom de profil notarytool requis (--profile)',
    'notarisation non acceptée : corriger, reconstruire, nouvel espace',
    'notarytool info en échec (authentification ou réseau) ; statut inchangé',
    'objet Git non exportable',
    'package manquant',
    "plan de signature incohérent : l'app doit être signée en dernier",
    'plan via un lien refusé',
    'prepare incomplet',
    'procédure macOS uniquement ; aucune action',
    'requête Apple non autorisée : ajouter --confirm-apple-query',
    "référence d'identité ambiguë : fournir l'empreinte SHA-1 de 40 caractères",
    "réponse d'une autre soumission",
    'réponse notarytool JSON inattendue',
    'réponse notarytool non JSON',
    'sanitize manquant',
    'signature ad hoc refusée',
    'signature en échec : candidat inutilisable',
    'signature non autorisée : ajouter --confirm-signing après accord explicite du pilote',
    "signature ou ticket en échec après extraction. Décision de packaging requise ; le workflow n'est pas modifié.",
    "sortie d'entitlements de forme inattendue",
    "sortie d'entitlements illisible",
    'stapling non autorisé : ajouter --confirm-stapling',
    'stapling refusé : notarisation Accepted et journal examiné requis',
    'statut Apple inattendu (valeur brute dans logs/ seulement)',
    'timestamp sécurisé absent',
    "type d'identité refusé (Developer ID Application requis)",
    'un build existe déjà dans cet espace : créer un nouvel espace',
    'une signature a déjà été tentée : reconstruire dans un nouvel espace',
    'une soumission existe déjà : utiliser notary-status, jamais un nouvel envoi',
    "valeur d'entitlement inattendue",
    'verify_archive.py en échec',
    'versions installées différentes du snapshot',
    'vérification de signature en échec',
    'vérifications de signature non passées',
    'échec de signature ou de timestamp : candidat inutilisable',
    'échec du stapling, de sa validation ou de la vérification',
    'équipe de signature absente',
    'équipes de signature différentes',
    'étape préalable manquante',
    'évaluation Gatekeeper non autorisée : ajouter --confirm-assessment',
))


# ─── Exécution des commandes externes (injectable pour les tests) ──────────
class Result:
    """Résultat d'une commande. Classe simple (pas de dataclass) : le module se charge aussi
    par importlib sans inscription préalable dans sys.modules (dataclasses y cherche le module
    pour interpréter les annotations différées)."""

    __slots__ = ("returncode", "stdout", "stderr", "timed_out")

    def __init__(self, returncode, stdout, stderr, timed_out=False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    @property
    def ok(self):
        return self.returncode == 0 and not self.timed_out

    def __eq__(self, other):
        if not isinstance(other, Result):
            return NotImplemented
        return (self.returncode, self.stdout, self.stderr, self.timed_out) == (
            other.returncode, other.stdout, other.stderr, other.timed_out)

    __hash__ = None

    def __repr__(self):
        return (f"Result(returncode={self.returncode!r}, stdout=<{len(self.stdout or '')} car.>, "
                f"stderr=<{len(self.stderr or '')} car.>, timed_out={self.timed_out!r})")


def _text(value):
    if value is None:
        return ""
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value


class Runner:
    """Lance une commande sans shell ; ne journalise jamais l'environnement."""

    def run(self, args, *, cwd=None, env=None, timeout=600):
        try:
            done = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True,
                                  text=True, encoding="utf-8", errors="replace", timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            return Result(None, _text(exc.stdout), _text(exc.stderr), timed_out=True)
        except OSError as exc:
            return Result(127, "", f"{type(exc).__name__}: {exc.strerror or exc}")
        return Result(done.returncode, done.stdout, done.stderr)


class DarwinXattrs:
    """listxattr/removexattr de libSystem, sans suivre les liens (XATTR_NOFOLLOW)."""

    NOFOLLOW = 0x0001

    def __init__(self):
        import ctypes
        self._ctypes = ctypes
        self._lib = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        self._lib.listxattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]
        self._lib.listxattr.restype = ctypes.c_ssize_t
        self._lib.removexattr.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        self._lib.removexattr.restype = ctypes.c_int

    def list(self, path):
        raw = os.fsencode(str(path))
        size = self._lib.listxattr(raw, None, 0, self.NOFOLLOW)
        if size < 0:
            raise OSError(self._ctypes.get_errno(), "listxattr", str(path))
        if size == 0:
            return []
        buf = self._ctypes.create_string_buffer(size)
        size = self._lib.listxattr(raw, buf, size, self.NOFOLLOW)
        if size < 0:
            raise OSError(self._ctypes.get_errno(), "listxattr", str(path))
        return [n.decode("utf-8", "replace") for n in buf.raw[:size].split(b"\0") if n]

    def remove(self, path, name):
        if self._lib.removexattr(os.fsencode(str(path)), name.encode(), self.NOFOLLOW) != 0:
            raise OSError(self._ctypes.get_errno(), "removexattr", str(path))


class NoXattrs:
    def list(self, path):
        return []

    def remove(self, path, name):
        raise ProcedureError("attributs étendus non pris en charge sur cette plateforme")


# ─── Fonctions pures : empreintes, arbres, liens, Mach-O ──────────────────
def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_id(path, length):
    data = Path(path).read_bytes()
    algo = hashlib.sha1 if length == 40 else hashlib.sha256
    return algo(b"blob %d\0" % len(data) + data).hexdigest()


def tree_manifest(root):
    """Contenu, modes et cibles de liens, sans jamais suivre un lien."""
    root = Path(root)
    entries = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(root).as_posix()
            info = os.lstat(path)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                entries[rel] = ("link", os.readlink(path))
            elif stat.S_ISDIR(info.st_mode):
                entries[rel] = ("dir", mode)
            elif stat.S_ISREG(info.st_mode):
                entries[rel] = ("file", mode, sha256_file(path))
            else:
                entries[rel] = ("special", mode)
    return entries


def tree_digest(manifest):
    payload = json.dumps(sorted(manifest.items()), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def manifest_differences(before, after):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(k for k in set(before) & set(after) if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def resolve_inside(root, rel):
    """Résout un chemin relatif à `root` en suivant les liens, sans jamais sortir de `root`.

    Retourne (chemin_résolu, None) ou (None, motif) : cible absolue, sortie, boucle, lien cassé.
    """
    root = Path(root)
    pending = [p for p in PurePosixPath(rel).parts if p not in ("", ".")]
    resolved = []
    hops = 0
    while pending:
        part = pending.pop(0)
        if part in ("", "."):
            continue
        if part == "..":
            if not resolved:
                return None, "sort du candidat"
            resolved.pop()
            continue
        candidate = root.joinpath(*resolved, part)
        try:
            info = os.lstat(candidate)
        except FileNotFoundError:
            return None, "lien cassé"
        if stat.S_ISLNK(info.st_mode):
            hops += 1
            if hops > MAX_LINK_HOPS:
                return None, "boucle de liens"
            target = os.readlink(candidate)
            if target.startswith("/") or os.path.isabs(target):
                return None, "cible absolue"
            pending = [p for p in PurePosixPath(target).parts] + pending
            continue
        if pending and not stat.S_ISDIR(info.st_mode):
            return None, "lien cassé"
        resolved.append(part)
    return "/".join(resolved), None


CPU_TYPES = {7: "i386", 0x01000007: "x86_64", 12: "arm", 0x0100000C: "arm64",
             0x0200000C: "arm64_32", 18: "ppc", 0x01000012: "ppc64"}
THIN_MAGIC = {b"\xfe\xed\xfa\xce": ">", b"\xfe\xed\xfa\xcf": ">",
              b"\xce\xfa\xed\xfe": "<", b"\xcf\xfa\xed\xfe": "<"}
FAT_MAGIC = {b"\xca\xfe\xba\xbe": (">", 20), b"\xca\xfe\xba\xbf": (">", 32),
             b"\xbe\xba\xfe\xca": ("<", 20), b"\xbf\xba\xfe\xca": ("<", 32)}
MH_EXECUTE, MH_DYLIB, MH_BUNDLE = 2, 6, 8
SIGNABLE_FILETYPES = {MH_EXECUTE: "executable", MH_DYLIB: "dylib", MH_BUNDLE: "bundle"}


def _arch_name(cputype, subtype):
    name = CPU_TYPES.get(cputype & 0xFFFFFFFF, f"cpu-{cputype & 0xFFFFFFFF:#x}")
    if name == "arm64" and subtype & 0xFF == 2:
        return "arm64e"
    return name


def macho_info(path):
    """Identifie un Mach-O par son en-tête (pas par extension ni bit exécutable)."""
    try:
        with open(path, "rb") as stream:
            head = stream.read(32)
            if len(head) < 8:
                return None
            magic = head[:4]
            if magic in THIN_MAGIC:
                if len(head) < 16:
                    return None
                endian = THIN_MAGIC[magic]
                cputype, subtype, filetype = struct.unpack(endian + "iII", head[4:16])
                return {"archs": [_arch_name(cputype, subtype)], "filetype": filetype, "fat": False}
            if magic in FAT_MAGIC:
                endian, size = FAT_MAGIC[magic]
                count = struct.unpack(endian + "I", head[4:8])[0]
                if not 0 < count <= 30:  # exclut notamment les fichiers .class Java
                    return None
                stream.seek(8)
                table = stream.read(count * size)
                if len(table) < count * size:
                    return None
                archs, filetypes = [], set()
                for index in range(count):
                    entry = table[index * size:(index + 1) * size]
                    if size == 20:
                        cputype, subtype, offset = struct.unpack(endian + "iII", entry[:12])
                    else:
                        cputype, subtype, offset = struct.unpack(endian + "iIQ", entry[:16])
                    stream.seek(offset)
                    slice_head = stream.read(16)
                    if len(slice_head) < 16 or slice_head[:4] not in THIN_MAGIC:
                        return None
                    filetypes.add(struct.unpack(THIN_MAGIC[slice_head[:4]] + "I", slice_head[12:16])[0])
                    archs.append(_arch_name(cputype, subtype))
                filetype = filetypes.pop() if len(filetypes) == 1 else -1
                return {"archs": archs, "filetype": filetype, "fat": True}
    except OSError:
        return None
    return None


def parse_identities(text):
    identities = []
    for line in text.splitlines():
        match = IDENTITY_LINE.match(line)
        if not match:
            continue
        label = match.group(2)
        kind = label.split(":", 1)[0].strip() if ":" in label else "inconnu"
        identities.append({"sha1": match.group(1).upper(), "type": kind, "label": label,
                           "valid": not match.group(3).strip()})
    return identities


def select_identity(identities, reference):
    """Retourne l'unique identité Developer ID Application désignée ; refuse tout le reste."""
    if not reference:
        raise ProcedureError("identité de signature non fournie (--identity, empreinte SHA-1)")
    if reference.strip() == "-":
        raise ProcedureError("signature ad hoc refusée")
    if not SHA1_RE.match(reference):
        raise ProcedureError("référence d'identité ambiguë : fournir l'empreinte SHA-1 de 40 caractères")
    matches = [i for i in identities if i["sha1"] == reference.upper() and i["valid"]]
    if not matches:
        raise ProcedureError("identité introuvable parmi les identités de signature valides")
    if len(matches) > 1:
        raise ProcedureError("identité ambiguë : même empreinte présente plusieurs fois")
    if matches[0]["type"] != DEVELOPER_ID_APPLICATION:
        raise ProcedureError("type d'identité refusé (Developer ID Application requis)", detail=matches[0]["type"])
    return matches[0]


def parse_otool_load_commands(text):
    info = {"minos": None, "sdk": None, "rpaths": [], "dylibs": [], "weak": [], "id": None}
    command = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("cmd "):
            command = line[4:].strip()
            continue
        key, _, value = line.partition(" ")
        value = re.sub(r"\s+\(offset \d+\)$", "", value.strip())
        if command == "LC_BUILD_VERSION" and key in ("minos", "sdk") and info[key] is None:
            info[key] = value
        elif command == "LC_VERSION_MIN_MACOSX" and key in ("version", "sdk"):
            info["minos" if key == "version" else "sdk"] = info["minos" if key == "version" else "sdk"] or value
        elif command == "LC_RPATH" and key == "path":
            info["rpaths"].append(value)
        elif command in ("LC_LOAD_DYLIB", "LC_REEXPORT_DYLIB", "LC_LAZY_LOAD_DYLIB",
                         "LC_LOAD_UPWARD_DYLIB") and key == "name":
            info["dylibs"].append(value)
        elif command == "LC_LOAD_WEAK_DYLIB" and key == "name":
            info["weak"].append(value)
        elif command == "LC_ID_DYLIB" and key == "name":
            info["id"] = value
    return info


def _join(*parts):
    joined = [p for part in parts if part for p in PurePosixPath(part).parts]
    return "/".join(joined)


def resolve_dependency(app, file_rel, name, rpaths, exec_dir):
    """Classe une dépendance : system, internal, external, unresolved ou escape."""
    if name.startswith(SYSTEM_PREFIXES):
        return "system", None
    prefix, _, rest = name.partition("/")
    loader_dir = str(PurePosixPath(file_rel).parent)
    loader_dir = "" if loader_dir == "." else loader_dir
    candidates = []
    if prefix == "@executable_path":
        candidates = [_join(exec_dir, rest)]
    elif prefix == "@loader_path":
        candidates = [_join(loader_dir, rest)]
    elif prefix == "@rpath":
        for rpath in rpaths:
            head, _, tail = rpath.partition("/")
            if head == "@loader_path":
                candidates.append(_join(loader_dir, tail, rest))
            elif head == "@executable_path":
                candidates.append(_join(exec_dir, tail, rest))
    elif name.startswith("/"):
        return "external", name
    else:
        return "unresolved", name
    escaped = False
    for candidate in candidates:
        resolved, error = resolve_inside(app, candidate)
        if resolved is not None and (Path(app) / resolved).is_file():
            return "internal", resolved
        escaped = escaped or error == "sort du candidat"
    return ("escape" if escaped else "unresolved"), name


def parse_codesign_details(text):
    authorities = re.findall(r"^Authority=(.*)$", text, re.M)
    team = re.search(r"^TeamIdentifier=(.*)$", text, re.M)
    flags = re.search(r"^CodeDirectory .*flags=0x[0-9a-fA-F]+\(([^)]*)\)", text, re.M)
    return {
        "authority_type": authorities[0].split(":", 1)[0].strip() if authorities else None,
        "chain": [a.split(":", 1)[0].strip() for a in authorities[1:]],
        "team": team.group(1).strip() if team else None,
        "runtime": bool(flags and "runtime" in flags.group(1).split(",")),
        "secure_timestamp": bool(re.search(r"^Timestamp=", text, re.M)),
        "signed_time_only": bool(re.search(r"^Signed Time=", text, re.M)),
        "adhoc": bool(re.search(r"^Signature=adhoc", text, re.M)),
    }


def parse_entitlements(result):
    """Entitlements embarqués, depuis le Result complet de `codesign -d --entitlements - --xml`.

    Une sortie vide ne vaut « aucun entitlement » qu'après une commande réellement réussie.
    Échec, expiration, XML partiel ou type inattendu : refus générique (diagnostic dans les logs privés).
    """
    if not isinstance(result, Result) or not result.ok:
        raise ProcedureError("lecture des entitlements en échec")
    text = (result.stdout or "").strip()
    if not text:
        return {}
    if not text.startswith(("<?xml", "<plist")) or not text.endswith("</plist>"):
        raise ProcedureError("sortie d'entitlements de forme inattendue")
    try:
        value = plistlib.loads(text.encode("utf-8"))
    except Exception:  # expat, plistlib, valeurs : jamais de texte brut propagé
        raise ProcedureError("sortie d'entitlements illisible") from None
    if not isinstance(value, dict):
        raise ProcedureError("entitlements de type inattendu")
    return value


def load_entitlements(path):
    try:
        value = plistlib.loads(Path(path).read_bytes())
    except (OSError, plistlib.InvalidFileException, ValueError) as exc:
        raise ProcedureError("fichier d'entitlements illisible", detail=repr(exc)) from None
    if not isinstance(value, dict) or not value:
        raise ProcedureError("fichier d'entitlements vide ou invalide")
    for key, item in value.items():
        if key in FORBIDDEN_ENTITLEMENTS:
            raise ProcedureError("entitlement interdit", detail=key)
        if key not in REVIEWABLE_ENTITLEMENTS:
            raise ProcedureError("entitlement non prévu par la procédure", detail=key)
        if item is not True:
            raise ProcedureError("valeur d'entitlement inattendue", detail=key)
    return value


def check_entitlements(found, approved):
    if found.get("com.apple.security.get-task-allow") is True:
        raise ProcedureError("get-task-allow=true embarqué")
    if found != approved:
        raise ProcedureError("entitlements embarqués différents des entitlements approuvés")


def parse_timeout(text):
    match = TIMEOUT_RE.match(text or "")
    if not match:
        raise ProcedureError("délai invalide : utiliser par exemple 30m, 2h, 900s")
    return int(match.group(1)) * {"s": 1, "m": 60, "h": 3600}[match.group(2)]


def parse_notary_json(text, *, need):
    try:
        value = json.loads(text)
    except (TypeError, ValueError):
        raise ProcedureError("réponse notarytool non JSON") from None
    if not isinstance(value, dict) or any(not isinstance(value.get(k), str) for k in need):
        raise ProcedureError("réponse notarytool JSON inattendue")
    if "id" in value and not UUID_RE.match(value["id"]):
        raise ProcedureError("identifiant de soumission inattendu")
    return value


APPLE_STATUSES = ("Accepted", "In Progress", "Invalid", "Rejected")
# Catégories partageables : vocabulaire fermé, jamais de texte fourni par Apple.
LOG_CATEGORIES = {
    "schema:log": "journal non objet JSON",
    "schema:jobId": "jobId absent ou de type inattendu",
    "schema:status": "status absent ou de type inattendu",
    "schema:sha256": "sha256 de type ou de forme inattendus",
    "schema:issues": "issues de type inattendu",
    "schema:issue": "élément d'issues mal formé",
    "schema:ticketContents": "ticketContents de type inattendu",
    "schema:ticket": "élément de ticketContents mal formé",
    "job-mismatch": "journal d'une autre soumission",
    "status-not-accepted": "statut du journal différent de Accepted",
    "sha256-mismatch": "empreinte différente du ZIP soumis",
    "sha256-absent": "empreinte de l'archive absente du journal",
    "issue-error": "issue Apple de sévérité error",
    "issue-unknown-severity": "issue Apple de sévérité inconnue",
    "issue-warning": "issue Apple de sévérité warning",
    "ticket-absent": "ticketContents absent",
    "uncovered-macho": "Mach-O absents de ticketContents",
}


def apple_status_category(value):
    return value if isinstance(value, str) and value in APPLE_STATUSES else "inattendu"


def examine_notary_log(log, *, submission_id, zip_sha256, macho_paths):
    """Analyse le journal Apple ; renvoie seulement des catégories contrôlées et des compteurs.

    Le texte des issues, les chemins et toute valeur fournie par Apple restent dans le journal privé.
    Les types bruts sont validés avant toute normalisation : `{}`, `False`, `0` ou `""` ne valent
    jamais « aucune issue ». Seules les absences (clé manquante ou null) sont admises.
    """
    errors, warnings = [], []
    counts = {"issues": 0, "issue_errors": 0, "issue_warnings": 0, "ticket_entries": 0, "uncovered": 0}

    def review(status):
        return {"errors": sorted(set(errors)), "warnings": sorted(set(warnings)), "status": status,
                "issues": counts["issues"], "issue_errors": counts["issue_errors"],
                "issue_warnings": counts["issue_warnings"], "ticket_entries": counts["ticket_entries"],
                "uncovered": counts["uncovered"]}

    if not isinstance(log, dict):
        errors.append("schema:log")
        return review(None)
    job = log.get("jobId")
    if not isinstance(job, str):
        errors.append("schema:jobId")
    elif job != submission_id:
        errors.append("job-mismatch")
    status = log.get("status")
    if not isinstance(status, str):
        errors.append("schema:status")
    elif status != "Accepted":
        errors.append("status-not-accepted")
    digest = log.get("sha256")
    if digest is None:
        warnings.append("sha256-absent")
    elif not isinstance(digest, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", digest):
        errors.append("schema:sha256")
    elif digest.lower() != zip_sha256:
        errors.append("sha256-mismatch")
    issues = log.get("issues")
    if issues is not None and not isinstance(issues, list):
        errors.append("schema:issues")
    for issue in issues if isinstance(issues, list) else []:
        if not isinstance(issue, dict) or not isinstance(issue.get("severity"), str) \
                or not isinstance(issue.get("message", ""), (str, type(None))):
            errors.append("schema:issue")
            continue
        counts["issues"] += 1
        if issue["severity"] == "error":
            counts["issue_errors"] += 1
            errors.append("issue-error")
        elif issue["severity"] == "warning":
            counts["issue_warnings"] += 1
            warnings.append("issue-warning")
        else:
            errors.append("issue-unknown-severity")
    tickets = log.get("ticketContents")
    covered = set()
    if tickets is None:
        warnings.append("ticket-absent")
    elif not isinstance(tickets, list):
        errors.append("schema:ticketContents")
    else:
        marker = APP_DIR + "/"
        for entry in tickets:
            if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                errors.append("schema:ticket")
                continue
            if marker in entry["path"]:
                covered.add(entry["path"].split(marker, 1)[1])
    counts["ticket_entries"] = len(covered)
    counts["uncovered"] = len(set(macho_paths) - covered)
    if counts["uncovered"]:
        warnings.append("uncovered-macho")
    return review(apple_status_category(status))


def describe_categories(codes):
    return [f"{code} ({LOG_CATEGORIES.get(code, 'catégorie inconnue')})" for code in codes]


def read_app_version(source):
    tree = ast.parse((Path(source) / "src/spoolscribe/core.py").read_text(encoding="utf-8"))
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "APP_VERSION" for t in node.targets))


def load_include_resource(source):
    path = Path(source) / "src/spoolscribe/packaging_rules.py"
    spec = importlib.util.spec_from_file_location("_export_packaging_rules", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.include_resource


def _now():
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()


# ─── Orchestrateur ─────────────────────────────────────────────────────────
class Procedure:
    def __init__(self, *, runner=None, platform=None, machine=None, xattrs=None, which=None,
                 out=None, checkout=None, tool_path=None):
        self.platform = platform or sys.platform
        self.machine = machine or _platform.machine()
        self.runner = runner or Runner()
        self._xattrs = xattrs
        self.which = which or shutil.which
        self.out = out or sys.stdout
        self.checkout = Path(checkout or DEFAULT_CHECKOUT)
        self.tool_path = Path(tool_path or TOOL_PATH)
        self.workspace = None
        self.state = None
        self._log_index = 0

    # ── Sortie et journal privé ────────────────────────────────────────
    def say(self, text=""):
        print(text, file=self.out)

    @property
    def xattrs(self):
        if self._xattrs is None:
            self._xattrs = DarwinXattrs() if self.platform == "darwin" else NoXattrs()
        return self._xattrs

    def run(self, args, *, step, cwd=None, env=None, timeout=600):
        result = self.runner.run(args, cwd=cwd, env=env, timeout=timeout)
        if self.workspace is not None:
            self._log_index += 1
            logs = self.workspace / "logs"
            name = f"{self.state['log_counter'] + self._log_index:04d}-{step}.txt"
            text = ("$ " + " ".join(str(a) for a in args) + "\n"
                    + f"returncode={result.returncode} timed_out={result.timed_out}\n"
                    + "--- stdout\n" + result.stdout + "\n--- stderr\n" + result.stderr + "\n")
            _write_private(logs / name, text)
        return result

    def tool(self, name):
        return TOOLS[name]

    def child_env(self, **extra):
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env.update(extra)
        return env

    def require_macos(self):
        if self.platform != "darwin":
            raise ProcedureError("procédure macOS uniquement ; aucune action", detail=self.platform)

    # ── Espace de travail possédé par la procédure ─────────────────────
    def check_private_destination(self, destination):
        destination = Path(destination).expanduser()
        if not destination.is_absolute():
            raise ProcedureError("le chemin de l'espace privé doit être absolu")
        if os.path.lexists(destination):
            raise ProcedureError("destination préexistante : choisir un dossier neuf")
        parent = destination.parent
        if parent.is_symlink() and not parent.exists():
            raise ProcedureError("dossier parent : lien cassé")
        if not parent.is_dir():
            raise ProcedureError("le dossier parent doit exister")
        real = Path(os.path.realpath(parent)) / destination.name
        checkout = Path(os.path.realpath(self.checkout))
        if real == checkout or checkout in real.parents or real in checkout.parents:
            raise ProcedureError("l'espace privé doit être hors du checkout")
        lowered = str(real).lower() + "/"
        if any(marker in lowered for marker in SYNCED_MARKERS):
            raise ProcedureError("l'espace privé doit être hors stockage synchronisé")
        for ancestor in [real.parent, *real.parent.parents]:
            try:
                names = self.xattrs.list(ancestor)
            except OSError:
                continue
            if any(n.startswith("com.apple.fileprovider.") for n in names):
                raise ProcedureError("l'espace privé est géré par un File Provider (stockage synchronisé)")
        return real

    def open_workspace(self, path):
        if not path:
            raise ProcedureError("--workspace est requis")
        workspace = Path(path).expanduser()
        try:
            info = os.lstat(workspace)
        except FileNotFoundError:
            raise ProcedureError("espace privé introuvable") from None
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise ProcedureError("l'espace privé doit être un dossier réel, pas un lien")
        if hasattr(os, "getuid") and info.st_uid != os.getuid():
            raise ProcedureError("l'espace privé n'appartient pas à l'utilisateur courant")
        if stat.S_IMODE(info.st_mode) & 0o077:
            raise ProcedureError("l'espace privé doit être en mode 0700")
        state_path = workspace / STATE_FILE
        try:
            state_info = os.lstat(state_path)
        except FileNotFoundError:
            raise ProcedureError("dossier non créé par cette procédure (marqueur absent)") from None
        if not stat.S_ISREG(state_info.st_mode):
            raise ProcedureError("marqueur de l'espace privé invalide")
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except ValueError:
            raise ProcedureError("marqueur de l'espace privé illisible") from None
        if state.get("marker") != MARKER or state.get("workspace") != os.path.realpath(workspace) \
                or not state.get("token"):
            raise ProcedureError("marqueur de l'espace privé incohérent (copie ou déplacement ?)")
        for name in ("logs", "private"):  # jamais d'écriture privée à travers un lien
            try:
                folder = os.lstat(workspace / name)
            except FileNotFoundError:
                raise ProcedureError("espace privé altéré : dossiers logs/ et private/ requis") from None
            if stat.S_ISLNK(folder.st_mode) or not stat.S_ISDIR(folder.st_mode):
                raise ProcedureError("espace privé altéré : dossiers logs/ et private/ requis")
        self.workspace = Path(os.path.realpath(workspace))
        self.state = state
        self._log_index = 0
        return state

    def save(self, step=None, outcome=None):
        state = self.state
        state["log_counter"] = state.get("log_counter", 0) + self._log_index
        self._log_index = 0
        if step:
            state.setdefault("history", []).append({"step": step, "time": _now(), "outcome": outcome,
                                                    "tool_sha256": sha256_file(self.tool_path)})
        _write_private(self.workspace / STATE_FILE, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
        _write_private(self.workspace / "summary.md", render_summary(state))

    @property
    def source(self):
        return self.workspace / "source"

    @property
    def app(self):
        return self.source / "dist" / APP_DIR

    @property
    def venv_python(self):
        return self.workspace / "venv/bin/python"

    def candidate_digest(self):
        if not self.app.is_dir() or self.app.is_symlink():
            raise ProcedureError("candidat absent : lancer build")
        return tree_digest(tree_manifest(self.app))

    def require_digest(self, key):
        expected = self.state.get("candidate", {}).get(key)
        if not expected:
            raise ProcedureError("étape préalable manquante", detail=key)
        if self.candidate_digest() != expected:
            raise ProcedureError("candidat modifié depuis l'étape enregistrée : reconstruire dans un nouvel espace",
                                 detail=key)

    # ── preflight ──────────────────────────────────────────────────────
    def preflight(self, python=None, identity=None, profile=None):
        if self.platform != "darwin":
            self.say(f"Plateforme {self.platform} : procédure macOS uniquement. Aucun outil appelé, aucune action.")
            self.say("Verdict : BLOQUÉ — ENVIRONNEMENT")
            return EXIT_BLOCKED
        blockers, human = [], []
        self.say(f"macOS {self.machine}")
        if self.machine not in PILOT_ARCHS:
            blockers.append(f"architecture hôte {self.machine} : le pilote couvre arm64 seulement")
        result = self.run([self.tool("xcode-select"), "-p"], step="preflight")
        self._line(result.ok, "Xcode actif", result.stdout.strip() if result.ok else "absent", blockers)
        result = self.run([self.tool("xcodebuild"), "-version"], step="preflight")
        self._line(result.ok, "xcodebuild", (result.stdout.splitlines() or ["?"])[0] if result.ok else "absent",
                   blockers)
        for name in ("codesign", "notarytool", "stapler"):
            result = self.run([self.tool("xcrun"), "--find", name], step="preflight")
            self._line(result.ok, name, "trouvé" if result.ok else "introuvable", blockers)
        result = self.run([self.tool("xcrun"), "notarytool", "--version"], step="preflight")
        self._line(result.ok, "notarytool --version", result.stdout.strip() if result.ok else "échec", blockers)
        for name in ("ditto", "lipo", "otool", "spctl", "security"):
            self._line(bool(self.which(self.tool(name))), name, "trouvé" if self.which(self.tool(name))
                       else "introuvable", blockers)
        self._line(bool(self.which("git")), "git", "trouvé" if self.which("git") else "introuvable", blockers)
        try:
            version = self.check_python(python)
            self.say(f"OK  Python de build : {version}")
        except ProcedureError as exc:
            blockers.append(f"Python de build : {exc}")
            self.say(f"--  Python de build : {exc}")
            self.say(f"    Attendu : python3 -B packaging/macos_notarize.py preflight --python /chemin/python3.12")
        result = self.run([self.tool("security"), "find-identity", "-v", "-p", "codesigning"], step="preflight")
        identities = parse_identities(result.stdout) if result.ok else []
        counts = {}
        for item in identities:
            kind = item["type"] if item["type"] in KNOWN_IDENTITY_TYPES else "autre type"
            counts[kind] = counts.get(kind, 0) + 1
        self.say("    Identités valides par type : " + (", ".join(f"{k} ×{v}" for k, v in sorted(counts.items()))
                                                       or "aucune"))
        if not counts.get(DEVELOPER_ID_APPLICATION):
            human.append("aucune identité Developer ID Application valide visible")
        try:
            select_identity(identities, identity)
            self.say("OK  Identité choisie : Developer ID Application (sujet à relire en privé par le titulaire)")
        except ProcedureError as exc:
            note = str(exc)
            if exc.detail in KNOWN_IDENTITY_TYPES:  # type Apple connu seulement, jamais un libellé brut
                note = f"type d'identité refusé : {exc.detail} (Developer ID Application requis)"
            human.append(f"identité : {note}")
            self.say(f"--  Identité : {note}")
        if profile is None:
            human.append("profil notarytool non fourni (--profile)")
            self.say("--  Profil notarytool : non fourni")
        elif not PROFILE_RE.match(profile):
            human.append("nom de profil notarytool invalide")
            self.say("--  Profil notarytool : nom invalide")
        else:
            self.say("..  Profil notarytool : nom fourni, NON VÉRIFIÉ (aucun appel Apple en préflight)")
        human = list(dict.fromkeys(human))
        if blockers:
            self.say("Blocages d'environnement : " + " ; ".join(blockers))
            self.say("Verdict : BLOQUÉ — ENVIRONNEMENT")
            return EXIT_BLOCKED
        if human:
            self.say("Prérequis humains manquants : " + " ; ".join(human))
            self.say("Verdict : " + VERDICT_READY)
            return EXIT_READY_MISSING
        self.say("Verdict : PRÉREQUIS PRÉSENTS — PILOTE PRIVÉ À AUTORISER (profil non vérifié)")
        return EXIT_OK

    def _line(self, ok, label, detail, blockers):
        self.say(f"{'OK' if ok else '--'}  {label} : {detail}")
        if not ok:
            blockers.append(f"{label} {detail}")

    def check_python(self, python):
        if not python:
            raise ProcedureError("interpréteur non fourni (--python)")
        path = Path(python).expanduser()
        if not path.is_absolute():
            raise ProcedureError("chemin absolu requis")
        if not path.exists():
            raise ProcedureError("interpréteur introuvable")
        code = ("import json,platform,sys;print(json.dumps({'version':list(sys.version_info[:3]),"
                "'machine':platform.machine()}))")
        result = self.run([str(path), "-I", "-c", code], step="python")
        try:
            info = json.loads(result.stdout)
            version = tuple(info["version"])
        except (ValueError, KeyError, TypeError):
            raise ProcedureError("interpréteur inutilisable") from None
        if version[:2] != REQUIRED_PYTHON:
            raise ProcedureError("Python 3.12 requis", detail=".".join(map(str, version)))
        if info.get("machine") not in PILOT_ARCHS:
            raise ProcedureError("interpréteur arm64 requis pour ce pilote", detail=info.get("machine"))
        return ".".join(map(str, version)) + " " + info["machine"]

    # ── prepare ────────────────────────────────────────────────────────
    def prepare(self, workspace, commit, python, wheelhouse=None):
        self.require_macos()
        if not commit or not COMMIT_RE.match(commit):
            raise ProcedureError("--commit doit être l'empreinte complète du commit approuvé")
        version = self.check_python(python)
        git = self.which("git") or "git"
        resolved = self.run([git, "-C", str(self.checkout), "rev-parse", "--verify", "--quiet",
                             commit + "^{commit}"], step="git")
        if not resolved.ok or resolved.stdout.strip() != commit:
            raise ProcedureError("commit approuvé introuvable dans le checkout")
        real = self.check_private_destination(workspace)
        os.mkdir(real, 0o700)
        os.chmod(real, 0o700)
        self.workspace = real
        self.state = {"marker": MARKER, "workspace": str(real), "token": secrets.token_hex(16),
                      "created": _now(), "checkout": str(self.checkout), "commit": commit,
                      "log_counter": 0, "steps": {}, "candidate": {}}
        for name in ("logs", "private"):
            os.mkdir(real / name, 0o700)
        self.save("prepare", "espace créé")
        tree = self.run([git, "-C", str(self.checkout), "rev-parse", commit + "^{tree}"], step="git").stdout.strip()
        tool_blob = self.run([git, "-C", str(self.checkout), "rev-parse", "--verify", "--quiet",
                              f"{commit}:packaging/macos_notarize.py"], step="git")
        tool_info = {"sha256": sha256_file(self.tool_path), "path_in_checkout": self._tool_relpath(),
                     "in_commit": tool_blob.ok,
                     "matches_commit": tool_blob.ok and tool_blob.stdout.strip() == git_blob_id(
                         self.tool_path, len(commit))}
        archive = self.workspace / "logs/source.tar"
        result = self.run([git, "-C", str(self.checkout), "archive", "--format=tar", "-o", str(archive), commit],
                          step="git-archive")
        if not result.ok or not archive.is_file():
            raise ProcedureError("export git archive impossible")
        os.mkdir(self.source, 0o700)
        _safe_extract(archive, self.source)
        listing = self.run([git, "-C", str(self.checkout), "ls-tree", "-r", "-z", "--full-tree", commit],
                           step="git")
        if not listing.ok:
            raise ProcedureError("ls-tree impossible")
        self._verify_export(listing.stdout, len(commit))
        self.state["steps"]["prepare"] = {"commit": commit, "tree": tree, "archive_sha256": sha256_file(archive),
                                          "tool": tool_info, "python": version}
        self.save("export", "commit exporté et vérifié")
        if not tool_info["matches_commit"]:
            self.say("Attention : l'outil exécuté diffère de sa version dans le commit exporté ; "
                     "son empreinte est consignée séparément.")
        result = self.run([str(Path(python).expanduser()), "-m", "venv", str(self.workspace / "venv")],
                          step="venv", timeout=600)
        if not result.ok or not self.venv_python.exists():
            raise ProcedureError("création de la venv privée impossible")
        requirements = self.source / "requirements/requirements-build.txt"
        install = [str(self.venv_python), "-m", "pip", "install", "--no-input", "--disable-pip-version-check",
                   "-r", str(requirements)]
        if wheelhouse:
            install += ["--no-index", "--find-links", str(Path(wheelhouse).expanduser())]
        result = self.run(install, step="pip", cwd=self.workspace, env=self.child_env(), timeout=3600)
        if not result.ok:
            raise ProcedureError("installation du snapshot de build impossible (voir logs privés)")
        freeze = self.run([str(self.venv_python), "-m", "pip", "freeze", "--all"], step="pip", env=self.child_env())
        if not freeze.ok:
            raise ProcedureError("lecture des versions installées impossible (voir logs privés)")
        mismatches = _pin_mismatches(requirements.read_text(encoding="utf-8"), freeze.stdout)
        if mismatches:
            raise ProcedureError("versions installées différentes du snapshot", detail=", ".join(mismatches))
        self.state["steps"]["venv"] = {"python": version, "pins_verified": True}
        self.save("venv", "venv privée conforme au snapshot")
        self.say(f"Espace privé prêt : {self.workspace}")
        self.say(f"Commit exporté : {commit} ; outil sha256 {tool_info['sha256']}")
        return EXIT_OK

    def _tool_relpath(self):
        try:
            return self.tool_path.resolve().relative_to(Path(os.path.realpath(self.checkout))).as_posix()
        except ValueError:
            return None

    def _verify_export(self, listing, length):
        expected = {}
        for record in listing.split("\0"):
            if not record:
                continue
            meta, _, name = record.partition("\t")
            mode, kind, obj = meta.split()
            if kind != "blob":
                raise ProcedureError("objet Git non exportable", detail=f"{name} ({kind})")
            expected[name] = (mode, obj)
        actual = {}
        for rel, entry in tree_manifest(self.source).items():
            if entry[0] != "dir":
                actual[rel] = entry
        if set(actual) != set(expected):
            diff = sorted(set(actual) ^ set(expected))[:5]
            raise ProcedureError("export différent du commit", detail=diff)
        for name, (mode, obj) in expected.items():
            path = self.source / name
            if mode == "120000":
                if actual[name][0] != "link":
                    raise ProcedureError("lien attendu dans l'export", detail=name)
                data = os.readlink(path).encode()
                algo = hashlib.sha1 if length == 40 else hashlib.sha256
                if algo(b"blob %d\0" % len(data) + data).hexdigest() != obj:
                    raise ProcedureError("cible de lien différente dans l'export", detail=name)
            elif actual[name][0] != "file" or git_blob_id(path, length) != obj:
                raise ProcedureError("contenu exporté différent du commit", detail=name)

    # ── build ──────────────────────────────────────────────────────────
    def build(self, workspace):
        self.require_macos()
        self.open_workspace(workspace)
        if "venv" not in self.state["steps"]:
            raise ProcedureError("prepare incomplet")
        if "build" in self.state["steps"] or os.path.lexists(self.source / "dist"):
            raise ProcedureError("un build existe déjà dans cet espace : créer un nouvel espace")
        result = self.run([str(self.venv_python), "-m", "PyInstaller", "packaging/spoolscribe.spec", "--noconfirm"],
                          step="pyinstaller", cwd=self.source, timeout=3600,
                          env=self.child_env(PYTHONPATH="src",
                                             PYINSTALLER_CONFIG_DIR=str(self.workspace / "pyinstaller-cache")))
        if not result.ok or not self.app.is_dir():
            raise ProcedureError("build PyInstaller en échec (voir logs privés)")
        digest = self.candidate_digest()
        self.state["candidate"]["built"] = digest
        self.state["steps"]["build"] = {"digest": digest, "spec": "packaging/spoolscribe.spec"}
        self.save("build", "candidat construit")
        self.say(f"Candidat construit : source/dist/{APP_DIR} ; empreinte d'arbre {digest}")
        return EXIT_OK

    # ── inspect ────────────────────────────────────────────────────────
    def inventory(self, app=None, *, require_signable=True):
        app = Path(app or self.app)
        errors, warnings = [], []
        entries = tree_manifest(app)
        links, machos, specials, xattr_hits = {}, {}, [], {}
        for rel, entry in entries.items():
            path = app / rel
            if entry[0] == "special":
                specials.append(rel)
                continue
            try:
                names = self.xattrs.list(path)
            except OSError:
                names = []
            for name in names:
                if name in FORBIDDEN_XATTRS:
                    xattr_hits.setdefault(name, []).append(rel)
            if entry[0] == "link":
                resolved, error = resolve_inside(app, rel)
                links[rel] = {"target": entry[1], "resolved": resolved, "error": error}
                if error:
                    errors.append(f"lien {rel} : {error}")
            elif entry[0] == "file":
                info = macho_info(path)
                if info:
                    machos[rel] = info
                    if require_signable and info["filetype"] not in SIGNABLE_FILETYPES:
                        errors.append(f"Mach-O de type inattendu ({info['filetype']}) : {rel}")
                    if entry[1] & (stat.S_ISUID | stat.S_ISGID):
                        errors.append(f"bit setuid/setgid : {rel}")
                elif rel.startswith("Contents/MacOS/"):
                    errors.append(f"fichier non Mach-O dans Contents/MacOS (signature en attribut perdue) : {rel}")
        for rel in specials:
            errors.append(f"fichier spécial refusé : {rel}")
        containers = self._containers(app, entries, machos, errors, warnings)
        mains = {c["main"] for c in containers}
        for rel in machos:
            if rel.startswith("Contents/Resources/") and rel not in mains:
                warnings.append(f"Mach-O sous Contents/Resources : {rel}")
        return {"entries": entries, "links": links, "machos": machos, "containers": containers,
                "xattrs": xattr_hits, "errors": errors, "warnings": warnings}

    def _containers(self, app, entries, machos, errors, warnings):
        containers = []
        root_plist = app / "Contents/Info.plist"
        try:
            info = plistlib.loads(root_plist.read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):
            errors.append("Info.plist de l'app illisible")
            info = {}
        executable = info.get("CFBundleExecutable")
        main = f"Contents/MacOS/{executable}" if executable else None
        if not main or main not in machos:
            errors.append("exécutable principal de l'app absent ou non Mach-O")
        containers.append({"path": ".", "kind": "app", "main": main})
        for rel, entry in entries.items():
            if entry[0] != "dir":
                continue
            name = PurePosixPath(rel).name
            if name.endswith(".framework"):
                stem = name[: -len(".framework")]
                versions = f"{rel}/Versions"
                if entries.get(versions, ("?",))[0] == "dir":
                    current = entries.get(f"{versions}/Current")
                    if not current or current[0] != "link":
                        warnings.append(f"framework sans Versions/Current : {rel}")
                    found = False
                    for child, kind in entries.items():
                        if PurePosixPath(child).parent.as_posix() != versions or kind[0] != "dir":
                            continue
                        binary = f"{child}/{stem}"
                        if binary in machos:
                            containers.append({"path": child, "kind": "framework", "main": binary})
                            found = True
                        else:
                            warnings.append(f"version de framework sans binaire : {child}")
                    if not found:
                        warnings.append(f"framework sans version signable : {rel}")
                elif f"{rel}/{stem}" in machos:
                    warnings.append(f"framework non versionné : {rel}")
                    containers.append({"path": rel, "kind": "framework", "main": f"{rel}/{stem}"})
            elif name.endswith(BUNDLE_SUFFIXES) and entries.get(f"{rel}/Contents/Info.plist", ("?",))[0] == "file":
                try:
                    nested = plistlib.loads((app / rel / "Contents/Info.plist").read_bytes())
                except (OSError, plistlib.InvalidFileException, ValueError):
                    errors.append(f"Info.plist illisible : {rel}")
                    continue
                exe = nested.get("CFBundleExecutable")
                binary = f"{rel}/Contents/MacOS/{exe}" if exe else None
                if binary and binary in machos:
                    containers.append({"path": rel, "kind": "nested", "main": binary})
                elif any(m.startswith(rel + "/") for m in machos):
                    errors.append(f"bundle imbriqué contenant du code sans exécutable déclaré : {rel}")
        return containers

    def signing_plan(self, inv):
        mains = {c["main"] for c in inv["containers"]}
        items = [{"kind": "file", "path": rel} for rel in inv["machos"] if rel not in mains]
        items += [{"kind": c["kind"], "path": c["path"]} for c in inv["containers"]]

        def depth(item):
            return len(PurePosixPath(item["path"]).parts) if item["path"] != "." else 0

        items.sort(key=lambda item: (-depth(item), item["path"]))
        if not items or items[-1]["path"] != ".":
            raise ProcedureError("plan de signature incohérent : l'app doit être signée en dernier")
        for item in items:
            parts = PurePosixPath(item["path"]).parts if item["path"] != "." else ()
            for index in range(1, len(parts) + 1):
                if inv["entries"].get("/".join(parts[:index]), ("?",))[0] == "link":
                    raise ProcedureError("plan via un lien refusé", detail=item["path"])
        return items

    def native_details(self, app, inv, errors, warnings):
        details = {}
        exec_dir = "Contents/MacOS"
        for rel, info in sorted(inv["machos"].items()):
            path = app / rel
            lipo = self.run([self.tool("lipo"), "-archs", str(path)], step="lipo")
            if not lipo.ok or sorted(lipo.stdout.split()) != sorted(info["archs"]):
                errors.append(f"architectures incohérentes (lipo/en-tête) : {rel}")
            per_arch = {}
            for arch in info["archs"]:
                otool = self.run([self.tool("otool"), "-arch", arch, "-l", str(path)], step="otool")
                if not otool.ok:
                    errors.append(f"otool en échec : {rel} ({arch})")
                    continue
                load = parse_otool_load_commands(otool.stdout)
                for name in load["dylibs"] + load["weak"]:
                    weak = name in load["weak"] and name not in load["dylibs"]
                    kind, value = resolve_dependency(app, rel, name, load["rpaths"], exec_dir)
                    if kind in ("external", "escape"):
                        errors.append(f"dépendance hors candidat ({kind}) : {rel} → {name}")
                    elif kind == "unresolved":
                        if weak or name.startswith("@rpath/"):
                            warnings.append(f"dépendance non résolue statiquement : {rel} → {name}")
                        else:
                            errors.append(f"dépendance introuvable : {rel} → {name}")
                for rpath in load["rpaths"]:
                    if rpath.startswith("/"):
                        warnings.append(f"rpath absolu : {rel} → {rpath}")
                per_arch[arch] = load
            details[rel] = per_arch
        return details

    def inspect(self, workspace, arch=None):
        self.require_macos()
        self.open_workspace(workspace)
        if "build" not in self.state["steps"]:
            raise ProcedureError("build manquant")
        report = self.inspect_candidate(self.app, arch=arch or PILOT_ARCHS[0])
        self.state["steps"]["inspect"] = report
        self.save("inspect", "PASS" if not report["errors"] else "FAIL")
        return EXIT_OK if not report["errors"] else EXIT_BLOCKED

    def inspect_candidate(self, app, *, arch):
        digest = tree_digest(tree_manifest(app))
        inv = self.inventory(app)
        errors, warnings = list(inv["errors"]), list(inv["warnings"])
        details = self.native_details(app, inv, errors, warnings)
        try:
            plan = self.signing_plan(inv)
        except ProcedureError as exc:
            errors.append(str(exc))
            plan = []
        self._check_plist(app, errors)
        resources = self.check_resources(app, errors)
        archs = None
        for info in inv["machos"].values():
            archs = set(info["archs"]) if archs is None else archs & set(info["archs"])
        if arch not in (archs or set()):
            errors.append(f"architecture {arch} absente d'au moins un Mach-O")
        deployment = {}
        for per_arch in details.values():
            load = per_arch.get(arch) or next(iter(per_arch.values()), None)
            if load:
                key = f"minOS {load['minos']} / SDK {load['sdk']}"
                deployment[key] = deployment.get(key, 0) + 1
        minos = [load.get("minos") for per in details.values() for load in per.values() if load.get("minos")]
        qml_frameworks = sorted({PurePosixPath(c["path"]).parts[-3][: -len(".framework")]
                                 for c in inv["containers"] if c["kind"] == "framework"
                                 and len(PurePosixPath(c["path"]).parts) >= 3
                                 and PurePosixPath(c["path"]).parts[-3].startswith(QML_PREFIXES)})
        qml_dependents = sorted(rel for rel, per in details.items() for load in per.values()
                                if any("/" + p in name for p in ("QtQml", "QtQuick") for name in load["dylibs"]))
        report = {
            "digest": digest, "errors": errors, "warnings": warnings,
            "macho_count": len(inv["machos"]), "machos": sorted(inv["machos"]),
            "frameworks": sum(1 for c in inv["containers"] if c["kind"] == "framework"),
            "nested_bundles": sum(1 for c in inv["containers"] if c["kind"] == "nested"),
            "links": len(inv["links"]), "archs_common": sorted(archs or []), "pilot_arch": arch,
            "deployment": deployment, "highest_minos": max(minos, key=_version_key) if minos else None,
            "forbidden_xattrs": {k: len(v) for k, v in inv["xattrs"].items()},
            "resources_verified": resources, "plan": plan,
            "app_main": next((c["main"] for c in inv["containers"] if c["path"] == "."), None),
            "qml_frameworks": qml_frameworks, "qml_dependents": len(qml_dependents),
        }
        self.say(f"Mach-O : {report['macho_count']} ; frameworks (versions) : {report['frameworks']} ; "
                 f"bundles imbriqués : {report['nested_bundles']} ; liens : {report['links']}")
        self.say(f"Architectures communes : {', '.join(report['archs_common']) or 'aucune'} "
                 f"(pilote {arch} seulement)")
        for key, count in sorted(deployment.items()):
            self.say(f"  {count} × {key}")
        if report["highest_minos"]:
            self.say(f"minOS le plus élevé déclaré : {report['highest_minos']} (aucune promesse en deçà sans essai)")
        if qml_frameworks:
            self.say(f"Frameworks QML/Quick embarqués : {', '.join(qml_frameworks)} ; {len(qml_dependents)} "
                     "Mach-O en dépendent (dépendance embarquée, aucune preuve d'exécution JIT)")
        self.say(f"Attributs interdits : {report['forbidden_xattrs'] or 'aucun'}")
        self.say(f"Ressources vérifiées contre l'export : {resources}")
        self.say(f"Plan de signature : {len(plan)} objets, de l'intérieur vers l'extérieur")
        for warning in warnings[:20]:
            self.say(f"  avertissement : {warning}")
        if len(warnings) > 20:
            self.say(f"  … {len(warnings) - 20} avertissements supplémentaires (state.json)")
        for error in errors:
            self.say(f"  ERREUR : {error}")
        self.say("Inspection : " + ("PASS" if not errors else "FAIL"))
        return report

    def _check_plist(self, app, errors):
        try:
            info = plistlib.loads((Path(app) / "Contents/Info.plist").read_bytes())
        except (OSError, plistlib.InvalidFileException, ValueError):
            errors.append("Info.plist illisible")
            return
        version = read_app_version(self.source)
        if info.get("CFBundleIdentifier") != BUNDLE_ID:
            errors.append("identifiant de bundle inattendu")
        if info.get("CFBundleExecutable") != APP_NAME:
            errors.append("exécutable de bundle inattendu")
        if info.get("CFBundleShortVersionString") != version or info.get("CFBundleVersion") != version:
            errors.append(f"version du bundle différente de core.APP_VERSION ({version})")

    def check_resources(self, app, errors):
        include = load_include_resource(self.source)
        expected = {}
        for top in ("data", "scripts"):
            for rel, entry in tree_manifest(self.source / top).items():
                name = f"{top}/{rel}"
                if entry[0] == "file" and include(name):
                    expected[name] = entry[2]
        base = Path(app) / "Contents/Resources"
        actual = {}
        for top in ("data", "scripts"):
            if not (base / top).is_dir():
                continue
            for rel, entry in tree_manifest(base / top).items():
                name = f"{top}/{rel}"
                if entry[0] == "file":
                    actual[name] = entry[2]
                elif entry[0] == "link":
                    resolved, error = resolve_inside(app, f"Contents/Resources/{name}")
                    if resolved and (Path(app) / resolved).is_file():
                        actual[name] = sha256_file(Path(app) / resolved)
        if set(actual) != set(expected):
            errors.append(f"ressources manquantes ou inattendues : {sorted(set(actual) ^ set(expected))[:10]}")
            return 0
        changed = [n for n in expected if actual[n] != expected[n]]
        if changed:
            errors.append(f"ressources modifiées : {changed[:10]}")
            return 0
        return len(expected)

    # ── probes ─────────────────────────────────────────────────────────
    def probes(self, workspace):
        self.require_macos()
        self.open_workspace(workspace)
        if "build" not in self.state["steps"]:
            raise ProcedureError("build manquant")
        if self.state.get("candidate", {}).get("stapled"):
            raise ProcedureError("candidat déjà staplé : sondes à relancer sur une extraction, pas sur le candidat")
        before = self.candidate_digest()
        if before not in (self.state["candidate"].get("built"), self.state["candidate"].get("signed")):
            raise ProcedureError("candidat différent du build et de la signature enregistrés")
        if self.state["steps"].get("sign") and not self.state["candidate"].get("signed"):
            raise ProcedureError("signature en échec : candidat inutilisable")
        if not self.state["steps"].get("oracles"):
            result = self.run([str(self.venv_python), "-m", "pip", "install", "--no-input",
                               "--disable-pip-version-check", *CI_ORACLES], step="oracles",
                              env=self.child_env(), timeout=1800)
            if not result.ok:
                raise ProcedureError("installation des oracles QA impossible (après PyInstaller)")
            self.state["steps"]["oracles"] = {"packages": list(CI_ORACLES), "after_build": True}
            self.save("oracles", "installés après PyInstaller")
        outcomes = {}
        for script in FROZEN_PROBES:
            result = self.run([str(self.venv_python), "-B", f".github/scripts/{script}"], step="probe",
                              cwd=self.source, env=self.child_env(PYTHONPATH="src", QT_QPA_PLATFORM="offscreen"),
                              timeout=900)
            marker = next((line.split()[0] for line in result.stdout.splitlines() if line.startswith("FROZEN_")),
                          None)
            outcomes[script] = "PASS" if result.ok and marker else "FAIL"
            self.say(f"{outcomes[script]}  {script}")
        after = self.candidate_digest()
        if after != before:
            raise ProcedureError("les sondes ont modifié le candidat")
        stage = "signed" if self.state["candidate"].get("signed") == before else "built"
        self.state["steps"].setdefault("probes", {})[stage] = {"digest": before, "results": outcomes}
        ok = all(v == "PASS" for v in outcomes.values())
        self.save("probes", f"{stage}: {'PASS' if ok else 'FAIL'}")
        self.say(f"Candidat inchangé par les sondes ({stage}).")
        return EXIT_OK if ok else EXIT_BLOCKED

    # ── sanitize ───────────────────────────────────────────────────────
    def sanitize(self, workspace):
        self.require_macos()
        self.open_workspace(workspace)
        self.require_digest("built")
        if self.state["candidate"].get("signed"):
            raise ProcedureError("candidat déjà signé")
        before = {}
        targets = [self.app] + [self.app / rel for rel in tree_manifest(self.app)]
        for path in targets:
            for name in self.xattrs.list(path):
                if name in FORBIDDEN_XATTRS:
                    before[name] = before.get(name, 0) + 1
                    self.xattrs.remove(path, name)
        remaining = sum(1 for path in targets for name in self.xattrs.list(path) if name in FORBIDDEN_XATTRS)
        if remaining:
            raise ProcedureError("attributs interdits encore présents")
        if self.candidate_digest() != self.state["candidate"]["built"]:
            raise ProcedureError("contenu du candidat modifié pendant le nettoyage")
        self.state["steps"]["sanitize"] = {"removed": before, "remaining": 0}
        self.save("sanitize", f"retirés {before or 'aucun'}")
        self.say(f"Attributs interdits retirés de la copie neuve : {before or 'aucun'} ; restants : 0")
        return EXIT_OK

    # ── sign ───────────────────────────────────────────────────────────
    def sign(self, workspace, identity, confirmed, entitlements=None):
        self.require_macos()
        if not confirmed:
            raise ProcedureError("signature non autorisée : ajouter --confirm-signing après accord explicite du pilote")
        self.open_workspace(workspace)
        if "sanitize" not in self.state["steps"]:
            raise ProcedureError("sanitize manquant")
        if self.state["candidate"].get("signed") or self.state["steps"].get("sign"):
            raise ProcedureError("une signature a déjà été tentée : reconstruire dans un nouvel espace")
        self.require_digest("built")
        approved = load_entitlements(entitlements) if entitlements else {}
        listed = self.run([self.tool("security"), "find-identity", "-v", "-p", "codesigning"], step="identity")
        chosen = select_identity(parse_identities(listed.stdout) if listed.ok else [], identity)
        _write_private(self.workspace / "private/identity.txt", chosen["label"] + "\n")
        report = self.inspect_candidate(self.app, arch=PILOT_ARCHS[0])
        if report["errors"]:
            raise ProcedureError("inspection en échec : signature refusée")
        if report["forbidden_xattrs"]:
            raise ProcedureError("attributs FinderInfo/ResourceFork présents : signature refusée")
        plan = report["plan"]
        self.state["steps"]["sign"] = {"started": _now(), "items": len(plan), "signed": 0,
                                       "entitlements": sorted(approved)}
        self.save("sign", "début")
        entitlements_file = None
        if approved:
            entitlements_file = self.workspace / "private/approved-entitlements.plist"
            _write_private(entitlements_file, plistlib.dumps(approved).decode("utf-8"))
        for index, item in enumerate(plan, 1):
            path = self.app if item["path"] == "." else self.app / item["path"]
            args = [self.tool("codesign"), "--force", "--sign", chosen["sha1"], "--options", "runtime", "--timestamp"]
            if item["path"] == "." and entitlements_file:
                args += ["--entitlements", str(entitlements_file)]
            result = self.run(args + [str(path)], step="codesign", timeout=600)
            if not result.ok:
                self.state["steps"]["sign"].update(failed=item["path"], signed=index - 1)
                self.save("sign", "échec")
                raise ProcedureError("échec de signature ou de timestamp : candidat inutilisable", detail=item["path"])
            self.state["steps"]["sign"]["signed"] = index
        self.save("sign", "objets signés")
        summary = self.verify_signatures(self.app, report, approved)
        digest = self.candidate_digest()
        self.state["candidate"]["signed"] = digest
        self.state["steps"]["sign"].update(verified=summary, digest=digest, macho=report["machos"])
        self.save("sign", "PASS")
        self.say(f"Signature vérifiée : {summary}")
        return EXIT_OK

    def verify_signatures(self, app, report, approved):
        """Vérifie chaque objet ; toute lecture interprétée doit d'abord avoir réussi (R1).

        Les entitlements approuvés valent pour l'app et pour son exécutable principal, deux vues du
        même programme (R4) ; tout autre objet doit n'en porter aucun.
        """
        objects = sorted(set(report["machos"]) | {i["path"] for i in report["plan"]})
        app_main = report.get("app_main")
        if not app_main or app_main not in objects:
            raise ProcedureError("exécutable principal de l'app introuvable pour la vérification")
        teams, private = set(), []
        for rel in objects:
            path = app if rel == "." else app / rel
            result = self.run([self.tool("codesign"), "--verify", "--strict", "--all-architectures",
                               "--verbose=2", str(path)], step="verify")
            if not result.ok:
                raise ProcedureError("vérification de signature en échec", detail=rel)
            shown = self.run([self.tool("codesign"), "-dvvv", str(path)], step="display")
            if not shown.ok:
                raise ProcedureError("lecture de la signature en échec", detail=rel)
            private.append(f"## {rel}\n{shown.stderr}{shown.stdout}")
            details = parse_codesign_details(shown.stderr + shown.stdout)
            if details["authority_type"] != DEVELOPER_ID_APPLICATION or details["adhoc"]:
                raise ProcedureError("autorité de signature inattendue", detail=rel)
            if details["chain"][:1] != ["Developer ID Certification Authority"]:
                raise ProcedureError("chaîne de certificats inattendue", detail=rel)
            if not details["runtime"]:
                raise ProcedureError("Hardened Runtime absent", detail=rel)
            if not details["secure_timestamp"] or details["signed_time_only"]:
                raise ProcedureError("timestamp sécurisé absent", detail=rel)
            if not details["team"] or details["team"] == "not set":
                raise ProcedureError("équipe de signature absente", detail=rel)
            teams.add(details["team"])
            read = self.run([self.tool("codesign"), "-d", "--entitlements", "-", "--xml", str(path)],
                            step="entitlements")
            try:
                found = parse_entitlements(read)
            except ProcedureError as exc:
                exc.detail = rel if exc.detail is None else f"{rel} : {exc.detail}"
                raise
            check_entitlements(found, approved if rel in (".", app_main) else {})
        if len(teams) != 1:
            raise ProcedureError("équipes de signature différentes")
        deep = self.run([self.tool("codesign"), "--verify", "--deep", "--strict", "--verbose=2", str(app)],
                        step="verify")
        if not deep.ok:
            raise ProcedureError("codesign --verify --deep --strict en échec")
        _write_private(self.workspace / "private/codesign-details.txt", "\n".join(private))
        return {"objects": len(objects), "type": DEVELOPER_ID_APPLICATION, "single_team": True,
                "runtime": True, "secure_timestamp": True, "entitlements": sorted(approved) or "aucun",
                "deep_strict": "PASS"}

    # ── notarize / notary-status ───────────────────────────────────────
    def notarize(self, workspace, profile, confirmed, wait_timeout="30m"):
        self.require_macos()
        if not confirmed:
            raise ProcedureError("envoi Apple non autorisé : ajouter --confirm-submission après accord explicite")
        if not profile or not PROFILE_RE.match(profile):
            raise ProcedureError("nom de profil notarytool requis (--profile)")
        seconds = parse_timeout(wait_timeout)
        self.open_workspace(workspace)
        if self.state.get("submission"):
            raise ProcedureError("une soumission existe déjà : utiliser notary-status, jamais un nouvel envoi")
        self.require_digest("signed")
        if self.state["steps"].get("sign", {}).get("verified", {}).get("deep_strict") != "PASS":
            raise ProcedureError("vérifications de signature non passées")
        folder = self.workspace / "submission"
        if os.path.lexists(folder):
            raise ProcedureError("dossier de soumission préexistant")
        os.mkdir(folder, 0o700)
        archive = folder / SUBMISSION_ZIP
        result = self.run([self.tool("ditto"), "-c", "-k", "--norsrc", "--noextattr", "--keepParent",
                           str(self.app), str(archive)], step="ditto")
        if not result.ok or not archive.is_file():
            raise ProcedureError("création du ZIP de soumission impossible")
        self.state["submission"] = {"zip_sha256": sha256_file(archive), "candidate": self.state["candidate"]["signed"],
                                    "profile": profile, "status": "UPLOADING", "time": _now()}
        self.save("notarize", "ZIP de soumission créé")
        result = self.run([self.tool("xcrun"), "notarytool", "submit", str(archive), "--keychain-profile", profile,
                           "--output-format", "json"], step="notary-submit", timeout=3600)
        if not result.ok:
            self.state["submission"]["status"] = "UNKNOWN" if result.timed_out else "SUBMIT_FAILED"
            self.save("notarize", self.state["submission"]["status"])
            raise ProcedureError("envoi notarytool en échec (authentification, réseau ou refus) ; voir logs privés. "
                                 "Ne pas renvoyer automatiquement : vérifier l'historique en privé.")
        try:
            submitted = parse_notary_json(result.stdout, need=("id",))
        except ProcedureError:
            self.state["submission"]["status"] = "UNKNOWN"
            self.save("notarize", "réponse inattendue")
            raise
        self.state["submission"].update(id=submitted["id"], status="PENDING")
        self.save("notarize", "soumis, identifiant conservé")
        self.say(f"Soumission conservée : {submitted['id']}")
        return self._follow(profile, seconds)

    def notary_status(self, workspace, profile, confirmed, wait_timeout=None):
        self.require_macos()
        if not confirmed:
            raise ProcedureError("requête Apple non autorisée : ajouter --confirm-apple-query")
        if not profile or not PROFILE_RE.match(profile):
            raise ProcedureError("nom de profil notarytool requis (--profile)")
        seconds = parse_timeout(wait_timeout) if wait_timeout else None
        self.open_workspace(workspace)
        submission = self.state.get("submission") or {}
        if not submission.get("id"):
            raise ProcedureError("aucun identifiant de soumission conservé : aucune reprise possible ici")
        if submission.get("status") not in ("PENDING", "Accepted"):
            raise ProcedureError("aucune reprise automatique pour ce statut de soumission", detail=submission.get("status"))
        return self._follow(profile, seconds)

    def _follow(self, profile, seconds):
        submission = self.state["submission"]
        sid = submission["id"]
        if seconds:
            try:
                waited = self.run([self.tool("xcrun"), "notarytool", "wait", sid, "--keychain-profile", profile,
                                   "--timeout", f"{seconds}s", "--output-format", "json"],
                                  step="notary-wait", timeout=seconds + 300)
            except KeyboardInterrupt:
                waited = Result(None, "", "interrompu", timed_out=True)
            if waited.timed_out:
                return self._pending("attente interrompue ou expirée")
        info = self.run([self.tool("xcrun"), "notarytool", "info", sid, "--keychain-profile", profile,
                         "--output-format", "json"], step="notary-info", timeout=600)
        if not info.ok:
            self.save("notary-info", "échec")
            raise ProcedureError("notarytool info en échec (authentification ou réseau) ; statut inchangé")
        status = parse_notary_json(info.stdout, need=("id", "status"))
        if status["id"] != sid:
            raise ProcedureError("réponse d'une autre soumission")
        if status["status"] == "In Progress":
            return self._pending("traitement Apple en cours")
        apple_status = apple_status_category(status["status"])
        if apple_status not in ("Accepted", "Invalid", "Rejected"):
            submission.update(status="BLOCKED", apple_status=apple_status)
            self.save("notary-info", "statut Apple inattendu")
            raise ProcedureError("statut Apple inattendu (valeur brute dans logs/ seulement)")
        log_path = self.workspace / "private/notary-log.json"
        if os.path.lexists(log_path):
            log_path = self.workspace / f"private/notary-log-{_now().replace(':', '')}.json"
        fetched = self.run([self.tool("xcrun"), "notarytool", "log", sid, "--keychain-profile", profile,
                            str(log_path)], step="notary-log", timeout=600)
        if not fetched.ok or not log_path.is_file():
            submission["status"] = "PENDING" if status["status"] == "Accepted" else "BLOCKED"
            self.save("notary-log", "journal indisponible")
            raise ProcedureError("journal notarial indisponible : rien n'est validé sans journal lu")
        os.chmod(log_path, 0o600)
        try:
            log = json.loads(log_path.read_text(encoding="utf-8"))
        except ValueError:
            log = None
        review = examine_notary_log(log, submission_id=sid, zip_sha256=submission["zip_sha256"],
                                    macho_paths=self.state["steps"]["sign"].get("macho", []))
        submission.update(apple_status=apple_status, log=log_path.name, review=review)
        private_note = f"détail consultable en privé seulement : private/{log_path.name}"
        if apple_status != "Accepted" or review["errors"]:
            submission["status"] = "BLOCKED"
            self.save("notary-log", f"BLOQUÉ ({apple_status}, {len(review['errors'])} catégorie(s) d'erreur)")
            self.say(f"Statut Apple : {apple_status} ; issues : {review['issues']} "
                     f"(error {review['issue_errors']}) ; catégories d'erreur : {len(review['errors'])}")
            for line in describe_categories(review["errors"]):
                self.say(f"  ERREUR : {line}")
            self.say("  " + private_note)
            raise ProcedureError("notarisation non acceptée : corriger, reconstruire, nouvel espace")
        submission["status"] = "Accepted"
        self.save("notary-log", "Accepted, journal examiné")
        self.say(f"Accepted ; journal examiné : {review['issues']} issue(s), {len(review['warnings'])} "
                 f"catégorie(s) d'avertissement, {review['ticket_entries']} entrées de ticket.")
        for line in describe_categories(review["warnings"]):
            self.say(f"  avertissement : {line}")
        if review["warnings"]:
            self.say("  " + private_note)
        return EXIT_OK

    def _pending(self, reason):
        self.state["submission"]["status"] = "PENDING"
        self.save("notary", f"PENDING ({reason})")
        self.say(f"PENDING : {reason}. Jamais Accepted à ce stade. Reprise sans nouvel envoi :")
        self.say("  python3 -B packaging/macos_notarize.py notary-status --workspace WS --profile PROFIL "
                 "--confirm-apple-query [--wait-timeout 30m]")
        return EXIT_PENDING

    # ── staple ─────────────────────────────────────────────────────────
    def staple(self, workspace, confirmed, acknowledge_warnings=False):
        self.require_macos()
        if not confirmed:
            raise ProcedureError("stapling non autorisé : ajouter --confirm-stapling")
        self.open_workspace(workspace)
        submission = self.state.get("submission") or {}
        review = submission.get("review") or {}
        if submission.get("status") != "Accepted" or review.get("status") != "Accepted" or review.get("errors"):
            raise ProcedureError("stapling refusé : notarisation Accepted et journal examiné requis")
        if review.get("warnings") and not acknowledge_warnings:
            raise ProcedureError("avertissements du journal à relire : relancer avec --acknowledge-log-warnings")
        if self.state["candidate"].get("stapled"):
            raise ProcedureError("candidat déjà staplé")
        self.require_digest("signed")
        if submission.get("candidate") != self.state["candidate"]["signed"]:
            raise ProcedureError("la soumission ne correspond pas au candidat signé")
        before = tree_manifest(self.app)
        for args in ([self.tool("xcrun"), "stapler", "staple", str(self.app)],
                     [self.tool("xcrun"), "stapler", "validate", str(self.app)],
                     [self.tool("codesign"), "--verify", "--deep", "--strict", "--verbose=2", str(self.app)]):
            result = self.run(args, step="staple", timeout=900)
            if not result.ok:
                self.save("staple", "échec")
                raise ProcedureError("échec du stapling, de sa validation ou de la vérification", detail=" ".join(args[1:3]))
        after = tree_manifest(self.app)
        diff = manifest_differences(before, after)
        allowed = {"Contents/CodeResources"}
        if diff["removed"] or set(diff["added"]) - allowed or set(diff["changed"]) - allowed:
            raise ProcedureError("le stapling a modifié autre chose que Contents/CodeResources")
        digest = tree_digest(after)
        self.state["candidate"]["stapled"] = digest
        self.state["steps"]["staple"] = {"digest": digest, "validate": "PASS", "deep_strict": "PASS",
                                         "warnings_acknowledged": bool(review.get("warnings"))}
        self.save("staple", "PASS")
        self.say("Ticket staplé sur l'app ; stapler validate et codesign --verify --deep --strict : PASS")
        return EXIT_OK

    # ── package ────────────────────────────────────────────────────────
    def package(self, workspace):
        self.require_macos()
        self.open_workspace(workspace)
        self.require_digest("stapled")
        if self.state["steps"].get("package"):
            raise ProcedureError("archive finale déjà produite dans cet espace")
        release = self.workspace / "release"
        if os.path.lexists(release):
            raise ProcedureError("dossier de sortie préexistant")
        os.mkdir(release, 0o700)
        archive = release / FINAL_ZIP
        result = self.run([self.tool("ditto"), "-c", "-k", "--norsrc", "--noextattr", "--keepParent",
                           str(self.app), str(archive)], step="ditto")
        if not result.ok or not archive.is_file():
            raise ProcedureError("création du ZIP final impossible")
        digest = sha256_file(archive)
        _write_private(release / (FINAL_ZIP + ".sha256"), f"{digest}  {FINAL_ZIP}\n", mode=0o644)
        checked = self.run([str(self.venv_python), "-B", str(self.source / ".github/scripts/verify_archive.py"),
                            str(archive)], step="verify-archive", cwd=self.workspace, env=self.child_env())
        if not checked.ok:
            raise ProcedureError("verify_archive.py en échec")
        extracted = self.extract(archive, "final")
        stapled = self.state["candidate"]["stapled"]
        if tree_digest(tree_manifest(extracted)) != stapled:
            diff = manifest_differences(tree_manifest(self.app), tree_manifest(extracted))
            raise ProcedureError("extraction différente du candidat staplé", detail=json.dumps(diff)[:2000])
        errors = []
        inv = self.inventory(extracted, require_signable=True)
        errors += [e for e in inv["errors"]]
        resources = self.check_resources(extracted, errors)
        if errors:
            raise ProcedureError("contrôles de l'extraction en échec", detail=" ; ".join(errors))
        for args in ([self.tool("codesign"), "--verify", "--deep", "--strict", "--verbose=2", str(extracted)],
                     [self.tool("xcrun"), "stapler", "validate", str(extracted)]):
            result = self.run(args, step="extracted", timeout=900)
            if not result.ok:
                self.save("package", "ticket ou signature perdu après extraction")
                raise ProcedureError("signature ou ticket en échec après extraction. "
                                     "Décision de packaging requise ; le workflow n'est pas modifié.",
                                     detail=" ".join(args[1:3]))
        if sha256_file(archive) != digest:
            raise ProcedureError("archive modifiée pendant les vérifications")
        self.state["steps"]["package"] = {"zip_sha256": digest, "verify_archive": "PASS",
                                          "extracted_identical": True, "resources": resources,
                                          "extracted_deep_strict": "PASS", "extracted_stapler_validate": "PASS"}
        self.save("package", "PASS")
        self.say(f"release/{FINAL_ZIP} : sha256 {digest}")
        self.say("verify_archive, extraction identique, ressources, signature et ticket après extraction : PASS")
        return EXIT_OK

    def extract(self, archive, purpose):
        index = 1
        while os.path.lexists(self.workspace / f"extracted-{purpose}-{index}"):
            index += 1
        folder = self.workspace / f"extracted-{purpose}-{index}"
        os.mkdir(folder, 0o700)
        result = self.run([self.tool("ditto"), "-x", "-k", str(archive), str(folder)], step="ditto-x")
        if not result.ok:
            raise ProcedureError("extraction ditto impossible")
        if sorted(os.listdir(folder)) != [APP_DIR]:
            raise ProcedureError("l'archive ne contient pas uniquement SpoolScribe.app")
        return folder / APP_DIR

    # ── assess ─────────────────────────────────────────────────────────
    def assess(self, workspace, confirmed):
        self.require_macos()
        if not confirmed:
            raise ProcedureError("évaluation Gatekeeper non autorisée : ajouter --confirm-assessment")
        self.open_workspace(workspace)
        package = self.state["steps"].get("package")
        if not package:
            raise ProcedureError("package manquant")
        archive = self.workspace / "release" / FINAL_ZIP
        if sha256_file(archive) != package["zip_sha256"]:
            raise ProcedureError("archive finale modifiée")
        extracted = self.extract(archive, "assess")
        result = self.run([self.tool("spctl"), "--assess", "--type", "execute", "-vvv", str(extracted)],
                          step="spctl")
        text = result.stderr + result.stdout
        _write_private(self.workspace / "private/spctl.txt", text)
        accepted = result.ok and ": accepted" in text
        source = re.search(r"^source=(.*)$", text, re.M)
        source = source.group(1).strip() if source else None
        verdict = "PASS" if accepted and source == "Notarized Developer ID" else "FAIL"
        self.state["steps"]["assess"] = {"spctl": verdict, "source": source, "standard_user_launch": "NON MESURÉ",
                                         "offline_ticket_launch": "NON MESURÉ"}
        self.save("assess", verdict)
        self.say(f"spctl --assess : {verdict} (source : {source or 'inconnue'})")
        self.say("Lancement Finder par un compte standard avec quarantaine effective : NON MESURÉ")
        self.say("Lancement hors ligne avec ticket : NON MESURÉ (voir docs/MACOS_NOTARIZATION.md)")
        return EXIT_OK if verdict == "PASS" else EXIT_BLOCKED

    # ── status ─────────────────────────────────────────────────────────
    def status(self, workspace):
        self.open_workspace(workspace)
        self.say(render_summary(self.state))
        return EXIT_OK


def _version_key(text):
    return tuple(int(p) if p.isdigit() else 0 for p in str(text).split("."))


def _write_private(path, text, mode=0o600):
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    if os.path.lexists(temp):
        os.unlink(temp)
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(text)
    os.chmod(temp, mode)
    os.replace(temp, path)


def _safe_extract(archive, destination):
    if not hasattr(tarfile, "data_filter"):
        raise ProcedureError("interpréteur sans extraction tar sûre (filtre 'data')")
    with tarfile.open(archive) as stream:
        stream.extractall(destination, filter="data")


def _pin_mismatches(requirements, freeze):
    installed = {}
    for line in freeze.splitlines():
        name, sep, version = line.partition("==")
        if sep:
            installed[re.sub(r"[-_.]+", "-", name).lower()] = version.strip()
    wrong = []
    for line in requirements.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or "==" not in line:
            continue
        spec, _, marker = line.partition(";")
        marker = marker.strip()
        if marker and marker != "sys_platform == 'darwin'":
            if not marker.startswith("python_full_version"):
                continue
            op, _, ver = marker[len("python_full_version"):].strip().partition(" ")
            current = tuple(REQUIRED_PYTHON)
            wanted = tuple(int(p) for p in ver.strip("'\"").split(".")[:2])
            if not {"<": current < wanted, ">=": current >= wanted}.get(op, False):
                continue
        name, _, version = spec.partition("==")
        key = re.sub(r"[-_.]+", "-", name.strip()).lower()
        if installed.get(key) != version.strip():
            wrong.append(f"{key} {installed.get(key)} ≠ {version.strip()}")
    return wrong


def render_summary(state):
    """Résumé partageable : ni identité, ni équipe, ni chemin hors espace privé."""
    steps = state.get("steps", {})
    candidate = state.get("candidate", {})
    submission = state.get("submission") or {}
    lines = ["# SpoolScribe — notarisation macOS (résumé partageable)", "",
             f"- Commit exporté : `{state.get('commit')}`"]
    tool = steps.get("prepare", {}).get("tool")
    if tool:
        lines.append(f"- Outil : sha256 `{tool['sha256']}` ; identique au commit : {tool['matches_commit']}")
    if "build" in steps:
        lines.append(f"- Candidat construit : `{candidate.get('built')}`")
    inspect = steps.get("inspect")
    if inspect:
        lines.append(f"- Inspection : {'PASS' if not inspect['errors'] else 'FAIL'} ; {inspect['macho_count']} Mach-O, "
                     f"{inspect['frameworks']} versions de framework, {inspect['links']} liens, "
                     f"archs {', '.join(inspect['archs_common'])} ; {len(inspect['warnings'])} avertissements")
    for stage, probe in steps.get("probes", {}).items():
        lines.append(f"- Sondes gelées ({stage}) : " + ", ".join(f"{k} {v}" for k, v in probe["results"].items()))
    if "sanitize" in steps:
        lines.append(f"- Attributs interdits retirés : {steps['sanitize']['removed'] or 'aucun'}")
    sign = steps.get("sign")
    if sign:
        verified = sign.get("verified")
        lines.append(f"- Signature : {sign['signed']}/{sign['items']} objets ; "
                     + (f"vérifiée ({verified['type']}, équipe unique, runtime, timestamp sécurisé, "
                        f"entitlements {verified['entitlements']})" if verified else "NON VÉRIFIÉE"))
    if submission:
        review = submission.get("review") or {}
        lines.append(f"- Notarisation : {submission.get('status')} ; soumission `{submission.get('id', '—')}` ; "
                     f"ZIP sha256 `{submission.get('zip_sha256')}`"
                     + (f" ; journal : {review.get('issues')} issue(s), {len(review.get('errors', []))} "
                        f"catégorie(s) d'erreur, {len(review.get('warnings', []))} catégorie(s) d'avertissement "
                        "(détail privé)" if review else ""))
    if "staple" in steps:
        lines.append("- Stapling : PASS (validate + verify deep strict)")
    if "package" in steps:
        lines.append(f"- {FINAL_ZIP} : sha256 `{steps['package']['zip_sha256']}` ; extraction vérifiée")
    if "assess" in steps:
        lines.append(f"- spctl : {steps['assess']['spctl']} ; utilisateur standard : NON MESURÉ")
    lines += ["", "Verdict : " + overall_verdict(state), ""]
    return "\n".join(lines)


def overall_verdict(state):
    steps, submission = state.get("steps", {}), state.get("submission") or {}
    if "assess" in steps:
        return f"ZIP FINAL NOTARISÉ, spctl {steps['assess']['spctl']} — ESSAI UTILISATEUR STANDARD NON MESURÉ"
    if "package" in steps:
        return "ZIP FINAL STAPLÉ VÉRIFIÉ — GATEKEEPER NON MESURÉ — AUCUNE PUBLICATION"
    if "staple" in steps:
        return "STAPLÉ — À EMPAQUETER"
    if submission.get("status") == "Accepted":
        return "ACCEPTED — À STAPLER"
    if submission.get("status") == "PENDING":
        return "PENDING — REPRISE PAR notary-status"
    if submission:
        return f"NOTARISATION BLOQUÉE ({submission.get('status')})"
    if state.get("candidate", {}).get("signed"):
        return "SIGNÉ ET VÉRIFIÉ — NON NOTARISÉ"
    if steps.get("sign"):
        return "SIGNATURE EN ÉCHEC — CANDIDAT INUTILISABLE"
    if "build" in steps:
        return "CANDIDAT NON SIGNÉ"
    return "PRÉPARATION"


def build_parser():
    parser = argparse.ArgumentParser(prog="macos_notarize.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("preflight", help="lecture seule")
    p.add_argument("--python")
    p.add_argument("--identity", help="empreinte SHA-1 de l'identité Developer ID Application")
    p.add_argument("--profile", help="nom d'un profil notarytool déjà configuré (non vérifié ici)")
    p = sub.add_parser("prepare")
    p.add_argument("--workspace", required=True)
    p.add_argument("--commit", required=True)
    p.add_argument("--python", required=True)
    p.add_argument("--wheelhouse", help="installation hors ligne depuis ce dossier de wheels")
    for name in ("build", "probes", "sanitize", "package", "status"):
        sub.add_parser(name).add_argument("--workspace", required=True)
    p = sub.add_parser("inspect")
    p.add_argument("--workspace", required=True)
    p.add_argument("--arch", choices=PILOT_ARCHS, default=PILOT_ARCHS[0])
    p = sub.add_parser("sign")
    p.add_argument("--workspace", required=True)
    p.add_argument("--identity", required=True)
    p.add_argument("--entitlements", help="exceptions approuvées (aucune par défaut)")
    p.add_argument("--confirm-signing", action="store_true")
    p = sub.add_parser("notarize")
    p.add_argument("--workspace", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--wait-timeout", default="30m")
    p.add_argument("--confirm-submission", action="store_true")
    p = sub.add_parser("notary-status")
    p.add_argument("--workspace", required=True)
    p.add_argument("--profile", required=True)
    p.add_argument("--wait-timeout")
    p.add_argument("--confirm-apple-query", action="store_true")
    p = sub.add_parser("staple")
    p.add_argument("--workspace", required=True)
    p.add_argument("--acknowledge-log-warnings", action="store_true")
    p.add_argument("--confirm-stapling", action="store_true")
    p = sub.add_parser("assess")
    p.add_argument("--workspace", required=True)
    p.add_argument("--confirm-assessment", action="store_true")
    return parser


def main(argv=None, **context):
    args = build_parser().parse_args(argv)
    proc = Procedure(**context)
    try:
        if args.command == "preflight":
            return proc.preflight(args.python, args.identity, args.profile)
        if args.command == "prepare":
            return proc.prepare(args.workspace, args.commit, args.python, args.wheelhouse)
        if args.command == "inspect":
            return proc.inspect(args.workspace, args.arch)
        if args.command == "sign":
            return proc.sign(args.workspace, args.identity, args.confirm_signing, args.entitlements)
        if args.command == "notarize":
            return proc.notarize(args.workspace, args.profile, args.confirm_submission, args.wait_timeout)
        if args.command == "notary-status":
            return proc.notary_status(args.workspace, args.profile, args.confirm_apple_query, args.wait_timeout)
        if args.command == "staple":
            return proc.staple(args.workspace, args.confirm_stapling, args.acknowledge_log_warnings)
        if args.command == "assess":
            return proc.assess(args.workspace, args.confirm_assessment)
        return getattr(proc, args.command)(args.workspace)
    except ProcedureError as exc:
        # Libellé public du catalogue seulement ; texte brut, détail et trace en privé.
        label = exc.public or UNLISTED_REFUSAL
        trace = _private_trace(proc, "refusal", args.command,
                               {"public": label, "raw": exc.raw, "detail": exc.detail})
        _record_block(proc, args.command, label)
        proc.say(f"BLOQUÉ [{args.command}] : {label} ; " + _trace_note(trace))
        return EXIT_BLOCKED
    except Exception as exc:  # jamais de trace brute (données externes) sur la sortie partageable
        label = f"erreur interne {type(exc).__name__}"
        trace = _private_trace(proc, "internal-error", args.command, {"public": label})
        _record_block(proc, args.command, label)
        proc.say(f"BLOQUÉ [{args.command}] : {label} ; " + _trace_note(trace))
        return EXIT_BLOCKED


def _private_trace(proc, kind, command, fields):
    """Écrit une nouvelle trace privée (jamais d'écrasement) ; None si aucun espace privé valide."""
    if proc.workspace is None or proc.state is None:
        return None
    import traceback
    folder = proc.workspace / "private"
    try:
        info = os.lstat(folder)
    except OSError:
        return None
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        return None
    body = "".join(f"{key}: {value!r}\n" for key, value in [("command", command), ("time", _now()),
                                                            *fields.items()])
    body += "\n" + traceback.format_exc()
    stamp = _now().replace(":", "")
    for index in range(1, 1000):
        name = f"{kind}-{stamp}-{index:03d}.txt"
        try:
            fd = os.open(folder / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        except OSError:
            return None
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(body)
        except OSError:
            return None
        return f"private/{name}"
    return None


def _record_block(proc, command, label):
    if proc.workspace is not None and proc.state is not None:
        try:
            proc.save(command, f"BLOQUÉ : {label}")
        except OSError:
            pass


def _trace_note(trace):
    return f"détail privé : {trace}" if trace else "détail privé indisponible (aucune trace enregistrée)"


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 ou plus récent requis pour lancer cette procédure.")
    sys.exit(main())
