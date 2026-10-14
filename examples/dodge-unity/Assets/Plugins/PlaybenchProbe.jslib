// playbench probe for Unity WebGL (contract: docs/reference.md, Probe contract).
// window.__game is defined when the framework script loads (the $PB postset), before the first C# frame, so the
// harness sees a readable state ({paused:true} while Unity boots) instead of null and detects tier 1/2, not tier 0.
// C# pushes its JSON state every frame via PB_SetState; state() parses the latest one.
var PlaybenchProbe = {
  $PB__postset: 'PB.init();',
  $PB: {
    json: null,
    init: function () {
      var q = new URLSearchParams(location.search);
      if (q.has('noprobe')) return;
      window.__game = {
        state: function () { return PB.json ? JSON.parse(PB.json) : { over: false, paused: true }; },
        actions: ['ArrowLeft', 'ArrowRight', 'Enter']
      };
      if (!q.has('nobot')) window.__game.bot = PB.bot;
    },
    // Greedy dodger: step away from the lowest enemy that is about to land on the player, else drift to centre.
    // ponytail: one threat at a time, no reaction delay, so it wins a lot; dodge-web's bot shows a beatable one.
    bot: function (s) {
      if (s.paused || s.over) return ['Enter'];
      var W = 480, PCY = 308, px = s.px;
      var near = s.enemies.filter(function (e) { return e[1] < PCY + 12 && PCY - e[1] < 150 && Math.abs(e[0] - px) < 34; })
        .sort(function (a, b) { return b[1] - a[1]; });
      if (near.length) {
        var left = near[0][0] !== px ? near[0][0] > px : px > W / 2;
        if (left && px < 30) left = false; else if (!left && px > W - 30) left = true;
        return [left ? 'ArrowLeft' : 'ArrowRight'];
      }
      var d = W / 2 - px;
      return Math.abs(d) < 8 ? [] : [d > 0 ? 'ArrowRight' : 'ArrowLeft'];
    }
  },
  PB_SetState__deps: ['$PB'],
  PB_SetState: function (p) { PB.json = UTF8ToString(p); },
  PB_Seed: function () {
    var p = window.__playbench;
    return p && typeof p.seed === 'number' ? p.seed | 0 : -1;
  },
  PB_Override: function (name, def) {
    var v = ((window.__playbench && window.__playbench.overrides) || {})[UTF8ToString(name)];
    return typeof v === 'number' ? v : def;
  },
  PB_Query: function (name) {
    var v = new URLSearchParams(location.search).get(UTF8ToString(name)) || '';
    var n = lengthBytesUTF8(v) + 1, buf = _malloc(n);
    stringToUTF8(v, buf, n);
    return buf;
  },
  PB_Crash: function () { throw new Error('planted js crash'); }
};
mergeInto(LibraryManager.library, PlaybenchProbe);
