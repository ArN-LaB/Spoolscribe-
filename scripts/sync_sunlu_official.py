"""Enrich SUNLU PLA from the manufacturer's factual technical/color tables."""
import os
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import db_io, official_sources as source
from scripts.catalogue_merge import apply_official_facts
ROOT=Path(__file__).resolve().parents[1]
DB_FILE=str(Path(os.environ.get('SPOOLSCRIBE_DATA_HOME') or ROOT)/'data/polymaker_db.json')

def main():
    try:facts=source.sunlu_facts(source.fetch(source.SUNLU_URL).decode('utf-8'))
    except Exception as exc:raise db_io.SourceUnavailable(f'SUNLU : {exc}') from exc
    db=db_io.load_db(DB_FILE);matched,conflicts=apply_official_facts(db,facts,'SUNLU officiel')
    if not matched:raise db_io.SourceUnavailable('Aucune famille SUNLU PLA correspondante ; activez un catalogue OFD/SpoolmanDB.')
    db_io.save_db(db,DB_FILE)
    print(f'SUNLU : {matched} produits rapprochés ; {len(conflicts)} corrections conservées.')

if __name__=='__main__':db_io.run_step(main,DB_FILE)
