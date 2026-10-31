"""Enrich existing Bambu families with explicitly published manufacturer facts."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import urllib.parse
from scripts import db_io, official_sources as source
from scripts.catalogue_merge import apply_official_facts
ROOT=Path(__file__).resolve().parents[1]
DB_FILE=db_io.default_db_path()
BASE='https://raw.githubusercontent.com/bambulab/BambuStudio/master/resources/profiles/'

MAX_PROFILES=600

def main():
    db=db_io.load_db(DB_FILE)
    previous=(db.get('_source_snapshots') or {}).get('bambu') or {}
    try:
        index=db_io.parse_json(source.fetch(BASE+'BBL.json',etag=previous.get('etag')))
        index_etag=getattr(source.fetch,'last_etag',None);index_etag=index_etag if isinstance(index_etag,str) else None
        profiles=[p for p in index['filament_list'] if p['name'].startswith('Bambu ') and p['name'].endswith(' @base')]
        if not profiles or len(profiles)>MAX_PROFILES:raise ValueError('Index Bambu vide ou inattendu')
    except source.NotModified:
        print('Bambu : index inchangé depuis la dernière synchronisation (ETag).');return 'unchanged'
    except Exception as exc:raise db_io.SourceUnavailable(f'Index Bambu : {exc}') from exc
    facts=[];errors=[]
    for p in profiles:
        try:
            path=p['sub_path']
            if not path.startswith('filament/') or '..' in path or '\\' in path:raise ValueError('Chemin Bambu invalide')
            url=BASE+'BBL/'+urllib.parse.quote(path)
            facts.append(source.bambu_fact(db_io.parse_json(source.fetch(url,1024*1024)),url))
        except Exception as exc:errors.append(str(exc))
    if not facts:raise db_io.SourceUnavailable('Aucun profil Bambu exploitable')
    matched,conflicts=apply_official_facts(db,facts,'Bambu Lab officiel')
    if not matched:raise db_io.SourceUnavailable('Aucune famille Bambu correspondante ; activez un catalogue OFD/SpoolmanDB.')
    if index_etag and not errors:db.setdefault('_source_snapshots',{})['bambu']={'etag':index_etag,'profiles':len(profiles)}
    db_io.save_db(db,DB_FILE)
    print(f'Bambu : {matched} produits rapprochés ; {len(conflicts)} corrections conservées.')
    if errors:raise db_io.PartialUpdate(f'{len(errors)} profils Bambu inaccessibles : {errors[0]}')

if __name__=='__main__':db_io.run_step(main,DB_FILE)
