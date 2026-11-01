"""Conservative source reconciliation with field provenance and explicit ambiguity."""
import copy
import re
import unicodedata
from scripts import db_io
from scripts.catalogue_sources import brand_key


def normalized(value):
    # '+' distinguishes product grades (PLA+ vs PLA, ABS+ vs ABS); every other
    # punctuation mark, accent and trademark symbol is ignored.
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or '').replace('™','').replace('®','').replace('©','')).casefold() if c.isalnum() or c=='+')


def identity(entry, product, sku=''):
    brand=brand_key(product.get('brand',''))
    article=entry.get('manufacturer_sku') or (sku if sku and not sku.startswith(('OFD-','SMDB-')) else '')
    package=(product.get('diameter'),entry.get('weight'),entry.get('spool_refill'))
    # Sources reuse one article number for several colours: the colour is part
    # of the identity, and only a compatible colour can match by article below.
    if article:return ('article',brand,normalized(article),normalized(entry.get('color_name')),*package)
    return ('description',brand,normalized(product.get('display_name') or entry.get('product')),
            normalized(entry.get('color_name')),*package)


def _color_compatible(a, b):
    """Same colour name, one unknown name, or the same HEX under different names."""
    name_a,name_b=normalized(a.get('color_name')),normalized(b.get('color_name'))
    if not name_a or not name_b or name_a==name_b:return True
    return bool(a.get('hex')) and a.get('hex')==b.get('hex')


def _package_compatible(a, b):
    return all(x is None or y is None or x==y for x,y in zip(a,b))


def merge_fields(target, incoming, source, rank, conflicts, prefix):
    before = copy.deepcopy(target)
    provenance=target.get('_field_sources',{})
    for key,value in incoming.items():
        if key.startswith('_') or key in ('source','source_id','source_path','product'):continue
        old=provenance.get(key)
        if key=='hex' and target.get('hex') is None and value is not None and (
                db_io.requires_manual_color(target) or target.get('source_colors') or
                any(target.get('source_traits',{}).get(k) for k in ('transparent','translucent','multicolor','multi_color'))):
            conflicts.append(f'{prefix}.{key}')
            continue
        if key not in target:
            target[key]=copy.deepcopy(value);provenance[key]=dict(source=source,rank=rank,value=copy.deepcopy(value))
        elif old and old.get('source')==db_io.USER_SOURCE:
            # An explicit local correction (even a deliberate null) is never replaced.
            if value is not None and target[key]!=value:conflicts.append(f'{prefix}.{key} (correction locale conservée)')
        elif old and target[key]==old.get('value') and value is None and target[key] is not None and old.get('source')==source:
            # A source that stops publishing a value never empties the local one.
            conflicts.append(f'{prefix}.{key} (valeur retirée par la source, conservée)')
        elif old and target[key]==old.get('value') and value is not None and (target[key] is None or rank>old.get('rank',0) or old.get('source')==source):
            target[key]=copy.deepcopy(value);provenance[key]=dict(source=source,rank=rank,value=copy.deepcopy(value))
        elif old is None and value is not None and (target[key] is None or rank>=db_io.LEGACY_OVERRIDE_RANK or target[key]==value):
            # Unknown provenance (historical catalogue, older installations): a
            # manufacturer source replaces it, anyone completes it, and an equal
            # value simply gains its provenance.
            target[key]=copy.deepcopy(value);provenance[key]=dict(source=source,rank=rank,value=copy.deepcopy(value))
        elif target[key]!=value and value is not None:
            conflicts.append(f'{prefix}.{key}')
    if provenance: target['_field_sources']=provenance
    # A partial source must not combine half of a new range with half of an
    # older/user range and make the whole database unsavable. Keep that pair.
    for low, high in (('min_temp', 'max_temp'), ('bed_min_temp', 'bed_max_temp')):
        if target.get(low) is not None and target.get(high) is not None and target[low] > target[high]:
            for key in (low, high):
                if key in before: target[key] = before[key]
                else: target.pop(key, None)
                previous = before.get('_field_sources', {}).get(key)
                if previous is not None: provenance[key] = previous
                else: provenance.pop(key, None)
            conflicts.append(f'{prefix}.{low}/{high} (plage incohérente, valeurs conservées)')


