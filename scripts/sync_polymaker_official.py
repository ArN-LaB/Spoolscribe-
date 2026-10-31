"""Manufacturer catalogue, with stable article identity and no guessed physics."""
import os
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts import db_io, catalogue_merge
from scripts import scrape_wholesale as wholesale
ROOT=Path(__file__).resolve().parents[1]
DB_FILE=db_io.default_db_path()


def adapt(rows):
    incoming={'_products':{},'_skus':{},'_brands':{'Polymaker':{'name':'Polymaker','source':'Polymaker officiel','logo_path':'data/polymaker_logo.svg'}}}
    rejected=[]
    for product in rows:
        title=product.get('title','')
        if not isinstance(title,str) or wholesale.is_skip(title):continue
        material=re.search(r'\b(PLA|PETG|PET|ABS|ASA|TPU|PVA|PVB|PC|PPS|PA\d*(?:/\d+)?)(?:[- ][A-Z]+\d*)?',title,re.I)
        if not material:continue
        for variant in product.get('variants',[]):
            sku=variant.get('sku','').strip()
            if not sku:continue
            if sku in incoming['_skus']:
                rejected.append(f'SKU fabricant dupliqué : {sku}');continue
            options=' '.join(str(variant.get(k) or '') for k in ('title','option1','option2','option3'))
            diameter=re.search(r'\b(\d+(?:\.\d+)?)\s*mm\b',options,re.I)
            weight=re.search(r'\b(\d+(?:\.\d+)?)\s*kg\b',options,re.I)
            color_source=str(variant.get('option3') or '')
            color=wholesale.clean_color_name(color_source)
            key=f'Polymaker officiel {product.get("id",title)} · {diameter[1] if diameter else "?"} mm'
            physical=dict(type=material[1].upper(),brand='Polymaker',display_name=title,
                diameter=float(diameter[1]) if diameter else None,density=None,
                min_temp=None,max_temp=None,bed_min_temp=None,bed_max_temp=None)
            item=dict(product=key,color_name=color or 'Couleur non précisée',hex=wholesale.extract_hex(color_source),
                manufacturer_sku=sku,source='Polymaker officiel',source_id=str(variant.get('id',sku)),
                weight=float(weight[1])*1000 if weight else None)
            mapped=wholesale.map_product_title(title)
            if mapped:item['_product_aliases']=[mapped,'Polymaker '+mapped]
            if 'refill' in (title+' '+options).casefold():item['spool_refill']=True
            try:
                db_io.validate_db({'_products':{key:physical},'_skus':{sku:item}})
                incoming['_products'][key]=physical;incoming['_skus'][sku]=item
            except ValueError as exc:rejected.append(str(exc))
    if not incoming['_skus']:raise db_io.SourceUnavailable('Polymaker : aucune variante filament exploitable')
    return incoming,rejected


def main():
    try:rows=wholesale.fetch_all_products()
    except Exception as exc:raise db_io.SourceUnavailable(f'Polymaker officiel : {exc}') from exc
    incoming,rejected=adapt(rows)
    db=db_io.load_db(DB_FILE);db_io.check_source_shrink(db,'polymaker',len(incoming['_skus']),'Polymaker')
    merged,conflicts=catalogue_merge.merge_catalogue(db,incoming,'Polymaker officiel',100)
    db.update(merged);db.setdefault('_source_snapshots',{})['polymaker']={'references':len(incoming['_skus'])};db.setdefault('_source_conflicts_by_source',{})['Polymaker officiel']=conflicts
    db_io.save_db(db,DB_FILE)
    print(f'Polymaker : {len(incoming["_skus"])} références fabricant examinées, {len(conflicts)} valeurs locales conservées.')
    if rejected:raise db_io.PartialUpdate(f'{len(rejected)} anomalies fabricant : {rejected[0]}')

if __name__=='__main__':db_io.run_step(main,DB_FILE)
