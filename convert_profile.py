#!/usr/bin/env python3
"""
convert_profile.py — Interface CLI (affichage terminal).

Toute la logique métier vit dans core.py. Ce fichier ne contient que
l'UI terminal (prompts, panneaux ANSI, boucle interactive).
"""
import argparse
import json
import os
import re
import sys

from pathlib import Path
import core
from core import (
    DB_PATH, OUTPUT_DIR,
    load_db, validate_hex,
    build_openspool, write_openspool as core_write_openspool,
    get_sku_view, list_skus, add_sku, set_sku_hex,
    logo_abs_path, logo_signature, db_stats, db_needs_update,
    run_update_pipeline,
)


# ─── Exceptions UI ────────────────────────────────────────────────────────
class UserQuit(Exception):
    """Levée quand l'utilisateur tape q/Q dans n'importe quel prompt."""


def ask(prompt, allow_empty=True):
    val = input(prompt).strip()
    if val.lower() == "q":
        raise UserQuit
    return val


# ─── Mise à jour DB (avec affichage) ──────────────────────────────────────
def _print_network_disclosure():
    print("\n─── Mise à jour des données : accès réseau ────────────")
    print("  Cette action télécharge des données depuis ces sources :")
    for s in core.NETWORK_SOURCES:
        print(f"    • {s['name']:<28} [{s['license']}]")
        print(f"      {s['host']}")
    print("  Aucune donnée personnelle n'est envoyée.")
    print("──────────────────────────────────────────────────────")


