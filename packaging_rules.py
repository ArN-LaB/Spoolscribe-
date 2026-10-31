"""Resources in the installer: code, artwork and licenses, never a catalogue/cache."""
from pathlib import Path, PurePosixPath


def include_resource(name):
    path=PurePosixPath(name)
    if '__pycache__' in path.parts:return False
    if path.parts[0]=='scripts':return path.suffix=='.py'
    if path.parts[0]!='data':return False
    return path.suffix.lower() in {'.svg','.png','.ico','.icns'} or name in {
        'data/brand_logos/manifest.json','data/brand_logos/OFD-LICENSE.txt','data/SpoolmanDB-LICENSE.txt',
        'data/TheFilamentDB-ATTRIBUTION.txt'}


def resources(root):
    root=Path(root)
    return sorted(str(p.relative_to(root)).replace('\\','/') for directory in ('data','scripts')
                  for p in (root/directory).rglob('*') if p.is_file() and include_resource(p.relative_to(root).as_posix()))
