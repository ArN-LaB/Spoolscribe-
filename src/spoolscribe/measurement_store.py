"""Local registry of colour measurements, separate from the catalogue.

One file (``colour_measurements.json`` next to the catalogue database by
default), validated by :mod:`colour_measurements`, written through the generic
revision-controlled storage of ``scripts.db_io``. Opening an absent registry
creates nothing; every operation is one atomic write with a backup.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts import db_io

from . import colour_measurements as cm


class RegistryError(cm.MeasurementError):
    """Registry operation refused; translatable like any MeasurementError."""


def default_path() -> Path:
    """Resolved when called, so test fixtures that patch ``core.DB_PATH`` are honoured."""
    from . import core
    return Path(core.DB_PATH).with_name("colour_measurements.json")


class MeasurementRegistry:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_path()
        self.document = cm.empty_registry()
        self.revision = None
        self.loaded = False
        self.load_error = None   # the error of the last failed load, while the file stays unusable

    # ── persistence ───────────────────────────────────────────────────────
    def load(self) -> dict:
        """Load and validate the registry; the size bound is checked before any read or parse.

        An unusable file (corrupt, unknown version, oversized) is reported, never
        reset: its revision is remembered so that an explicit :meth:`restore`
        can replace exactly the bytes that were seen, and nothing else.
        """
        try:
            document, revision = db_io.load_validated_json(self.path, cm.validate_registry, missing_ok=True,
                                                           max_bytes=cm.LIMITS["registry_bytes"])
        except db_io.DatabaseError as exc:
            self.document = cm.empty_registry()
            self.revision = getattr(exc, "revision", None)
            self.loaded = False
            self.load_error = exc
            raise
        self.document = document if document is not None else cm.empty_registry()
        self.revision = revision
        self.loaded = True
        self.load_error = None
        return self.document

    def exists(self) -> bool:
        return self.path.exists()

    def save(self) -> str:
        self.revision = db_io.save_validated_json(self.path, self.document, self.revision, cm.validate_registry,
                                                  max_bytes=cm.LIMITS["registry_bytes"])
        return self.revision

    def backup_path(self) -> Path:
        return Path(str(self.path) + ".bak")

    def restore(self, backup: str | Path | None = None) -> dict:
        """Explicit restoration from the chosen backup; the replaced file is kept, even invalid.

        Works after a failed :meth:`load` (the revision of the unusable file was
        captured then) and refuses any file that changed since, before and
        immediately before the replacement.
        """
        source = Path(backup) if backup is not None else self.backup_path()
        if not source.is_file():
            raise RegistryError("Aucune sauvegarde du registre à restaurer.")
        self.revision = db_io.restore_validated_json(self.path, source, cm.validate_registry, self.revision,
                                                     max_bytes=cm.LIMITS["registry_bytes"])
        return self.load()

    # ── queries ───────────────────────────────────────────────────────────
    @property
    def measurements(self) -> dict:
        return self.document["measurements"]

    def get(self, identifier: str) -> dict | None:
        return self.measurements.get(identifier)

    def items(self):
        return sorted(self.measurements.items(), key=lambda kv: (kv[1]["created_at"], kv[0]), reverse=True)

    def linked_to(self, sku: str) -> list[str]:
        return [key for key, m in self.measurements.items() if (m.get("association") or {}).get("sku") == sku]

    # ── mutations (each one write) ────────────────────────────────────────
    def _stage(self, mutate):
        """Apply ``mutate`` to a copy, validate and write; the in-memory state only changes on success."""
        if not self.loaded:
            self.load()
        candidate = copy.deepcopy(self.document)
        mutate(candidate["measurements"])
        if len(candidate["measurements"]) > cm.LIMITS["registry_count"]:
            raise RegistryError("Registre limité à {v0} mesures.", v0=cm.LIMITS['registry_count'])
        candidate = cm.validate_registry(candidate)
        previous = self.document
        self.document = candidate
        try:
            self.save()
        except Exception:
            self.document = previous
            raise
        return candidate

    def create(self, measurement: dict) -> str:
        return self.create_many([measurement])[0]

    def create_many(self, measurements: list[dict]) -> list[str]:
        """Add several validated measurements in one atomic write (none on failure)."""
        identifiers = []

        def mutate(store):
            for measurement in measurements:
                identifier = cm.new_id()
                while identifier in store:
                    identifier = cm.new_id()
                store[identifier] = cm.validate_measurement(measurement)
                identifiers.append(identifier)
        try:
            self._stage(mutate)
        except Exception:
            identifiers.clear()
            raise
        return identifiers

    def rename(self, identifier: str, name: str) -> None:
        def mutate(store):
            if identifier not in store:
                raise RegistryError("Mesure introuvable.")
            store[identifier]["name"] = name
        self._stage(mutate)

    def associate(self, identifier: str, sku: str) -> None:
        """Link to an exact variant SKU or USER identifier chosen by the user; values untouched."""
        if not isinstance(sku, str) or not sku.strip():
            raise RegistryError("Référence de filament requise.")

        def mutate(store):
            if identifier not in store:
                raise RegistryError("Mesure introuvable.")
            store[identifier]["association"] = {"sku": sku}
        self._stage(mutate)

    def detach(self, identifier: str) -> None:
        def mutate(store):
            if identifier not in store:
                raise RegistryError("Mesure introuvable.")
            store[identifier]["association"] = None
        self._stage(mutate)

    def set_role(self, identifier: str, role: str) -> None:
        def mutate(store):
            if identifier not in store:
                raise RegistryError("Mesure introuvable.")
            store[identifier]["role"] = role
        self._stage(mutate)

    def delete(self, identifier: str) -> None:
        """Remove one measurement (the previous registry bytes stay in the backup)."""
        def mutate(store):
            if identifier not in store:
                raise RegistryError("Mesure introuvable.")
            del store[identifier]
        self._stage(mutate)

    def replace_values(self, identifier: str, original: dict, conditions=None) -> str:
        """Changing numbers creates a new measurement; the old one stays available."""
        source = self.get(identifier)
        if source is None:
            raise RegistryError("Mesure introuvable.")
        fresh = copy.deepcopy(source)
        fresh["original"] = original
        if conditions is not None:
            fresh["conditions"] = conditions
        fresh["created_at"] = cm.now_utc()
        fresh.pop("content_digest", None)
        return self.create(fresh)

    def resolve_association(self, measurement: dict, db: dict) -> dict:
        """Context of a link: the real reference when the SKU exists, flagged otherwise.

        A missing SKU keeps the link and is reported ``unresolved``; it is never
        re-attributed to a filament with the same name or HEX.
        """
        association = measurement.get("association")
        if not association:
            return {"state": "none", "sku": None, "entry": None}
        sku = association["sku"]
        entry = (db.get("_skus") or {}).get(sku)
        if entry is None:
            return {"state": "unresolved", "sku": sku, "entry": None}
        product = (db.get("_products") or {}).get(entry.get("product"), {})
        return {"state": "resolved", "sku": sku, "entry": entry, "product": product,
                "label": f"{product.get('display_name') or entry.get('product', '')} · {entry.get('color_name', '')}".strip(" ·")}

    def serialized_size(self) -> int:
        return len(json.dumps(self.document, ensure_ascii=False, indent=2).encode("utf-8"))
