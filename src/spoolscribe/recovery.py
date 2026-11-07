"""Reprise d'une restauration interrompue, exécutée avant tout chargement du modèle.

Ce module n'utilise que la bibliothèque standard et n'importe **jamais**
``spoolscribe.core`` ni un module qui l'importe : ``core`` calcule les chemins
et charge la liste d'imprimantes dès son import, ce qui lirait une restauration
partielle. Les points d'entrée (``packaging/gui_entry.py``,
``python -m spoolscribe``, ``spoolscribe-cli``) appellent :func:`bootstrap`
avant d'importer l'interface ou le modèle.

Protocole (partagé avec :mod:`spoolscribe.backup`) :

* ``<DATA_HOME>/.spoolscribe-restore/`` est privé (0700). Il contient
  ``restore.lock`` (verrou noyau ``flock``/``msvcrt`` : libéré par le système si
  le processus meurt, donc sans verrou périmé ni réutilisation de PID) et un
  dossier ``tx-<id>/`` par transaction : ``journal.json``, ``new/<n>`` (octets à
  publier) et ``snapshot/<n>`` (copie **exacte** du fichier remplacé ; une
  absence est notée ``before: null``).
* Le journal (version 2) est écrit (écriture atomique + fsync) avec la phase
  ``publishing`` et la liste complète des éléments **avant** la première
  publication. Chaque élément enregistre l'identité (``dev``, ``ino``, taille,
  ``mtime_ns``) de l'objet qu'il remplace. **Avant** chaque publication, une
  preuve durable ``done/<n>`` enregistre l'identité de l'objet privé exact que
  nous allons publier ; une cible absente est publiée par ``os.link`` (création
  sans remplacement possible), une cible présente par ``os.replace`` après
  contrôle de son identité et de son empreinte. L'état d'un élément est déduit
  de la **propriété** de l'objet présent, jamais de la seule égalité d'octets :
  identité égale à la preuve et empreinte ``after`` = publié par nous (rétabli) ;
  empreinte ``before`` = intact ; octets identiques sans propriété prouvée =
  **ambigu**, conservé et signalé ; autre contenu = tiers ou conflit, jamais
  écrasé ni supprimé. Un journal de version 1 (sans preuve) est conservé et
  signalé, jamais rejoué.
* La même règle vaut pour nos objets **temporaires** et les noms de sonde :
  l'objet préparé est tenu par un descripteur ouvert jusqu'à la fin de sa
  publication ; un nom n'est utilisé (lien, remplacement, suppression) qu'après
  vérification que l'occupant du nom est cet objet ; une publication dont le
  résultat n'est pas cet objet est refusée (``ConcurrentChange``) ; un occupant
  étranger d'un nom temporaire ou de sonde n'est jamais supprimé, même à octets
  identiques. Limite : sur les systèmes sans lien par descripteur (macOS), la
  vérification d'identité puis l'opération sur le nom ne sont pas atomiques ;
  la fenêtre résiduelle est détectée après coup, pas exclue.
* Une configuration hors de ``DATA_HOME`` est signalée par un pointeur
  ``<config>.restore-pending`` vers la transaction, pour qu'un lancement avec
  un autre ``DATA_HOME`` mais la même configuration la détecte aussi.
* Reprise d'une transaction inachevée = **retour arrière** de chaque élément
  publié (restauration de l'instantané, ou suppression d'un fichier que nous
  avions créé et dont l'empreinte est toujours la nôtre). Si un élément ne peut
  être rétabli, la transaction reste en ``rollback_incomplete`` avec son
  journal et ses instantanés : état « récupérable », jamais « réussi ».

Limites honnêtes : il s'agit d'une transaction **logique** pour les lecteurs et
écrivains coopérants (verrou de restauration, verrous d'écriture par fichier,
reprise au démarrage). Plusieurs ``os.replace`` successifs ne forment pas une
transaction atomique globale du système de fichiers ; un programme externe qui
ignore ces verrous peut observer un état intermédiaire ou s'intercaler entre la
dernière vérification d'empreinte et le remplacement.
"""
from __future__ import annotations

import datetime as _dt
import errno
import hashlib
import json
import os
import secrets
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "SpoolScribe"
TX_ROOT_NAME = ".spoolscribe-restore"
LOCK_NAME = "restore.lock"
JOURNAL_NAME = "journal.json"
TX_PREFIX = "tx-"
POINTER_SUFFIX = ".restore-pending"
JOURNAL_FORMAT = "spoolscribe-restore-journal"
POINTER_FORMAT = "spoolscribe-restore-pointer"
PROOF_FORMAT = "spoolscribe-restore-proof"
JOURNAL_VERSION = 2          # v2: identities and per-item proofs of publication (v1 journals are kept, never replayed)
IDENTITY_KEYS = ("dev", "ino", "size", "mtime_ns")
# Phases of a journal. Pending ones are resolved (rolled back) at startup.
PENDING_PHASES = ("publishing", "rolling_back", "rollback_incomplete", "reverting")
KEPT_PHASES = ("committed", "dismissed")      # snapshot kept for an explicit undo
KEEP_SNAPSHOTS = 3                            # committed/dismissed transactions kept

STARTUP_STATUS: dict | None = None            # result of the last bootstrap(), read by the GUI

