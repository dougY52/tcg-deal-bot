"""Read-only cloud diagnosis and new-shop live validation; never sends alerts."""
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen
from tcg_bot.__main__ import load_config, ADAPTERS
from tcg_bot.http import Client
from tcg_bot import preorders

def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None

def emit(label, data):
    print(label+' '+json.dumps(data, ensure_ascii=False), flush=True)

def production_state():
    try:
        subprocess.run(['git','fetch','--no-tags','origin','refs/heads/bot-state'],
                       check=True, capture_output=True, timeout=45)
        body = subprocess.run(['git','show','FETCH_HEAD:state.json'],check=True,
                              capture_output=True, timeout=20).stdout
        state=json.loads(body)
        targets=state.get('fast_targets',{})
        alerts=[r['last_alert'] for r in state.get('preorder_products',{}).values() if r.get('last_alert')]
        emit('PRODUCTION_STATE', {'fast_last_run':stamp(state.get('fast_last_run')),
            'targets':len(targets), 'targets_by_shop':dict(Counter(r['offer']['shop'] for r in targets.values())),
            'targets_by_status':dict(Counter(str(r['offer'].get('available')) for r in targets.values())),
            'last_delivered':stamp(max((a['at'] for a in alerts), default=0)),
            'delivered_products':len(alerts), 'cooldowns':len(state.get('http_backoff',{})),
            'catalog_last_checks':{k:stamp(v) for k,v in state.get('fast_catalog_checks',{}).items()}})
    except Exception as exc:
        emit('PRODUCTION_STATE_ERROR',{'type':type(exc).__name__})
    # Read metadata only; token is never logged or written to a file.
    token=os.environ.get('GH_TOKEN')
    if not token:
        return
    try:
        req=Request('https://api.github.com/repos/dougY52/tcg-deal-bot/actions/runs?per_page=40',
                    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json'})
        with urlopen(req,timeout=20) as response:
            runs=json.load(response)['workflow_runs']
        emit('PRODUCTION_RUNS',[{k:r.get(k) for k in ('id','name','path','event','status','conclusion','created_at','run_started_at')}
                               for r in runs if r.get('event') in ('schedule','workflow_dispatch')][:8])
    except Exception as exc:
        emit('PRODUCTION_RUNS_ERROR',{'type':type(exc).__name__})
    for path in Path('.github/workflows').glob('*.yml'):
        text=path.read_text()
        emit('WORKFLOW_TRIGGER',{'path':str(path),'cron':[l.strip() for l in text.splitlines() if 'cron:' in l]})

def new_shops():
    cfg=load_config('config/config.json')
    for shop in cfg['shops']:
        if shop['id'] not in ('ani-kuni','daesu-cards'):
            continue
        client=Client()
        client.deadline=time.monotonic()+55
        try:
            rows,notes=ADAPTERS[shop['adapter']](shop,client)
            relevant=[]
            for row in rows:
                obj,reason=preorders.identity(row,cfg)
                if obj and float(row['price'])<=200:
                    relevant.append(row)
            relevant.sort(key=lambda o: (not o['available'], 'FB11' not in o['title'].upper(), o['price']))
            checks=[]
            for row in relevant[:3]:
                try:
                    live,reason=preorders.live(row,shop,client,time.time())
                    checks.append({'title':row['title'],'url':row['url'],'reason':reason,
                                   'price':live.get('price') if live else None,
                                   'status':live.get('availability_status') if live else None,
                                   'cart':live.get('add_to_cart_available') if live else None})
                except Exception as exc:
                    checks.append({'title':row['title'],'reason':type(exc).__name__})
            emit('NEW_SHOP_AUDIT',{'shop':shop['id'],'variants':len(rows),'relevant_under_200':len(relevant),'notes':notes,'live_checks':checks})
        except Exception as exc:
            emit('NEW_SHOP_ERROR',{'shop':shop['id'],'type':type(exc).__name__})
        finally:
            client.close()

production_state()
new_shops()
