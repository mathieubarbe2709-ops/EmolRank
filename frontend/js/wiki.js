// Page Wiki d'un joueur : infobox (personnage principal), texte éditable, tableau des résultats.
import { api } from './api.js';
import { h, fmtDay, fmtDate } from './dom.js';
import { sparkline } from './views.js';

const LEGEND = [
  ['gold', '1er'], ['silver', '2e'], ['bronze', '3e'], ['orange', '4e'],
  ['lightblue', '5-6e'], ['darkblue', '7-8e'], ['purple', '9e et au-delà'],
];
const profileLink = (id, tag) => h('a', { class: 'wlink', href: `#wiki=${encodeURIComponent(id)}`, text: tag });

function charIcon(c, size = 28) {
  return c.icon ? h('img', { src: `assets/characters/${c.icon}.png`, alt: c.name, width: size, height: size, loading: 'lazy' })
                : h('span', { class: 'char__ph', style: `width:${size}px;height:${size}px`, title: c.name }, '?');
}

// ---------------------------------------------------------------- infobox (à gauche)
function infobox(page, player) {
  const s = page.stats, c = page.main_character;
  const art = c
    ? h('div', { class: 'infobox__char' },
        c.icon ? h('img', { src: `assets/characters/${c.icon}.png`, alt: c.name, width: 200, height: 200 })
               : h('div', { class: 'char__ph big', title: c.name }, '?'),
        h('p', { class: 'infobox__charname', text: c.name }),
        h('p', { class: 'muted', text: `Personnage principal · ${c.games} games` }))
    : h('div', { class: 'infobox__char' }, h('div', { class: 'char__ph big' }, '?'),
        h('p', { class: 'infobox__charname', text: 'Aucun personnage renseigné' }));
  const rows = [
    ['Classement', `#${s.rank}`], ['ELO', s.elo], ['Bilan sets', `${s.wins} V – ${s.losses} D`],
    ['Tournois', `${s.tournaments_played} / ${s.tournaments_total}`],
    ['Meilleure place', s.best_place ? (s.best_place === 1 ? '1er' : `${s.best_place}e`) : '—'],
  ];
  return h('aside', { class: 'infobox panel' },
    h('div', { class: 'panel__head' }, h('h2', { text: 'Fiche joueur' })),
    art,
    h('dl', { class: 'infobox__stats' }, rows.flatMap(([k, v]) => [h('dt', { text: k }), h('dd', { text: v })])),
    h('div', { class: 'infobox__spark' }, h('h3', { text: 'Évolution de l\'ELO' }), sparkline(player.history, -1)));
}

// ---------------------------------------------------------------- texte éditable
function textSection(page, toast) {
  let current = page.text, isDefault = page.is_default, updatedAt = page.updated_at, dirty = false;
  const body = h('div', { class: 'panel__body' });
  const editBtn = h('button', { class: 'btn btn--ghost', type: 'button', text: 'Modifier' });
  const guard = (e) => { if (dirty) { e.preventDefault(); e.returnValue = ''; } };
  window.addEventListener('beforeunload', guard);

  function renderView() {
    dirty = false; editBtn.hidden = false;
    body.replaceChildren(...[
      h('div', { class: 'wiki__text', text: current }),
      isDefault && h('p', { class: 'muted hint', text: 'Texte par défaut : cliquez sur « Modifier » pour ajouter des informations.' }),
      updatedAt && h('p', { class: 'muted hint', text: `Dernière modification : ${fmtDate(updatedAt)}` }),
    ].filter(Boolean));
  }

  function renderEdit() {
    editBtn.hidden = true;
    const area = h('textarea', { class: 'editor', rows: 10, maxlength: 20000, 'aria-label': 'Texte de la page Wiki' });
    area.value = current;
    const status = h('span', { class: 'muted', 'aria-live': 'polite' });
    const save = h('button', { class: 'btn', type: 'button', text: 'Enregistrer' });
    const cancel = h('button', { class: 'btn btn--ghost', type: 'button', text: 'Annuler' });
    const reset = h('button', { class: 'btn btn--ghost btn--danger', type: 'button', text: 'Rétablir le texte par défaut' });
    area.addEventListener('input', () => { dirty = area.value !== current; status.textContent = `${area.value.length} / 20000`; });
    area.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') save.click(); });

    async function persist(text) {
      save.disabled = reset.disabled = true; status.textContent = 'Enregistrement…';
      try {
        // Le texte par défaut n'est pas stocké : il suit le pseudo du joueur s'il change.
        const saved = await api.saveWiki(page.player_id, text.trim() === page.default_text.trim() ? '' : text);
        current = saved.text; isDefault = saved.is_default; updatedAt = saved.updated_at;
        renderView(); toast('Page enregistrée');
      } catch (err) {
        status.textContent = `Échec : ${err.message}`; save.disabled = reset.disabled = false;
      }
    }
    save.onclick = () => persist(area.value);
    reset.onclick = () => { if (confirm('Supprimer le texte personnalisé de cette page ?')) persist(''); };
    cancel.onclick = () => { if (!dirty || confirm('Abandonner les modifications ?')) renderView(); };
    body.replaceChildren(area, h('div', { class: 'editor__bar' }, save, cancel, reset, status));
    area.focus(); area.setSelectionRange(area.value.length, area.value.length);
  }

  editBtn.onclick = renderEdit;
  renderView();
  return h('section', { class: 'panel', 'aria-labelledby': 'wikiTextTitle' },
    h('div', { class: 'panel__head' }, h('h2', { id: 'wikiTextTitle', text: 'Présentation' }), editBtn), body);
}

