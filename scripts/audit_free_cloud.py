"""One-off public-source research; no alert/state mutations or credentials in output."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener
from urllib.robotparser import RobotFileParser
from tcg_bot.cloud_reader import github_token
from tcg_bot.http import NoRedirect, robots_allowed
from scripts.audit_public_interfaces import page_info

ENDPOINT='https://tcg-retailer-research.tcg-deal-bot-dougy52.workers.dev/read'


def run():
    token=github_token(urlsplit(ENDPOINT)._replace(path='').geturl(),10)
    def fetch(url, mode='http'):
        request=Request(ENDPOINT+'?'+urlencode({'url':url,'mode':mode}),
            headers={'Authorization':'Bearer '+token,'User-Agent':'TCGRetailWatch/1.0'})
        with build_opener(NoRedirect()).open(request,timeout=35) as response:
            raw=response.read(24000001)
            if len(raw)>24000000: raise ValueError('Response limit')
            data=json.loads(raw)
        if data.get('url')!=url or not -5<=time.time()-data.get('fetched_at',0)<=60:
            raise ValueError('Response mismatch/stale')
        return data
    targets=json.loads(Path('research/free-cloud-targets-2026-10-25.json').read_text())
    groups={}
    for target in targets:groups.setdefault(urlsplit(target['url']).netloc,[]).append(target)
    def probe_group(items):
        result=[]
        origin='https://'+urlsplit(items[0]['url']).netloc
        try:
            r=fetch(origin+'/robots.txt')
            if r['status']==404:body='User-agent: *\nAllow: /'
            elif r['status']==200 and not r['body'].lstrip().startswith('<'):body=r['body']
            else:raise ValueError('Robots unavailable HTTP '+str(r['status']))
            parser=RobotFileParser();parser.parse(body.splitlines())
            delay=max(1,parser.crawl_delay('TCGRetailWatch') or 0)
            if delay>10:raise ValueError('Required delay exceeds audit budget')
        except Exception as exc:
            return [dict(t,result='policy_unconfirmed',reason=str(exc)[:100] if isinstance(exc,ValueError) else type(exc).__name__,inventory_confirmed=False) for t in items]
        for t in items:
            record=dict(t,inventory_confirmed=False)
            try:
                if not robots_allowed(body,t['url']):
                    record['result']='robots_disallowed';result.append(record);continue
                time.sleep(delay)
                response=fetch(t['url'])
                record.update(http_status=response['status'],http=page_info(response['body'],t['url']) if response['status']==200 else {'status':'unavailable'})
                if t['id']=='pokemoncenter-de' and parser.can_fetch('CloudflareBrowserRendering',t['url']):
                    time.sleep(delay);start=time.monotonic()
                    rendered=fetch(t['url'],'browser')
                    raw=rendered['body']
                    try:
                        obj=json.loads(raw)
                        if isinstance(obj,dict):raw=obj.get('result',raw)
                        if not isinstance(raw,str):raw=json.dumps(raw)
                    except ValueError:pass
                    record['cloud_browser']={'status':rendered['status'],'seconds':round(time.monotonic()-start,2),
                        'page':page_info(raw,t['url']) if rendered['status']==200 else {'status':'unavailable','detail':raw[:300]}}
            except Exception as exc:record['error']=type(exc).__name__
            result.append(record)
        return result
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=[r for group in pool.map(probe_group,groups.values()) for r in group]
    output={'checked_at':datetime.now(timezone.utc).isoformat(),'route':'GitHub Actions -> Cloudflare',
            'discord_sent':False,'inventory_confirmed':False,'results':results}
    Path('free-cloud-audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
    for row in results:print('FREE_CLOUD_AUDIT '+json.dumps(row,ensure_ascii=False))


if __name__=='__main__':run()
