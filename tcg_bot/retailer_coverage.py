"""Periodic source coverage checks, distinct from verified inventory."""
import re
import time
from urllib.parse import urlsplit
from .http import FetchError
from .web_sources import Document, structured_products

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
    if original is not None: client.deadline=end
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
                    products=structured_products(doc)
                    links=[{'name':p.get('name',''),'url':p.get('url')} for p in products
                           if re.search(r'pok.mon|dragon.ball|one.piece|naruto',p.get('name',''),re.I)
                           and p.get('url') and urlsplit(p['url']).netloc==urlsplit(source['url']).netloc][:50]
                    record.update(status='reachable_discovery_only',candidate_links=links,
                                  candidate_count=len(links),kind=source.get('kind'))
            except Exception as exc:
                record['status']='blocked_or_unavailable'
                record['reason']=str(exc)[:140] if isinstance(exc,FetchError) else type(exc).__name__
            table[source['id']]=record
            result['sources'].append(record)
    finally:
        if original is not None: client.deadline=original
    result['registered']=len(entries)
    result['deferred']=max(0,len(due)-result['checked'])
    return result
