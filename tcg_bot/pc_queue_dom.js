// Read only the rendered public page and its currently embedded primary frame.
// No requests, clicks, cookie access, forms, or verification interactions.
await new Promise(resolve => setTimeout(resolve, 2000));
const capture = {version: 1, home_path: location.pathname, documents: []};
const allowedHome = location.origin === 'https://www.pokemoncenter.com' &&
  ['/de-de', '/de-de/', '/en-de', '/en-de/'].includes(location.pathname);
const ignored = new Set(['SCRIPT', 'STYLE', 'TEMPLATE', 'NOSCRIPT', 'NAV',
  'FOOTER', 'SELECT', 'SVG', 'IMG', 'IFRAME', 'INPUT', 'TEXTAREA']);
const blockTags = new Set(['H1', 'H2', 'H3', 'P', 'DIV', 'SPAN', 'STRONG',
  'SECTION', 'ASIDE', 'MAIN', 'BR', 'UL', 'LI']);
function shown(element) {
  const style = element.ownerDocument.defaultView.getComputedStyle(element);
  return !element.hidden && element.getAttribute('aria-hidden') !== 'true' &&
    style.display !== 'none' && style.visibility !== 'hidden' &&
    style.visibility !== 'collapse' && style.opacity !== '0';
}
function captureDocument(doc, kind) {
  if (!doc.body) return;
  let count = 0, characters = 0;
  function copy(node) {
    if (++count > 10000) throw new Error('bounded capture');
    if (node.nodeType === Node.TEXT_NODE) {
      characters += node.textContent.length;
      if (characters > 120000) throw new Error('bounded capture');
      return doc.createTextNode(node.textContent);
    }
    if (node.nodeType !== Node.ELEMENT_NODE || ignored.has(node.tagName) || !shown(node)) return null;
    const out = doc.createElement(blockTags.has(node.tagName) ? node.tagName.toLowerCase() : 'span');
    for (const child of node.childNodes) {
      const item = copy(child);
      if (item) out.appendChild(item);
    }
    return out;
  }
  const body = copy(doc.body);
  const title = doc.createElement('title');
  title.textContent = doc.title;
  if (body) capture.documents.push({kind, html: title.outerHTML + body.outerHTML});
}
if (allowedHome) {
  try { captureDocument(document, 'home'); } catch (_) { capture.home_error = true; }
  const frames = Array.from(document.querySelectorAll('iframe#main-iframe')).filter(frame => {
    for (let node = frame; node; node = node.parentElement) if (!shown(node)) return false;
    return true;
  });
  capture.primary_frames = frames.length;
  if (frames.length === 1) {
    try {
      const expected = new URL(frames[0].getAttribute('src'), location.href);
      const actual = new URL(frames[0].contentWindow.location.href);
      if (expected.origin === location.origin && expected.pathname === '/_Incapsula_Resource' &&
          expected.search && actual.href === expected.href && !expected.hash) {
        captureDocument(frames[0].contentDocument, 'primary_frame');
      }
    } catch (_) { capture.frame_error = true; }
  }
}
// Return a bounded snapshot in a non-executable result element. It contains no
// attributes, resource/session URLs, scripts, hidden text, cookies or XHRs.
document.querySelectorAll('#tcg-queue-visible-v1').forEach(node => node.remove());
const marker = document.createElement('script');
marker.id = 'tcg-queue-visible-v1';
marker.type = 'application/json';
marker.textContent = JSON.stringify(capture).replace(/</g, '\\u003c');
document.documentElement.appendChild(marker);
