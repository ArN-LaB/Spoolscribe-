"""« Sauvegarder / Restaurer mes données » : dialogs over :mod:`backup` (which holds every rule).

The engine validates, journals and rolls back; this module only asks, previews and
reports. Restoration is refused while an update worker runs or a draft is open, a
preview always precedes it, and success never hides a recoverable state.
"""
from __future__ import annotations

import datetime as _dt
import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QLabel,
                               QMessageBox, QVBoxLayout)

from . import backup, core
from .i18n import tr
from .ui_surfaces import fit_dialog
from .ui_widgets import WrapLabel

STATE_LABELS = {"included": "inclus", "absent": "absent", "excluded": "non inclus", "invalid": "invalide"}
SETTINGS_CATEGORY_LABELS = {"catalogue": "Catalogue", "filaments": "Filaments", "labels": "Étiquettes et export",
                            "colours": "Couleurs", "interface": "Interface", "layout": "Disposition et filtres",
                            "export_path": "Dossier d’export"}
_SHOWN_UNKNOWN = 5


# ── Text helpers ───────────────────────────────────────────────────────────
def error_text(exc) -> str:
    """Translated text of a :class:`backup.BackupError` (values translated recursively) or a validator error."""
    template = getattr(exc, "template", None)
    if template:
        values = {k: (error_text(v) if isinstance(v, BaseException) else v)
                  for k, v in (getattr(exc, "values", None) or {}).items()}
        return tr(template, **values)
    return tr(str(exc))


def _category(name) -> str:
    return tr(backup.CATEGORY_LABELS.get(name, name))


def _settings_categories(names) -> str:
    return ", ".join(tr(SETTINGS_CATEGORY_LABELS.get(n, n)) for n in names) or tr("aucune")


def _size(value: int) -> str:
    for unit, factor in (("Mio", 1024 * 1024), ("Kio", 1024)):
        if value >= factor:
            return f"{value / factor:.1f}".rstrip("0").rstrip(".") + " " + tr(unit)
    return tr("{v0} octets", v0=value)


def _busy(window) -> bool:
    return bool(window.worker and window.worker.isRunning()) or bool(
        getattr(window, "_release_worker", None) and window._release_worker.isRunning())


def _refuse_if_busy(window, title) -> bool:
    if _busy(window):
        QMessageBox.information(window, title, tr("Une actualisation est en cours. Réessayez après sa fin."))
        return True
    return False


def _wait(function, *args, **kwargs):
    QApplication.setOverrideCursor(Qt.WaitCursor)
    try:
        return function(*args, **kwargs)
    finally:
        QApplication.restoreOverrideCursor()


def _buttons(dlg, ok_text, *, enabled=True):
    bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.button(QDialogButtonBox.Ok).setText(ok_text)
    bb.button(QDialogButtonBox.Ok).setEnabled(enabled)
    bb.button(QDialogButtonBox.Cancel).setText(tr("Annuler"))
    bb.accepted.connect(dlg.accept)
    bb.rejected.connect(dlg.reject)
    return bb


def _counts_text(counts: dict) -> str:
    return tr("{v0} références, dont {v1} copies personnelles ; {v2} mesures de couleur ({v3} liées) ; "
              "{v4} réglages d’appareil ; {v5} profils Orca.",
              v0=counts.get("skus", 0), v1=counts.get("personal", 0), v2=counts.get("measurements", 0),
              v3=counts.get("linked", 0), v4=counts.get("presets", 0), v5=counts.get("orca_profiles", 0))


# ── Create ─────────────────────────────────────────────────────────────────
def plan_text(plan) -> list:
    """Lines of the inventory preview (pure: used by the dialog and tests)."""
    lines = [_counts_text(plan.counts)]
    for name in backup.CATEGORY_LABELS:
        info = plan.categories.get(name)
        if not info:
            continue
        reason = tr(backup.REASON_LABELS[info["reason"]]) if info.get("reason") else ""
        lines.append(tr("{v0} : {v1}", v0=_category(name), v1=tr(STATE_LABELS.get(info["state"], info["state"])))
                     + (tr(" — {v0}", v0=reason) if reason else ""))
    if plan.unknown:
        shown = ", ".join(plan.unknown[:_SHOWN_UNKNOWN]) + (" …" if len(plan.unknown) > _SHOWN_UNKNOWN else "")
        lines.append(tr("Fichiers non reconnus, ni inclus ni supprimés ({v0}) : {v1}", v0=len(plan.unknown), v1=shown))
    for error in plan.blocking:
        lines.append(error_text(error))
    lines.append(tr("Total : {v0} fichiers, {v1}.", v0=plan.member_count, v1=_size(plan.total_bytes)))
    return lines