# Every user-facing message: French template with named {v0}… placeholders.
MESSAGES = {
    # Verrous et transactions
    "busy": "Une restauration est déjà en cours pour ce dossier de données ; réessayez quand elle sera terminée.",
    "lock_unavailable": "Verrou de restauration indisponible sur ce dossier ({v0}) ; opération refusée.",
    "writer_busy": "Écriture déjà en cours sur {v0} ; réessayez quand elle sera terminée.",
    "recovery_pending": "Une restauration précédente est inachevée ; sa reprise doit être terminée avant toute nouvelle opération.",
    "journal_invalid": "Journal de restauration illisible ({v0}) ; dossier conservé pour une reprise manuelle : {v1}",
    "not_found": "Transaction de restauration introuvable : {v0}",
    "not_revertible": "Cette restauration ne peut pas être annulée (état : {v0}).",
    "not_dismissable": "Cette reprise ne peut pas être classée (état : {v0}).",
    # Résultats de reprise (bootstrap / recover)
    "recovery_nothing": "Aucune restauration inachevée.",
    "recovery_cleaned": "Fichiers temporaires d'une restauration non publiée retirés ; données inchangées.",
    "recovery_done": "Restauration interrompue annulée : {v0} élément(s) rétabli(s) dans leur état précédent.",
    "recovery_reverted": "Restauration annulée : {v0} élément(s) rétabli(s) dans leur état d'avant restauration.",
    "recovery_incomplete": "Retour arrière incomplet : {v0} élément(s) n'ont pas pu être rétablis. Journal et instantanés conservés dans {v1}.",
    "recovery_busy": "Une restauration est en cours dans un autre processus ; aucune reprise tentée.",
    "bootstrap_failed": "Vérification de restauration impossible au démarrage : {v0}",
    "recovery_dismissed": "Reprise classée : l'état actuel est conservé ; l'instantané d'avant restauration reste disponible dans {v0}.",
    # Sauvegarde
    "destination_exists": "Le fichier {v0} existe déjà ; confirmez explicitement son remplacement.",
    "destination_invalid": "Emplacement de sauvegarde refusé : {v0}",
    "catalogue_missing": "Catalogue absent : aucune sauvegarde possible.",
    "source_invalid": "{v0} invalide : {v1}. Sauvegarde non créée.",
    "source_unreadable": "Lecture impossible de {v0} : {v1}",
    "source_changed": "{v0} a changé pendant la sauvegarde ; recommencez.",
    "source_too_large": "{v0} : {v1} octets, au-delà de la limite ({v2} octets). Sauvegarde non créée.",
    "backup_too_large": "Sauvegarde trop volumineuse : {v0} (limite {v1}).",
    "write_failed": "Écriture de la sauvegarde impossible : {v0}",
    "cancelled": "Opération annulée ; aucune donnée n'a été écrite.",
    # Analyse
    "archive_unreadable": "Archive illisible : {v0}",
    "not_a_backup": "Ce fichier n'est pas une sauvegarde SpoolScribe.",
    "archive_too_large": "Archive trop volumineuse : {v0} octets (limite {v1}).",
    "too_many_members": "Archive refusée : {v0} membres (limite {v1}).",
    "manifest_missing": "Manifeste absent : archive refusée.",
    "manifest_duplicate": "Manifeste en double : archive refusée.",
    "manifest_invalid": "Manifeste invalide : {v0}",
    "unsupported_version": "Version de sauvegarde {v0} non prise en charge.",
    "unsafe_path": "Chemin refusé dans l'archive : {v0}",
    "unsafe_target": "Destination refusée (lien, dossier ou hors du dossier de données) : {v0}",
    "duplicate_member": "Membre en double ou en collision (casse/normalisation) : {v0}",
    "link_member": "Lien refusé dans l'archive : {v0}",
    "not_regular": "Membre non régulier refusé : {v0}",
    "encrypted_member": "Membre chiffré ou compression non prise en charge : {v0}",
    "missing_member": "Membre annoncé mais absent de l'archive : {v0}",
    "unexpected_member": "Membre inattendu dans l'archive : {v0}",
    "member_too_large": "{v0} : {v1} octets, au-delà de la limite ({v2} octets).",
    "total_too_large": "Contenu décompressé trop volumineux : {v0} octets (limite {v1}).",
    "size_mismatch": "{v0} : taille différente de celle annoncée.",
    "digest_mismatch": "{v0} : empreinte SHA-256 différente de celle annoncée.",
    "member_corrupt": "{v0} : contenu illisible ({v1}).",
    "member_invalid": "{v0} : {v1}",
    "options_mismatch": "Contenu incohérent avec les options annoncées : {v0}",
    # Restauration
    "archive_changed": "L'archive a changé depuis l'aperçu ; analysez-la de nouveau.",
    "changed_since_analysis": "{v0} a changé depuis l'aperçu ; analysez de nouveau avant de restaurer.",
    "paths_changed": "Les dossiers de données ont changé depuis l'aperçu ; analysez de nouveau.",
    "staging_failed": "Préparation de la restauration impossible : {v0}. Aucune donnée active modifiée.",
    "restore_failed": "Restauration interrompue : {v0}. Les fichiers déjà remplacés ont été rétablis.",
    "restore_recoverable": "Restauration interrompue : {v0}. Le retour arrière n'a pas pu se terminer ; journal et instantanés conservés pour une reprise.",
    "concurrent_change": "{v0} a été modifié par un autre programme pendant la restauration.",
}


class BackupError(Exception):
    """Refused or failed backup/restore operation, translatable.

    ``template`` is the French source text (named ``{v0}``… placeholders) and
    ``values`` its parameters; a value may itself be an exception carrying its
    own ``template``/``values`` (see ``colour_measurements.error_text``).
    ``details`` holds structured data for the interface (never shown raw).
    """

    def __init__(self, code: str, *, details: dict | None = None, **values):
        self.code = code
        self.template = MESSAGES[code]
        self.values = values
        self.details = details or {}
        super().__init__(self.template.format(**values) if values else self.template)


# ── Paths, computed exactly like spoolscribe.core (without importing it) ──
def user_data_dir() -> str:
    """Same rule as ``core.user_data_dir``: per-OS writable user folder."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, APP_NAME)


def data_home() -> str:
    """Same value as ``core.DATA_HOME`` for the current environment."""
    return os.environ.get("SPOOLSCRIBE_DATA_HOME") or user_data_dir()


def config_path() -> str:
    """Same value as ``core.CONFIG_PATH`` for the current environment (may be outside DATA_HOME)."""
    return os.environ.get("SPOOLSCRIBE_CONFIG_PATH") or os.path.join(user_data_dir(), "config.json")


def tx_root(home: str | os.PathLike) -> Path:
    return Path(home) / TX_ROOT_NAME


def pointer_path(config: str | os.PathLike) -> Path:
    return Path(str(config) + POINTER_SUFFIX)


# ── Small durable-file helpers ────────────────────────────────────────────
def now_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def file_digest(path: str | os.PathLike) -> str | None:
    """SHA-256 of a regular file, streamed; ``None`` when it does not exist."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except FileNotFoundError:
        return None
    return digest.hexdigest()


