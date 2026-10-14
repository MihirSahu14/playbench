"""Regenerate the README visuals in docs/assets from real runs of examples/dodge-web.

Usage (from the repo root):  python docs/assets/generate.py
Needs: Pillow, and Playwright with Chromium (python -m pip install pillow playwright && python -m playwright install chromium).
Writes demo.gif (bot playing + live checks), flow-light.svg / flow-dark.svg (pipeline), showcase.png (4 steps).
"""
import base64, functools, http.server, io, shutil, subprocess, sys, tempfile, threading, time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "assets"
GAME = Path(tempfile.mkdtemp()) / "dodge-web"  # scratch copy, so playtest output never lands in the repo
shutil.copytree(ROOT / "examples" / "dodge-web", GAME)
# real planted-crash playtest; its screenshot goes into the showcase. Exit 1 (FAIL) is expected.
subprocess.run([sys.executable, str(ROOT / "scripts" / "playtest.py"), "run", f"{GAME}?bug=crash", "--mode", "quick", "--out", str(GAME / "playtests")], check=False)

def font(names, size):
    for n in names:  # Windows fonts first, then common Linux/macOS fallbacks
        for d in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", "/Library/Fonts/", ""):
            try: return ImageFont.truetype(d + n, size)
            except OSError: pass
    return ImageFont.load_default(size)
mono = lambda s: font(["CascadiaCode.ttf", "consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"], s)
ui = lambda s, b=False: font(["segoeuib.ttf" if b else "segoeui.ttf", "DejaVuSans-Bold.ttf" if b else "DejaVuSans.ttf", "Arial.ttf"], s)
BG, PANEL, LINE, TXT, DIM, GREEN, RED, AMBER, BLUE = "#0d1117", "#161b22", "#30363d", "#e6edf3", "#8b949e", "#3fb950", "#f85149", "#d29922", "#58a6ff"