def _ask_backup_options(window):
    """Options and inventory preview; returns :class:`backup.Options` or None."""
    dlg = QDialog(window)
    dlg.setWindowTitle(tr("Sauvegarder mes données"))
    lay = QVBoxLayout(dlg)
    lay.setSpacing(10)
    lay.addWidget(WrapLabel(tr("Archive ZIP non chiffrée de vos données locales. Seuls les éléments ci-dessous sont "
                               "inclus ; ce n’est pas une copie de tout le disque.")))
    config = QCheckBox(tr("Inclure les préférences (dont les réglages OpenTag3D par référence)"))
    config.setObjectName("includeConfig")
    config.setChecked(True)
    layout = QCheckBox(tr("Inclure la disposition et les filtres"))
    layout.setObjectName("includeLayout")
    folder = QCheckBox(tr("Inclure le chemin du dossier d’export"))
    folder.setObjectName("includeExportPath")
    folder.setToolTip(tr("Chemin absolu de cet ordinateur ; il peut révéler un nom de dossier personnel."))
    exports = QCheckBox(tr("Inclure les exports générés (dossier output du dossier de données)"))
    exports.setObjectName("includeExports")
    for box in (config, layout, folder, exports):
        lay.addWidget(box)
    preview = WrapLabel("")
    preview.setObjectName("backupInventory")
    preview.setTextFormat(Qt.PlainText)
    lay.addWidget(preview)
    lay.addWidget(WrapLabel(tr("Sauvegarde chiffrée : non disponible dans cette version. Conservez l’archive dans un "
                               "emplacement protégé.")))
    bb = _buttons(dlg, tr("Enregistrer…"))
    lay.addWidget(bb)
    state = {}

    def options():
        layout.setEnabled(config.isChecked())
        folder.setEnabled(config.isChecked())
        return backup.Options(include_config=config.isChecked(),
                              include_layout=config.isChecked() and layout.isChecked(),
                              include_export_path=config.isChecked() and folder.isChecked(),
                              include_exports=exports.isChecked())

    def refresh(*_):
        state["options"] = options()
        try:
            plan = backup.plan_backup(backup.Paths.current(), state["options"])
        except (backup.BackupError, OSError, ValueError) as exc:
            preview.setText(error_text(exc))
            bb.button(QDialogButtonBox.Ok).setEnabled(False)
            return
        preview.setText("\n".join(plan_text(plan)))
        bb.button(QDialogButtonBox.Ok).setEnabled(plan.ok)

    for box in (config, layout, folder, exports):
        box.toggled.connect(refresh)
    refresh()
    fit_dialog(dlg, preferred_width=620)
    if dlg.exec() != QDialog.Accepted:
        return None
    return state["options"]


def create_backup(window):
    title = tr("Sauvegarder mes données")
    if _refuse_if_busy(window, title) or not window._confirm_draft_transition():
        return
    window._save_ui_preferences()
    options = _ask_backup_options(window)
    if options is None:
        return
    name = "SpoolScribe-sauvegarde-" + _dt.date.today().strftime("%Y%m%d") + ".zip"
    path, _ = QFileDialog.getSaveFileName(window, title, name, tr("Sauvegarde SpoolScribe (*.zip)"))
    if not path:
        return
    if not path.lower().endswith(".zip"):
        path += ".zip"
    if _refuse_if_busy(window, title):
        return
    try:
        # The save dialog has asked to confirm replacing an existing file: that is the explicit choice.
        manifest = _wait(backup.create_backup, path, backup.Paths.current(), options,
                         overwrite=os.path.exists(path))
    except (backup.BackupError, OSError) as exc:
        QMessageBox.warning(window, title, error_text(exc))
        return
    window.status.showMessage(tr("Sauvegarde créée : {v0} fichiers. Archive non chiffrée.",
                                 v0=len(manifest.get("entries", []))), 8000)


