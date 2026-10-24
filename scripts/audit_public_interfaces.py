"""Public, read-only interface inventory. Never records credentials or HAR files.

An ordinary fresh Chromium context observes GET/XHR metadata; POSTs (including
cart, consent, telemetry and challenge submissions) are blocked. Public robot
rules gate page visits. Reaching JSON/HTML never confirms inventory or a drop.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit, parse_qsl, urljoin
from tcg_bot.http import Client, FetchError
from tcg_bot.web_sources import Document, structured_products

RELEVANT = re.compile(r'pok[eé]mon|dragon.?ball|one.?piece', re.I)
SEALED = re.compile(r'booster|display|trainer.?box|collection|kollektion|bundle|\betb\b|premium', re.I)
CHALLENGE = re.compile(r'access denied|client challenge|just a moment|captcha|request unsuccessful|incapsula incident|zugriff verweigert', re.I)


def endpoint(url):
    """Strip values, fragments, credentials and opaque path identifiers."""
    u=urlsplit(url)
    path='/'.join(':opaque' if (len(p)>28 and re.fullmatch(r'[A-Za-z0-9_.:=-]+',p)) else p for p in u.path.split('/'))
    return {'host':u.hostname,'path':path[:280], 'query_keys':sorted({k for k,_ in parse_qsl(u.query)})[:20]}


def page_info(body, url):
    doc=Document(body)
    headings=[n.text().strip()[:180] for n in doc.root.walk() if n.tag in ('title','h1')]
    text=' '.join(headings)+' '+doc.root.text()[:1200]
    if CHALLENGE.search(text):
        return {'status':'challenge','bytes':len(body)}
    if len(doc.root.text().strip())<40:
        return {'status':'empty_or_script_shell','bytes':len(body)}
    products=structured_products(doc)
    candidates={}
    for n in doc.root.walk():
        if n.tag!='a':continue
        title=re.sub(r'\s+',' ',n.text()).strip()
        target=urljoin(url,n.attrs.get('href',''))
        u=urlsplit(target)
        if (RELEVANT.search(title) and SEALED.search(title) and u.scheme=='https'
                and u.netloc==urlsplit(url).netloc and not u.query and not u.fragment):
            candidates[target]=title[:160]
    return {'status':'readable_discovery_only','bytes':len(body),'headings':headings[:3],
            'structured_product_count':len(products),
            'embedded_state': [s for s in ('__PRELOADED_STATE__','__NEXT_DATA__','__NUXT__','Shopify','application/ld+json') if s in body],
            'candidate_links':[{'url':u,'name':n} for u,n in list(candidates.items())[:12]],
            'inventory_confirmed':False}


def http_probe(target):
    record=dict(target, checked_at=datetime.now(timezone.utc).isoformat(), inventory_confirmed=False)
    client=Client();client.deadline=time.monotonic()+22
    try:
        client.check_allowed(target['url'])
        record['policy_allowed']=True
        origin='https://'+urlsplit(target['url']).netloc
        robots=client.robots.get(origin,'')
        record['sitemaps']=[u for u in re.findall(r'^Sitemap:\s*(\S+)',robots,re.M|re.I)
                            if urlsplit(u).scheme=='https' and urlsplit(u).netloc==urlsplit(target['url']).netloc][:5]
        record['http']=page_info(client.text(target['url']),target['url'])
    except Exception as e:
        record['http']={'status':'unavailable','reason':str(e)[:120] if isinstance(e,FetchError) else type(e).__name__}
    return record


def browser_probe(browser, record):
    if not record.get('policy_allowed'):
        record['browser']={'status':'not_attempted_policy_unconfirmed'};return
    url=record['url'];host=urlsplit(url).hostname
    context=browser.new_context(locale='de-DE',service_workers='block')
    page=context.new_page();seen={}
    def note(request, status=None, blocked=False):
        if request.resource_type not in ('xhr','fetch'):return
        u=urlsplit(request.url)
        # Keep first-party inventory traffic, not advertising/personal identifiers.
        base=host.removeprefix('www.')
        if not(u.hostname==base or (u.hostname or '').endswith('.'+base)):return
        if re.search(r'setCookie|/session|/wishlist|/basket|/consent|tracking|/sda-|/gate/|_fs-ch|challenge-platform',u.path,re.I):return
        data=endpoint(request.url)|{'method':request.method,'resource_type':request.resource_type}
        query=dict(parse_qsl(u.query))
        operation=query.get('operationName','')
        if re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}',operation):
            data['operation_name']=operation
            try:
                variables=json.loads(query.get('variables','{}'))
                data['variable_keys']=sorted(variables)[:30] if isinstance(variables,dict) else []
                if operation in ('CategoryV4','SearchV4') and isinstance(variables,dict):
                    extensions=json.loads(query.get('extensions','{}'))
                    allowed={'cofrConfig','filters','locale','page','pimCode','query','salesLine','hasMarketplace',
                             'isCrossLinkingActive','isCustomerBehaviorInfluenceActive','isDemonstrationModelAvailabilityActive',
                             'isPdpFaqSectionActive','isPdpLoyaltyPointsActive','isRefurbishedGoodsActive','searchExperiment',
                             'brandCategory','bypassStandardization'}
                    if set(variables)<=allowed:
                        record['public_query']={'operation':operation,'variables':variables,
                            'extensions':{k:v for k,v in extensions.items() if k in ('persistedQuery','pwa')},
                            'headers':{k:v for k,v in request.headers.items() if k in ('x-operation','x-mms-salesline','x-mms-country','x-mms-language','x-cacheable','apollographql-client-name','apollographql-client-version')}}
            except (ValueError,TypeError):pass
        if request.method=='POST':
            try:
                payload=json.loads(request.post_data or '{}')
                if isinstance(payload,dict) and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,79}',str(payload.get('operationName',''))):
                    data['operation_name']=payload['operationName']
            except (ValueError,TypeError):pass
        if status is not None:data['status']=status
        if blocked:data['blocked_read_only']=True
        key=json.dumps(endpoint(request.url),sort_keys=True)+request.method+data.get('operation_name','')
        seen[key]=dict(seen.get(key,{}),**data)
    def route(r):
        request=r.request
        blocked=request.method not in ('GET','HEAD')
        note(request,blocked=blocked)
        if blocked or request.resource_type in ('image','media','font') or (request.is_navigation_request() and urlsplit(request.url).hostname!=host):
            r.abort()
        else:r.continue_()
    page.route('**/*',route)
    page.on('response',lambda response:note(response.request,response.status))
    try:
        response=page.goto(url,wait_until='domcontentloaded',timeout=16000)
        if response and response.status==200:
            page.wait_for_timeout(1800)
            record['browser']=page_info(page.content(),url)|{'http_status':200}
            if record.get('load_more'):
                button=page.get_by_role('button',name=re.compile(r'(?:12 )?weitere Produkte anzeigen|mehr Produkte anzeigen',re.I))
                if button.count()==1:
                    try:
                        button.click(timeout=4000)
                        page.wait_for_timeout(1200)
                        record['load_more_observed']=True
                    except Exception as exc:
                        record['load_more_error']=type(exc).__name__
        else:record['browser']={'status':'unavailable','http_status':response.status if response else None}
    except Exception as e:record['browser']={'status':'unavailable','reason':type(e).__name__}
    finally:
        record['network']=list(seen.values())[:35]
        context.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--http-only',action='store_true');parser.add_argument('--ids',default='')
    parser.add_argument('--output',default='public-interface-audit.json');args=parser.parse_args()
    targets=json.loads(Path('config/public-interface-targets.json').read_text())
    if args.ids:targets=[t for t in targets if t['id'] in args.ids.split(',')]
    with ThreadPoolExecutor(max_workers=4) as pool:
        rows=list(pool.map(http_probe,targets))
    if not args.http_only:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            for row in rows:
                if row.get('browser_check'):browser_probe(browser,row)
                print('PUBLIC_INTERFACE '+json.dumps({k:v for k,v in row.items() if k not in ('network','public_query')},ensure_ascii=False),flush=True)
            browser.close()
    out={'checked_at':datetime.now(timezone.utc).isoformat(), 'scope':'public read-only, no cart writes or authentication', 'sources':rows}
    Path(args.output).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    for row in rows:
        print(json.dumps({'id':row['id'],'http':row['http']['status'],'browser':row.get('browser',{}).get('status'),
                          'network_requests':len(row.get('network',[]))}),flush=True)

if __name__=='__main__':main()