# ---------- 1. hero GIF: real bot run + live check panel ----------
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(type('Quiet', (http.server.SimpleHTTPRequestHandler,), {'log_message': lambda *a: None}), directory=str(GAME)))
threading.Thread(target=srv.serve_forever, daemon=True).start()
PROBE = "() => { const g = window.__game; const s = typeof g.state === 'function' ? g.state() : g.state; return {s, k: g.bot ? g.bot(s) : []}; }"

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 480, "height": 320})
    page.goto(f"http://127.0.0.1:{srv.server_port}/index.html"); page.wait_for_function("window.__game")
    page.keyboard.press("Enter")
    caps, held, t0, after = [], set(), time.time(), 0
    for _ in range(300):
        r = page.evaluate(PROBE)
        want = set(r["k"] or [])
        for k in held - want: page.keyboard.up(k)
        for k in want - held: page.keyboard.down(k)
        held = want
        caps.append((Image.open(io.BytesIO(page.locator("canvas").screenshot())).convert("RGB"), r["s"], sorted(want), time.time() - t0))
        if r["s"].get("over"):
            after += 1
            if after > 6: break
        time.sleep(0.05)

    W, H, TOP, SIDE = 480 + 250, 320 + 44, 44, 250
    ARROW = {"ArrowLeft": "<", "ArrowRight": ">"}
    def frame(img, s, keys, t, final=False):
        c = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(c)
        d.rectangle([0, 0, W, TOP - 1], fill=PANEL); d.line([0, TOP - 1, W, TOP - 1], fill=LINE)
        for i, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")): d.ellipse([14 + i * 20, 16, 26 + i * 20, 28], fill=col)
        d.text((84, 12), "playbench  ·  bot playtest  ·  examples/dodge-web", font=mono(14), fill=DIM)
        c.paste(img, (0, TOP)); d.line([480, TOP, 480, H], fill=LINE)
        x, y = 498, TOP + 16
        d.text((x, y), "LIVE RUN", font=ui(12, True), fill=DIM); y += 24
        for k, v in (("time", f"{t:4.1f}s"), ("score", str(s.get("score", 0))), ("bot keys", " ".join(ARROW.get(k, k) for k in keys) or "-")):
            d.text((x, y), k, font=mono(14), fill=DIM); d.text((x + 100, y), v, font=mono(14), fill=TXT); y += 22
        y += 14; d.text((x, y), "WATCHING FOR", font=ui(12, True), fill=DIM); y += 24
        for label in ("boots", "input works", "no crash", "no freeze", "no softlock"):
            d.ellipse([x, y + 3, x + 15, y + 18], fill=GREEN if t > 0.3 else LINE)
            d.line([(x + 4, y + 11), (x + 7, y + 14), (x + 12, y + 7)], fill=BG, width=2)
            d.text((x + 24, y), label, font=ui(15), fill=TXT); y += 24
        if final:
            ov = Image.new("RGBA", (W, H), (13, 17, 23, 205)); c.paste(ov, (0, 0), ov); d = ImageDraw.Draw(c)
            d.rounded_rectangle([W // 2 - 230, H // 2 - 58, W // 2 + 230, H // 2 + 58], 14, fill=PANEL, outline=GREEN, width=2)
            d.text((W // 2, H // 2 - 22), "PASS", font=ui(34, True), fill=GREEN, anchor="mm")
            d.text((W // 2, H // 2 + 20), "6 bot runs · 0 crashes · 0 freezes · 0 softlocks", font=ui(16), fill=TXT, anchor="mm")
        return c.quantize(colors=96, method=Image.Quantize.FASTOCTREE)

    frames = [frame(*cap) for cap in caps[::2]]
    frames += [frame(*caps[-1], final=True)] * 1
    durs = [100] * (len(frames) - 1) + [2600]
    frames[0].save(OUT / "demo.gif", save_all=True, append_images=frames[1:], duration=durs, loop=0, optimize=True)
    print("wrote demo.gif", len(frames), "frames,", round((OUT / "demo.gif").stat().st_size / 1024), "KB")

    # ---------- 3. showcase: 4 steps, one image ----------
    shot = next((GAME / "playtests" / "shots").glob("*crash*.png"))  # from the crash playtest above
    b64 = base64.b64encode(shot.read_bytes()).decode()
    bars = "".join(
        f'<div class=row><span class=lbl>speed {v}</span><div class=track><div class=fill style="width:{max(w, 2)}%;background:{GREEN if w >= 67 else AMBER if w else RED}"></div></div><b class=pct>{w}%</b></div>'
        for v, w in ((1.0, 100), (2.0, 100), (3.0, 0), (4.0, 33)))
    cards = [
        ("1", "Ask what's next", "you: what's next for this game?", f"""<b style=color:{BLUE}>Next: run a quick bot playtest.</b>
Both must-list features are built.

<span class=y>Stage: playable</span>
  ☐ Latest quick playtest is PASS
  ☐ A human played it
<span class=dim>Playtest debt: 1 commit (limit 3)</span>"""),
        ("2", "Bots playtest every feature", "you: playtest it", f"""<span class=ok>PASS</span> 6 runs, no crash/freeze/softlock
<span class=dim>…a bug sneaks in…</span>
<span class=bad>FAIL</span> crash at 4.0s <span class=dim>(seed 1)</span>
<span class=y>regression</span> win rate 1.0 → 0.0<img class=shot src="data:image/png;base64,{b64}">"""),
        ("3", "Balance on the real build", "you: is bat speed balanced?", f"""<span class=dim>bot win rate per bat_speed</span>
{bars}<span class=dim>cliff between 2 and 3 → tune there</span>"""),
        ("4", "Ship only when you say so", "you: ship to itch", f"""<span class=bad>ARTGATE BLOCKED</span>
  hero_placeholder.png not disclosed
<span class=ok>ARTGATE PASS</span> <span class=dim>after disclosure</span>

<span class=y>☐</span> Final playtest is PASS
<span class=y>☐</span> I approve this release
<span class=bad>upload withheld</span> until <b>you</b> tick gates"""),
    ]
    html = f"""<html><head><style>
body{{margin:0;background:transparent;font-family:'Segoe UI',system-ui,sans-serif}}
#g{{display:grid;grid-template-columns:1fr 1fr;gap:22px;width:1180px;padding:4px}}
.step{{display:flex;align-items:center;gap:10px;margin:0 0 9px 2px;font-size:19px;font-weight:600;color:#c9d1d9}}
.num{{width:28px;height:28px;border-radius:50%;background:#d97757;color:#fff;display:grid;place-items:center;font-size:15px}}
.card{{background:{BG};border:1px solid {LINE};border-radius:12px;overflow:hidden;height:290px}} .h{{color:{TXT};font-size:17px;font-weight:600}} .p{{color:#d97757}}
.bar{{background:{PANEL};padding:11px 16px;display:flex;gap:7px;align-items:center;border-bottom:1px solid {LINE}}}
.dot{{width:11px;height:11px;border-radius:50%}} .t{{margin-left:10px;color:{DIM};font:13px 'Cascadia Code',Consolas,monospace}}
.body{{padding:16px 20px;color:{TXT};font:15px/1.6 'Cascadia Code',Consolas,monospace;white-space:pre-wrap;position:relative}}
.ok{{color:{GREEN};font-weight:bold}} .bad{{color:{RED};font-weight:bold}} .dim{{color:{DIM}}} .y{{color:{AMBER}}}
.shot{{position:absolute;right:18px;top:18px;width:210px;border:2px solid {RED};border-radius:6px}}
.row{{display:flex;align-items:center;gap:12px;margin:9px 0}} .lbl{{width:92px}} .track{{flex:1;background:#21262d;border-radius:4px;height:20px}}
.fill{{height:20px;border-radius:4px}} .pct{{width:48px;text-align:right}}
</style></head><body><div id=g>""" + "".join(
        f"""<div class=card><div class=bar><span class=num>{n}</span><span class=h>{h}</span></div><div class=body><span class=p>&gt; {title[5:]}</span>
{body}</div></div>""" for n, h, title, body in cards) + "</div></body></html>"
    page = browser.new_page(viewport={"width": 1200, "height": 900}, device_scale_factor=2)
    page.set_content(html); page.locator("#g").screenshot(path=str(OUT / "showcase.png"), omit_background=True)
    print("wrote showcase.png")
    browser.close()
srv.shutdown()

# ---------- 2. horizontal flow diagram, light + dark SVG ----------
NODES = [("Design", "one chat, one page"), ("Build", "one feature"), ("Bot playtest", "crash · freeze · softlock"),
         ("Balance", "sweep the knobs"), ("Human playtest", "is it fun?"), ("Ship", "itch · Steam · web")]
def flow(th):
    nw, gap, x0, y0, nh = 156, 40, 12, 34, 62
    cx = lambda i: x0 + i * (nw + gap) + nw / 2
    W = x0 * 2 + 6 * nw + 5 * gap
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 6 {W} 162" width="{W}" height="162" font-family="Segoe UI,-apple-system,system-ui,sans-serif">',
         f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{th["line"]}"/></marker>'
         f'<marker id="r" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{th["red"]}"/></marker></defs>']
    for i, (t, sub) in enumerate(NODES):
        x = x0 + i * (nw + gap)
        hot, ship = i == 2, i == 5
        fill, stroke = (th["hotfill"], th["green"]) if hot else (th["fill"], th["accent"] if ship else th["stroke"])
        s.append(f'<rect x="{x}" y="{y0}" width="{nw}" height="{nh}" rx="12" fill="{fill}" stroke="{stroke}" stroke-width="{2 if hot or ship else 1.2}"/>')
        s.append(f'<text x="{x + nw / 2}" y="{y0 + 27}" text-anchor="middle" font-size="16" font-weight="600" fill="{th["text"]}">{t}</text>')
        s.append(f'<text x="{x + nw / 2}" y="{y0 + 47}" text-anchor="middle" font-size="12" fill="{th["dim"]}">{sub}</text>')
        if i < 5:
            s.append(f'<line x1="{x + nw + 4}" y1="{y0 + nh / 2}" x2="{x + nw + gap - 4}" y2="{y0 + nh / 2}" stroke="{th["line"]}" stroke-width="1.6" marker-end="url(#a)"/>')
    s.append(f'<text x="{cx(5) - nw / 2 - gap / 2}" y="{y0 - 10}" text-anchor="middle" font-size="12" font-weight="600" fill="{th["accent"]}">you tick the gates</text>')
    yb = y0 + nh
    s.append(f'<path d="M{cx(2)} {yb + 4} C{cx(2)} {yb + 44} {cx(1) + 18} {yb + 44} {cx(1) + 18} {yb + 6}" fill="none" stroke="{th["red"]}" stroke-width="1.6" marker-end="url(#r)"/>')
    s.append(f'<text x="{cx(2) + 10}" y="{yb + 26}" text-anchor="start" font-size="12" font-weight="600" fill="{th["red"]}">FAIL → fix</text>')
    s.append(f'<path d="M{cx(4)} {yb + 4} C{cx(4)} {yb + 82} {cx(1) - 18} {yb + 82} {cx(1) - 18} {yb + 6}" fill="none" stroke="{th["line"]}" stroke-width="1.4" stroke-dasharray="5 4" marker-end="url(#a)"/>')
    s.append(f'<text x="{(cx(1) + cx(4)) / 2}" y="{yb + 82}" text-anchor="middle" font-size="12" fill="{th["dim"]}">next feature</text>')
    s.append("</svg>")
    return "\n".join(s)
LIGHT = dict(fill="#ffffff", stroke="#d0d7de", text="#1f2328", dim="#656d76", line="#8c959f", green="#1a7f37", hotfill="#dafbe1", red="#cf222e", accent="#c4623f")
DARK = dict(fill="#161b22", stroke="#30363d", text="#e6edf3", dim="#8b949e", line="#6e7681", green="#3fb950", hotfill="#0f2e1a", red="#f85149", accent="#d97757")
(OUT / "flow-light.svg").write_text(flow(LIGHT), encoding="utf-8")
(OUT / "flow-dark.svg").write_text(flow(DARK), encoding="utf-8")
print("wrote flow-light.svg, flow-dark.svg")
