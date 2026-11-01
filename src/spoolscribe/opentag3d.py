"""Independent OpenTag3D 2.004 encoder; factual wire layout, no upstream code.

Reference: https://opentag3d.info/spec.json at GooborgStudios/OpenTag3D
5e5069cf5696e03bdd328e7bc3d15ee2fde97909. No network at runtime.
Only explicitly supplied values are encoded. Unknown optional bytes are zero.
"""
from decimal import Decimal, InvalidOperation
import base64
import json
import re

VERSION = '2.004'
MIME = b'application/opentag3d'
CAPACITIES = {'NTAG215':496, 'NTAG216':872}
OUTPUTS = ('nfctools-mobile','nfctools-desktop','ndef')
# name: (offset, byte count, scalar or text encoding). Normative units, not defaults.
FIELDS = {
    'material':(0x02,5,'text'), 'material_mod':(0x07,5,'text'),
    'manufacturer':(0x0c,16,'text'), 'color_name':(0x1c,32,'text'),
    **{f'color_{i}':(0x3c+4*(i-1),4,'rgba') for i in range(1,5)},
    'serial':(0x4c,32,'text'), 'sku':(0x6c,16,'text'),
    'diameter':(0x8c,2,'0.001'), 'tolerance':(0x8e,1,'0.01'),
    'nozzle_diameter':(0x8f,1,'0.1'),
    'print_temp':(0x90,1,'5'), 'min_print_temp':(0x91,1,'5'),
    'max_print_temp':(0x92,1,'5'), 'chamber_temp':(0x93,1,'5'),
    'bed_temp':(0x94,1,'5'), 'min_bed_temp':(0x95,1,'5'),
    'max_bed_temp':(0x96,1,'5'),
    'density':(0x9c,2,'0.001'), 'weight':(0x9e,2,'1'),
}
REQUIRED = ('material','manufacturer','color_1','diameter','density','print_temp','chamber_temp','bed_temp','weight')
EDITABLE = ('material','material_mod','manufacturer','color_name','sku','print_temp','bed_temp','chamber_temp','weight','min_print_temp','max_print_temp','min_bed_temp','max_bed_temp')


def encode(values: dict) -> bytes:
    if not isinstance(values,dict):raise ValueError('OpenTag3D : objet attendu.')
    unknown=set(values)-set(FIELDS)
    if unknown:raise ValueError('OpenTag3D : champs inconnus : '+', '.join(sorted(unknown)))
    for name in REQUIRED:
        if values.get(name) is None or values.get(name)=='':raise ValueError('OpenTag3D : champ requis : '+name)
    result=bytearray(224);result[:2]=(2004).to_bytes(2,'big')
    for name,(offset,length,kind) in FIELDS.items():
        value=values.get(name)
        if value is None or value=='':continue
        if kind=='text':
            if not isinstance(value,str) or any(ord(c)<32 or ord(c)==127 for c in value):
                raise ValueError('OpenTag3D : texte invalide : '+name)
            raw=value.encode('utf-8')
            if len(raw)>length:raise ValueError(f'OpenTag3D : {name} dépasse {length} octets UTF-8 ; utilisez un libellé court explicite.')
        elif kind=='rgba':
            if not isinstance(value,str) or not re.fullmatch('[0-9A-Fa-f]{8}',value):
                raise ValueError('OpenTag3D : RGBA sur huit caractères requis : '+name)
            raw=bytes.fromhex(value)
        else:
            if type(value) not in (int,float,Decimal):raise ValueError('OpenTag3D : nombre requis : '+name)
            try:
                number=Decimal(str(value));units=number/Decimal(kind)
                if not number.is_finite() or units!=units.to_integral_value() or not 0<=units<256**length:
                    raise ValueError(f'OpenTag3D : {name} non représentable (pas de {kind}).')
                if name in ('diameter','density','weight','print_temp') and number<=0:
                    raise ValueError('OpenTag3D : valeur positive requise : '+name)
                raw=int(units).to_bytes(length,'big')
            except InvalidOperation as exc:raise ValueError('OpenTag3D : nombre invalide : '+name) from exc
        result[offset:offset+len(raw)]=raw
    for target,lo,hi in [('print_temp','min_print_temp','max_print_temp'),('bed_temp','min_bed_temp','max_bed_temp')]:
        low=values.get(lo);high=values.get(hi);t=values[target]
        if (low is not None and t<low) or (high is not None and t>high):
            raise ValueError('OpenTag3D : température cible hors de la plage source : '+target)
    return bytes(result)