# ── Restore ────────────────────────────────────────────────────────────────
def analysis_text(analysis) -> list:
    """Lines of the restoration preview (pure: used by the dialog and tests)."""
    lines = [tr("Sauvegarde du {v0}, SpoolScribe {v1}.", v0=analysis.created_utc, v1=analysis.app_version),
             _counts_text(analysis.counts)]
    for label, entries in ((tr("Remplacés"), analysis.replaced), (tr("Créés"), analysis.created),
                           (tr("Inchangés"), analysis.unchanged)):
        if entries:
            names = sorted({_category(e["type"]) for e in entries})
            lines.append(tr("{v0} : {v1}", v0=label, v1=", ".join(names)))
    if analysis.absent:
        lines.append(tr("Absents de la sauvegarde, vos fichiers actuels sont conservés : {v0}",
                        v0=", ".join(_category(t) for t in analysis.absent)))
    kept = sorted({_category(k["type"]) for k in analysis.kept})
    if kept:
        lines.append(tr("Conservés tels quels sur cet ordinateur : {v0}", v0=", ".join(kept)))
    if analysis.ignored:
        lines.append(tr("Non contenus dans la sauvegarde : {v0}",
                        v0=", ".join(_category(i["category"]) for i in analysis.ignored)))
    config = analysis.config
    if config:
        lines.append(tr("Préférences remplacées : {v0}. Conservées : {v1}.",
                        v0=_settings_categories(config["replaced_categories"]),
                        v1=_settings_categories(config["kept_categories"])))
        lines.append(tr("Réglages OpenTag3D par référence : {v0}.", v0=config.get("opentag3d", 0)))
        if config.get("export_directory"):
            lines.append(tr("Dossier d’export de la sauvegarde : {v0}", v0=config["export_directory"]))
        lines.append(tr("Autorisation réseau, dates et état des actualisations de cet ordinateur : conservés."))
        if config.get("sources_change"):
            lines.append(tr("Les sources du catalogue changent : l’autorisation réseau vous sera redemandée avant "
                            "toute actualisation."))
    lines.append(tr("Avant tout remplacement, une copie exacte de vos fichiers actuels est conservée sur cet "
                    "ordinateur ; vous pourrez annuler cette restauration."))
    return lines


def _confirm_restore(window, analysis) -> bool:
    dlg = QDialog(window)
    dlg.setWindowTitle(tr("Restaurer mes données"))
    lay = QVBoxLayout(dlg)
    lay.setSpacing(10)
    text = WrapLabel("\n".join(analysis_text(analysis)))
    text.setObjectName("restorePreview")
    text.setTextFormat(Qt.PlainText)
    lay.addWidget(text)
    lay.addWidget(_buttons(dlg, tr("Restaurer"), enabled=bool(analysis.replaced or analysis.created)))
    fit_dialog(dlg, preferred_width=640)
    return dlg.exec() == QDialog.Accepted


def _offer_restart(window, title, text):
    box = QMessageBox(window)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Information)
    box.setText(text)
    box.setInformativeText(tr("Redémarrez SpoolScribe pour recharger toutes les vues et préférences."))
    now = box.addButton(tr("Redémarrer maintenant"), QMessageBox.AcceptRole)
    later = box.addButton(tr("Plus tard"), QMessageBox.RejectRole)
    now.setEnabled(not window._restart_busy())
    box.setDefaultButton(now if now.isEnabled() else later)
    box.setEscapeButton(later)
    box.exec()
    if box.clickedButton() is now and now.isEnabled():
        window._request_language_restart()


def reload_after_restore(window, *, layout_restored: bool) -> None:
    """Coordinated reload: catalogue, printer list and views read the restored files.

    When the layout was restored, the window stops saving its own (older) layout,
    so the restored one is applied at the next start instead of being overwritten.
    """
    if layout_restored:
        window._skip_ui_save = True
    from . import printer_profiles
    printer_profiles.reload()
    try:
        window.db = core.load_db()
    except (core.DatabaseError, OSError) as exc:
        QMessageBox.critical(window, tr("Base illisible"), str(exc))
        return
    window._chosen_variant = None
    window._reload_table()
    window._refresh_logo()
    window._update_stats()
    window._show_empty()
    window._refresh_nfc_capacity()
    window._refresh_colour_limit_label()
    if hasattr(window, "inspector"):
        window.inspector.clear()


def _pending(window):
    try:
        return backup.pending_recovery(core.DATA_HOME, core.CONFIG_PATH)
    except (backup.BackupError, OSError) as exc:
        QMessageBox.warning(window, tr("Restaurer mes données"), error_text(exc))
        return False


def resolve_pending(window, pending) -> None:
    """An unfinished restoration blocks new operations: retry the rollback, or keep the current state."""
    title = tr("Restauration inachevée")
    box = QMessageBox(window)
    box.setWindowTitle(title)
    box.setIcon(QMessageBox.Warning)
    box.setText(tr("Une restauration précédente est inachevée ; sa reprise doit être terminée avant toute nouvelle "
                   "opération."))
    if pending.get("conflicts"):
        box.setInformativeText(tr("{v0} fichier(s) ont été modifiés depuis par un autre programme ; ils ne sont pas "
                                  "touchés. Journal et instantanés conservés dans {v1}.",
                                  v0=len(pending["conflicts"]), v1=pending.get("dir", "")))
    retry = box.addButton(tr("Réessayer le retour arrière"), QMessageBox.AcceptRole)
    keep = box.addButton(tr("Conserver l’état actuel"), QMessageBox.DestructiveRole) if pending.get("conflicts") else None
    box.addButton(tr("Annuler"), QMessageBox.RejectRole)
    box.exec()
    try:
        if box.clickedButton() is retry:
            result = _wait(backup.recover, core.DATA_HOME, core.CONFIG_PATH)
        elif keep is not None and box.clickedButton() is keep:
            result = backup.dismiss_recovery(core.DATA_HOME, pending["txid"])
        else:
            return
    except (backup.BackupError, OSError) as exc:
        QMessageBox.warning(window, title, error_text(exc))
        return
    _report_recovery(window, title, result)


