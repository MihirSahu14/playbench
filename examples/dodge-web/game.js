// dodge-web: tiny fixture game for the playloop harness. Contract: docs/superpowers/specs (Probe contract).
// URL switches: ?bug=softlock|crash|deadinput, ?noprobe, ?nobot
const q = new URLSearchParams(location.search), bug = q.get('bug');
const cv = document.getElementById('game'), g = cv.getContext('2d'), W = cv.width, H = cv.height;
const PS = (window.__playloop?.overrides ?? {}).player_speed ?? 4; // px per frame at 60 fps
const PW = 16, PY = H - PW - 4, PCY = PY + PW / 2, WIN_S = 20;
const hero = new Image(); hero.src = 'art/hero_placeholder.png';
let kinds = null, timers = [], enemies = [], started = false, over = false, won = false, playT = 0, px = W / 2, last = null;
const keys = {};

fetch('data/enemies.csv').then(r => r.text()).then(t => {
  const [head, ...rows] = t.trim().split(/\r?\n/).map(l => l.split(',').map(s => s.trim()));
  kinds = rows.map(r => Object.fromEntries(head.map((h, i) => [h, h === 'id' ? r[i] : +r[i]])));
  timers = kinds.map(() => 0);
});

const start = () => { started = true; };
addEventListener('keydown', e => {
  if (e.key === 'Enter' || e.key === ' ') start();
  if (e.key.startsWith('Arrow')) { e.preventDefault(); if (bug !== 'deadinput') keys[e.key] = true; }
});
addEventListener('keyup', e => { keys[e.key] = false; });
cv.addEventListener('click', start);

const score = () => Math.floor(Math.min(playT, WIN_S));

function update(dt) {
  if (bug === 'softlock' && playT >= 8) return; // planted: world freezes, input ignored, never over
  playT += dt;
  px += ((keys.ArrowRight ? 1 : 0) - (keys.ArrowLeft ? 1 : 0)) * PS * 60 * dt;
  px = Math.max(PW / 2, Math.min(W - PW / 2, px));
  kinds.forEach((k, i) => {
    timers[i] += dt * 1000;
    if (timers[i] >= k.spawn_ms) {
      timers[i] -= k.spawn_ms;
      enemies.push({ x: k.size / 2 + Math.random() * (W - k.size), y: -k.size / 2, k });
    }
  });
  for (const e of enemies) e.y += e.k.speed * 60 * dt;
  enemies = enemies.filter(e => e.y - e.k.size / 2 < H);
  for (const e of enemies) {
    const r = (e.k.size + PW) / 2;
    if (Math.abs(e.x - px) < r && Math.abs(e.y - PCY) < r) { over = true; won = false; return; }
  }
  if (playT >= WIN_S) { over = true; won = true; }
}

function draw() {
  g.fillStyle = '#111'; g.fillRect(0, 0, W, H);
  for (const e of enemies) {
    g.fillStyle = e.k.id === 'bat' ? '#d55' : '#5c5';
    g.fillRect(e.x - e.k.size / 2, e.y - e.k.size / 2, e.k.size, e.k.size);
  }
  if (hero.complete && hero.naturalWidth) g.drawImage(hero, px - PW / 2, PY, PW, PW);
  else { g.fillStyle = '#5af'; g.fillRect(px - PW / 2, PY, PW, PW); }
  g.fillStyle = '#fff'; g.font = '16px monospace'; g.textAlign = 'center';
  g.fillText('score ' + score(), W / 2, 20);
  const msg = !started ? 'Press Enter or click to start' : !kinds ? 'loading...'
    : over ? (won ? 'You survived! ' : 'Hit! ') + 'Score ' + score() : '';
  if (msg) {
    if (!started || over) { g.fillStyle = 'rgba(0,0,0,.6)'; g.fillRect(0, H / 2 - 30, W, 44); g.fillStyle = '#fff'; }
    g.fillText(msg, W / 2, H / 2);
  }
}

function frame(ts) {
  const dt = last === null ? 0 : Math.min(ts - last, 50) / 1000;
  last = ts;
  if (bug === 'crash' && playT >= 5) {
    // planted: the loop dies with an uncaught error. Thrown from a microtask because Playwright's page.clock
    // catches errors thrown directly in a faked rAF callback and rethrows them from clock.run_for, not pageerror.
    queueMicrotask(() => { throw new Error('planted crash'); });
    return;
  }
  if (kinds && started && !over) update(dt);
  draw();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

function state() {
  const threats = enemies.filter(e => e.y - e.k.size / 2 < PY + PW) // above = not yet fallen past the player
    .map(e => [Math.round(e.x - px) + 0, Math.round(PCY - e.y) + 0]) // +0 turns -0 into 0 for stable hashes
    .sort((a, b) => Math.hypot(...a) - Math.hypot(...b)).slice(0, 3);
  return { over, won, paused: !started || !kinds, score: score(), px: Math.round(px), n: enemies.length,
    ey: Math.round(enemies.reduce((s, e) => s + e.y, 0)), threats };
}

// Heuristic dodger with a human-ish reaction time: it sees enemies where they were REACTION_MS ago
// (page clock, so deterministic under page.clock) but knows where it is now. Without the delay the player
// is so fast that enemy speed barely matters; with it, faster bats beat the bot more often.
// ponytail: greedy, one threat at a time; a planner would win more, but the fixture wants a beatable bot.
const REACTION_MS = 800, seen = [];
function bot(s) {
  const now = performance.now();
  seen.push([now, s]);
  while (seen.length > 1 && seen[1][0] <= now - REACTION_MS) seen.shift();
  const o = seen[0][1], th = o.threats.map(([dx, dy]) => [dx + o.px - s.px, dy]);
  const blocked = side => th.some(([dx, dy]) => dy < 40 && Math.sign(dx) === side && Math.abs(dx) >= 14 && Math.abs(dx) < 40);
  const t = th.find(([dx, dy]) => Math.abs(dx) < 30 && dy < 140);
  if (t) {
    let left = t[0] !== 0 ? t[0] > 0 : s.px > W / 2; // away from it...
    if (left && (s.px < 40 || blocked(-1))) left = false; // ...unless that side has less room
    else if (!left && (s.px > W - 40 || blocked(1))) left = true;
    return [left ? 'ArrowLeft' : 'ArrowRight'];
  }
  const d = W / 2 - s.px; // drift to centre, but don't walk back under something nearby
  if (Math.abs(d) < 8 || th.some(([dx, dy]) => dy < 140 && Math.abs(dx) < 60 && Math.sign(dx) === Math.sign(d))) return [];
  return [d > 0 ? 'ArrowRight' : 'ArrowLeft'];
}

if (!q.has('noprobe')) {
  window.__game = { state, actions: ['ArrowLeft', 'ArrowRight', 'Enter'] };
  if (!q.has('nobot')) window.__game.bot = bot;
}
