"""Replay observed public catalog GET queries without cookies/auth or cart writes."""
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from urllib.error import HTTPError
from tcg_bot.http import Client, NoRedirect, UA
from tcg_bot.web_sources import walk_json


def probe(spec):
    host=spec['host'];q=spec['query']
    assert host in ('www.mediamarkt.de','www.saturn.de')
    assert q['operation'] in ('CategoryV4','SearchV4')
    url='https://'+host+'/api/v1/graphql?'+urlencode({
        'operationName':q['operation'],'variables':json.dumps(q['variables'],separators=(',',':')),
        'extensions':json.dumps(q['extensions'],separators=(',',':'))})
    out={'host':host,'operation':q['operation'],'inventory_confirmed':False}
    client=Client();client.deadline=time.monotonic()+25
    try:
        client.check_allowed(url)
        allowed={'x-operation','x-mms-salesline','x-mms-country','x-mms-language','x-cacheable',
                 'apollographql-client-name','apollographql-client-version'}
        headers={k:v for k,v in q['headers'].items() if k in allowed}
        headers.update({'Accept':'application/json','Content-Type':'application/json','User-Agent':UA,'Referer':'https://'+host+'/'})
        with build_opener(NoRedirect()).open(Request(url,headers=headers),timeout=15) as response:
            out['http_status']=response.status
            data=response.read(3000001)
            if len(data)>3000000:raise ValueError('response_limit')
            doc=json.loads(data)
        out['data_keys']=list((doc.get('data') or {}).keys())[:20]
        out['error_codes']=[str(e.get('extensions',{}).get('code','unknown'))[:70] for e in doc.get('errors',[])][:4]
        out['product_count']=sum('productAggregate' in d for d in walk_json(doc))
        out['status']='catalog_json_received' if out['data_keys'] and not out['error_codes'] else 'graphql_error'
    except HTTPError as e:out.update(status='unavailable',http_status=e.code)
    except Exception as e:out.update(status='unavailable',reason=type(e).__name__)
    finally:client.close()
    return out


def main():
    specs=json.loads(Path('config/public-mms-queries.json').read_text())
    rows=[]
    for spec in specs:
        row=probe(spec);rows.append(row);print('PUBLIC_MMS_QUERY '+json.dumps(row),flush=True)
        time.sleep(2)
    Path('public-mms-query-audit.json').write_text(json.dumps(rows,indent=2)+'\n')

if __name__=='__main__':main()
