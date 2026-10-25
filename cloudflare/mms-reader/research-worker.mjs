// Temporary, authenticated research only. No production alert integration.
import {githubAuthorized} from './worker.mjs';
import targets from '../../research/free-cloud-targets-2026-10-25.json';
const pages = new Set(targets.map(t=>t.url));
const robots = new Set(targets.map(t=>new URL(t.url).origin+'/robots.txt'));
export default {
  async fetch(request, env) {
    const headers={'Cache-Control':'no-store'};
    if (!env.AUDIT_EXPIRES || Date.now()>Date.parse(env.AUDIT_EXPIRES))
      return new Response('Audit expired',{status:410,headers});
    const u=new URL(request.url), token=request.headers.get('Authorization')||'';
    if (!token.startsWith('Bearer ') || !await githubAuthorized(token.slice(7),env,u.origin))
      return new Response('Unauthorized',{status:401,headers});
    const target=u.searchParams.get('url'), mode=u.searchParams.get('mode')||'http';
    if(request.method!=='GET'||u.pathname!=='/read'||(!pages.has(target)&&!robots.has(target)))
      return new Response('Unsupported target',{status:400,headers});
    try {
      let response;
      if(mode==='browser' && target==='https://www.pokemoncenter.com/en-de') {
        response=await env.BROWSER.quickAction('content',{
          url:target,gotoOptions:{waitUntil:'networkidle2',timeout:15000},
          rejectResourceTypes:['image','media','font'],
        });
      } else if(mode==='http') {
        response=await fetch(target,{redirect:'manual',signal:AbortSignal.timeout(15000),
          headers:{'User-Agent':'TCGRetailWatch/1.0'},cf:{cacheTtl:0}});
      } else return new Response('Unsupported mode',{status:400,headers});
      const body=await response.text();
      if(body.length>12000000)return new Response('Too large',{status:502,headers});
      return Response.json({url:target,mode,status:response.status,body,fetched_at:Date.now()/1000},{headers});
    } catch(e) {
      return Response.json({url:target,mode,status:0,error:e.name,body:'',fetched_at:Date.now()/1000},{headers});
    }
  }
};
