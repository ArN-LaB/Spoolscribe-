#!/usr/bin/env python3
"""
app_gui.py — Application graphique multiplateforme (Windows / macOS / Linux).

Construite sur PySide6 (Qt). Toute la logique métier vient de core.py :
cette couche ne fait que de l'affichage et de l'orchestration UI.

Lancement :  python app_gui.py
"""
from __future__ import annotations

import json
import os
import sys
import traceback

from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QColor, QFont, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLineEdit, QTableWidget, QTableWidgetItem, QLabel, QPushButton, QPlainTextEdit,
    QHeaderView, QAbstractItemView, QFrame, QMessageBox, QProgressBar, QGridLayout,
    QSizePolicy,
)

try:
    from PySide6.QtSvgWidgets import QSvgWidget
    HAS_SVG = True
except Exception:
    HAS_SVG = False

import core


# ─── Thread de mise à jour DB ─────────────────────────────────────────────
class UpdateWorker(QThread):
    """Exécute la pipeline de scrapers sans bloquer l'UI."""
    progress = Signal(str, int, int)   # label, index, total
    finished_ok = Signal(list)         # list[core.StepResult]
    failed = Signal(str)

    def run(self):
        try:
            results = core.run_update_pipeline(
                progress=lambda label, i, total: self.progress.emit(label, i, total),
                consent=core.has_network_consent(),
            )
            self.finished_ok.emit(results)
        except Exception:
            self.failed.emit(traceback.format_exc())


# ─── Pastille couleur ─────────────────────────────────────────────────────
def make_swatch_pixmap(hex_code: str | None, size: int = 18) -> QPixmap:
    pm = QPixmap(size, size)
    h = (hex_code or "").strip().lstrip("#")
    if len(h) == 6:
        color = QColor(f"#{h}")
    else:
        color = QColor("#dddddd")
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(color)
    p.setPen(QColor("#888888"))
    p.drawRoundedRect(0, 0, size - 1, size - 1, 4, 4)
    p.end()
    return pm


