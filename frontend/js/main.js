import { api } from './api.js';
import { h } from './dom.js';
import { renderWiki } from './wiki.js';
import { chronology, detail, row, rules, timeline, tournamentMeta } from './views.js';

const $ = (id) => document.getElementById(id);
const state = { scrollY: 0, overview: null, index: 0, ranking: null, openId: null, filter: '', onlyHere: false };
const rankingCache = new Map();
const playerCache = new Map();

function toast(msg, ms = 5000) {
  const el = $('toast');
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast.t); toast.t = setTimeout(() => { el.hidden = true; }, ms);
}

const hashIndex = () => { const m = location.hash.match(/t=(\d+)/); return m ? Number(m[1]) : null; };

async function loadOverview(keepIndex = true) {
  rankingCache.clear(); playerCache.clear();
  state.overview = await api.overview();
  const n = state.overview.tournaments.length;
  $('chrono').replaceChildren(chronology(state.overview.chronology, state.overview.missing, state.overview.problems));
  $('rules').replaceChildren(rules(state.overview.rules));
  if (!n) return renderEmpty();
  const wanted = hashIndex() ?? (keepIndex ? state.index : n - 1);
  await select(Math.min(Math.max(wanted, 0), n - 1));
}

function renderEmpty() {
  $('tourName').textContent = 'Aucun tournoi';
  $('tourMeta').textContent = '';
  $('timeline').replaceChildren(); $('rows').replaceChildren(); $('movers').replaceChildren();
  const empty = $('empty'); empty.hidden = false;
  empty.replaceChildren(h('span', {}, 'Ajoutez des liens start.gg dans '), h('code', { text: 'tournaments.txt' }),
    h('span', {}, ', puis cliquez sur « Actualiser ».'));
  $('prevBtn').disabled = $('nextBtn').disabled = true;
}

async function select(index) {
  state.index = index; state.openId = null;
  history.replaceState(null, '', `#t=${index}`);
  if (!rankingCache.has(index)) rankingCache.set(index, await api.ranking(index));
  state.ranking = rankingCache.get(index);
  renderTournament();
}

function renderTournament() {
  const { tournaments } = state.overview, t = tournaments[state.index];
  $('tourName').textContent = t.name;
  $('tourMeta').textContent = tournamentMeta(t);
  $('tourEyebrow').textContent = `Classement après le tournoi ${state.index + 1} / ${tournaments.length}`;
  $('backBtn').href = `#t=${state.index}`;
  $('prevBtn').disabled = state.index === 0;
  $('nextBtn').disabled = state.index === tournaments.length - 1;
  $('timeline').replaceChildren(...timeline(tournaments, state.index, select));
  $('timeline').querySelector('[aria-current="true"]')?.scrollIntoView({ block: 'nearest', inline: 'center' });
  renderRows(); renderMovers();
}

function visibleEntries() {
  const q = state.filter.trim().toLowerCase();
  return state.ranking.entries.filter((e) => (!state.onlyHere || e.played_here) && (!q || e.tag.toLowerCase().includes(q)));
}

function renderRows() {
  const entries = visibleEntries();
  const rows = $('rows');
  rows.replaceChildren(...entries.map((e) => row(e, { open: e.player_id === state.openId, onToggle: () => toggle(e.player_id) })));
  $('empty').hidden = entries.length > 0;
  if (!entries.length) $('empty').textContent = 'Aucun joueur ne correspond.';
  if (state.openId) attachDetail(state.openId);
}

async function toggle(id) {
  state.openId = state.openId === id ? null : id;
  renderRows();
}

async function attachDetail(id) {
  const li = $('rows').querySelector(`[data-id="${CSS.escape(id)}"]`);
  if (!li) return;
  try {
    if (!playerCache.has(id)) playerCache.set(id, await api.player(id));
    if (state.openId !== id) return;
    li.querySelector('.detail')?.remove();
    li.append(detail(playerCache.get(id), state.index));
  } catch (err) { toast(err.message); }
}

function renderMovers() {
  const top = state.ranking.entries.filter((e) => e.played_here && !e.is_new && e.elo_delta > 0)
    .sort((a, b) => b.elo_delta - a.elo_delta).slice(0, 5);
  $('movers').replaceChildren(...(top.length ? top.map((e) => h('li', {},
    h('span', { class: 'tag', text: e.tag }), h('span', { class: 'delta up', text: `+${e.elo_delta.toFixed(1)}` })))
    : [h('li', { class: 'muted', text: 'Aucune progression à afficher.' })]));
}

async function sync() {
  const btn = $('syncBtn'); btn.disabled = true; btn.textContent = 'Synchronisation…';
  try {
    const r = await api.sync(false);
    await loadOverview(true);
    const msg = `${r.fetched.length} nouveau(x) tournoi(s), ${r.cached.length} déjà en cache`;
    toast(r.errors.length ? `${msg} — ${r.errors[0]}` : msg, r.errors.length ? 9000 : 4000);
  } catch (err) { toast(err.message, 9000); } finally { btn.disabled = false; btn.textContent = 'Actualiser'; }
}

$('prevBtn').onclick = () => state.index > 0 && select(state.index - 1);
$('nextBtn').onclick = () => state.index < state.overview.tournaments.length - 1 && select(state.index + 1);
$('syncBtn').onclick = sync;
$('search').oninput = (e) => { state.filter = e.target.value; if (state.ranking) renderRows(); };
$('onlyHere').onchange = (e) => { state.onlyHere = e.target.checked; if (state.ranking) renderRows(); };
document.addEventListener('keydown', (e) => {
  if (e.target.matches('input, textarea') || !$('wikiView').hidden) return;
  if (e.key === 'ArrowLeft') $('prevBtn').click();
  if (e.key === 'ArrowRight') $('nextBtn').click();
});
// ---------------------------------------------------------------- routage par ancre : #t=<n> (classement) ou #wiki=<id>
const route = () => {
  const m = location.hash.match(/^#wiki=([A-Za-z0-9_-]+)/);
  return m ? { view: 'wiki', id: m[1] } : { view: 'ranking' };
};

async function applyRoute() {
  const r = route(), leaving = !$('rankingView').hidden;
  if (leaving && r.view === 'wiki') state.scrollY = window.scrollY;
  $('rankingView').hidden = r.view !== 'ranking';
  $('wikiView').hidden = r.view !== 'wiki';
  $('syncBtn').hidden = r.view === 'wiki';
  $('backBtn').hidden = r.view !== 'wiki';
  try {
    if (r.view === 'wiki') {
      window.scrollTo(0, 0);
      await renderWiki($('wikiView'), r.id, { toast });
      return;
    }
    document.title = 'Smash Ranking — Classement ELO';
    if (!state.overview) await loadOverview(false);
    else if (hashIndex() != null && hashIndex() !== state.index) await select(hashIndex());
    window.scrollTo(0, state.scrollY);
  } catch (err) {
    if (r.view === 'wiki') $('wikiView').replaceChildren(h('p', { class: 'empty', text: `Impossible d'afficher cette page : ${err.message}` }));
    else { $('tourName').textContent = 'Erreur'; }
    toast(err.message, 9000);
  }
}

window.addEventListener('hashchange', applyRoute);
applyRoute();