def fsync_dir(path: str | os.PathLike) -> None:
    """Make a rename/unlink durable where the OS allows it (no-op on Windows)."""
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def atomic_write(path: str | os.PathLike, data: bytes, *, before_replace=None) -> None:
    """Same protocol as ``scripts.db_io.atomic_write`` (temp in the same folder, fsync, replace), plus a folder fsync."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if before_replace is not None:
            before_replace()
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    fsync_dir(path.parent)


def write_private(path: str | os.PathLike, data: bytes) -> None:
    """Exclusive creation of a private file (0600), flushed to disk."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _json_bytes(document) -> bytes:
    return json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False).encode("utf-8")


# ── Object identity and proof of publication ──────────────────────────────
class ConcurrentChange(Exception):
    """The target is not the object seen at the preview (or appeared meanwhile); nothing was written to it."""


class StagingConflict(ConcurrentChange):
    """Writing our temporary failed and its name no longer holds our object: nothing removed, reported.

    ``residue`` (``target``, ``temporary``, ``state``) is recorded in the journal by the caller, so the
    restore stays recoverable (never ``complete``) while that non-attributable object remains.
    """

    def __init__(self, target: Path, temporary: str, state: str):
        self.residue = {"target": str(target), "temporary": str(temporary), "state": state}
        super().__init__(f"{target.name} (nom temporaire occupé ou déplacé par un tiers après une erreur d'écriture)")


def _identity_of_stat(st) -> dict:
    return {"dev": st.st_dev, "ino": st.st_ino, "size": st.st_size, "mtime_ns": st.st_mtime_ns}


def file_identity(path: str | os.PathLike) -> dict | None:
    """Identity of the regular file at ``path`` (``None`` if absent); a link or non-regular object is an OSError."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(st.st_mode):
        raise OSError(errno.EINVAL, "objet non régulier", str(path))
    return _identity_of_stat(st)


def same_identity(current, expected) -> bool:
    return bool(current) and bool(expected) and all(current.get(k) == expected.get(k) for k in IDENTITY_KEYS)


def valid_identity(value) -> bool:
    return isinstance(value, dict) and set(value) == set(IDENTITY_KEYS) and \
        all(type(value[k]) is int and value[k] >= 0 for k in IDENTITY_KEYS)


def _unlink_quiet(path) -> None:
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _owned_name(name, identity: dict) -> bool:
    """Whether the regular file currently at ``name`` is exactly the object ``identity``."""
    try:
        return same_identity(file_identity(name), identity)
    except OSError:
        return False


def _unlink_owned(name, identity: dict) -> bool:
    """Remove ``name`` only if its occupant is our object ``identity``; a foreign or ambiguous occupant is kept.

    Not atomic: the identity check and the removal are two operations on the
    name (no unlink-by-descriptor); the window is documented, not excluded.
    """
    if not _owned_name(name, identity):
        return False
    try:
        os.unlink(name)
    except FileNotFoundError:
        return False
    return True


def _stage_temporary(path: Path, data: bytes) -> tuple:
    """Private temporary object in the target folder, flushed; returns ``(temporary, identity, fd)``.

    The descriptor stays open (the caller closes it): while it is held, the
    object cannot be freed, so its identity cannot be reused by another file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
        identity = _identity_of_stat(os.fstat(fd))
    except BaseException as exc:
        state = _release_failed_stage(temporary, fd, data)
        if state is not None:
            raise StagingConflict(path, temporary, state) from exc
        raise
    return temporary, identity, fd


def _release_failed_stage(temporary: str, fd: int, data: bytes) -> str | None:
    """After a failed write: remove ``temporary`` only if its occupant is still our object; close ``fd``.

    Ownership is the ``(dev, ino)`` of our open descriptor (size/mtime change during a partial write
    and are not compared); while the descriptor is held, that inode cannot be reused. Returns ``None``
    when nothing non-attributable remains, else the state of the name: ``foreign``/``ambiguous``
    (another object, other/same bytes as ours) or ``missing`` (our object was moved away; not chased).
    Not atomic: the name check and ``unlink`` are two operations on the name (documented window).
    """
    try:
        try:
            st = os.fstat(fd)
            ours = (st.st_dev, st.st_ino)
            occupant = os.lstat(temporary)
        except FileNotFoundError:
            return "missing"
        except OSError:
            return "unreadable"
        if stat.S_ISREG(occupant.st_mode) and (occupant.st_dev, occupant.st_ino) == ours:
            if os.name != "nt":                         # POSIX: removed while our descriptor pins the inode
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    return "missing"
                except OSError:
                    return "unreadable"
                return None
            os.close(fd)                                # Windows: an open file cannot be removed
            fd = -1
            try:
                again = os.lstat(temporary)
                if (again.st_dev, again.st_ino) == ours:
                    os.unlink(temporary)
                    return None
            except FileNotFoundError:
                return "missing"
            except OSError:
                return "unreadable"
        try:
            same = file_digest(temporary) == hashlib.sha256(data).hexdigest()
        except OSError:
            return "unreadable"
        return "ambiguous" if same else "foreign"
    finally:
        if fd >= 0:
            os.close(fd)


def publish_new(path: str | os.PathLike, data: bytes, *, before_publish=None) -> dict:
    """Create ``path`` with ``data`` without ever replacing an object that exists or appears meanwhile.

    The private temporary is hard-linked to ``path`` (atomic creation, refused by
    the OS with ``FileExistsError`` if anything is there); ``before_publish(identity)``
    runs between the flush and the link, to record the proof of what is published.
    Other OSErrors (link unsupported, permission) propagate: nothing was published.
    """
    path = Path(path)
    temporary, identity, fd = _stage_temporary(path, data)
    try:
        if before_publish is not None:
            before_publish(identity)
        if not _owned_name(temporary, identity):          # the staged name was taken by another object
            raise ConcurrentChange(f"{path.name} (objet temporaire remplacé avant publication)")
        os.link(temporary, path)                          # FileExistsError: an occupant appeared, never replaced
        _publish_hook("linked", path)
        if not _owned_name(path, identity):               # the link attached an object that is not ours
            raise ConcurrentChange(f"{path.name} (objet publié non attribuable à la restauration)")
        if not _unlink_owned(temporary, identity):        # the source name is now a third party's: kept
            raise ConcurrentChange(f"{path.name} (nom temporaire occupé par un tiers après publication)")
    finally:
        os.close(fd)
        _unlink_owned(temporary, identity)                # our own leftover only; never a name without proof
    fsync_dir(path.parent)
    return identity


