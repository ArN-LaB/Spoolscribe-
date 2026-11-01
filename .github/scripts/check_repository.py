"""Offline checks for documentation links, version authority and source layout."""
import ast
import json
from pathlib import Path
import re
import subprocess
import hashlib
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]


def check(root=ROOT):
    names = subprocess.check_output(
        ['git', 'ls-files', '--cached', '--others', '--exclude-standard'],
        cwd=root, text=True).splitlines()
    files = sorted({root / name for name in names if (root / name).is_file()})
    errors = []
    links = 0
    for path in files:
        if path.suffix != '.md':
            continue
        text = path.read_text(encoding='utf-8')
        targets = re.findall(r'\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
        targets += re.findall(r'(?:src|href)="([^"]+)"', text)
        if '[[' in text and path.parent == root / 'docs/wiki':
            errors.append(f'{path.relative_to(root)}: non-portable Wiki link')
        for target in targets:
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            dest = path.parent / unquote(parsed.path)
            links += 1
            if not dest.exists():
                errors.append(f'{path.relative_to(root)}: missing {target}')
    tree = ast.parse((root / 'src/spoolscribe/core.py').read_text(encoding='utf-8'))
    version = next(ast.literal_eval(n.value) for n in tree.body
                   if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'APP_VERSION' for t in n.targets))
    metadata = (root / 'pyproject.toml').read_text(encoding='utf-8')
    if re.search(r'^version\s*=\s*"([^"]+)"', metadata, re.M).group(1) != version:
        errors.append('pyproject/core version mismatch')
    manifest = json.loads((root / '.macos-local-install.json').read_text(encoding='utf-8'))
    if 'packaging/spoolscribe.spec' not in manifest['build']:
        errors.append('local installer points to obsolete spec')
    if list(root.glob('*.py')) or list(root.glob('*.spec')):
        errors.append('application/build modules must be grouped below src/ or packaging/')
    sys.path.insert(0, str(root/'src'))
    from spoolscribe.packaging_rules import resources
    try:
        declared = set(resources(root))
        actual = {p.relative_to(root).as_posix() for p in (root/'data').rglob('*')
                  if p.is_file() and not p.name.startswith('.') and p.suffix != '.md'}
        errors.extend('Unregistered data asset: '+name for name in sorted(actual-declared))
        seen = {}
        for name in sorted(actual):
            if Path(name).suffix not in ('.png','.svg','.webp','.ico','.icns'):continue
            digest=hashlib.sha256((root/name).read_bytes()).hexdigest()
            if digest in seen:errors.append('Duplicate image bytes: '+name+' = '+seen[digest])
            seen[digest]=name
        fixture=json.loads((root/'tests/fixtures/manifest.json').read_text(encoding='utf-8'))
        for name, entry in fixture['files'].items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=entry['sha256']:
                errors.append('Historical fixture changed: '+name)
    except (OSError,ValueError,KeyError) as exc:
        errors.append('Data layout: '+str(exc))
    return {'version': version, 'markdown': sum(p.suffix == '.md' for p in files),
            'local_links': links, 'errors': errors}


if __name__ == '__main__':
    result = check()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['errors']))
