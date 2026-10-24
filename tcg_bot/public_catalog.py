"""Observed public MMS catalog queries. URLs only; never stock/price evidence."""
import copy
import json
import re
from urllib.parse import urlencode, urljoin, urlsplit
from .http import FetchError
from .product_types import product_kind
from .rules import language


def product_links(data, shop):
    from .web_sources import walk_json
    links=[]
    patterns=shop.get('_franchise_patterns',[r'pok[eé]mon',r'dragon.?ball',r'one.?piece'])
    for obj in walk_json(data):
        core=(obj.get('cofrProductAggregate') or {}).get('cofrCoreFeature') or {}
        product=(obj.get('productAggregate') or {}).get('product') or {}
        title=core.get('productName') or product.get('title','')
        if not any(re.search(p,title,re.I) for p in patterns) or product_kind(title) is None:
            continue
        if re.search(r'\bdvd\b|blu.?ray|vinyl|schlüsselanhänger|keychain|funko|figur|repack|mystery|sleeve|acryl',title,re.I):
            continue
        lang=language({'title':title,'variant':'','description':''})
        if lang=='OTHER' or (re.search(r'pok[eé]mon',title,re.I) and lang=='EN') or (re.search(r'dragon.?ball|one.?piece',title,re.I) and lang=='DE'):
            continue
        pid=str(product.get('id',''))
        href=core.get('urlRelative','')
        url=urljoin(shop['base_url'],href);parts=urlsplit(url)
        if (pid.isdigit() and parts.scheme=='https' and parts.netloc==urlsplit(shop['base_url']).netloc
                and not parts.query and not parts.fragment and parts.path.startswith('/de/product/')
                and parts.path.endswith('-'+pid+'.html')):
            links.append(url)
    return list(dict.fromkeys(links))


def discover(shop, client):
    profile=shop.get('_public_catalog_query')
    if not profile:return []
    q=copy.deepcopy(profile['query'])
    assert profile['host']==urlsplit(shop['base_url']).hostname
    cursor=shop.get('_catalog_pages',{}).get('_public_catalog_cursor',0)
    searches=shop.get('public_catalog_searches',[])
    if searches and q['operation']=='SearchV4':
        q['variables']['query']=searches[cursor%len(searches)]
        q['variables'].pop('brandCategory',None)
    page=1+(cursor//max(1,len(searches)))%shop.get('public_catalog_max_pages',5)
    q['variables']['page']=page
    url=shop['base_url']+'/api/v1/graphql?'+urlencode({'operationName':q['operation'],
        'variables':json.dumps(q['variables'],separators=(',',':')),
        'extensions':json.dumps(q['extensions'],separators=(',',':'))})
    data=client.public_catalog_json(url,q['headers'])
    if data.get('errors') or not data.get('data'):
        raise FetchError('Public catalog query unavailable or changed')
    shop.setdefault('_catalog_next_pages',dict(shop.get('_catalog_pages',{})))['_public_catalog_cursor']=cursor+1
    return product_links(data,shop)