def _report_recovery(window, title, result) -> None:
    text = tr(result.template, **result.values)
    if result.ok:
        if result.rolled_back:
            reload_after_restore(window, layout_restored=False)
            _offer_restart(window, title, text)
        else:
            QMessageBox.information(window, title, text)
    else:
        QMessageBox.critical(window, title, text)


def restore_backup(window):
    title = tr("Restaurer mes données")
    if _refuse_if_busy(window, title) or not window._confirm_draft_transition():
        return
    pending = _pending(window)
    if pending is False:
        return
    if pending:
        resolve_pending(window, pending)
        return
    # Write the current layout now: a write after the preview would (rightly) invalidate it.
    window._save_ui_preferences()
    path, _ = QFileDialog.getOpenFileName(window, title, "", tr("Sauvegarde SpoolScribe (*.zip)"))
    if not path:
        return
    try:
        analysis = _wait(backup.analyze_backup, path, backup.Paths.current())
    except (backup.BackupError, OSError) as exc:
        QMessageBox.warning(window, title, error_text(exc))
        return
    if not (analysis.replaced or analysis.created):
        QMessageBox.information(window, title, tr("Vos données sont déjà identiques à cette sauvegarde ; rien à restaurer."))
        return
    if not _confirm_restore(window, analysis):
        return
    # The worker may have started and a draft may have opened while the preview was shown.
    if _refuse_if_busy(window, title) or not window._confirm_draft_transition():
        return
    try:
        result = _wait(backup.restore_backup, analysis, backup.Paths.current())
    except backup.BackupError as exc:
        if exc.code == "restore_recoverable":
            QMessageBox.critical(window, title, error_text(exc))
        else:
            QMessageBox.warning(window, title, error_text(exc))
        return
    except OSError as exc:
        QMessageBox.warning(window, title, error_text(exc))
        return
    reload_after_restore(window, layout_restored=bool(analysis.options.get("include_layout")))
    text = tr("Restauration terminée : {v0} fichier(s) remplacé(s) ou créé(s), {v1} inchangé(s). Vous pouvez "
              "l’annuler depuis Paramètres › Données et sauvegardes.",
              v0=len(result.published), v1=len(result.unchanged))
    if result.sources_changed:
        text += "\n" + tr("Les sources du catalogue ont changé : l’autorisation réseau vous sera redemandée avant "
                          "toute actualisation.")
    _offer_restart(window, title, text)


# ── Explicit rollback of a finished restoration ──────────────────────────
def last_restore():
    try:
        done = backup.committed_restores(core.DATA_HOME)
    except (backup.BackupError, OSError):
        return None
    return done[0] if done else None


def revert_last_restore(window):
    title = tr("Annuler la dernière restauration")
    if _refuse_if_busy(window, title) or not window._confirm_draft_transition():
        return
    pending = _pending(window)
    if pending is False:
        return
    if pending:
        resolve_pending(window, pending)
        return
    last = last_restore()
    if last is None:
        QMessageBox.information(window, title, tr("Aucune restauration à annuler."))
        return
    answer = QMessageBox.question(
        window, title,
        tr("Rétablir vos fichiers dans leur état d’avant la restauration du {v0} ? Un fichier modifié depuis n’est "
           "pas touché.", v0=last.get("created_utc") or last.get("txid")),
        QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    if answer != QMessageBox.Yes:
        return
    try:
        result = _wait(backup.revert_restore, core.DATA_HOME, last["txid"], core.CONFIG_PATH)
    except (backup.BackupError, OSError) as exc:
        QMessageBox.warning(window, title, error_text(exc))
        return
    window._skip_ui_save = True   # the restored-over layout file is authoritative again
    _report_recovery(window, title, result)


# ── Startup ────────────────────────────────────────────────────────────────
def show_startup_recovery(window, status=None) -> None:
    """Report what :func:`recovery.bootstrap` did before the model was loaded; silent when nothing happened."""
    from . import recovery
    status = recovery.STARTUP_STATUS if status is None else status
    if not status or status.get("state") in (None, "clean"):
        return
    template = status.get("template")
    text = tr(template, **(status.get("values") or {})) if template else tr(status.get("message", ""))
    state = status["state"]
    if state == "cleaned":
        window.status.showMessage(text, 8000)
    elif state == "recovered":
        QMessageBox.information(window, tr("Restauration interrompue"), text)
    else:  # recoverable, busy, error: never presented as a success
        QMessageBox.warning(window, tr("Restauration inachevée"), text)
