// Composants de présentation (aucune logique métier : tout vient de l'API).
import { h, fmtDate, fmtShort, signed } from './dom.js';

export function characterCell(c) {
  if (!c) return h('div', { class: 'char' }, h('div', { class: 'char__ph', title: 'Aucun personnage renseigné' }, '?'), h('span', { text: '—' }));
  const icon = c.icon ? h('img', { src: `assets/characters/${c.icon}.png`, alt: c.name, loading: 'lazy', width: 36, height: 36 })
                      : h('div', { class: 'char__ph', title: c.name }, '?');
  return h('div', { class: 'char', title: `${c.name} — ${c.games} games` }, icon, h('span', { text: c.name }));
}

function rankChange(e) {
  if (e.is_new) return h('span', { class: 'chg new', title: 'Nouveau joueur' }, 'NEW');
  if (e.rank_change > 0) return h('span', { class: 'chg up', title: `+${e.rank_change} place(s)` }, `▲${e.rank_change}`);
  if (e.rank_change < 0) return h('span', { class: 'chg down', title: `${e.rank_change} place(s)` }, `▼${-e.rank_change}`);
  return h('span', { class: 'chg flat' }, '–');
}

export function row(e, { open, onToggle }) {
  const cls = e.elo_delta > 0 ? 'up' : e.elo_delta < 0 ? 'down' : 'none';
  const main = h('button', { class: 'row__main', type: 'button', 'aria-expanded': String(open), onclick: onToggle },
    h('span', { class: 'c-rank rank' },
      h('span', { class: `rank__n ${e.rank === 1 ? 'top1' : e.rank <= 3 ? 'top3' : ''}`, text: e.rank }), rankChange(e)),
    h('span', { class: 'c-player tag', text: e.tag }),
    h('span', { class: 'c-char' }, characterCell(e.main_character)),
    h('span', { class: 'c-elo elo', text: e.elo }),
    h('span', { class: `c-delta delta ${e.played_here ? cls : e.elo_delta ? 'down' : 'none'}`,
                text: e.played_here || e.elo_delta ? signed(e.elo_delta) : '·',
                title: e.played_here ? '' : 'Absent de ce tournoi : malus d\'inactivité' }),
    h('span', { class: 'c-wl num', text: `${e.wins}-${e.losses}` }),
    h('span', { class: 'c-t num', text: e.tournaments_played }));
  return h('li', { class: `row ${open ? 'is-open' : ''} ${e.played_here ? '' : 'is-away'}`, 'data-id': e.player_id }, main);
}

export function sparkline(history, currentIndex) {
  const W = 360, H = 130, P = { l: 34, r: 12, t: 12, b: 22 };
  const svg = h('svg:svg', { class: 'spark', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'Évolution de l\'ELO' });
  const elos = history.map((p) => p.elo);
  let lo = Math.min(...elos, 1000), hi = Math.max(...elos, 1000);
  if (hi - lo < 40) { hi += 20; lo -= 20; }
  const x = (i) => P.l + (history.length === 1 ? (W - P.l - P.r) / 2 : (i / (history.length - 1)) * (W - P.l - P.r));
  const y = (v) => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
  [lo, 1000, hi].forEach((v, i, arr) => {
    if (i && arr[i - 1] === v) return;
    svg.append(h('svg:line', { class: 'grid-l', x1: P.l, x2: W - P.r, y1: y(v), y2: y(v), 'stroke-dasharray': v === 1000 ? '3 3' : '' }),
               h('svg:text', { x: 2, y: y(v) + 3, text: Math.round(v) }));
  });
  svg.append(h('svg:polyline', { class: 'line', points: history.map((p, i) => `${x(i)},${y(p.elo)}`).join(' ') }));
  history.forEach((p, i) => svg.append(
    h('svg:circle', { class: `dot ${p.index === currentIndex ? 'cur' : ''}`, cx: x(i), cy: y(p.elo), r: p.index === currentIndex ? 5 : 3 },
      h('svg:title', {}, `${p.tournament} — ${p.elo} ELO (#${p.rank})`))));
  svg.append(h('svg:text', { x: P.l, y: H - 6, text: fmtShort(history[0].date) }),
             h('svg:text', { x: W - P.r, y: H - 6, 'text-anchor': 'end', text: fmtShort(history[history.length - 1].date) }));
  return svg;
}