def publish_replace(path: str | os.PathLike, data: bytes, *, expected: dict, before_publish=None) -> dict:
    """Replace the exact object ``expected`` (``identity`` and ``digest``) at ``path`` with ``data``.

    ``before_publish(identity)`` runs between the flush and the replacement. If the
    object present is not the expected one, :class:`ConcurrentChange` is raised and
    nothing is written to ``path``.
    """
    path = Path(path)
    temporary, identity, fd = _stage_temporary(path, data)
    try:
        if before_publish is not None:
            before_publish(identity)
        if not _owned_name(temporary, identity):
            raise ConcurrentChange(f"{path.name} (objet temporaire remplacé avant publication)")
        if not same_identity(file_identity(path), expected.get("identity")) or file_digest(path) != expected.get("digest"):
            raise ConcurrentChange(path.name)
        os.replace(temporary, path)
        _publish_hook("replaced", path)
        if not _owned_name(path, identity):
            raise ConcurrentChange(f"{path.name} (objet publié non attribuable à la restauration)")
    finally:
        os.close(fd)
        _unlink_owned(temporary, identity)
    fsync_dir(path.parent)
    return identity


# Test hook (None in production): called with ("linked" | "replaced", path) right after a publication.
_PUBLISH_HOOK = None


def _publish_hook(label: str, path: Path) -> None:
    if _PUBLISH_HOOK is not None:
        _PUBLISH_HOOK(f"{label}:{path.name}")


_LINK_UNSUPPORTED = tuple(getattr(errno, name) for name in ("EPERM", "ENOTSUP", "EOPNOTSUPP", "EXDEV", "EMLINK", "ENOSYS", "EINVAL")
                          if hasattr(errno, name))


PROBE_ATTEMPTS = 8


def link_supported(directory: str | os.PathLike) -> bool:
    """Whether ``directory`` allows the no-replace creation used by :func:`publish_new` (probe, nothing kept)."""
    if not hasattr(os, "link"):
        return False
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".spoolscribe-probe.", suffix=".tmp", dir=directory)
    except OSError:
        return True      # not writable at all: the publication itself will be refused by the OS, nothing replaced
    identity = _identity_of_stat(os.fstat(fd))
    try:
        for _ in range(PROBE_ATTEMPTS):
            second = f"{temporary}.{secrets.token_hex(4)}.link"
            if not _owned_name(temporary, identity):
                return False                              # our probe object was taken away: nothing proven
            try:
                os.link(temporary, second)
            except FileExistsError:
                continue                                  # a third party's name: never touched, try another
            except OSError as exc:
                return exc.errno not in _LINK_UNSUPPORTED
            # Capability is proven only by a link of our own object; the created name is removed only if ours.
            proven = _owned_name(second, identity)
            _unlink_owned(second, identity)
            return proven
        return False                                      # no owned probe could be completed
    finally:
        os.close(fd)
        _unlink_owned(temporary, identity)


def remove_orphan_temporary(target: str | os.PathLike, identity: dict) -> bool:
    """Remove a leftover private temporary of ``target`` proven ours by ``identity`` (crash before publication)."""
    target = Path(target)
    removed = False
    try:
        names = os.listdir(target.parent)
    except OSError:
        return False
    for name in names:
        if not (name.startswith(f".{target.name}.") and name.endswith(".tmp")):
            continue
        candidate = target.parent / name
        try:
            if same_identity(file_identity(candidate), identity):
                os.unlink(candidate)
                removed = True
        except OSError:
            continue
    if removed:
        fsync_dir(target.parent)
    return removed


def _remove_tree(path: Path) -> None:
    """Remove one of our private transaction folders (never anything else)."""
    if path.name.startswith(TX_PREFIX) and path.parent.name == TX_ROOT_NAME:
        shutil.rmtree(path)
        fsync_dir(path.parent)


# ── Restore lock (kernel lock, released by the OS if the process dies) ────
def _try_lock(fd: int) -> bool:
    if os.name == "nt":
        import msvcrt
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import errno
    import fcntl
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return False
    except OSError as exc:
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            return False
        raise BackupError("lock_unavailable", v0=exc.strerror or exc) from exc
    return True


def _unlock(fd: int) -> None:
    try:
        if os.name == "nt":
            import msvcrt
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def restore_lock(home: str | os.PathLike):
    """Exclusive restore/recovery lock for one data folder; ``BackupError('busy')`` if held elsewhere.

    Not re-entrant: a second acquisition in the same process is also refused.
    """
    root = tx_root(home)
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(root / LOCK_NAME, os.O_RDWR | os.O_CREAT, 0o600)
    except OSError as exc:
        raise BackupError("lock_unavailable", v0=exc.strerror or exc) from exc
    try:
        if not _try_lock(fd):
            raise BackupError("busy")
    except BaseException:
        os.close(fd)
        raise
    try:
        os.ftruncate(fd, 0)
        os.lseek(fd, 0, os.SEEK_SET)
        os.write(fd, str(os.getpid()).encode("ascii"))
        yield
    finally:
        _unlock(fd)
        os.close(fd)


# ── Journal ───────────────────────────────────────────────────────────────
RESIDUE_STATES = ("foreign", "ambiguous", "missing", "unreadable")
_ITEM_KEYS = {"index", "type", "member", "target", "before", "after", "snapshot", "staged", "before_identity"}


