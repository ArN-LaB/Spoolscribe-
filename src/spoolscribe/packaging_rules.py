"""Resources in the installer: code, artwork and licenses, never a catalogue/cache."""
from pathlib import Path, PurePosixPath
import json

FIXED_DATA = {
    *{f'data/app/{name}' for name in ('app.png','app.ico','app.icns','spoolscribe_logo.svg','spoolscribe_logo_animated.svg')},
    'data/ui/check.svg','data/ui/chevron-down.svg',
    'data/brands/manifest.json','data/brands/logos/rosa3d.png',
    'data/printers.json','data/printers/photos/manifest.json',
    'data/licenses/OFD-LICENSE.txt','data/licenses/SpoolmanDB-LICENSE.txt',
    'data/licenses/TheFilamentDB-ATTRIBUTION.txt','data/translations/messages.json',
}


def include_resource(name):
    path=PurePosixPath(name)
    if '__pycache__' in path.parts:return False
    if path.parts[0]=='scripts':return path.suffix=='.py'
    if path.parts[0]!='data':return False
    if path.parts[:2]==('data','app'):
        return path.name in {'app.png','app.ico','app.icns','spoolscribe_logo.svg','spoolscribe_logo_animated.svg'}
    if path.parts[:2]==('data','ui'):
        return path.name in {'check.svg','chevron-down.svg'}
    if path.parts[:3]==('data','brands','logos'):
        return len(path.parts)==4 and path.suffix in {'.png','.svg'}
    if path.parts[:3]==('data','printers','photos'):
        return len(path.parts)==4 and (path.suffix in {'.png','.webp'} or path.name=='manifest.json')
    return name in {'data/brands/manifest.json','data/licenses/OFD-LICENSE.txt',
        'data/licenses/SpoolmanDB-LICENSE.txt','data/licenses/TheFilamentDB-ATTRIBUTION.txt',
        'data/printers.json','data/translations/messages.json'}


def resources(root):
    root=Path(root)
    declared=set(FIXED_DATA)
    brands=json.loads((root/'data/brands/manifest.json').read_text(encoding='utf-8'))
    photos=json.loads((root/'data/printers/photos/manifest.json').read_text(encoding='utf-8'))
    for name in [entry['path'] for entry in brands.values()] + [
            'data/printers/photos/'+entry['file'] for entry in photos.values()]:
        if not include_resource(name) or '..' in PurePosixPath(name).parts:
            raise ValueError(f'Invalid declared resource: {name}')
        declared.add(name)
    for name in declared:
        if not (root/name).is_file():raise ValueError(f'Missing resource: {name}')
    declared.update(p.relative_to(root).as_posix() for p in (root/'scripts').glob('*.py'))
    return sorted(declared)
