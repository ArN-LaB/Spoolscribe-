"""Resource aliases only: keep old saved logo paths without copying user files."""
import os
from pathlib import Path

FILE_ALIASES = {
    'data/polymaker_logo.svg': 'data/brands/logos/polymaker-lines.svg',
    'data/prusament_logo.png': 'data/brands/logos/prusament.svg',
    'data/rosa3d_logo.png': 'data/brands/logos/rosa3d.png',
    **{f'data/brand_logos/{name}.svg': 'data/brands/logos/polymaker-lines.svg'
       for name in ('polyflex', 'polylite', 'polymide', 'polysonic')},
    **{f'data/brand_logos/{name}.png': 'data/brands/logos/primavalue.png'
       for name in ('easyprint', 'primaselect', '3d_prima_basic')},
    'data/brand_logos/manifest.json': 'data/brands/manifest.json',
    **{f'data/{name}': f'data/app/{name}' for name in
       ('app.png', 'app.ico', 'app.icns', 'spoolscribe_logo.svg', 'spoolscribe_logo_animated.svg')},
    **{f'data/{name}': f'data/ui/{name}' for name in ('check.svg', 'chevron-down.svg')},
}


def canonical_resource_path(name):
    name = str(name).replace('\\', '/')
    if name in FILE_ALIASES:
        return FILE_ALIASES[name]
    for old, new in [('data/brand_logos/', 'data/brands/logos/'),
                     ('data/printer_photos/', 'data/printers/photos/')]:
        if name.startswith(old):
            return new + name[len(old):]
    return name


def resource_candidates(name):
    """Read aliases in place; the caller must still enforce its data-root boundary."""
    canonical = canonical_resource_path(name)
    paths = [str(name), canonical]
    paths.extend(old for old, new in FILE_ALIASES.items() if new == canonical)
    for new, old in [('data/brands/logos/', 'data/brand_logos/'),
                     ('data/printers/photos/', 'data/printer_photos/')]:
        if canonical.startswith(new):
            paths.append(old + canonical[len(new):])
    return list(dict.fromkeys(paths))


def user_data_home():
    """Standalone workers share the application default, never the repository root."""
    from scripts.db_io import default_db_path
    return str(Path(default_db_path()).parents[1])


def legacy_snapshot_path(resource_root=None, user_home=None):
    """Optional legacy dump: user copy first, developer fixture otherwise; never bundled."""
    root = Path(resource_root or os.environ.get('SPOOLSCRIBE_RESOURCE_DIR') or Path(__file__).resolve().parents[1])
    home = Path(user_home or user_data_home())
    user = home / 'data/thefilamentdb.jsonl.gz'
    return user if user.is_file() else root / 'tests/fixtures/legacy/thefilamentdb.jsonl.gz'