def _hex64(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_journal(document) -> dict:
    """Structural check of our own journal before acting on it."""
    if not isinstance(document, dict) or document.get("format") != JOURNAL_FORMAT:
        raise ValueError("format inconnu")
    version = document.get("version")
    if type(version) is not int or version != JOURNAL_VERSION:
        # A journal without proofs of publication (v1) must never be replayed: kept and reported instead.
        raise ValueError(f"version {version!r} : preuve de propriété absente, dossier conservé")
    if document.get("phase") not in PENDING_PHASES + KEPT_PHASES + ("rolled_back", "reverted"):
        raise ValueError("phase inconnue")
    items = document.get("items")
    if not isinstance(items, list):
        raise ValueError("éléments absents")
    for item in items:
        if not isinstance(item, dict) or not _ITEM_KEYS <= set(item):
            raise ValueError("élément incomplet")
        if not isinstance(item["target"], str) or not os.path.isabs(item["target"]):
            raise ValueError("destination non absolue")
        for key in ("before", "after"):
            if item[key] is not None and not _hex64(item[key]):
                raise ValueError("empreinte invalide")
        if item["after"] is None:
            raise ValueError("empreinte publiée absente")
        for key in ("snapshot", "staged"):
            value = item[key]
            if value is not None and (not isinstance(value, str) or Path(value).is_absolute() or ".." in Path(value).parts):
                raise ValueError("chemin interne invalide")
        if (item["before"] is None) != (item["snapshot"] is None):
            raise ValueError("instantané incohérent")
        if (item["before"] is None) != (item["before_identity"] is None):
            raise ValueError("identité incohérente")
        if item["before_identity"] is not None and not valid_identity(item["before_identity"]):
            raise ValueError("identité invalide")
    for key in ("residues", "dismissed_residues"):     # optional: non-attributable staging leftovers (B03)
        residues = document.get(key, [])
        if not isinstance(residues, list) or any(
                not isinstance(r, dict) or not isinstance(r.get("target"), str) or not os.path.isabs(r["target"])
                or not isinstance(r.get("temporary"), str) or not os.path.isabs(r["temporary"])
                or r.get("state") not in RESIDUE_STATES for r in residues):
            raise ValueError("résidus invalides")
    return document


def read_journal(txdir: Path) -> dict:
    raw = (txdir / JOURNAL_NAME).read_bytes()
    return validate_journal(json.loads(raw.decode("utf-8")))


def write_journal(txdir: Path, journal: dict) -> None:
    journal["updated_utc"] = now_utc()
    atomic_write(txdir / JOURNAL_NAME, _json_bytes(journal))


def new_transaction(home: str | os.PathLike) -> tuple[str, Path]:
    """Create a private, empty transaction folder (caller holds the restore lock)."""
    txid = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    txdir = tx_root(home) / (TX_PREFIX + txid)
    txdir.mkdir(mode=0o700)
    (txdir / "new").mkdir(mode=0o700)
    (txdir / "snapshot").mkdir(mode=0o700)
    (txdir / "done").mkdir(mode=0o700)
    return txid, txdir


INVALID_PROOF = object()


def write_proof(txdir: Path, index: int, after: str, identity: dict) -> None:
    """Durable, exclusive proof written **before** publishing item ``index``: the identity of our exact object.

    At recovery, only an object whose identity equals this proof (and whose
    digest is ``after``) is ours; byte equality alone never proves ownership.
    """
    document = {"format": PROOF_FORMAT, "version": JOURNAL_VERSION, "index": int(index), "after": after,
                "identity": dict(identity)}
    write_private(txdir / "done" / str(int(index)), _json_bytes(document))
    fsync_dir(txdir / "done")


def read_proof(txdir: Path, item: dict):
    """Identity recorded for ``item``: ``None`` (publication never attempted), a dict, or :data:`INVALID_PROOF`."""
    path = txdir / "done" / str(item["index"])
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return INVALID_PROOF
    try:
        document = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return INVALID_PROOF
    if not isinstance(document, dict) or document.get("format") != PROOF_FORMAT \
            or document.get("index") != item["index"] or document.get("after") != item["after"] \
            or not valid_identity(document.get("identity")):
        return INVALID_PROOF
    return document["identity"]


def write_pointer(config: str | os.PathLike, txdir: Path) -> Path:
    path = pointer_path(config)
    atomic_write(path, _json_bytes({"format": POINTER_FORMAT, "version": 1, "transaction": str(txdir)}))
    return path


def remove_pointer(config: str | os.PathLike | None, txdir: Path | None = None) -> None:
    """Remove the config-side pointer, only when it designates ``txdir`` (or is unreadable/stale)."""
    if not config:
        return
    path = pointer_path(config)
    target = _read_pointer(path)
    if target is None and not path.exists():
        return
    if txdir is None or target is None or Path(target) == Path(txdir):
        try:
            path.unlink()
            fsync_dir(path.parent)
        except FileNotFoundError:
            pass


def _read_pointer(path: Path) -> str | None:
    try:
        document = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if isinstance(document, dict) and document.get("format") == POINTER_FORMAT and isinstance(document.get("transaction"), str):
        return document["transaction"]
    return None


# ── Discovery ─────────────────────────────────────────────────────────────
def _transaction_dirs(home: str | os.PathLike | None, config: str | os.PathLike | None) -> list[Path]:
    found: dict[str, Path] = {}
    if home:
        root = tx_root(home)
        try:
            names = sorted(os.listdir(root))
        except OSError:
            names = []
        for name in names:
            path = root / name
            if name.startswith(TX_PREFIX) and path.is_dir() and not path.is_symlink():
                found[str(path)] = path
    if config:
        target = _read_pointer(pointer_path(config))
        if target:
            path = Path(target)
            if path.name.startswith(TX_PREFIX) and path.parent.name == TX_ROOT_NAME and path.is_dir():
                found.setdefault(str(path), path)
    return list(found.values())


def _quick_phase(txdir: Path) -> str:
    """Journal phase without hashing any file: ``staging`` (no journal), ``invalid`` or the phase."""
    if not (txdir / JOURNAL_NAME).exists():
        return "staging"
    try:
        return read_journal(txdir)["phase"]
    except (OSError, ValueError):
        return "invalid"


def _is_pending_phase(phase: str) -> bool:
    return phase in PENDING_PHASES or phase in ("staging", "invalid")


def _describe(txdir: Path, *, states: bool = True) -> dict:
    """State of one transaction folder, without writing anything (``states`` hashes the targets)."""
    base = {"txid": txdir.name[len(TX_PREFIX):], "dir": str(txdir), "items": [], "published": [], "conflicts": []}
    if not (txdir / JOURNAL_NAME).exists():
        return dict(base, phase="staging", pending=True)
    try:
        journal = read_journal(txdir)
    except (OSError, ValueError) as exc:
        return dict(base, phase="invalid", pending=True, error=str(exc))
    items, published, conflicts = [], [], []
    for item in journal["items"]:
        entry = {"type": item["type"], "member": item["member"], "target": item["target"]}
        if states:
            committed = journal["phase"] in KEPT_PHASES + ("reverting",)
            entry["state"], _ = item_state(txdir, item, published=True if committed else None)
            if entry["state"] == "published":
                published.append(entry)
            elif entry["state"] in CONFLICT_STATES:
                conflicts.append(entry)
        items.append(entry)
    if states and journal["phase"] in PENDING_PHASES:
        conflicts += residue_conflicts(journal)
    return dict(base, txid=journal.get("txid") or base["txid"], phase=journal["phase"],
                pending=journal["phase"] in PENDING_PHASES, created_utc=journal.get("created_utc"),
                committed_utc=journal.get("committed_utc"), config_pointer=journal.get("config_pointer"),
                items=items, published=published, conflicts=conflicts)


CONFLICT_STATES = ("conflict", "ambiguous", "unreadable", "missing")


def item_state(txdir: Path, item: dict, *, published=None) -> tuple:
    """Ownership-based state of one item, as ``(state, proof_identity)``.

    ``published``: ``True`` (known published, e.g. a committed journal being
    reverted), ``False`` (known never published, in-process), ``None`` (decide
    from the durable proof). States: ``original`` (previous content or absent
    never-created target: nothing to do), ``published`` (the exact object we
    published: may be rolled back), ``conflict`` (our object changed, replaced
    or missing: kept and reported), ``ambiguous`` (same bytes as ours but not
    our object: kept and reported), ``foreign`` (a third party's content where
    we published nothing: left alone), ``missing``/``unreadable`` (reported).
    """
    if item["before"] == item["after"]:
        return "original", None
    proof = read_proof(txdir, item)
    if proof is INVALID_PROOF:
        return "unreadable", None
    try:
        current = file_identity(item["target"])
    except OSError:
        return "unreadable", proof
    if current is None:
        if item["before"] is None:
            return "original", proof
        return ("foreign" if published is False else "missing"), proof
    try:
        digest = file_digest(item["target"])
    except OSError:
        return "unreadable", proof
    if digest == item["before"]:
        return "original", proof
    if proof is not None and same_identity(current, proof):
        # The exact object we staged (its publication may have completed just before a later failure).
        return ("published" if digest == item["after"] else "conflict"), proof
    if published is False or (published is None and proof is None):
        # Known, or proven by the absent proof, never to have been published by us: a third party's object.
        return ("ambiguous" if digest == item["after"] else "foreign"), proof
    return ("ambiguous" if digest == item["after"] else "conflict"), proof


def pending_recovery(home: str | os.PathLike | None = None, config: str | os.PathLike | None = None) -> dict | None:
    """Describe an unfinished transaction (or ``None``); reads only, takes no lock.

    The dict has ``txid``, ``dir``, ``phase`` (``staging`` = nothing published,
    ``invalid`` = unreadable journal, or a pending journal phase), ``items`` with
    their state (``original``/``published``/``conflict``), ``published``,
    ``conflicts``, ``busy`` (another process holds the restore lock) and
    ``transactions`` (all pending ones; normally a single one).
    """
    home = data_home() if home is None else home
    config = config_path() if config is None else config
    pending = [_describe(d) for d in _transaction_dirs(home, config) if _is_pending_phase(_quick_phase(d))]
    if not pending:
        return None
    first = dict(pending[0])
    first["transactions"] = pending
    first["busy"] = _is_busy(Path(first["dir"]).parent.parent)
    return first


def _is_busy(home: Path) -> bool:
    root = tx_root(home)
    if not (root / LOCK_NAME).exists():
        return False
    try:
        with restore_lock(home):
            return False
    except BackupError as exc:
        return exc.code == "busy"


def committed_restores(home: str | os.PathLike | None = None) -> list[dict]:
    """Finished restorations whose exact pre-restore snapshot is still kept (newest first)."""
    home = data_home() if home is None else home
    done = [_describe(d, states=False) for d in _transaction_dirs(home, None) if _quick_phase(d) in KEPT_PHASES]
    return sorted(done, key=lambda d: d["txid"] or "", reverse=True)


# ── Rollback ──────────────────────────────────────────────────────────────
def record_residue(journal: dict, residue: dict) -> None:
    """Add a staging leftover to the journal's ``residues`` once (keyed by its temporary name); durable when the
    caller writes the journal (``finish_rollback`` does it for every incomplete outcome)."""
    residues = journal.setdefault("residues", [])
    if not any(r["temporary"] == residue["temporary"] for r in residues):
        residues.append(dict(residue))


def residue_conflicts(journal: dict) -> list:
    """Recorded staging leftovers still unresolved: a name still occupied, or our object moved away.

    Never removed by us; reported until the occupant disappears or the user keeps the current state.
    """
    labels = {item["target"]: item for item in journal.get("items", [])}
    found = []
    for residue in journal.get("residues", []):
        if residue["state"] != "missing" and not os.path.lexists(residue["temporary"]):
            continue                                      # the third party removed its own object
        item = labels.get(residue["target"], {})
        found.append({"type": item.get("type"), "member": item.get("member"), "target": residue["target"],
                      "temporary": residue["temporary"], "state": residue["state"]})
    return found


def rollback_items(txdir: Path, journal: dict, *, all_published: bool = False, completed=None) -> dict:
    """Return every item **we** published to its recorded previous state (caller holds the restore lock).

    Newest publication first. Only the exact object we published (identity equal
    to the proof, digest ``after``) is touched: the snapshot is rewritten in its
    place, or the file is removed when it did not exist before. Anything else is
    left untouched: the previous content (nothing to do), a third party's content
    (``foreign``, listed), or an object of ambiguous ownership (``ambiguous``,
    reported as a conflict so the state stays recoverable, never a false success).
    ``completed`` (in-process) lists the indices whose publication returned;
    ``all_published`` is the revert of a committed journal.
    """
    rolled_back, conflicts, errors, foreign = [], [], [], []
    for item in reversed(journal["items"]):
        label = {"type": item["type"], "member": item["member"], "target": item["target"]}
        if all_published:
            known = True
        elif completed is not None:
            known = item["index"] in completed
        else:
            known = None
        try:
            state, proof = item_state(txdir, item, published=known)
            if state == "original":
                if proof is not None:
                    remove_orphan_temporary(item["target"], proof)   # crash between proof and publication
                continue
            if state == "foreign":
                foreign.append(dict(label, state=state))
                continue
            if state != "published":
                conflicts.append(dict(label, state=state))
                continue
            target = Path(item["target"])
            if item["before"] is None:
                # Our created object: checked again immediately before removal.
                # Our created object: digest and identity checked again immediately before removal.
                if file_digest(target) != item["after"] or not _unlink_owned(target, proof):
                    conflicts.append(dict(label, state="conflict"))
                    continue
                fsync_dir(target.parent)
                remove_orphan_temporary(target, proof)        # our object under its staged name after a crash
            else:
                data = (txdir / item["snapshot"]).read_bytes()
                if hashlib.sha256(data).hexdigest() != item["before"]:
                    errors.append(dict(label, error="snapshot_corrupt"))
                    continue
                try:
                    publish_replace(target, data, expected={"identity": proof, "digest": item["after"]})
                except StagingConflict as exc:
                    # Our temporary's name was taken while staging the snapshot: the target is untouched (still
                    # ours, retried later) and the third party's object is recorded, never removed.
                    record_residue(journal, exc.residue)
                    conflicts.append(dict(label, state="conflict"))
                    continue
                except ConcurrentChange:
                    conflicts.append(dict(label, state="conflict"))
                    continue
            rolled_back.append(label)
        except OSError as exc:
            errors.append(dict(label, error=str(exc)))
    # Every unresolved leftover, including one born in this very rollback or in an explicit revert.
    conflicts += residue_conflicts(journal)
    return {"rolled_back": rolled_back, "conflicts": conflicts, "errors": errors, "foreign": foreign,
            "complete": not conflicts and not errors}


def finish_rollback(txdir: Path, journal: dict, outcome: dict, *, success_phase: str = "rolled_back") -> None:
    """Record the outcome; a complete rollback removes the transaction folder and pointer."""
    pointer = journal.get("config_pointer")
    if outcome["complete"]:
        journal["phase"] = success_phase
        try:
            write_journal(txdir, journal)
        except OSError:
            pass
        remove_pointer(pointer, txdir)
        _remove_tree(txdir)
    else:
        if journal["phase"] != "reverting":
            journal["phase"] = "rollback_incomplete"
        journal["last_recovery"] = {"utc": now_utc(), "conflicts": outcome["conflicts"], "errors": outcome["errors"]}
        write_journal(txdir, journal)


def prune_kept(home: str | os.PathLike, keep: int = KEEP_SNAPSHOTS) -> None:
    """Keep only the newest ``keep`` committed/dismissed snapshots (our private folders only)."""
    for described in committed_restores(home)[keep:]:
        _remove_tree(Path(described["dir"]))


# ── Recovery entry points ─────────────────────────────────────────────────
@dataclass
class RecoveryResult:
    """``state``: ``nothing``, ``cleaned``, ``recovered``, ``recoverable`` or ``busy``.

    ``code``/``template``/``values`` give the translatable summary; ``rolled_back``
    and ``conflicts`` list items (type, member, target); ``transactions`` the
    per-transaction outcome; ``kept_dir`` where journal/snapshots remain.
    """
    state: str
    code: str
    values: dict = field(default_factory=dict)
    rolled_back: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    transactions: list = field(default_factory=list)
    kept_dir: str | None = None

    @property
    def template(self) -> str:
        return MESSAGES[self.code]

    @property
    def message(self) -> str:
        return self.template.format(**self.values) if self.values else self.template

    @property
    def ok(self) -> bool:
        return self.state in ("nothing", "cleaned", "recovered")

    def as_status(self) -> dict:
        return {"state": self.state, "code": self.code, "template": self.template, "values": dict(self.values),
                "message": self.message, "rolled_back": list(self.rolled_back), "conflicts": list(self.conflicts),
                "errors": list(self.errors), "kept_dir": self.kept_dir}


def _homes_of(dirs: list[Path]) -> list[Path]:
    return list(dict.fromkeys(d.parent.parent for d in dirs))


def recover(home: str | os.PathLike | None = None, config: str | os.PathLike | None = None) -> RecoveryResult:
    """Roll back / clean any unfinished transaction; never reports success it did not achieve."""
    home = data_home() if home is None else home
    config = config_path() if config is None else config
    dirs = _transaction_dirs(home, config)
    if not _needs_recovery(dirs, config):
        return RecoveryResult("nothing", "recovery_nothing")
    rolled, conflicts, errors, outcomes, kept = [], [], [], [], None
    cleaned = False
    for each_home in _homes_of(dirs):          # never creates a data folder for a stale pointer
        try:
            lock = restore_lock(each_home)
            lock.__enter__()
        except BackupError as exc:
            if exc.code == "busy":
                return RecoveryResult("busy", "recovery_busy")
            raise
        try:
            candidates = _transaction_dirs(each_home, None) + [d for d in dirs if d.parent.parent == each_home]
            for txdir in dict.fromkeys(candidates):
                if not txdir.exists():
                    continue
                phase = _quick_phase(txdir)
                if phase == "staging":
                    _remove_tree(txdir)          # nothing was published before the journal existed
                    cleaned = True
                    continue
                if phase == "invalid":
                    errors.append({"dir": str(txdir), "error": _describe(txdir, states=False).get("error")})
                    kept = str(txdir)
                    continue
                journal = read_journal(txdir)
                if journal["phase"] in ("rolled_back", "reverted"):
                    _remove_tree(txdir)          # finished, interrupted during its own cleanup
                    cleaned = True
                    continue
                if journal["phase"] in KEPT_PHASES:
                    if (txdir / "new").exists():
                        shutil.rmtree(txdir / "new", ignore_errors=True)
                        cleaned = True
                    continue
                if journal["phase"] not in PENDING_PHASES:
                    continue
                reverting = journal["phase"] == "reverting"
                if not reverting:
                    journal["phase"] = "rolling_back"
                    write_journal(txdir, journal)
                outcome = rollback_items(txdir, journal, all_published=reverting)
                finish_rollback(txdir, journal, outcome, success_phase="reverted" if reverting else "rolled_back")
                outcomes.append({"txid": journal.get("txid"), "reverting": reverting, **outcome})
                rolled += outcome["rolled_back"]
                conflicts += outcome["conflicts"]
                errors += outcome["errors"]
                if not outcome["complete"]:
                    kept = str(txdir)
        finally:
            lock.__exit__(None, None, None)
    # A pointer whose transaction is gone or finished is stale.
    if config and pointer_path(config).exists():
        target = _read_pointer(pointer_path(config))
        if target is None or not Path(target).exists() or not _is_pending_phase(_quick_phase(Path(target))):
            remove_pointer(config)
            cleaned = True
    if conflicts or errors:
        return RecoveryResult("recoverable", "recovery_incomplete", {"v0": len(conflicts) + len(errors), "v1": kept or ""},
                              rolled, conflicts, errors, outcomes, kept)
    if outcomes:
        code = "recovery_reverted" if all(o["reverting"] for o in outcomes) else "recovery_done"
        return RecoveryResult("recovered", code, {"v0": len(rolled)}, rolled, [], [], outcomes)
    return RecoveryResult("cleaned" if cleaned else "nothing", "recovery_cleaned" if cleaned else "recovery_nothing")


def _needs_recovery(dirs: list[Path], config) -> bool:
    """Something to roll back or clean, decided from journal phases only (no hashing)."""
    for txdir in dirs:
        phase = _quick_phase(txdir)
        if _is_pending_phase(phase) or phase in ("rolled_back", "reverted") or \
                (phase in KEPT_PHASES and (txdir / "new").exists()):
            return True
    return bool(config) and pointer_path(config).exists()


def _find(home, txid: str) -> Path:
    txdir = tx_root(home) / (TX_PREFIX + str(txid))
    if not isinstance(txid, str) or os.sep in txid or "/" in txid or not txdir.is_dir():
        raise BackupError("not_found", v0=txid)
    return txdir


def _journal_of(txdir: Path) -> dict:
    try:
        return read_journal(txdir)
    except (OSError, ValueError) as exc:
        raise BackupError("journal_invalid", v0=str(exc), v1=str(txdir)) from exc


def revert_restore(home: str | os.PathLike, txid: str, config: str | os.PathLike | None = None) -> RecoveryResult:
    """Explicitly undo a committed restoration from its exact pre-restore snapshot.

    Only items still holding the restored content are reverted; a file changed
    since is a conflict and left untouched. The phase ``reverting`` is journaled
    first, so an interruption is finished by the next :func:`recover`.
    """
    with restore_lock(home):
        txdir = _find(home, txid)
        journal = _journal_of(txdir)
        if journal["phase"] not in ("committed", "dismissed"):
            raise BackupError("not_revertible", v0=journal["phase"])
        journal["phase"] = "reverting"
        write_journal(txdir, journal)
        if journal.get("config_pointer"):
            write_pointer(journal["config_pointer"], txdir)
        outcome = rollback_items(txdir, journal, all_published=True)
        finish_rollback(txdir, journal, outcome, success_phase="reverted")
    if not outcome["complete"]:
        return RecoveryResult("recoverable", "recovery_incomplete",
                              {"v0": len(outcome["conflicts"]) + len(outcome["errors"]), "v1": str(txdir)},
                              outcome["rolled_back"], outcome["conflicts"], outcome["errors"], [outcome], str(txdir))
    return RecoveryResult("recovered", "recovery_reverted", {"v0": len(outcome["rolled_back"])}, outcome["rolled_back"])


def dismiss_recovery(home: str | os.PathLike, txid: str) -> RecoveryResult:
    """Accept the current files of an incomplete rollback (conflicts); keep its snapshot for an explicit undo."""
    with restore_lock(home):
        txdir = _find(home, txid)
        journal = _journal_of(txdir)
        if journal["phase"] not in ("rollback_incomplete", "reverting"):
            raise BackupError("not_dismissable", v0=journal["phase"])
        journal["phase"] = "dismissed"
        if journal.get("residues"):
            journal["dismissed_residues"] = journal.pop("residues")
        write_journal(txdir, journal)
        remove_pointer(journal.get("config_pointer"), txdir)
        shutil.rmtree(txdir / "new", ignore_errors=True)
    return RecoveryResult("cleaned", "recovery_dismissed", {"v0": str(txdir / "snapshot")}, kept_dir=str(txdir))


def bootstrap(home: str | os.PathLike | None = None, config: str | os.PathLike | None = None) -> dict:
    """Resolve an interrupted restoration before the model is imported; never raises.

    Cheap when there is nothing to do (one directory listing and one ``stat``).
    Returns (and stores in :data:`STARTUP_STATUS`) a status dict whose
    ``state`` is ``clean`` (nothing to do), ``cleaned``, ``recovered``,
    ``recoverable`` (journal and snapshots kept, the GUI must say so),
    ``busy`` (another process is restoring) or ``error``.
    """
    global STARTUP_STATUS
    try:
        home = data_home() if home is None else home
        config = config_path() if config is None else config
        if not _needs_recovery(_transaction_dirs(home, config), config):
            status = {"state": "clean", "code": "recovery_nothing", "template": MESSAGES["recovery_nothing"],
                      "values": {}, "message": MESSAGES["recovery_nothing"]}
        else:
            result = recover(home, config)
            status = result.as_status()
            if status["state"] == "nothing":
                status["state"] = "clean"
    except Exception as exc:  # A startup check must not prevent launching; it reports instead.
        values = {"v0": str(exc)}
        status = {"state": "error", "code": "bootstrap_failed", "template": MESSAGES["bootstrap_failed"],
                  "values": values, "message": MESSAGES["bootstrap_failed"].format(**values)}
    STARTUP_STATUS = status
    return status