def decode(payload: bytes) -> dict:
    """Inspect our complete, pinned payload; not a general untrusted tag importer."""
    if len(payload)!=224 or payload[:2]!=(2004).to_bytes(2,'big'):raise ValueError('Payload OpenTag3D 2.004 attendu.')
    out={}
    for name,(offset,length,kind) in FIELDS.items():
        raw=payload[offset:offset+length]
        if kind=='text':value=raw.rstrip(b'\0').decode('utf-8')
        elif kind=='rgba':value=raw.hex().upper()
        else:value=float(Decimal(int.from_bytes(raw,'big'))*Decimal(kind))
        out[name]=value
    return out


def ndef(payload: bytes) -> bytes:
    # One complete MIME message; ID absent, MB/ME set, never a Text record.
    length=len(payload)
    return (bytes([0xd2,len(MIME),length]) if length<256 else bytes([0xc2,len(MIME)])+length.to_bytes(4,'big'))+MIME+payload


def budget(payload: bytes,tag_type='NTAG216',reserved_bytes=0) -> dict:
    if tag_type not in CAPACITIES:raise ValueError('OpenTag3D : NTAG215 ou NTAG216 requis.')
    if type(reserved_bytes) is not int or reserved_bytes<0:raise ValueError('Réserve NFC invalide.')
    length=len(ndef(payload));occupied=length+(2 if length<255 else 4)+1
    remaining=CAPACITIES[tag_type]-occupied-reserved_bytes
    if remaining<0:raise ValueError('OpenTag3D : capacité NFC insuffisante avec cette réserve.')
    return dict(payload=len(payload),ndef=length,occupied=occupied,capacity=CAPACITIES[tag_type],remaining=remaining)


def export(payload: bytes,output='nfctools-mobile') -> bytes:
    if output=='ndef':return ndef(payload)
    if output=='nfctools-desktop':
        doc={'ntgui_version':18,'data':[{'kRecordDescription':'OpenTag3D 2.004',
            'kRecordSelection':9,'kRecordField1':MIME.decode(),
            'kRecordField2':payload.decode('latin1'),'kRecordSize':len(payload),
            'kRecordObject':{'kTnf':2,'kChunked':False,'kType':list(MIME),'kId':[],'kPayload':list(payload)}}]}
    elif output=='nfctools-mobile':
        def b64(data):return base64.b64encode(data).decode('ascii')
        def pack(data):return b64(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode('utf-8'))
        record={'identifier':'','type':b64(MIME),'payload':b64(payload),'format':b64(b'\x02')}
        # NFC Tools import envelope. Empty tag metadata is not a real UID or a tag dump.
        names=('Identifier Tech Type Iso PMm ATQA SAK SystemCode NdefStatus NdefSize NdefMaxSize '
               'DataFormat PlatformName PlatformDescription Signature PasswordStatus TagTamperStatus '
               'HistoricalBytes TagAFI TagDSFID TagLockedOverrideStatus').split()
        fields=[{name:''} for name in names]+[{'NDEFMessage':pack([{'NDEFRecord':pack(record)}])}]
        doc={'type':'nfc-tools-profiles','profiles':[{'name':'OpenTag3D 2.004','recordsCount':'1','data':pack(fields)}],'version':1}
    else:raise ValueError('Format de fichier OpenTag3D inconnu.')
    return json.dumps(doc,ensure_ascii=True,indent=2,allow_nan=False).encode('utf-8')
