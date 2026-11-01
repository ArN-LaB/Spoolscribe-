"""Preview/copy reviewed Wiki pages; never commit, push or delete remote pages."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def rendered(text):
    # Repository pages use normal relative .md links; GitHub Wiki routes omit .md.
    return re.sub(r'(\]\()([A-Za-z0-9_-]+)\.md(#[^)]*)?(\))',
                  lambda m: m[1] + m[2] + (m[3] or '') + m[4], text)


def synchronize(checkout, *, apply=False):
    checkout = checkout.resolve()
    if checkout == ROOT or not (checkout / '.git').exists():
        raise ValueError('Use a separate GitHub Wiki checkout')
    remote = subprocess.check_output(['git', '-C', str(checkout), 'remote', 'get-url', 'origin'], text=True).strip()
    if not re.fullmatch(r'(?:git@github\.com:|https://github\.com/)ArN-LaB/Spoolscribe-\.wiki\.git', remote):
        raise ValueError('Unexpected Wiki origin; no files copied')
    status = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True)
    if status.strip():
        raise ValueError('Wiki checkout must be clean; preserve existing edits first')
    changes = []
    for source in sorted((ROOT / 'docs/wiki').glob('*.md')):
        target = checkout / source.name
        if target.is_symlink():
            raise ValueError(f'Refuse symlink: {target}')
        content = rendered(source.read_text(encoding='utf-8'))
        if not target.exists() or target.read_text(encoding='utf-8') != content:
            changes.append(source.name)
            if apply:
                target.write_text(content, encoding='utf-8')
    return changes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', required=True, type=Path)
    parser.add_argument('--apply', action='store_true', help='copy pages after the preview')
    args = parser.parse_args()
    for name in synchronize(args.checkout, apply=args.apply):
        print(('COPY ' if args.apply else 'WOULD COPY ') + name)
    print('No commit, push or deletion performed.')
