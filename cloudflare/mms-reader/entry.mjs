import {DurableObject} from 'cloudflare:workers';
import reader, {githubAuthorized} from './worker.mjs';
import {CardPalRelay, safeError} from './cardpal-relay.mjs';

export class CardPalOwner extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.relay = new CardPalRelay(ctx.storage); }
  async configure(value) { return this.relay.configure(value); }
  async status() { return this.relay.status(); }
  async discovery() { return this.relay.discovery(); }
  async alarm() { await this.relay.cycle(); }
}
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith('/cardpal/')) return reader.fetch(request, env, ctx);
    const headers = {'Cache-Control': 'no-store'};
    const bearer = request.headers.get('Authorization') || '';
    if (url.search || !bearer.startsWith('Bearer ') ||
        !await githubAuthorized(bearer.slice(7), env, url.origin))
      return Response.json({error: 'UNAUTHORIZED'}, {status: 401, headers});
    const owner = env.CARDPAL_OWNER.getByName(env.GITHUB_OWNER_ID);
    try {
      if (request.method === 'GET' && url.pathname === '/cardpal/status')
        return Response.json(await owner.status(), {headers});
      if (request.method === 'GET' && url.pathname === '/cardpal/discovery')
        return Response.json(await owner.discovery(), {headers});
      if (request.method === 'POST' && url.pathname === '/cardpal/configure') {
        const body = await request.text();
        if (body.length > 10000) return new Response('Too large', {status: 413, headers});
        return Response.json(await owner.configure(JSON.parse(body)), {headers});
      }
      return new Response('Not found', {status: 404, headers});
    } catch (error) { return Response.json({error: safeError(error)}, {status: 400, headers}); }
  }
};