export function detail(player, index) {
  const here = player.history.find((p) => p.index === index);
  const matches = here ? here.matches : [];
  const table = matches.length
    ? h('table', { class: 'matches' },
        h('thead', {}, h('tr', {}, ['Adversaire', 'Round', 'Score', 'ELO'].map((t) => h('th', { text: t })))),
        h('tbody', {}, matches.map((m) => h('tr', {},
          h('td', {}, h('span', { class: m.won ? 'w' : 'l', text: m.won ? 'V ' : 'D ' }), m.opponent),
          h('td', {}, h('span', { class: `pill ${m.bracket === 'losers' ? 'lb' : ''}`, text: m.bracket === 'losers' ? 'LB' : 'WB' }), ' ', m.round),
          h('td', { text: m.score }),
          h('td', { class: m.delta >= 0 ? 'delta up' : 'delta down', text: signed(m.delta) })))))
    : h('p', { class: 'muted', text: 'Pas de match dans ce tournoi.' });
  return h('div', { class: 'detail' },
    h('div', { class: 'detail__bar' },
      h('a', { class: 'btn', href: `#wiki=${encodeURIComponent(player.player_id)}` }, 'Voir la page Wiki')),
    h('div', {}, h('h3', { text: 'Évolution de l\'ELO' }), sparkline(player.history, index)),
    h('div', {}, h('h3', { text: 'Matchs de ce tournoi' }), table));
}

export function chronology(chrono, missing, problems) {
  const errors = chrono.issues.filter((i) => i.level === 'error');
  const cls = errors.length ? 'bad' : chrono.issues.length || missing.length || problems.length ? 'warn' : '';
  const label = errors.length ? `${errors.length} anomalie(s) bloquante(s)`
    : chrono.issues.length ? 'Ordre vérifié, avertissements' : 'Ordre chronologique vérifié';
  return h('div', {},
    h('div', { class: `status ${cls}` }, h('span', { class: 'dot-s' }), label),
    h('p', { class: 'muted', text: 'Tournois classés par date, sets rejoués par horodatage, rounds contrôlés. Revérifié à chaque calcul.' }),
    h('ul', { class: 'issues' },
      chrono.issues.map((i) => h('li', { class: i.level }, h('small', { text: `${i.level === 'error' ? 'Erreur' : 'Avertissement'}${i.tournament ? ' · ' + i.tournament : ''}` }), i.message)),
      missing.map((u) => h('li', {}, h('small', { text: 'Non synchronisé' }), `${u} — cliquez sur « Actualiser » (jeton start.gg requis).`)),
      problems.map((p) => h('li', {}, h('small', { text: 'tournaments.txt' }), p))));
}

export function rules(r) {
  return h('div', {},
    h('dl', {},
      h('dt', { text: 'ELO de départ' }), h('dd', { text: r.initial_elo }),
      h('dt', { text: 'Facteur K' }), h('dd', { text: r.k_factor }),
      h('dt', { text: 'Poids Winner Bracket' }), h('dd', { text: '× 1,00' }),
      h('dt', { text: 'Poids Loser Bracket' }), h('dd', { text: `× ${r.losers_weight.toFixed(2).replace('.', ',')}` }),
      h('dt', { text: 'Perte en cas de défaite' }), h('dd', { text: `${Math.round(r.loss_factor * 100)} % du gain` }),
      h('dt', { text: 'Inactivité' }), h('dd', { text: `−${r.decay} / tournoi manqué` })),
    h('p', { text: 'Un ELO est calculé à chaque set (pas à chaque game). Le vainqueur gagne le montant ELO plein, le perdant n\'en perd qu\'une partie. Chaque tournoi manqué retire des points aux joueurs déjà classés. Les DQ sont ignorés. Les personnages sont comptés game par game, jusqu\'au tournoi affiché.' }));
}

export function timeline(tournaments, current, onSelect) {
  return tournaments.map((t) => h('li', {},
    h('button', { type: 'button', 'aria-current': String(t.index === current), title: t.name, onclick: () => onSelect(t.index) },
      h('b', { text: `#${t.index + 1}` }), fmtShort(t.date))));
}

export const tournamentMeta = (t) =>
  `${fmtDate(t.date)} · ${t.participants} joueurs · ${t.sets_counted} sets comptés${t.completed ? '' : ' · EN COURS'}`;
