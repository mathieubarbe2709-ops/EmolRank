// Petits utilitaires DOM. Tout le texte passe par textContent : aucun pseudo n'est interprété comme du HTML.
const SVG = 'http://www.w3.org/2000/svg';

export function h(tag, props = {}, ...children) {
  const el = tag.startsWith('svg:') ? document.createElementNS(SVG, tag.slice(4)) : document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === 'class') el.setAttribute('class', v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'text') el.textContent = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const c of children.flat()) {
    if (c == null || c === false) continue;
    el.append(c.nodeType ? c : document.createTextNode(String(c)));
  }
  return el;
}

const dateFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Paris' });
const shortFmt = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', timeZone: 'Europe/Paris' });
const dayFmt = new Intl.DateTimeFormat('fr-FR', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Europe/Paris' });
export const fmtDay = (ts) => (ts ? dayFmt.format(new Date(ts * 1000)) : '?');
export const fmtDate = (ts) => (ts ? dateFmt.format(new Date(ts * 1000)) : 'date inconnue');
export const fmtShort = (ts) => (ts ? shortFmt.format(new Date(ts * 1000)) : '?');
export const signed = (n) => (n > 0 ? `+${n.toFixed(1)}` : n < 0 ? `−${Math.abs(n).toFixed(1)}` : '0');
