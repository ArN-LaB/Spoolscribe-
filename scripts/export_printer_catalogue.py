"""Export the printer catalogue to SpoolScribe Companion, deterministically and offline.

Usage (from the Desktop repository)::

    python3 scripts/export_printer_catalogue.py --companion-root ../spoolscribe_companion
    python3 scripts/export_printer_catalogue.py --companion-root ../spoolscribe_companion --check

It reads only the canonical local ``data/printers.json`` (never a personal
configuration or a downloaded copy) and the historical v1 fixture
``tests/fixtures/printer_catalogue/legacy_v1_84d4866.json``, then writes exactly
three files in Companion, and nothing else:

* ``assets/compatibility/printers.snapshot.json``: the exact bytes of the catalogue;
* ``assets/compatibility/printers.snapshot.manifest.json``: provenance and digest;
* ``test/fixtures/compatibility/catalogue_conformance.generated.json``: the shared
  conformance corpus (see docs/PRINTER-CATALOGUE-CONTRACT.md).

Outputs depend only on the inputs and the Git state of the catalogue file: running
it again changes nothing. ``--check`` compares without writing (exit 1 on a
difference). The run time is printed to the log only. No network access.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = 'data/printers.json'
LEGACY = 'tests/fixtures/printer_catalogue/legacy_v1_84d4866.json'
LEGACY_COMMIT = '84d4866'
SNAPSHOT = 'assets/compatibility/printers.snapshot.json'
MANIFEST = 'assets/compatibility/printers.snapshot.manifest.json'
CORPUS = 'test/fixtures/compatibility/catalogue_conformance.generated.json'
OUTPUTS = (SNAPSHOT, MANIFEST, CORPUS)


def _profiles_module(desktop_root: Path):
    """Import the reader without any personal context: no user copy, no settings, no storage."""
    for key in ('SPOOLSCRIBE_DATA_HOME', 'SPOOLSCRIBE_CONFIG_PATH'):
        os.environ.pop(key, None)
    os.environ['SPOOLSCRIBE_RESOURCE_DIR'] = str(desktop_root)
    for entry in (str(desktop_root / 'src'), str(desktop_root)):
        if entry not in sys.path:
            sys.path.insert(0, entry)
    from spoolscribe import printer_profiles
    return printer_profiles


def _git(desktop_root: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')  # read only: never refresh the index
    return subprocess.run(['git', '-C', str(desktop_root), *args], capture_output=True, env=env)


def _repository(url: str) -> str | None:
    for prefix in ('git@github.com:', 'https://github.com/', 'ssh://git@github.com/'):
        if url.startswith(prefix):
            name = url[len(prefix):]
            return 'github.com/' + (name[:-4] if name.endswith('.git') else name)
    return None


def _provenance(desktop_root: Path, raw: bytes) -> dict:
    head = _git(desktop_root, 'rev-parse', 'HEAD')
    if head.returncode:
        return {'repository': None, 'path': CATALOGUE, 'head': None, 'catalogueAgainstHead': 'unknown'}
    origin = _git(desktop_root, 'remote', 'get-url', 'origin')
    tracked = _git(desktop_root, 'ls-files', '--error-unmatch', '--', CATALOGUE).returncode == 0
    state = 'untracked'
    if tracked:
        committed = _git(desktop_root, 'show', 'HEAD:' + CATALOGUE)
        state = 'identical' if committed.returncode == 0 and committed.stdout == raw else 'modified'
    return {'repository': _repository(origin.stdout.decode().strip()) if origin.returncode == 0 else None,
            'path': CATALOGUE, 'head': head.stdout.decode().strip(), 'catalogueAgainstHead': state}


# ---------------------------------------------------------------- corpus ----
# Each case: id, input, expected first error code (None = accepted) and, for an
# accepted document, the expected update refusal. Bases: "real" (the canonical
# catalogue), "legacy" (historical v1 without configuration metadata).

def _set(path, value):
    return {'op': 'set', 'path': path, 'value': value}


def _delete(path):
    return {'op': 'delete', 'path': path}


def _append(path, value):
    return {'op': 'append', 'path': path, 'value': value}


U1 = ['printers', 0]
PAXX = U1 + ['firmwares', 0]
STOCK_U1 = U1 + ['firmwares', 3]
HIDDEN = ['printers', 3]

DOCUMENT_CASES = [
    # accepted
    ('real', 'real', [], None, None, 'canonical catalogue'),
    ('legacy-v1', 'legacy', [], None, None, 'historical v1 (84d4866) without configuration metadata'),
    ('legacy-v1-undated', 'legacy', [_delete(['updated'])], None, 'updated_missing',
     'readable, but not admissible as an update; a missing date is not "today"'),
    ('real-without-source', 'real', [_delete(['source'])], None, 'source_missing', 'readable, not admissible'),
    ('real-inert-extras', 'real', [_set(['x_future'], {'capacity': 999, 'u1': True}),
                                   _set(U1 + ['x_note'], 'future'), _set(PAXX + ['x_capacity_bytes'], 868)],
     None, None, 'extra optional fields are tolerated and never interpreted'),
    ('real-future-reader-token', 'real', [_append(PAXX + ['reader_formats'], 'openrfid_v2')], None, None,
     'unknown reader token kept verbatim as unknown'),
    ('real-date-offset', 'real', [_set(['updated'], '2026-11-01T22:00:00+08:00')], None, None,
     'same instant as 2026-11-01T14:00:00Z'),
    ('real-date-only', 'real', [_set(['updated'], '2026-11-02')], None, None, 'date only = 00:00 UTC'),
    ('real-date-fraction', 'real', [_set(['updated'], '2026-11-01T14:00:00.5Z')], None, None, 'fraction'),
    ('real-hidden-without-metadata', 'real', [_delete(HIDDEN + ['firmwares', 0, 'url'])], None, None,
     'hidden historical alias keeps the old, lighter rules'),
    # refused, in validation order
    ('format', 'real', [_set(['format'], 'spoolscribe-printer')], 'format', None, ''),
    ('format-not-object', 'real', [{'op': 'replace-root', 'value': ['spoolscribe-printers']}], 'format', None, ''),
    ('version-2', 'real', [_set(['version'], 2)], 'version', None, ''),
    ('version-bool', 'real', [_set(['version'], True)], 'version', None, 'true is not 1'),
    ('version-float', 'real', [_set(['version'], 1.0)], 'version', None, '1.0 is not 1'),
    ('schema-2', 'real', [_set(['configuration_schema'], 2)], 'schema', None, 'unknown sub-schema'),
    ('schema-string', 'real', [_set(['configuration_schema'], '1')], 'schema', None, ''),
    ('updated-month', 'real', [_set(['updated'], '2026-13-01')], 'updated', None, ''),
    ('updated-calendar', 'real', [_set(['updated'], '2026-02-30')], 'updated', None, ''),
    ('updated-no-offset', 'real', [_set(['updated'], '2026-11-01T14:00:00')], 'updated', None, 'ambiguous time'),
    ('updated-text', 'real', [_set(['updated'], 'yesterday')], 'updated', None, ''),
    ('updated-non-ascii-digits', 'real', [_set(['updated'], '\u0662\u0660\u0662\u0666-11-01')], 'updated', None,
     'ASCII digits only'),
    ('updated-offset-overflow', 'real', [_set(['updated'], '0001-01-01T00:30:00+01:00')], 'updated', None,
     'outside the representable UTC range'),
    ('source-http', 'real', [_set(['source'], 'http://example.org/printers.json')], 'source', None, ''),
    ('groups-unknown', 'real', [_set(['groups', 'brand'], 'x')], 'groups', None, ''),
    ('printers-empty', 'real', [_set(['printers'], [])], 'printers', None, ''),
    ('printer-not-object', 'real', [_set(['printers', 0], 'u1')], 'printer', None, ''),
    ('printer-id-empty', 'real', [_set(U1 + ['id'], '')], 'id', None, ''),
    ('printer-id-upper', 'real', [_set(U1 + ['id'], 'U1')], 'id', None, ''),
    ('printer-duplicate', 'real', [_set(['printers', 1, 'id'], 'u1')], 'duplicate', None, ''),
    ('hidden-string', 'real', [_set(HIDDEN + ['hidden'], 'true')], 'hidden', None, ''),
    ('group-unknown', 'real', [_set(U1 + ['group'], 'brand')], 'group', None, ''),
    ('label-empty', 'real', [_set(U1 + ['label'], '')], 'text', None, ''),
    ('label-nul', 'real', [_set(U1 + ['label'], 'U1\u0000')], 'text', None, ''),
    ('label-too-long', 'real', [_set(U1 + ['label'], 'x' * 201)], 'text', None, '201 code points'),
    ('fields-number', 'real', [_set(U1 + ['fields', 'Type'], 3)], 'fields', None, ''),
    ('firmwares-empty', 'real', [_set(U1 + ['firmwares'], [])], 'firmwares', None, ''),
    ('openspool-string', 'real', [_set(PAXX + ['openspool'], 'true')], 'firmwares', None, ''),
    ('openspool-number', 'real', [_set(PAXX + ['openspool'], 1)], 'firmwares', None, ''),
    ('configuration-duplicate', 'real', [_set(U1 + ['firmwares', 1, 'id'], 'paxx12')], 'duplicate', None, ''),
    ('configuration-id', 'real', [_set(PAXX + ['id'], 'paxx 12')], 'id', None, ''),
    ('url-javascript', 'real', [_set(PAXX + ['url'], 'javascript:alert(1)')], 'url', None, ''),
    ('formats-unknown', 'real', [_set(PAXX + ['formats'], ['openprinttag'])], 'formats', None,
     'only the exporters Desktop has'),
    ('formats-duplicate', 'real', [_set(PAXX + ['formats'], ['openspool', 'openspool'])], 'formats', None, ''),
    ('formats-openspool-mismatch', 'real', [_set(PAXX + ['formats'], ['opentag3d'])], 'formats', None, ''),
    ('reader-formats-missing-export', 'real', [_set(PAXX + ['reader_formats'], ['snapmaker'])],
     'reader_formats', None, 'an exported format must be read'),
    ('reader-formats-duplicate', 'real', [_set(PAXX + ['reader_formats'], ['openspool', 'openspool'])],
     'reader_formats', None, ''),
    ('reader-formats-upper', 'real', [_set(PAXX + ['reader_formats'], ['OpenSpool', 'openspool'])],
     'reader_formats', None, 'tokens are exact, lower case'),
    ('reader-formats-string', 'real', [_set(PAXX + ['reader_formats'], 'openspool')], 'reader_formats', None, ''),
    ('connection-unknown', 'real', [_set(PAXX + ['connection'], 'bluetooth')], 'metadata', None, ''),
    ('evidence-unknown', 'real', [_set(PAXX + ['evidence'], 'tested')], 'metadata', None, ''),
    ('effect-missing', 'real', [_delete(PAXX + ['effect'])], 'metadata', None, 'schema 1 requires it'),
    ('checked-calendar', 'real', [_set(PAXX + ['checked'], '2026-11-31')], 'date', None, ''),
    ('export-unverified', 'real', [_set(PAXX + ['evidence'], 'unverified')], 'export', None,
     'an unverified configuration cannot enable an export'),
    ('export-without-effect', 'real', [_set(PAXX + ['effect'], 'none')], 'export', None, ''),
    ('external-reader-http', 'real', [_set(['external_readers', 0, 'url'], 'http://example.org')],
     'external_readers', None, ''),
    ('unverified-number', 'real', [_set(['unverified'], [1])], 'unverified', None, ''),
]

# Byte-level cases: raw text (UTF-8), hexadecimal bytes, or a transform of the real bytes.
BYTE_CASES = [
    ('bytes-real', {'base': 'real'}, None, 'exact canonical bytes'),
    ('bytes-reformatted', {'base': 'real', 'transform': 'compact'}, None, 'formatting is not data'),
    ('bytes-bom', {'base': 'real', 'transform': 'bom'}, 'utf8', 'no byte order mark'),
    ('bytes-utf16', {'base': 'real', 'transform': 'utf16'}, 'utf8', ''),
    ('bytes-invalid-utf8', {'hex': '7b22666f726d6174223a22ff227d'}, 'utf8', ''),
    ('bytes-oversize', {'base': 'real', 'transform': 'pad-over-limit'}, 'size', 'over 512 KiB'),
    ('bytes-empty', {'text': ''}, 'json', ''),
    ('bytes-truncated', {'text': '{"format": "spoolscribe-printers", "version": 1'}, 'json', ''),
    ('bytes-duplicate-key', {'text': '{"format": "spoolscribe-printers", "format": "x", "version": 1}'}, 'json',
     'duplicate keys are refused'),
    ('bytes-nan', {'text': '{"format": "spoolscribe-printers", "version": NaN}'}, 'json', ''),
    ('bytes-trailing-comma', {'text': '{"format": "spoolscribe-printers", "version": 1,}'}, 'json', ''),
    ('bytes-lone-surrogate', {'text': '{"format":"spoolscribe-printers","version":1,"printers":[{"id":"a",'
                                      '"label":"\\ud800","group":"none","firmwares":[{"id":"b","label":"c",'
                                      '"openspool":false}]}]}'}, 'text', ''),
    ('bytes-too-deep', {'text': '{"format":"spoolscribe-printers","version":1,"x":' + '[' * 64 + ']' * 64 + '}'},
     'json', 'nesting over 64 levels'),
    ('bytes-deep-enough', {'text': '{"format":"spoolscribe-printers","version":1,"x":' + '[' * 63 + ']' * 63 + ','
                                   '"printers":[{"id":"a","label":"A","group":"none","firmwares":[{"id":"b",'
                                   '"label":"B","openspool":false}]}]}'}, None, 'nesting of exactly 64 levels'),
    ('bytes-minimal-v1', {'text': '{"format":"spoolscribe-printers","version":1,"printers":[{"id":"a",'
                                  '"label":"A","group":"none","firmwares":[{"id":"b","label":"B",'
                                  '"openspool":false}]}]}'}, None, 'smallest readable v1 document'),
]

# Update decisions: active list, candidate, expected decision.
UPDATE_CASES = [
    ('same', {'case': 'real'}, {'case': 'real'}, 'unchanged', 'identical content'),
    ('same-reformatted', {'case': 'real'}, {'case': 'bytes-reformatted'}, 'unchanged', 'formatting only'),
    ('same-with-origin-marker', {'case': 'real'}, {'case': 'real', 'ops': [_set(['_origin'], 'user')]},
     'unchanged', 'runtime marker is not data'),
    ('same-instant-other-notation', {'case': 'real'}, {'case': 'real-date-offset'}, 'unchanged',
     'compared by time value'),
    ('same-date-different', {'case': 'real'}, {'case': 'real', 'ops': [_set(U1 + ['label'], 'Snapmaker U1 bis')]},
     'conflict', 'keep the active list'),
    ('older', {'case': 'real'}, {'case': 'legacy-v1'}, 'regression', '2026-11-01 < 2026-11-01T14:00:00Z'),
    ('newer', {'case': 'real'}, {'case': 'real', 'ops': [_set(['updated'], '2026-11-02T00:00:00Z')]}, 'install', ''),
    ('newer-than-legacy', {'case': 'legacy-v1'}, {'case': 'real'}, 'install', ''),
    ('active-undated', {'case': 'legacy-v1-undated'}, {'case': 'real'}, 'install', ''),
    ('candidate-undated', {'case': 'real'}, {'case': 'legacy-v1-undated'}, 'not_admissible', ''),
    ('candidate-without-source', {'case': 'real'}, {'case': 'real-without-source'}, 'not_admissible', ''),
]


def apply_ops(doc, ops):
    """Tiny, explicit patch language shared with the Dart test."""
    doc = copy.deepcopy(doc)
    for op in ops:
        if op['op'] == 'replace-root':
            doc = copy.deepcopy(op['value'])
            continue
        *parents, last = op['path']
        target = doc
        for key in parents:
            target = target[key]
        if op['op'] == 'set':
            target[last] = copy.deepcopy(op['value'])
        elif op['op'] == 'delete':
            del target[last]
        elif op['op'] == 'append':
            target[last].append(copy.deepcopy(op['value']))
        else:
            raise ValueError(op['op'])
    return doc


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _bytes_input(spec: dict, real: bytes, limit: int) -> bytes:
    if 'text' in spec:
        return spec['text'].encode('utf-8')
    if 'hex' in spec:
        return bytes.fromhex(spec['hex'])
    transform = spec.get('transform')
    if transform is None:
        return real
    if transform == 'compact':
        return json.dumps(json.loads(real), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if transform == 'bom':
        return b'\xef\xbb\xbf' + real
    if transform == 'utf16':
        return real.decode('utf-8').encode('utf-16')
    if transform == 'pad-over-limit':
        return real + b' ' * (limit + 1 - len(real))
    raise ValueError(transform)


def build_corpus(pp, real: bytes, legacy: bytes) -> dict:
    bases = {'real': json.loads(real), 'legacy': json.loads(legacy)}
    documents, results = [], {}

    def outcome(run):
        try:
            doc = run()
        except pp.CatalogueError as exc:
            return None, exc.code
        return doc, None

    for case_id, base, ops, code, refusal, note in DOCUMENT_CASES:
        doc, got = outcome(lambda: pp.validate_catalogue(apply_ops(bases[base], ops)))
        if got != code:
            raise SystemExit(f'{case_id}: expected {code}, Python reader gives {got}')
        entry = {'id': case_id, 'note': note, 'input': {'document': {'base': base, 'ops': ops}},
                 'expect': {'code': code}}
        if doc is not None:
            if pp.update_refusal(doc) != refusal:
                raise SystemExit(f'{case_id}: expected refusal {refusal}, got {pp.update_refusal(doc)}')
            view = pp.projection(doc)
            entry['expect'].update(updateRefusal=refusal, projectionSha256=hashlib.sha256(canonical(view)).hexdigest())
            if case_id in ('real', 'legacy-v1'):
                entry['expect']['projection'] = view
            results[case_id] = doc
        documents.append(entry)
    byte_cases = []
    for case_id, spec, code, note in BYTE_CASES:
        doc, got = outcome(lambda: pp.parse_catalogue_bytes(_bytes_input(spec, real, pp.MAX_CATALOGUE_BYTES)))
        if got != code:
            raise SystemExit(f'{case_id}: expected {code}, Python reader gives {got}')
        entry = {'id': case_id, 'note': note, 'input': {'bytes': spec}, 'expect': {'code': code}}
        if doc is not None:
            entry['expect'].update(updateRefusal=pp.update_refusal(doc),
                                   projectionSha256=hashlib.sha256(canonical(pp.projection(doc))).hexdigest())
            results[case_id] = doc
        byte_cases.append(entry)
    updates = []
    for case_id, active, candidate, decision, note in UPDATE_CASES:
        a = apply_ops(results[active['case']], active.get('ops', []))
        c = apply_ops(results[candidate['case']], candidate.get('ops', []))
        got = pp.compare_update(a, c)
        if got != decision:
            raise SystemExit(f'{case_id}: expected {decision}, Python gives {got}')
        updates.append({'id': case_id, 'note': note, 'active': active, 'candidate': candidate,
                        'expect': {'decision': decision}})
    return {
        'format': 'spoolscribe-printers-conformance', 'corpusVersion': 1,
        'contract': 'docs/PRINTER-CATALOGUE-CONTRACT.md',
        'generator': 'scripts/export_printer_catalogue.py',
        'limits': {'maxBytes': pp.MAX_CATALOGUE_BYTES},
        'canonicalJson': 'sorted keys, separators "," and ":", UTF-8 without ASCII escaping',
        'bases': {
            'real': {'path': CATALOGUE, 'sha256': hashlib.sha256(real).hexdigest(), 'document': bases['real']},
            'legacy': {'path': LEGACY, 'commit': LEGACY_COMMIT, 'sha256': hashlib.sha256(legacy).hexdigest(),
                       'document': bases['legacy']},
        },
        'documents': documents, 'bytes': byte_cases, 'updates': updates,
    }


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1) + '\n').encode('utf-8')


def build_outputs(desktop_root: Path = ROOT) -> dict[str, bytes]:
    pp = _profiles_module(desktop_root)
    real = (desktop_root / CATALOGUE).read_bytes()
    legacy = (desktop_root / LEGACY).read_bytes()
    doc = pp.parse_catalogue_bytes(real)
    refusal = pp.update_refusal(doc)
    if refusal:
        raise SystemExit(f'Catalogue canonique non exportable : {refusal}')
    corpus = _json_bytes(build_corpus(pp, real, legacy))
    visible = [p for p in doc['printers'] if p.get('hidden') is not True]
    manifest = {
        'format': 'spoolscribe-printers-snapshot-manifest', 'manifestVersion': 1,
        'generator': 'scripts/export_printer_catalogue.py',
        'provenance': 'local-canonical',
        'note': 'Byte-for-byte copy of the local canonical file; publication at this revision is not verified.',
        'source': _provenance(desktop_root, real),
        'snapshot': {'path': SNAPSHOT, 'bytes': len(real), 'sha256': hashlib.sha256(real).hexdigest()},
        'catalogue': {'format': doc['format'], 'version': doc['version'],
                      'configurationSchema': doc.get('configuration_schema'), 'updated': doc.get('updated'),
                      'printers': len(doc['printers']), 'visiblePrinters': len(visible),
                      'configurations': sum(len(p['firmwares']) for p in doc['printers'])},
        'corpus': {'path': CORPUS, 'sha256': hashlib.sha256(corpus).hexdigest()},
    }
    return {SNAPSHOT: real, MANIFEST: _json_bytes(manifest), CORPUS: corpus}


def differences(companion_root: Path, outputs: dict[str, bytes]) -> list[str]:
    out = []
    for name, data in outputs.items():
        path = companion_root / name
        if not path.is_file() or path.read_bytes() != data:
            out.append(name)
    return out


def write(companion_root: Path, outputs: dict[str, bytes]) -> list[str]:
    """Write only the declared outputs; never delete anything; unchanged files are not rewritten."""
    changed = []
    for name in differences(companion_root, outputs):
        assert name in OUTPUTS
        path = companion_root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name('.' + path.name + '.export-tmp')
        tmp.write_bytes(outputs[name])
        os.replace(tmp, path)
        changed.append(name)
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--companion-root', type=Path, required=True,
                        help='Companion project root (contains pubspec.yaml)')
    parser.add_argument('--desktop-root', type=Path, default=ROOT, help='Desktop repository (default: this one)')
    parser.add_argument('--check', action='store_true', help='compare without writing; exit 1 on a difference')
    args = parser.parse_args(argv)
    companion = args.companion_root.resolve()
    if not (companion / 'pubspec.yaml').is_file():
        parser.error(f'Not a Companion root: {companion}')
    outputs = build_outputs(args.desktop_root.resolve())
    stamp = datetime.now(timezone.utc).isoformat(timespec='seconds')
    if args.check:
        diff = differences(companion, outputs)
        print(f'[{stamp}] check {"OK" if not diff else "DIFFERENT: " + ", ".join(diff)}')
        return 1 if diff else 0
    changed = write(companion, outputs)
    print(f'[{stamp}] written: {", ".join(changed) if changed else "nothing (already identical)"}')
    for name, data in outputs.items():
        print(f'  {hashlib.sha256(data).hexdigest()}  {len(data):>7}  {name}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
