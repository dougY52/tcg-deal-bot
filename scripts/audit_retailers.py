"""Read-only retailer audit. No credentials, carts, Discord or bot state writes."""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from tcg_bot.http import Client
from tcg_bot.web_sources import Document, structured_products, mms_state, walk_json

def inspect(body):
    doc=Document(body)
    result={"titles":[n.text().strip()[:200] for n in doc.root.walk() if n.tag in ("title","h1")],
            "products":structured_products(doc)[:2],
            "buttons":[{"text":n.text().strip()[:160],"attrs":n.attrs} for n in doc.root.walk()
                       if n.tag=="button" and re.search(r"warenkorb|cart|vorbestell|abhol|verfügbar",n.text(),re.I)][:8],
            "forms":[n.attrs for n in doc.root.walk() if n.tag=="form"][:5]}
    result["products"]=[{k:p.get(k) for k in ("@type","name","sku","gtin13","url","offers")} for p in result["products"]]
    try:
        state=mms_state(body)
        result["mms"]=[{k:d.get(k) for k in ("productAggregate","cofrProductAggregate")} for d in walk_json(state)
                       if "productAggregate" in d and "cofrProductAggregate" in d][:1]
        # Descriptions/assets are not useful in diagnostic output.
        for row in result["mms"]:
            p=row.get("productAggregate",{}).get("product",{})
            row["productAggregate"]={"product":{k:p.get(k) for k in ("id","title","ean","language")}}
    except Exception as e:
        result["mms_error"]=type(e).__name__
    result["details"]=[n.text().strip()[:3000] for n in doc.root.walk() if n.tag=="main"][:1]
    result["product_attributes"]=[n.attrs for n in doc.root.walk() if any(re.search(r"product|article|sku|availability",k,re.I) for k in n.attrs)][:30]
    result["tcg_links"]=[{"name":p.get("name"),"url":p.get("url")} for p in structured_products(doc)
                         if re.search(r"pok.mon.*(?:top.trainer|booster|kollektion|display|tin.box)",p.get("name",""),re.I)][:10]
    result["stock_text"]=[m.group(0) for m in re.finditer(r".{0,70}(?:keine Lieferung|nicht lieferbar|lieferbar|ausverkauft|vorrätig|sold out|Client Challenge).{0,90}",doc.root.text(),re.I)][:8]
    return result

def main():
    from playwright.sync_api import sync_playwright
    targets=json.loads(Path("config/retailer-audit.json").read_text())
    client=Client()
    output=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        for name,url in targets:
            record={"retailer":name,"url":url}
            # Check policy before browser requests too; never bypass a challenge.
            try:
                client.deadline=time.monotonic()+40
                client.check_allowed(url)
                body=client.raw(url)
                record["http"]=inspect(body)
            except Exception as e:
                record["http_error"]=str(e)[:120] if type(e).__name__=="FetchError" else type(e).__name__
                output.append(record)
                print("RETAILER_AUDIT "+json.dumps(record,ensure_ascii=False),flush=True)
                continue
            context=browser.new_context(locale="de-DE",service_workers="block")
            page=context.new_page()
            try:
                response=page.goto(url,wait_until="domcontentloaded",timeout=20000)
                record["browser_status"]=response.status if response else None
                if response and response.status==200 and urlsplit(page.url).hostname==urlsplit(url).hostname:
                    page.wait_for_timeout(1500)
                    record["browser"]=inspect(page.content())
            except Exception as e:
                record["browser_error"]=type(e).__name__
            finally:
                context.close()
            output.append(record)
            print("RETAILER_AUDIT "+json.dumps(record,ensure_ascii=False),flush=True)
            if name=="mueller":
                for link in record.get("http",{}).get("tcg_links",[])[:3]:
                    try:
                        client.deadline=time.monotonic()+25
                        detail={"retailer":"mueller-detail","url":link["url"],"http":inspect(client.text(link["url"]))}
                        print("RETAILER_AUDIT "+json.dumps(detail,ensure_ascii=False),flush=True)
                        output.append(detail)
                    except Exception as e:
                        print("DETAIL_ERROR "+(str(e)[:120] if type(e).__name__=="FetchError" else type(e).__name__),flush=True)
        browser.close()
    Path("retailer-audit-report.json").write_text(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