// ---------------------------------------------------------------- tableau des résultats
function opponentCell(p) {
  const pl = p.placement, won = pl.kind === 'final' && pl.place === 1;
  const note = won ? `Grande finale${pl.reset ? ' (reset)' : ''} gagnée contre`
                   : pl.kind === 'final' ? `Grande finale${pl.reset ? ' (reset)' : ''} perdue contre` : `Éliminé (${pl.round}) par`;
  return h('td', { class: 'res__opp' }, h('small', { class: 'muted', text: note }),
    pl.opponent.player_id ? profileLink(pl.opponent.player_id, pl.opponent.tag) : h('span', { text: pl.opponent.tag || '—' }));
}

function characterCell(list) {
  if (!list.length) return h('td', { class: 'res__char' }, h('span', { class: 'muted', text: '—', title: 'Personnage non renseigné' }));
  return h('td', { class: 'res__char' }, list.map((c) => h('span', { class: 'chip', title: c.name }, charIcon(c), h('span', { text: c.name }))));
}

function resultsSection(page) {
  const rows = page.results.map((r) => {
    const pl = r.placement;
    const tr = h('tr', {},
      h('td', { class: 'nowrap', text: fmtDay(r.date) }),
      h('td', {}, h('a', { class: 'wlink', href: r.url, target: '_blank', rel: 'noopener noreferrer', text: r.tournament })));
    if (!pl) {
      tr.append(h('td', { class: 'pl pl-none', text: 'En cours' }), h('td', { class: 'muted', colspan: 3, text: 'Résultat final non disponible' }));
    } else {
      tr.append(h('td', { class: `pl pl-${pl.band}`, text: pl.label }), opponentCell(r),
        h('td', { class: 'nowrap', text: pl.score }), characterCell(pl.opponent_characters));
    }
    return tr;
  });
  const table = rows.length
    ? h('div', { class: 'tablewrap' }, h('table', { class: 'results' },
        h('thead', {}, h('tr', {}, ['Date', 'Tournoi', 'Place', 'Adversaire', 'Score', 'Personnage adverse'].map((t) => h('th', { text: t })))),
        h('tbody', {}, rows)))
    : h('p', { class: 'muted panel__body', text: 'Aucun résultat.' });
  return h('section', { class: 'panel', 'aria-labelledby': 'wikiResTitle' },
    h('div', { class: 'panel__head' }, h('h2', { id: 'wikiResTitle', text: 'Résultats des tournois' })), table,
    h('ul', { class: 'legend' }, LEGEND.map(([b, t]) => h('li', {}, h('i', { class: `pl-${b}` }), t))));
}

// ---------------------------------------------------------------- point d'entrée
export async function renderWiki(root, playerId, { toast }) {
  root.replaceChildren(h('p', { class: 'empty', text: 'Chargement…' }));
  const [page, player] = await Promise.all([api.wiki(playerId), api.player(playerId)]);
  document.title = `${page.tag} — Wiki · DUC E-Sport`;
  root.replaceChildren(h('div', { class: 'wiki' },
    infobox(page, player),
    h('article', { class: 'wiki__main' },
      h('header', { class: 'wiki__head' }, h('p', { class: 'eyebrow', text: 'Wiki joueur' }), h('h1', { text: page.tag })),
      textSection(page, toast), resultsSection(page))));
}