def family_keys(entry, product):
    brand=brand_key(product.get('brand',''))
    labels=[product.get('display_name') or entry.get('product')] + entry.get('_product_aliases',[])
    keys=[]
    for label in labels:
        family=normalized(label)
        if family.startswith(brand):family=family[len(brand):]
        keys.append((brand,family,normalized(entry.get('color_name'))))
    return keys


def merge_catalogue(local, incoming, source, rank=10):
    result=copy.deepcopy(local);conflicts=[];pending=[]
    product_users={}
    for entry in result['_skus'].values():
        key=entry.get('product');product_users[key]=product_users.get(key,0)+1
    by_identity={}
    for sku,e in result['_skus'].items():
        p=result['_products'].get(e.get('product'),{})
        by_identity.setdefault(identity(e,p,sku),[]).append(sku)
    article_index={}
    for ident,skus in by_identity.items():
        if ident[0]=='article':article_index.setdefault(ident[:3],[]).extend(skus)
    family_index={}
    for sku,e in result['_skus'].items():
        for key in family_keys(e,result['_products'].get(e.get('product'),{})):
            family_index.setdefault(key,[]).append(sku)
    existing_brands={brand_key(p.get('brand','')) for p in result['_products'].values()}
    for sku,e in incoming['_skus'].items():
        p=incoming['_products'][e['product']]
        ident=identity(e,p,sku)
        matches=[sku] if sku in result['_skus'] else by_identity.get(ident,[])
        if not matches and ident[0]=='article':
            candidates=article_index.get(ident[:3],[])
            for candidate in candidates:
                old=result['_skus'][candidate];old_p=result['_products'].get(old.get('product'),{})
                old_id=identity(old,old_p,candidate)
                if _package_compatible(ident[4:],old_id[4:]) and _color_compatible(e,old):matches.append(candidate)

        if not matches:
            candidates=set(c for key in family_keys(e,p) for c in family_index.get(key,[]))
            for candidate in sorted(candidates):
                old=result['_skus'][candidate];old_p=result['_products'].get(old.get('product'),{})
                old_article=old.get('manufacturer_sku')
                if old_article and e.get('manufacturer_sku') and normalized(old_article)!=normalized(e['manufacturer_sku']):continue
                old_package=(old_p.get('diameter'),old.get('weight'),old.get('spool_refill'))
                package=(p.get('diameter'),e.get('weight'),e.get('spool_refill'))
                if _package_compatible(package,old_package):matches.append(candidate)
        if len(matches)>1:
            pending.append(dict(source_id=sku,reason='Identité ambiguë',candidates=matches));continue
        # Unproven cross-source identities stay outside the selectable table.
        # Exact manufacturer references/names above can still complement data.
        if not matches and brand_key(p.get('brand','')) in existing_brands:
            brand_sources=[x.get('source','') for x in result['_brands'].values() if brand_key(x.get('name',''))==brand_key(p.get('brand',''))]
            cross_community=source in ('SpoolmanDB','Polymaker officiel') and source not in brand_sources
            manufacturer_first=source=='Open Filament Database' and (not brand_sources or any(s not in ('Open Filament Database','SpoolmanDB','https://github.com/OpenFilamentCollective/open-filament-database') for s in brand_sources))
            if cross_community or manufacturer_first:
                pending.append(dict(source_id=sku,reason='Rapprochement fabricant/produit non démontré'));continue
        if matches:
            canonical=matches[0];target=result['_skus'][canonical];pkey=target['product']
            # A historical orphan reference (product record missing) is healed
            # with the matching source product instead of aborting the refresh.
            current=result['_products'].setdefault(pkey,{})
            previous_identity=identity(target,current,canonical)
            previous_families=family_keys(target,current)
            updated=copy.deepcopy(current)
            merge_fields(updated,p,source,rank,conflicts,'_products.'+pkey)
            physical=('diameter','density','min_temp','max_temp','bed_min_temp','bed_max_temp','type')
            if product_users.get(pkey,0)>1 and any(updated.get(k)!=current.get(k) for k in physical):
                # A historical product can be shared by 1.75 and 2.85 mm SKUs.
                # Updating one article must not change all the others. Retain
                # the old record and give this reference a stable private product.
                old_key=pkey
                base='@reference/'+canonical
                pkey=base
                index=1
                while pkey in result['_products'] and pkey!=target['product']:
                    pkey=base+f'/{index}';index+=1
                updated.setdefault('display_name',current.get('display_name',old_key))
                target['product']=pkey
                product_users[old_key]-=1
                product_users[pkey]=1
            result['_products'][pkey]=updated
            merge_fields(target,e,source,rank,conflicts,'_skus.'+canonical)
            # Later records in this same refresh must see the updated identity.
            for index,key in [(by_identity,previous_identity),
                              *[(family_index,k) for k in previous_families],
                              *([(article_index,previous_identity[:3])] if previous_identity[0]=='article' else [])]:
                if canonical in index.get(key,[]):index[key].remove(canonical)
            current_identity=identity(target,updated,canonical)
            by_identity.setdefault(current_identity,[]).append(canonical)
            if current_identity[0]=='article':article_index.setdefault(current_identity[:3],[]).append(canonical)
            for key in family_keys(target,updated):
                if canonical not in family_index.setdefault(key,[]):family_index[key].append(canonical)
            if canonical != sku:
                # Every absorbed source record stays traceable, not only the last one.
                aliases=target.setdefault('_source_aliases',{})
                known=aliases.get(source)
                known=[known] if isinstance(known,str) else list(known or [])
                if sku not in known:known.append(sku)
                aliases[source]=known
        else:
            pkey=e['product'];result['_products'].setdefault(pkey,{})
            merge_fields(result['_products'][pkey],p,source,rank,conflicts,'_products.'+pkey)
            result['_skus'][sku]=copy.deepcopy(e)
            product_users[pkey]=product_users.get(pkey,0)+1
            result['_skus'][sku]['_field_sources']={k:dict(source=source,rank=rank,value=copy.deepcopy(v)) for k,v in e.items() if not k.startswith('_')}
            by_identity.setdefault(ident,[]).append(sku)
            if ident[0]=="article":article_index.setdefault(ident[:3],[]).append(sku)
            for key in family_keys(e,p):family_index.setdefault(key,[]).append(sku)
    used_brands={p.get('brand') for p in result['_products'].values()}
    for brand,meta in incoming.get('_brands',{}).items():
        if brand not in used_brands:continue
        target=result['_brands'].setdefault(brand,{})
        for key,value in meta.items():target.setdefault(key,copy.deepcopy(value))
    result.setdefault('_pending_source_matches',{})[source]=pending
    db_io.validate_db(result)
    return result,conflicts


def apply_official_facts(db, facts, source):
    """Exact product names only; contextual temperatures must not become universal."""
    matched=0;conflicts=[]
    for fact in facts:
        candidates=[(key,p) for key,p in db['_products'].items()
                    if brand_key(p.get('brand',''))==brand_key(fact['brand'])
                    and normalized(p.get('display_name',key)) in {normalized(n) for n in fact['names']}]
        for key,p in candidates:
            matched+=1
            merge_fields(p,fact.get('physical',{}),source,100,conflicts,'_products.'+key)
            p.setdefault('_official_references',{})[source]=fact['url']
            for sku,e in db['_skus'].items():
                if e.get('product')!=key:continue
                color=fact.get('colors',{}).get(normalized(e.get('color_name')))
                if color:merge_fields(e,{'hex':color},source,100,conflicts,'_skus.'+sku)
    db.setdefault('_source_conflicts_by_source',{})[source]=conflicts
    db_io.validate_db(db)
    return matched,conflicts