def ensure_consent_interactive(force=False):
    """Demande le consentement réseau une fois, de façon explicite. Retourne bool."""
    if core.consent_was_asked() and not force:
        return core.has_network_consent()
    _print_network_disclosure()
    try:
        resp = input("  Autoriser les mises à jour réseau ? (o/N) : ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        resp = "n"
    consent = resp in ("o", "oui", "y", "yes")
    core.set_network_consent(consent, auto_update=False)
    print(f"  → Consentement réseau : {'ACCORDÉ' if consent else 'REFUSÉ'}. "
          "Les sources choisies seront actualisées au démarrage. Modifiable via U.\n")
    return consent


def check_and_update_db(force=False):
    """Met à jour la DB UNIQUEMENT avec consentement explicite de l'utilisateur."""
    if not force and core.db_restored_this_session(DB_PATH):
        return
    cfg = core.load_config()
    db = core.load_db() if DB_PATH == core.DB_PATH and not Path(DB_PATH).exists() else load_db(DB_PATH)

    if force:
        # Commande U : action explicite de l'utilisateur.
        if not ensure_consent_interactive(force=True):
            print("  Mise à jour ignorée (réseau refusé).\n")
            return
    else:
        if not core.has_network_consent():
            if db.get("_skus") or core.consent_was_asked() or not ensure_consent_interactive():
                return

    print("\n─── Mise à jour du catalogue ──────────────────────────")

    def progress(label, i, total):
        print(f"  [{i}/{total}] {label} …")

    results = run_update_pipeline(progress=progress, consent=core.has_network_consent())
    print(f"  Résultat global : {core.UPDATE_STATUS_LABELS[core.update_status(results)]}")
    for r in results:
        if r.ok:
            print(f"  {r.label} : {'sans changement' if r.status == 'unchanged' else 'OK'}")
        else:
            print(f"  {r.label} : echec (code {r.code})")
            if r.stderr:
                first = r.stderr.splitlines()[0] if r.stderr.splitlines() else r.stderr
                print(f"    {first}")
    print("──────────────────────────────────────────────────────")


# ─── Prompts ──────────────────────────────────────────────────────────────
def prompt_new_sku(sku, products_dict):
    print(f"\n[INFO] SKU inconnu : {sku}")
    print("Choisissez le produit (Q pour annuler) :\n")
    product_names = sorted(products_dict.keys())
    for i, name in enumerate(product_names, 1):
        p = products_dict[name]
        print(f"  {i:2}. {name}  [{p['type']}]")
    while True:
        choice = ask("\nNuméro de produit : ")
        if choice.isdigit() and 1 <= int(choice) <= len(product_names):
            product = product_names[int(choice) - 1]
            break
        print("[ERR] Numéro invalide.")

    color_name = ask("Nom de la couleur (ex: Silk Lime) : ")

    hex_val = None
    while True:
        raw = ask("Code HEX (6 chars, vide si inconnu) : ")
        if raw == "":
            break
        hex_val = validate_hex(raw)
        if hex_val:
            break
        print("[ERR] Code HEX invalide. Entrez 6 caractères hexadécimaux ou laissez vide.")

    return {"product": product, "color_name": color_name, "hex": hex_val}


def prompt_hex_for_entry(sku, entry):
    print(f"\n[INFO] Pas de code HEX pour {sku} ({entry['color_name']}).")
    while True:
        raw = ask("HEX représentatif (6 chars, vide pour annuler l'export, Q pour revenir) : ")
        if raw == "":
            return None
        hex_val = validate_hex(raw)
        if hex_val:
            return hex_val
        print("[ERR] Code HEX invalide.")


def print_known_skus(db, *, limit=100, **filters):
    rows = core.query_catalogue(list_skus(db), **filters)
    if not rows:
        print("  (aucun SKU enregistré)")
        return
    print(f"\n{'SKU':<12} {'Produit':<30} {'Couleur':<28} {'HEX'}")
    print("-" * 85)
    for e in rows[:limit]:
        hex_disp = e.get("hex") or "(null)"
        print(f"{e['sku']:<12} {e['product']:<30} {e['color_name']:<28} {hex_disp}")
    print(f"\n{min(limit, len(rows))} / {len(rows)} résultats. Utilisez --search, --brand, --material ou --limit.\n")


# ─── Helpers d'affichage ──────────────────────────────────────────────────
PANEL_W = 66
COMPACT_PANEL_W = 56
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _fit(text, width):
    s = str(text)
    if width <= 0:
        return ""
    if len(s) <= width:
        return s
    if width == 1:
        return "…"
    return s[: width - 1] + "…"


def _visible_len(text):
    return len(ANSI_RE.sub("", str(text)))


def _pad_visible(text, width):
    s = str(text)
    vis = _visible_len(s)
    if vis >= width:
        return s
    return s + (" " * (width - vis))


def _supports_ansi():
    return sys.stdout.isatty() and os.getenv("NO_COLOR") is None


def _ansi(text, code, enabled=True):
    if not enabled:
        return str(text)
    return f"\x1b[{code}m{text}\x1b[0m"


def _print_box(title, lines, width=PANEL_W):
    inner = width - 2
    print(f"╔{'═' * inner}╗")
    print(f"║{_fit(title, inner):^{inner}}║")
    print(f"╠{'═' * inner}╣")
    for line in lines:
        print(f"║ {_fit(line, inner - 2):<{inner - 2}} ║")
    print(f"╚{'═' * inner}╝")


def _hex_swatch(hex_code, use_ansi=True):
    h = (hex_code or "").strip().lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", h):
        return "(aucun)"
    if not use_ansi:
        return f"#{h.upper()}"
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    block = f"\x1b[48;2;{r};{g};{b}m   \x1b[0m"
    return f"{block} #{h.upper()}"


# ─── Boucle principale ────────────────────────────────────────────────────
def main():
    if core.maybe_run_as_script_worker(sys.argv):
        return
    # Console Windows : forcer l'UTF-8 pour les cadres Unicode et les accents,
    # sinon `cp1252` lève UnicodeEncodeError au premier affichage.
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true", help="Affichage détaillé")
    parser.add_argument("--compact", action="store_true", help="Mode compact")
    parser.add_argument("--export-format", choices=("nfc", "archive"), default="nfc",
                        help="NFC compact (défaut) ou archive JSON lisible, mêmes champs")
    parser.add_argument("--tag-type", choices=tuple(core.NFC_CAPACITIES), default="NTAG216")
    parser.add_argument("--nfc-profile", choices=("full", "essential"), default="full",
                        help="Essentiel : omet descriptifs et logos, conserve tous les paramètres d'impression/couleur")
    parser.add_argument("--reserve-bytes", type=int, default=0, help="Réserve pour les ajouts du logiciel d'écriture")
    parser.add_argument("--sources", nargs="+", choices=tuple(core.SOURCE_GROUPS), help="Sources à conserver pour les prochaines mises à jour")
    parser.add_argument("--list", action="store_true", help="Lister le catalogue filtré hors ligne, puis quitter")
    parser.add_argument("--search", default="")
    parser.add_argument("--brand", default="")
    parser.add_argument("--material", default="")
    parser.add_argument("--quality", choices=("all", "ready", "incomplete"), default="all")
    parser.add_argument("--sort1", choices=tuple(core.CATALOGUE_SORT_FIELDS), default="brand")
    parser.add_argument("--sort2", choices=tuple(core.CATALOGUE_SORT_FIELDS), default="product")
    parser.add_argument("--descending1", action="store_true")
    parser.add_argument("--descending2", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--orca-overrides", action="store_true",
                        help="Préférer explicitement les valeurs Orca aux valeurs locales à l'export")
    parser.add_argument("--restore-db", nargs="?", const=DB_PATH + ".bak", metavar="SAUVEGARDE",
                        help="Restaurer explicitement une sauvegarde (défaut : .bak)")
    args, _ = parser.parse_known_args()
    if args.sources is not None:
        cfg = core.load_config()
        if args.sources != cfg["selected_sources"]:
            cfg["network_sources_revision"] = 0
        cfg["selected_sources"] = list(dict.fromkeys(args.sources))
        core.save_config(cfg)
    if args.limit < 1 or not 0 <= args.reserve_bytes <= core.NFC_CAPACITIES[args.tag_type]:
        parser.error("Limite de résultats ou réserve NFC invalide.")
    filters = dict(text=args.search, brand=args.brand, material=args.material, quality=args.quality,
                   sort1=args.sort1, sort2=args.sort2, descending1=args.descending1, descending2=args.descending2)
    nfc_options = dict(tag_type=args.tag_type, profile=args.nfc_profile, reserved_bytes=args.reserve_bytes)
    verbose = args.verbose
    compact = args.compact
    use_ansi = _supports_ansi()

    def show_header(db_obj):
        panel_w = COMPACT_PANEL_W if compact else PANEL_W
        st = db_stats(db_obj)
        logo_ok = bool(logo_abs_path(db_obj))
        v_state = "ON" if verbose else "OFF"
        c_state = "ON" if compact else "OFF"
        if compact:
            lines = [
                f"SKUs: {st['skus']}   Produits: {st['products']}   HEX manquants: {st['missing_hex']}",
                f"Logo: {'disponible' if logo_ok else 'absent'}   Verbose: {v_state}   Compact: {c_state}",
                "Cmd: SKU, L liste, U maj, V verb, C comp, Q quit",
            ]
        else:
            lines = [
                f"SKUs: {st['skus']}   Produits: {st['products']}   HEX manquants: {st['missing_hex']}",
                f"Logo: {'OK' if logo_ok else 'absent'}   Verbose: {v_state}   Compact: {c_state}",
                "Cmd: SKU, L liste, U maj, V verbose, C compact, Q quitter",
                "Fiche SKU: I inspect JSON avant export",
            ]
        print()
        _print_box(f"SpoolScribe {core.APP_VERSION} — OpenSpool / NFC", lines, width=panel_w)
        print()

    try:
        if args.restore_db:
            answer = input(f"Restaurer {args.restore_db} ? Le fichier actuel sera conservé. (o/N) : ").strip().lower()
            if answer not in ("o", "oui", "y", "yes"):
                return 0
            core.restore_db(DB_PATH, args.restore_db)
        if not args.list:
            check_and_update_db()
        db = load_db(DB_PATH)
    except (core.DatabaseError, OSError) as exc:
        print(f"[ERREUR] {exc}\nRestauration possible : --restore-db [chemin de sauvegarde]")
        return 1
    if args.list:
        print_known_skus(db, limit=args.limit, **filters)
        return 0
    show_header(db)

    try:
      while True:
        raw = input("▶  SKU / commande : ").strip()
        if not raw or raw == " ":
            continue
        cmd = raw.upper()

        if cmd == "Q":
            break

        if cmd in ("U", "UPDATE"):
            try:
                check_and_update_db(force=True)
                db = load_db(DB_PATH)
            except (core.DatabaseError, OSError) as exc:
                print(f"[ERREUR] {exc}")
                continue
            st = db_stats(db)
            print(f"  ✔  DB rechargée — {st['skus']} SKUs, {st['products']} produits, "
                  f"{st['missing_hex']} hex manquants.\n")
            continue

        if cmd in ("V", "VERBOSE"):
            verbose = not verbose
            print(f"  ✔  Verbose: {'ON' if verbose else 'OFF'}\n")
            continue

        if cmd in ("C", "COMPACT"):
            compact = not compact
            print(f"  ✔  Compact: {'ON' if compact else 'OFF'}\n")
            continue

        if cmd in ("L", "LIST"):
            print_known_skus(db, limit=args.limit, **filters)
            continue

        sku = cmd
        products = db.get("_products", {})

        try:
            if sku not in db.get("_skus", {}):
                entry = prompt_new_sku(sku, products)
                add_sku(db, sku, entry["product"], entry["color_name"], entry["hex"])
                print(f"[OK] SKU {sku} enregistré.")

            view = get_sku_view(db, sku)
            if view is None:
                product_name = db.get("_skus", {}).get(sku, {}).get("product", "")
                print(f"[WARN] Produit '{product_name}' introuvable dans _products. Vérifiez la DB.")
                continue

            if not view.hex:
                hex_val = prompt_hex_for_entry(sku, db["_skus"][sku])
                if not hex_val:
                    print("Export annulé : aucune couleur représentative validée.")
                    continue
                alpha = ask("Opacité alpha facultative (00 transparent, FF opaque ; vide pour conserver) : ")
                if alpha and not re.fullmatch(r"[0-9A-Fa-f]{2}", alpha):
                    print("[ERREUR] Alpha invalide ; export annulé.")
                    continue
                set_sku_hex(db, sku, hex_val, alpha=alpha or None)
                view = get_sku_view(db, sku)
                print(f"[OK] HEX {hex_val} enregistré pour {sku}.")

            panel_w = COMPACT_PANEL_W if compact else PANEL_W
            W = panel_w - 4
            LBL = 10
            VAL = W - LBL - 4

            def row(label, value, color=None):
                clipped = _fit(value, VAL)
                if color:
                    clipped = _ansi(clipped, color, enabled=use_ansi)
                padded = _pad_visible(clipped, VAL)
                return f"  │  {label:<{LBL}}: {padded}│"

            title_fill = "─" * max(2, (W - len(sku) - 3))
            print(f"\n  ┌─ {sku} {title_fill}┐")
            print(row("Produit", view.display_product))
            print(row("Couleur", view.color_name))
            print(row("HEX", _hex_swatch(view.hex, use_ansi=use_ansi)))
            print(row("Type", view.type_str, color="96"))
            print(row("Nozzle", view.nozzle_str))
            print(row("Bed", view.bed_str))
            if not compact:
                print(row("Densité", view.density_str))

            logo_path = (view.brand_meta or {}).get("logo_path", "")
            logo_state = "OK" if logo_path else "absent"
            print(row("Logo", logo_state, color="92" if logo_state == "OK" else "91"))
            if not compact:
                print(row("Logo File", logo_path if logo_path else "(absent)"))
                print(row("Logo View", "SVG image (non affichable en terminal texte)"))

            if verbose:
                subtype = view.product_data.get("subtype") or "-"
                print(row("Brand", view.product_data.get("brand", "Polymaker"), color="94"))
                print(row("Subtype", subtype))
                if not compact:
                    print(row("Logo Meta", logo_signature(logo_abs_path(db, view.product_data.get("brand", "")))))
                print(row("Logo URL", (view.brand_meta or {}).get("logo_url", "(absent)")))
            print(f"  └{'─' * W}┘")

            entry = db["_skus"][sku]
            while True:
                confirm = ask(f"  Exporter ({args.export_format}) ? (O/n/I/Q) : ").lower()
                if confirm in ("", "o", "y"):
                    out = core_write_openspool(sku, entry, view.product_data,
                                               OUTPUT_DIR, brand_meta=view.brand_meta, mode=args.export_format,
                                               **nfc_options,
                                               use_orca_overrides=args.orca_overrides)
                    print(f"[OK] Fichier généré : {os.path.basename(out)}")
                    break
                if confirm in ("i", "info"):
                    preview_entry = dict(entry)
                    preview_entry["sku"] = sku
                    payload = build_openspool(preview_entry, view.product_data, brand_meta=view.brand_meta,
                                             use_orca_overrides=args.orca_overrides)
                    print("\n  -- Payload JSON --")
                    text = core.serialize_openspool(payload, mode=args.export_format, **nfc_options)
                    size = core.nfc_size(text, tag_type=args.tag_type, reserved_bytes=args.reserve_bytes)
                    print(text)
                    print(f"JSON UTF-8 : {size.utf8_bytes} octets ; NDEF : {size.ndef_bytes} ; "
                          f"avec TLV : {size.type2_bytes}/{size.capacity_bytes} octets (un record MIME).")
                    print("  ------------------")
                    continue
                print("  Annulé.")
                break
            print()

        except UserQuit:
            print("  Retour au menu principal.\n")
            continue
        except (core.ExportValidationError, core.DatabaseError, OSError, ValueError) as exc:
            print(f"[ERREUR] {exc}\n")
            continue

    except (KeyboardInterrupt, UserQuit):
        pass

    _print_box("Fin de session", ["Au revoir."], width=(COMPACT_PANEL_W if compact else PANEL_W))
    print()


if __name__ == "__main__":
    sys.exit(main())
