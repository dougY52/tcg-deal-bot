"""Periodic source coverage checks, distinct from verified inventory."""
import re
import time
from urllib.parse import urlsplit, urljoin, urlunsplit, parse_qsl, urlencode
from .http import FetchError
from .web_sources import Document, structured_products
from .rules import franchise
from .product_types import product_kind

def candidate_links(doc, source, cfg):
    """Persist public product links as hints, never price/stock confirmation."""
    scope=dict(cfg)
    scope.setdefault('franchises', {'Pokémon':r'pok[eé]mon','Dragon Ball':r'dragon.?ball','One Piece':r'one.?piece'})
    candidates=[(p.get('name',''),p.get('url','')) for p in structured_products(doc)]
    candidates.extend((n.text().strip(),n.attrs.get('href','')) for n in doc.root.walk() if n.tag=='a')
    links={}
    for name,href in candidates:
        if not isinstance(name,str) or not isinstance(href,str) or not href:
            continue
        if not franchise({'title':name},scope) or product_kind(name) is None:
            continue
        url=urlsplit(urljoin(source['url'],href))
        if url.scheme!='https' or url.netloc!=urlsplit(source['url']).netloc or url.username or url.password:
            continue
        # Keep concrete variant selectors; discard tracking and fragments.
        query=urlencode([(k,v) for k,v in parse_qsl(url.query) if k in ('variant','itemId','variationId')])
        target=urlunsplit((url.scheme,url.netloc,url.path,query,''))
        links[target]={'name':name[:240],'url':target}
    return list(links.values())[:50]


def check_sources(cfg, state, client, now):
    settings=cfg.get('retailer_coverage',{})
    result={'checked':0,'sources':[]}
    if not settings.get('enabled'):
        return result
    table=state.setdefault('retailer_coverage',{})
    entries=cfg.get('retailer_sources',[])
    due=[s for s in entries if now-table.get(s['id'],{}).get('checked_at',0)>=settings.get('recheck_seconds',21600)]
    due.sort(key=lambda s:table.get(s['id'],{}).get('checked_at',0))
    original=getattr(client,'deadline',None)
    end=time.monotonic()+settings.get('budget_seconds',15)
    if original is not None:
        end=min(end,original)
        client.deadline=end
    try:
        for source in due[:settings.get('max_checks',4)]:
            if time.monotonic()>=end: break
            result['checked']+=1
            record={'id':source['id'],'checked_at':now,'url':source['url'],'inventory_confirmed':False}
            try:
                body=client.text(source['url'])
                doc=Document(body)
                title=' '.join(n.text() for n in doc.root.walk() if n.tag=='title')
                if re.search(r'access denied|client challenge|just a moment|captcha|zugriff verweigert',title,re.I):
                    record['status']='challenge'
                else:
                    links=candidate_links(doc,source,cfg)
                    record.update(status='reachable_discovery_only',candidate_links=links,
                                  candidate_count=len(links),kind=source.get('kind'))
            except Exception as exc:
                if isinstance(exc,FetchError) and str(exc) in ('Run request budget exhausted','Browser request budget exhausted'):
                    # Local limits say nothing about retailer availability. Keep due.
                    record.update(status='deferred_budget',reason=str(exc),
                                  checked_at=table.get(source['id'],{}).get('checked_at',0))
                    table[source['id']]=record
                    result['sources'].append(record)
                    result['checked']-=1
                    break
                record['status']='blocked_or_unavailable'
                record['reason']=str(exc)[:140] if isinstance(exc,FetchError) else type(exc).__name__
            queue=state.setdefault('retailer_product_candidates',{})
            for link in record.get('candidate_links',[]):
                key=source['id']+'|'+link['url']
                old=queue.get(key,{})
                queue[key]=dict(link,source_id=source['id'],source_url=source['url'],
                    first_seen=old.get('first_seen',now),last_seen=now,
                    status='needs_live_variant_seller_price_validation',inventory_confirmed=False)
            state['retailer_product_candidates']=dict(sorted(
                ((k,v) for k,v in queue.items() if now-v['last_seen']<30*86400),
                key=lambda pair:pair[1]['last_seen'],reverse=True)[:500])
            table[source['id']]=record
            result['sources'].append(record)
    finally:
        if original is not None: client.deadline=original
    result['registered']=len(entries)
    result['deferred']=max(0,len(due)-result['checked'])
    return result
