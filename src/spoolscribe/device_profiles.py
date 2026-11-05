"""User-declared entry presets, separate from measurements and the catalogue.

No device discovery, certification, calibration reuse or measurement values.
Writes use the existing revision-checked JSON store and retain a backup.
"""
from __future__ import annotations
import copy
from pathlib import Path
import uuid
from scripts import db_io
from . import colour_measurements as cm

_ALLOWED = {'illuminant', 'illuminant_note', 'observer', 'geometry', 'specular', 'aperture', 'profile_note'}

def empty():
    return {'schema': 'spoolscribe-device-presets', 'version': 1, 'default': None, 'profiles': {}}

def validate(document):
    if (not isinstance(document, dict) or set(document) != set(empty()) or
        document.get('schema') != empty()['schema'] or type(document.get('version')) is not int or document['version'] != 1 or
        not isinstance(document.get('profiles'), dict) or len(document['profiles']) > 32):
        raise cm.MeasurementError('Fichier de réglages d’appareil invalide.')
    result = empty()
    for identifier, profile in document['profiles'].items():
        if (not isinstance(identifier, str) or len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier) or
            not isinstance(profile, dict) or set(profile) != {'name', 'conditions', 'manufacturer', 'model'}):
            raise cm.MeasurementError('Fichier de réglages d’appareil invalide.')
        if not isinstance(profile['conditions'], dict) or set(profile['conditions']) - _ALLOWED:
            raise cm.MeasurementError('Fichier de réglages d’appareil invalide.')
        conditions = cm.validate_conditions(profile['conditions'])
        clean = {'conditions': {k: v for k,v in conditions.items() if k in _ALLOWED and v is not None}}
        for key in ('name', 'manufacturer', 'model'):
            value = profile[key]
            if not isinstance(value,str) or len(value)>cm.LIMITS['short'] or any(ord(c)<32 for c in value) or (key=='name' and not value.strip()):
                raise cm.MeasurementError('Fichier de réglages d’appareil invalide.')
            clean[key] = value.strip()
        result['profiles'][identifier] = clean
    default = document['default']
    if default is not None and (not isinstance(default,str) or default not in result['profiles']):
        raise cm.MeasurementError('Fichier de réglages d’appareil invalide.')
    result['default'] = default
    return result

class DeviceProfiles:
    def __init__(self, path):
        self.path=Path(path); self.document=empty(); self.revision=None; self.loaded=False

    def load(self):
        self.loaded=False
        document, self.revision=db_io.load_validated_json(self.path, validate, missing_ok=True, max_bytes=65536)
        self.document=document if document is not None else empty(); self.loaded=True
        return self.document

    def _write(self, edit):
        if not self.loaded:self.load()
        candidate=copy.deepcopy(self.document); edit(candidate); candidate=validate(candidate)
        revision=db_io.save_validated_json(self.path,candidate,self.revision,validate,max_bytes=65536)
        self.document=candidate; self.revision=revision

    def add(self,name,conditions,manufacturer,model):
        identifier=uuid.uuid4().hex
        preset={'name':name,'conditions':{k:v for k,v in conditions.items() if k in _ALLOWED},'manufacturer':manufacturer,'model':model}
        self._write(lambda document: document['profiles'].update({identifier:preset}))
        return identifier

    def set_default(self,identifier):
        self._write(lambda document: document.update(default=identifier))

    def delete(self,identifier):
        def edit(document):
            document['profiles'].pop(identifier,None)
            if document['default']==identifier:document['default']=None
        self._write(edit)
