"""Bounded manufacturer downloads and parsers, separate from personal services."""
import re
import time
from html.parser import HTMLParser
import urllib.error
import urllib.request
import urllib.parse
from scripts import db_io
from scripts.catalogue_merge import normalized

class SameHost(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        old,new=urllib.parse.urlsplit(req.full_url),urllib.parse.urlsplit(newurl)
        if new.scheme!='https' or new.hostname!=old.hostname or new.username or new.port not in (None,443):
            raise db_io.SourceUnavailable('Redirection fabricant hors de l’hôte déclaré')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

USER_AGENT='SpoolScribe/0.3 (+https://github.com/ArN-LaB/Spoolscribe-; public filament data)'

def _retry_after(value,default=5.0,maximum=30.0):
    try:return min(maximum,max(1.0,float(value)))
    except (TypeError,ValueError):return default


class NotModified(Exception):
    """The source answered 304: the cached data is still current."""

def fetch(url,limit=8*1024*1024,*,etag=None,timeout=30,allowed_host=None):
    """Bounded same-host HTTPS download. With an ETag, a 304 raises NotModified.

    ``allowed_host`` lets a redirect target stay within one declared host when
    the request's own host differs (archive endpoints); by default the request
    host is the only acceptable one.
    """
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme!='https':raise db_io.SourceUnavailable('Source non HTTPS refusée')
    headers={'User-Agent':USER_AGENT}
    if etag:headers['If-None-Match']=etag
    req=urllib.request.Request(url,headers=headers)
    for attempt in range(3):
        try:
            with urllib.request.build_opener(SameHost()).open(req,timeout=timeout) as response:
                final=urllib.parse.urlsplit(response.url)
                if final.hostname not in (parsed.hostname,allowed_host):raise db_io.SourceUnavailable('Redirection inattendue')
                raw=response.read(limit+1);new_etag=response.headers.get('ETag')
            break
        except urllib.error.HTTPError as exc:
            if exc.code==304 and etag:raise NotModified()
            if exc.code in (429,503) and attempt<2:
                # The source throttles us: wait what it asks (bounded), then retry once or twice.
                delay=_retry_after(exc.headers.get('Retry-After'))
                time.sleep(delay);continue
            if exc.code==429:
                raise db_io.SourceUnavailable('Source saturée (HTTP 429) : réessayez plus tard, les données locales sont conservées.') from exc
            raise
    if len(raw)>limit:raise db_io.SourceUnavailable('Réponse fabricant trop volumineuse')
    fetch.last_etag=new_etag
    return raw
fetch.last_etag=None


def bambu_fact(row,url):
    name=row.get('name','')
    if not name.startswith('Bambu ') or not name.endswith(' @base'):raise ValueError('Profil générique fabricant attendu')
    physical={}
    for src,dst in (('filament_density','density'),('filament_diameter','diameter'),
                    ('nozzle_temperature_range_low','min_temp'),('nozzle_temperature_range_high','max_temp')):
        value=row.get(src)
        if value is not None:
            if not isinstance(value,list) or len(value)!=1:raise ValueError('Valeur fabricant ambiguë')
            number=float(value[0])
            if dst.endswith('temp'):
                if int(number)!=number:raise ValueError('Température non entière')
                number=int(number)
            physical[dst]=number
    # Do not generalize a plate-specific or printer-specific setting.
    product=dict(type='PLA',brand='Bambu Lab',min_temp=None,max_temp=None,bed_min_temp=None,bed_max_temp=None,diameter=None,density=None)
    product.update(physical);db_io.validate_db({'_products':{'check':product},'_skus':{}})
    base=name.removesuffix(' @base')
    return dict(brand='Bambu Lab',names=[base,base.replace('Bambu ','Bambu Lab ',1)],physical=physical,url=url)

class TableReader(HTMLParser):
    def __init__(self):super().__init__();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,tag,attrs):
        if tag=='tr':self.row=[]
        if tag in ('td','th') and self.row is not None:self.cell=[]
    def handle_data(self,data):
        if self.cell is not None:self.cell.append(data)
    def handle_endtag(self,tag):
        if tag in ('td','th') and self.cell is not None:
            self.row.append(' '.join(self.cell).strip());self.cell=None
        if tag=='tr' and self.row is not None:self.rows.append(self.row);self.row=None

SUNLU_URL='https://www.sunlu.com/products/pla-3d-printing-filament'

def sunlu_facts(html):
    parser=TableReader();parser.feed(html)
    physical={};colors={}
    for row in parser.rows:
        for i,cell in enumerate(row[:-1]):
            value=row[i+1]
            if normalized(cell).startswith('density'):
                match=re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*',value)
                if match:physical['density']=float(match[1])
            if normalized(cell)=='bedtemperature':
                match=re.fullmatch(r'\s*(\d+)\s*[-–]\s*(\d+)\s*[°℃C\s]*',value)
                if match:physical.update(bed_min_temp=int(match[1]),bed_max_temp=int(match[2]))
        if len(row)>=2 and re.fullmatch(r'#[0-9a-fA-F]{6}',row[1]):colors[normalized(row[0])]=row[1][1:].upper()
    # Nozzle temperatures depend on print speed on this page: keep the context
    # in the source reference, not an invented universal range.
    if not physical or not colors:raise db_io.SourceUnavailable('SUNLU : tableau technique/couleurs non reconnu ; aucune donnée supposée')
    return [dict(brand='SUNLU',names=['SUNLU PLA','PLA'],physical=physical,colors=colors,url=SUNLU_URL)]