# ─── Fenêtre principale ───────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"SpoolScribe {core.APP_VERSION} — OpenSpool / NFC")
        self.resize(1040, 680)

        self.db = core.load_db()
        self.current_sku: str | None = None
        self.worker: UpdateWorker | None = None

        self._build_ui()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()

    # ── Construction UI ──────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Barre du haut : stats + recherche + bouton update
        top = QHBoxLayout()
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color:#444; font-size:12px;")
        top.addWidget(self.stats_label)
        top.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher : SKU, produit, couleur…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(self._apply_filter)
        top.addWidget(self.search)

        self.update_btn = QPushButton("Mettre à jour la DB")
        self.update_btn.clicked.connect(self._start_update)
        top.addWidget(self.update_btn)
        root.addLayout(top)

        # Barre de progression (cachée par défaut)
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setTextVisible(True)
        root.addWidget(self.progress)

        # Splitter : table à gauche, détail à droite
        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter, 1)

        # Table SKU
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "SKU", "Produit", "Couleur"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 28)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_select)
        splitter.addWidget(self.table)

        # Panneau détail
        detail = QWidget()
        dl = QVBoxLayout(detail)
        dl.setContentsMargins(12, 4, 6, 6)
        dl.setSpacing(8)

        # Logo SVG
        logo_row = QHBoxLayout()
        if HAS_SVG:
            self.logo = QSvgWidget()
            self.logo.setFixedSize(120, 120)
        else:
            self.logo = QLabel("(SVG non supporté)")
            self.logo.setFixedSize(120, 120)
        logo_row.addWidget(self.logo)
        logo_row.addStretch(1)
        dl.addLayout(logo_row)

        # Titre fiche
        self.title = QLabel("Sélectionnez un filament")
        f = QFont()
        f.setPointSize(15)
        f.setBold(True)
        self.title.setFont(f)
        self.title.setWordWrap(True)
        dl.addWidget(self.title)

        # Grille des champs
        self.fields = QGridLayout()
        self.fields.setVerticalSpacing(4)
        self.fields.setHorizontalSpacing(10)
        dl.addLayout(self.fields)

        self._field_widgets: dict[str, QLabel] = {}
        labels = ["Produit", "Couleur", "HEX", "Type", "Nozzle", "Bed", "Densité", "Marque"]
        for i, name in enumerate(labels):
            lab = QLabel(name)
            lab.setStyleSheet("color:#666;")
            val = QLabel("—")
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.fields.addWidget(lab, i, 0, Qt.AlignTop)
            self.fields.addWidget(val, i, 1)
            self._field_widgets[name] = val

        # Swatch couleur (gros carré)
        self.swatch = QLabel()
        self.swatch.setFixedHeight(28)
        self.swatch.setStyleSheet("border:1px solid #999; border-radius:4px; background:#eee;")
        dl.addWidget(self.swatch)

        # Boutons d'action
        btns = QHBoxLayout()
        self.btn_generate = QPushButton("Générer NFC JSON")
        self.btn_generate.clicked.connect(self._generate)
        self.btn_generate.setEnabled(False)
        self.btn_inspect = QPushButton("Inspecter JSON")
        self.btn_inspect.clicked.connect(self._toggle_inspect)
        self.btn_inspect.setEnabled(False)
        self.btn_open_out = QPushButton("Ouvrir dossier export")
        self.btn_open_out.clicked.connect(self._open_output)
        btns.addWidget(self.btn_generate)
        btns.addWidget(self.btn_inspect)
        btns.addWidget(self.btn_open_out)
        btns.addStretch(1)
        dl.addLayout(btns)

        # Zone d'inspection JSON
        self.inspector = QPlainTextEdit()
        self.inspector.setReadOnly(True)
        self.inspector.setVisible(False)
        self.inspector.setFont(QFont("Consolas" if os.name == "nt" else "monospace", 9))
        dl.addWidget(self.inspector, 1)

        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([560, 460])

        self.status = self.statusBar()
        self.status.showMessage("Prêt.")

    # ── Données / table ──────────────────────────────────────────────────
    def _reload_table(self):
        self._all_rows = core.list_skus(self.db)
        self._populate(self._all_rows)

    def _populate(self, rows):
        self.table.setRowCount(0)
        self.table.setRowCount(len(rows))
        for r, e in enumerate(rows):
            sw = QTableWidgetItem()
            sw.setIcon(QIcon(make_swatch_pixmap(e.get("hex"))))
            self.table.setItem(r, 0, sw)
            self.table.setItem(r, 1, QTableWidgetItem(e["sku"]))
            self.table.setItem(r, 2, QTableWidgetItem(e["product"]))
            color_item = QTableWidgetItem(e["color_name"])
            if not e.get("hex"):
                color_item.setForeground(QColor("#b00"))
            self.table.setItem(r, 3, color_item)

    def _apply_filter(self, text):
        t = text.strip().lower()
        if not t:
            self._populate(self._all_rows)
            return
        filtered = [
            e for e in self._all_rows
            if t in e["sku"].lower() or t in e["product"].lower() or t in e["color_name"].lower()
        ]
        self._populate(filtered)

    def _update_stats(self):
        st = core.db_stats(self.db)
        age = core.db_age_days(self.db)
        age_str = f"{age:.0f} j" if age is not None else "?"
        self.stats_label.setText(
            f"SKUs: {st['skus']}    Produits: {st['products']}    "
            f"HEX manquants: {st['missing_hex']}    DB: {age_str}"
        )

    def _refresh_logo(self):
        abs_path = core.logo_abs_path(self.db)
        if HAS_SVG and abs_path and os.path.exists(abs_path):
            try:
                self.logo.load(abs_path)
                return
            except Exception:
                pass
        if not HAS_SVG:
            self.logo.setText("(SVG non dispo)")

    # ── Sélection ────────────────────────────────────────────────────────
    def _on_select(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        sku_item = self.table.item(row, 1)
        if not sku_item:
            return
        self.current_sku = sku_item.text()
        self._show_detail(self.current_sku)

    def _show_detail(self, sku):
        view = core.get_sku_view(self.db, sku)
        if view is None:
            self.title.setText(f"{sku} — produit introuvable")
            for v in self._field_widgets.values():
                v.setText("—")
            self.btn_generate.setEnabled(False)
            self.btn_inspect.setEnabled(False)
            return

        self.title.setText(f"{view.sku} · {view.color_name}")
        self._field_widgets["Produit"].setText(view.product)
        self._field_widgets["Couleur"].setText(view.color_name)
        self._field_widgets["HEX"].setText(f"#{view.hex}" if view.hex else "(inconnu → 000000)")
        self._field_widgets["Type"].setText(view.type_str)
        self._field_widgets["Nozzle"].setText(view.nozzle_str)
        self._field_widgets["Bed"].setText(view.bed_str)
        self._field_widgets["Densité"].setText(view.density_str)
        self._field_widgets["Marque"].setText(view.product_data.get("brand", "Polymaker"))

        h = view.hex or "000000"
        self.swatch.setStyleSheet(
            f"border:1px solid #999; border-radius:4px; background:#{h};"
        )

        self.btn_generate.setEnabled(True)
        self.btn_inspect.setEnabled(True)
        if self.inspector.isVisible():
            self._refresh_inspector()

    def _build_payload(self):
        view = core.get_sku_view(self.db, self.current_sku)
        if view is None:
            return None
        entry = dict(self.db["_skus"][self.current_sku])
        entry["sku"] = self.current_sku
        return core.build_openspool(entry, view.product_data, brand_meta=view.brand_meta)

    # ── Actions ──────────────────────────────────────────────────────────
    def _generate(self):
        if not self.current_sku:
            return
        try:
            view = core.get_sku_view(self.db, self.current_sku)
            entry = self.db["_skus"][self.current_sku]
            out = core.write_openspool(self.current_sku, entry, view.product_data,
                                       brand_meta=view.brand_meta)
            self.status.showMessage(f"Généré : {out}", 8000)
            QMessageBox.information(self, "Export OpenSpool",
                                    f"Fichier généré :\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Échec de l'export :\n{e}")

    def _toggle_inspect(self):
        if self.inspector.isVisible():
            self.inspector.setVisible(False)
            self.btn_inspect.setText("Inspecter JSON")
        else:
            self._refresh_inspector()
            self.inspector.setVisible(True)
            self.btn_inspect.setText("Masquer JSON")

    def _refresh_inspector(self):
        payload = self._build_payload()
        if payload is not None:
            self.inspector.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))

    def _open_output(self):
        out_dir = core.OUTPUT_DIR
        os.makedirs(out_dir, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(out_dir)  # noqa
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", out_dir])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", out_dir])
        except Exception as e:
            QMessageBox.warning(self, "Ouverture", f"Impossible d'ouvrir le dossier :\n{e}")

    # ── Mise à jour DB ───────────────────────────────────────────────────
    def _ask_network_consent(self) -> bool:
        """Affiche les sources et demande le consentement réseau explicite."""
        if core.has_network_consent():
            return True
        sources = "\n".join(
            f"  • {s['name']}  [{s['license']}]\n      {s['host']}"
            for s in core.NETWORK_SOURCES
        )
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle("Mise à jour des données — accès réseau")
        box.setText(
            "Cette action va télécharger des données depuis Internet.\n"
            "Aucune donnée personnelle n'est envoyée.\n\n"
            "Sources contactées :"
        )
        box.setDetailedText(sources)
        box.setInformativeText("Autoriser les mises à jour réseau ?")
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        consent = box.exec() == QMessageBox.Yes
        core.set_network_consent(consent)
        return consent

    def _start_update(self):
        if self.worker and self.worker.isRunning():
            return
        if not self._ask_network_consent():
            self.status.showMessage("Mise à jour annulée (réseau refusé).", 6000)
            return
        self.update_btn.setEnabled(False)
        self.progress.setVisible(True)
        self.progress.setRange(0, len(core.UPDATE_PIPELINE))
        self.progress.setValue(0)
        self.status.showMessage("Mise à jour en cours…")

        self.worker = UpdateWorker()
        self.worker.progress.connect(self._on_update_progress)
        self.worker.finished_ok.connect(self._on_update_done)
        self.worker.failed.connect(self._on_update_failed)
        self.worker.start()

    def _on_update_progress(self, label, i, total):
        self.progress.setValue(i)
        self.progress.setFormat(f"{i}/{total} — {label}")

    def _on_update_done(self, results):
        self.progress.setVisible(False)
        self.update_btn.setEnabled(True)
        self.db = core.load_db()
        self._reload_table()
        self._refresh_logo()
        self._update_stats()
        if self.current_sku:
            self._show_detail(self.current_sku)
        n_ok = sum(1 for r in results if r.ok)
        n_ko = [r for r in results if not r.ok]
        msg = f"Mise à jour terminée — {n_ok}/{len(results)} étapes OK."
        self.status.showMessage(msg, 10000)
        if n_ko:
            detail = "\n".join(f"• {r.label} (code {r.code})" for r in n_ko)
            QMessageBox.warning(self, "Mise à jour partielle",
                                f"{msg}\n\nÉtapes en échec :\n{detail}")

    def _on_update_failed(self, tb):
        self.progress.setVisible(False)
        self.update_btn.setEnabled(True)
        QMessageBox.critical(self, "Erreur de mise à jour", tb)


def main():
    # Mode worker (exécutable gelé relançant un scraper) : agir puis sortir.
    if core.maybe_run_as_script_worker(sys.argv):
        return
    app = QApplication(sys.argv)
    app.setApplicationName("SpoolScribe")
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
