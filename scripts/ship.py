#!/usr/bin/env python3
"""playloop ship: artgate, gate, itch, steam, web.
Never runs butler or steamcmd; it only prints the commands for the human to run.
Exit codes: 0 pass, 1 blocked, 2 usage or environment error."""
import argparse, contextlib, fnmatch, io, json, os, posixpath, re, shutil, struct, subprocess, sys, tempfile, zipfile, zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STORE = {
    'itch': {'max_files': 1000, 'max_total_mb': 500, 'max_file_mb': 200, 'max_path': 240},
    'steam': {'capsules': {'header_capsule.png': (920, 430), 'small_capsule.png': (462, 174),
                           'main_capsule.png': (1232, 706), 'vertical_capsule.png': (748, 896)},
              'screenshots_min': 5, 'screenshot_px': (1920, 1080), 'aspect': 16 / 9, 'aspect_tol': 0.01},
    'AS_OF': '2026-10-13',
    'SOURCES': {'itch': 'https://itch.io/docs/creators/html5', 'butler': 'https://itch.io/docs/butler/pushing.html',
                'steam_assets': 'https://partner.steamgames.com/doc/store/assets/standard',
                'steampipe': 'https://partner.steamgames.com/doc/sdk/uploading'}}
SIG = b'\x89PNG\r\n\x1a\n'
GEN = re.compile(rb'midjourney|dall-?e|stable.?diffusion|novelai|firefly|comfyui', re.I)
TAG = re.compile(r'_(placeholder|ai|wip)(?=\.[^.]+$)', re.I)
KEYS = {b'parameters', b'prompt', b'workflow'}
ABS = re.compile(r"""(?:src|href)\s*=\s*["']/(?!/)|url\(\s*["']?/(?!/)|fetch\(\s*["']/(?!/)""")
ASSET = re.compile(r"""["']([\w./-]+\.(?:png|jpe?g|webp|gif|svg|ogg|mp3|wav|json|csv|js|css|wasm|pck|html))["']""")
# excluded only when build_dir is the game root, so playloop state and dotfiles (.env) never reach an upload
SKIP = {'build', 'playtests', 'steam', 'store', 'balance', 'design'}
SKIP_FILES = {'studio.json', 'gates.md', 'disclosure.md', 'art/PLACEHOLDERS.json'}
MB = 1_000_000  # ponytail: decimal MB, the stricter reading of itch's limits


def _run(build, mode='boot'):
    """Hook for playtest.run; the selftest swaps in a fake."""
    sys.path.insert(0, str(HERE))
    from playtest import run
    return run(build, mode=mode)


def git(cwd, *a):
    try:
        r = subprocess.run(['git', *a], cwd=cwd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    except OSError:
        return None
    return r.stdout if r.returncode == 0 else None


def cfg(game):
    p = game / 'studio.json'
    try:
        return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else {}
    except ValueError as e:
        print(f'ERROR {p} is not valid JSON: {e}')
        raise SystemExit(2)


def walk(base, game):
    out, at_root = [], base.resolve() == game.resolve()
    for root, dirs, fs in os.walk(base):
        if at_root and Path(root) == base:
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith('.')]
            fs = [f for f in fs if not f.startswith('.')]
        out += [Path(root, f).relative_to(base).as_posix() for f in fs]
    return sorted(f for f in out if not (at_root and f in SKIP_FILES))


def relto(p, game):
    return Path(os.path.relpath(p, game)).as_posix()


# ---------- artgate ----------
def png_flag(data):
    i = 8
    while i + 8 <= len(data):
        n, t = struct.unpack('>I4s', data[i:i + 8])
        body, i = data[i + 8:i + 8 + n], i + 12 + n
        if t == b'caBX': return 'PNG caBX chunk (C2PA content credentials)'
        if t == b'IEND': break
        if t not in (b'tEXt', b'zTXt', b'iTXt'): continue
        key, _, rest = body.partition(b'\0')
        if key.lower() in KEYS: return f'PNG {t.decode()} key "{key.decode("latin-1")}"'
        with contextlib.suppress(zlib.error):
            if t == b'zTXt': rest = zlib.decompress(rest[1:])
            elif t == b'iTXt':  # flag, method, language\0, translated keyword\0, text
                txt = rest[2:].split(b'\0', 2)[-1]
                rest = zlib.decompress(txt) if rest[:1] == b'\1' else txt
        m = GEN.search(rest)
        if m: return f'PNG {t.decode()} mentions "{m.group().decode("latin-1")}"'
    return None


def flag_file(path, name, names):
    ext = name.rsplit('.', 1)[-1].lower()
    if name in names: return 'listed in art/PLACEHOLDERS.json'
    if TAG.search(name): return 'placeholder/ai/wip filename tag'
    if ext == 'png':
        data = path.read_bytes()
        return png_flag(data) if data[:8] == SIG else None
    if ext in ('jpg', 'jpeg', 'webp'):
        with open(path, 'rb') as f: head = f.read(65536)
        m = b'c2pa' if b'c2pa' in head else (GEN.search(head) or [None])[0]
        return f'{ext.upper()} header contains "{m.decode("latin-1")}"' if m else None
    return None


def scan(game, dirs):
    try:
        ph = json.loads((game / 'art/PLACEHOLDERS.json').read_text(encoding='utf-8-sig')).get('placeholders', [])
    except (OSError, ValueError):
        ph = []
    names = {posixpath.basename(p.get('path', '').replace('\\', '/')) for p in ph} - {''}
    flags = {}
    for d in dirs:
        base = (game / d).resolve()
        for rel in walk(base, game) if base.is_dir() else []:
            why = flag_file(base / rel, posixpath.basename(rel), names)
            if why: flags[relto(base / rel, game)] = why
    return sorted(flags.items())


def artgate(game, dirs=None):
    # ponytail: store/ is scanned by policy; Steam's marketing-asset scope for AI disclosure is unverified.
    dirs = dirs or [cfg(game).get('build_dir', '.'), 'store']
    p = game / 'disclosure.md'
    lines = p.read_text(encoding='utf-8-sig').splitlines() if p.exists() else []
    # a line counts only once its description is filled in (not empty, not the printed <...> template)
    globs = [m.group(1).strip() for m in (re.match(r'^- (.+?):\s*[^<\s]', l) for l in lines) if m]
    flags, missing = scan(game, dirs), []
    if flags: print(f'{"file":<44} {"reason":<46} disclosed')
    for rel, why in flags:
        ok = any(fnmatch.fnmatchcase(rel, g) for g in globs)
        missing += [] if ok else [rel]
        print(f'{rel:<44} {why:<46} {"yes" if ok else "NO"}')
    print(f'ARTGATE {"BLOCKED" if missing else "PASS"} ({len(flags)} flagged, {len(missing)} undisclosed; scanned {", ".join(dirs)})')
    if missing:
        print('Replace these files, or add these lines to disclosure.md (say what is AI or placeholder):')
        print('\n'.join(f'- {rel}: <what AI or placeholder content this is>' for rel in missing))
    elif flags:
        print('Disclose on the store too: Steam Content Survey (AI-generated content), itch.io AI-generated tag.')
    print('Heuristic: stripped metadata is not detected. This is a safety net, not enforcement.')
    return 1 if missing else 0


# ---------- gate ----------
def gate(game):
    p = game / 'gates.md'
    lines = p.read_text(encoding='utf-8-sig').splitlines() if p.exists() else []
    heads = [i for i, l in enumerate(lines) if l.startswith('## ')]
    if not heads:
        print('GATE BLOCKED: no gates.md with a "## <stage>" section (run studio init)')
        return 1
    tracked = git(game, 'ls-files', '--error-unmatch', '--', 'gates.md') is not None
    ok = tracked
    print(f'Gate audit: ## {lines[heads[-1]][3:].strip()}')
    if not tracked: print('WARN gates.md is not tracked by git: ticks cannot be attributed')
    for n in range(heads[-1] + 1, len(lines)):
        m = re.match(r'\s*- \[([ xX])\]\s*(.*)', lines[n])
        if not m: continue
        box = m.group(2)
        b = git(game, 'blame', '--porcelain', '-L', f'{n + 1},{n + 1}', '--', 'gates.md') if tracked and m.group(1) != ' ' else ''
        if m.group(1) == ' ':
            print(f'  UNTICKED  {box}')
            ok = False
        elif not b:  # untracked, or blame failed: never attributable, so never a pass
            print(f'  TICKED    {box}  (unattributed)')
            ok = False
        elif set(b.split()[0]) == {'0'}:
            print(f'  TICKED    {box}  WARN uncommitted tick (cannot attribute; commit gates.md)')
            ok = False
        else:
            when = datetime.fromtimestamp(int(re.search(r'^author-time (\d+)', b, re.M).group(1))).strftime('%Y-%m-%d')
            print(f'  TICKED    {box}  by {re.search(r"^author (.*)$", b, re.M).group(1)}, {when}, {b.split()[0][:8]}')
    print(f'GATE {"PASS" if ok else "BLOCKED"}')
    return 0 if ok else 1


# ---------- itch / web / steam ----------
def limits(build, files, itch=True):
    S, errs, total = STORE['itch'], [], 0
    if 'index.html' not in files: errs.append('no index.html at the build root')
    if itch and len(files) > S['max_files']: errs.append(f'{len(files)} files (itch max {S["max_files"]})')
    for rel in files if itch else []:
        size = (build / rel).stat().st_size
        total += size
        if size > S['max_file_mb'] * MB: errs.append(f'{rel}: {size / MB:.1f} MB (itch max {S["max_file_mb"]} MB per file)')
        if len(rel) > S['max_path']: errs.append(f'path of {len(rel)} chars (itch max {S["max_path"]}): {rel[:60]}...')
    if total > S['max_total_mb'] * MB: errs.append(f'{total / MB:.1f} MB in total (itch max {S["max_total_mb"]} MB)')
    have, lower = set(files), {f.lower(): f for f in files}
    for rel in files:
        if rel.rsplit('.', 1)[-1].lower() not in ('html', 'htm', 'js', 'css'): continue
        text = (build / rel).read_text(encoding='utf-8', errors='replace')
        errs += [f'{rel}: root-absolute URL {m.group()!r} breaks under itch\'s sub-path host' for m in ABS.finditer(text)]
        for m in ASSET.finditer(text) if itch else []:
            ref = m.group(1)
            cands = {posixpath.normpath(posixpath.join(posixpath.dirname(rel), ref)), posixpath.normpath(ref)}
            hit = None if cands & have else next((lower[c.lower()] for c in cands if c.lower() in lower), None)
            if hit: errs.append(f'{rel}: "{ref}" matches {hit} only case-insensitively (itch is case-sensitive)')
    return errs


def boot(target):
    try:
        r = _run(str(target), mode='boot')
    except SystemExit as e:
        print(f'WARN boot check skipped: {e.code if isinstance(e.code, str) else f"playtest exited {e.code} (is playwright installed?)"}')
        return 'SKIP'
    except ImportError as e:
        print(f'WARN boot check skipped: {e}')
        return 'SKIP'
    print(f'boot: {r.get("summary") or r.get("verdict")}')
    return r.get('verdict', 'FAIL')


def release_reasons(game, verdict=None):
    print('\n== artgate ==')
    reasons = ['artgate BLOCKED'] if artgate(game) else []
    print('\n== gate ==')
    if gate(game): reasons.append('gate not fully ticked, committed and tracked')
    if verdict in ('FAIL', 'SKIP'): reasons.append(f'boot check {verdict}')
    return reasons


def build_of(game, c):
    b = (game / c.get('build_dir', '.')).resolve()
    if b.is_dir(): return b
    print(f'ERROR build_dir not found: {b} (set "build_dir" in studio.json)')
    raise SystemExit(2)


def verdict_line(reasons, real_cmd, what='upload'):
    print()
    if reasons:
        print(f'Real {what} command withheld: {"; ".join(reasons)}')
        return 1
    print(f'REAL {what.upper()} (run it yourself): {real_cmd}')
    return 0


def itch(game, real=False):  # --real is accepted; the real command prints whenever everything passes
    c = cfg(game)
    build, out = build_of(game, c), game / 'build' / 'itch.zip'
    files = [f for f in walk(build, game) if (build / f).resolve() != out.resolve()]
    errs = limits(build, files)
    print('\n'.join(f'BLOCKED {e}' for e in errs) or f'itch limits PASS ({len(files)} files)')
    if errs: return verdict_line([f'itch limits ({STORE["SOURCES"]["itch"]})'], '')
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, strict_timestamps=False) as z:  # pre-1980 mtimes crash otherwise
        for rel in files: z.write(build / rel, rel)
    print(f'wrote {out}')
    verdict, target = boot(out), c.get('itch') or '<user/game>'
    print(f'\nDry run: butler push build/itch.zip {target}:html5 --if-changed --dry-run')
    if not shutil.which('butler'): print('install butler: https://itch.io/docs/butler/installing.html')
    print('Manual steps (itch dashboard, Edit game):\n  1. Kind of project: HTML.\n'
          '  2. On the upload, tick "This file will be played in the browser".\n'
          '  3. Embed: set the viewport to your canvas size, enable the fullscreen button, disable scrollbars.\n'
          '  4. SharedArrayBuffer support: enable only for threaded builds.\n'
          '  5. Edit theme: colors, banner, fonts; add 3-5 screenshots and a GIF; put the controls first.')
    if c.get('context') == 'jam':
        print('Jam checklist:\n  [ ] submit to the jam page before the deadline\n  [ ] cover image and screenshots added\n'
              '  [ ] controls written in the description\n  [ ] uploaded page tested in a private window')
    reasons = release_reasons(game, verdict) + ([] if c.get('itch') else ['studio.json has no "itch": "user/game"'])
    return verdict_line(reasons, f'butler push build/itch.zip {target}:html5 --if-changed')


def web(game):
    build = build_of(game, cfg(game))
    errs, rel = limits(build, walk(build, game), itch=False), relto(build, game)
    print('\n'.join(f'BLOCKED {e}' for e in errs) or 'index.html and URLs PASS')
    verdict = boot(build)
    print('\nGitHub Pages: push the repo, then Settings > Pages > Source: main, / (root).' if rel == '.' else
          f'\nGitHub Pages: commit the build, then `git subtree push --prefix {rel} origin gh-pages` and set Settings >\n'
          '  Pages > Source to the gh-pages branch (or copy the build into /docs and pick main /docs).')
    print(f'Netlify: `netlify deploy --dir {rel}` gives a draft URL to check first.')
    reasons = (['index.html / root-absolute URL problems'] if errs else []) + release_reasons(game, verdict)
    return verdict_line(reasons, f'netlify deploy --dir {rel} --prod', 'deploy')


def png_size(p):
    with open(p, 'rb') as f: d = f.read(24)
    return struct.unpack('>II', d[16:24]) if d[:8] == SIG and d[12:16] == b'IHDR' else None


def store_errs(game):
    S, errs = STORE['steam'], []
    for name, want in S['capsules'].items():
        p = game / 'store' / name
        got = (png_size(p) or 'not a PNG') if p.exists() else 'missing'
        if got != want: errs.append(f'store/{name}: {got if isinstance(got, str) else "%dx%d" % got} (need {want[0]}x{want[1]} PNG)')
    shots, (mw, mh) = sorted((game / 'store' / 'screenshots').glob('*.png')), S['screenshot_px']
    if len(shots) < S['screenshots_min']:
        errs.append(f'{len(shots)} screenshots in store/screenshots (need at least {S["screenshots_min"]})')
    for p in shots:
        wh = png_size(p)
        if not wh or wh[0] < mw or wh[1] < mh or abs(wh[0] / wh[1] / S['aspect'] - 1) > S['aspect_tol']:
            errs.append(f'store/screenshots/{p.name}: {wh} (need >= {mw}x{mh}, 16:9)')
    return errs


def steam(game, real=False):
    c = cfg(game)
    s = c.get('steam') or {}
    miss = [f'steam.{k}' for k in ('appid', 'depotid') if not s.get(k)]
    if miss:
        print(f'ERROR studio.json is missing {", ".join(miss)}; add "steam": {{"appid": <app id>, "depotid": <depot id>}}')
        return 2
    build, vdf = build_of(game, c), (game / 'steam' / 'app_build.vdf').resolve()

    def write(preview):
        vdf.parent.mkdir(exist_ok=True)
        vdf.write_text(f'"AppBuild"\n{{\n "AppID" "{s["appid"]}"\n "Desc" "playloop build"\n "Preview" "{preview}"\n'
                       f' "ContentRoot" "{build.as_posix()}"\n "BuildOutput" "{vdf.parent.as_posix()}/output/"\n'
                       f' "Depots"\n {{\n  "{s["depotid"]}"\n  {{\n'
                       '   "FileMapping" { "LocalPath" "*" "DepotPath" "." "recursive" "1" }\n  }\n }\n}\n', encoding='utf-8')
    write(1)
    print(f'wrote {vdf} (Preview "1": checks the build, uploads nothing)')
    errs = store_errs(game)
    print('\n'.join(f'BLOCKED {e}' for e in errs) or 'store assets PASS', f'({STORE["SOURCES"]["steam_assets"]}, as of {STORE["AS_OF"]})')
    reasons = (['store assets'] if errs else []) + release_reasons(game)
    cmd = f'steamcmd +login <your_steam_user> +run_app_build "{vdf}" +quit'
    if real and not reasons:
        write(0)
        verdict_line([], cmd)
        print('Then set the build live on a branch in Steamworks (App Admin > SteamPipe > Builds).')
        return 0
    print(f'\nPreview (run it yourself): {cmd}')
    verdict_line(reasons or ['rerun with --real'], cmd)
    return 1 if reasons else 0


# ---------- selftest ----------
def mkpng(w=1, h=1, extra=()):
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    # ponytail: IDAT is a valid 1x1 RGB image; larger sizes only need a correct IHDR for these checks
    return (SIG + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + b''.join(ch(t, d) for t, d in extra)
            + ch(b'IDAT', zlib.compress(b'\0\0\0\0')) + ch(b'IEND', b''))


def selftest():
    global _run
    real_run, saved = _run, dict(STORE['itch'])
    _run = lambda build, mode='boot': {'verdict': 'PASS', 'summary': 'PASS: fake boot'}
    tmp, dw = Path(tempfile.mkdtemp(prefix='ship-selftest-')), HERE.parent / 'examples' / 'dodge-web'

    def cap(fn, *a, **k):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): code = fn(*a, **k)
        return code, buf.getvalue()

    def put(root, files):
        for rel, data in files.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_bytes(data if isinstance(data, bytes) else data.encode())
        return root
    steam_ok = {'store/header_capsule.png': mkpng(920, 430), 'store/small_capsule.png': mkpng(462, 174),
                'store/main_capsule.png': mkpng(1232, 706), 'store/vertical_capsule.png': mkpng(748, 896),
                **{f'store/screenshots/{i}.png': mkpng(1920, 1080) for i in range(5)}}
    try:
        # 1. artgate
        g = put(tmp / 'art', {'studio.json': '{"build_dir": "."}', 'index.html': '<p>hi</p>', 'clean.png': mkpng(),
                              't.png': mkpng(extra=[(b'tEXt', b'parameters\0steps: 20')]),
                              'c.png': mkpng(extra=[(b'caBX', b'jumbf')]),
                              'z.png': mkpng(extra=[(b'zTXt', b'Comment\0\0' + zlib.compress(b'made in Stable Diffusion'))]),
                              'i.png': mkpng(extra=[(b'iTXt', b'Description\0\0\0en\0\0ComfyUI render')]),
                              'photo.jpg': b'\xff\xd8\xff\xe0 jumb c2pa manifest',
                              'art/tree_placeholder.png': mkpng(), 'sprites/boss.png': mkpng(),
                              'art/PLACEHOLDERS.json': '{"placeholders":[{"path":"art/old/boss.png","source":"ai","note":"x"}]}'})
        flagged = dict(scan(g, ['.']))
        assert set(flagged) == {'t.png', 'c.png', 'z.png', 'i.png', 'photo.jpg', 'art/tree_placeholder.png', 'sprites/boss.png'}, flagged
        code, out = cap(artgate, g)
        assert code == 1 and 'ARTGATE BLOCKED' in out and '- sprites/boss.png:' in out and 'Heuristic' in out, out
        put(g, {'disclosure.md': out[out.index('- '):out.index('Heuristic')]})  # printed template, pasted unfilled
        assert cap(artgate, g)[0] == 1, 'unfilled <...> disclosure lines must not count'
        put(g, {'disclosure.md': '# Disclosure\n- *.png: AI test images\n- photo.jpg: C2PA photo\n'})
        code, out = cap(artgate, g)
        assert code == 0 and 'ARTGATE PASS' in out and 'Content Survey' in out, out
        print('ok artgate')
        if (dw / 'art' / 'hero_placeholder.png').exists():
            code, out = cap(artgate, shutil.copytree(dw, tmp / 'dw'))
            assert code == 1 and 'art/hero_placeholder.png' in out, out
            print('ok artgate dodge-web blocked')
        else:
            print('SKIP artgate dodge-web: examples/dodge-web/art/hero_placeholder.png not found')

        # 2. itch limits, each violation planted alone
        def errs_for(name, files):
            b = put(tmp / name, files)
            return ' | '.join(limits(b, walk(b, b)))
        assert errs_for('ok', {'index.html': '<img src="Hero.png">', 'Hero.png': 'x'}) == ''
        assert 'no index.html' in errs_for('noidx', {'main.js': ''})
        assert '1001 files' in errs_for('many', {'index.html': '', **{f'f/{i}.txt': '' for i in range(1000)}})
        assert 'root-absolute' in errs_for('abs', {'index.html': '<script src="/x.js"></script>', 'x.js': ''})
        assert 'only case-insensitively' in errs_for('case', {'index.html': '<img src="hero.png">', 'Hero.png': 'x'})
        STORE['itch'].update(max_file_mb=10 / MB, max_total_mb=20 / MB)
        e = errs_for('size', {'index.html': 'x' * 15, 'a.js': 'x' * 15})
        assert 'per file' in e and 'in total' in e, e
        STORE['itch'].update(saved)
        try:
            e = errs_for('long', {'index.html': '', '/'.join(['d' * 50] * 5) + '/f.txt': ''})
            assert 'chars' in e, e
            print('ok itch limits')
        except OSError as ex:
            print(f'ok itch limits (except long path)\nSKIP itch long path: OS rejected it ({type(ex).__name__})')

        # 3. zip + boot
        z = put(tmp / 'zip', {'studio.json': '{"build_dir": ".", "itch": "me/dodge", "context": "jam"}',
                              'index.html': '<p>hi</p>', 'js/game.js': '', '.env': 'KEY=x', 'gates.md': '',
                              'design/design.md': '', 'art/PLACEHOLDERS.json': '{}'})
        code, out = cap(itch, z)
        names = zipfile.ZipFile(z / 'build' / 'itch.zip').namelist()
        assert 'index.html' in names and 'js/game.js' in names and not any(n.startswith('build/') for n in names), names
        assert not {'.env', 'studio.json', 'gates.md', 'design/design.md', 'art/PLACEHOLDERS.json'} & set(names), names
        assert code == 1 and '--dry-run' in out and 'withheld' in out and 'REAL UPLOAD' not in out and 'Jam checklist' in out, out
        print('ok itch zip + fake boot')
        import importlib.util
        if (HERE / 'playtest.py').exists() and (dw / 'index.html').exists() and importlib.util.find_spec('playwright'):
            cp = shutil.copytree(dw, tmp / 'dwboot')
            cap(itch, cp)
            r = real_run(str(cp / 'build' / 'itch.zip'), mode='boot')
            assert r['verdict'] == 'PASS', r
            print('ok itch real boot on dodge-web zip')
        else:
            print('SKIP itch real boot: needs scripts/playtest.py, examples/dodge-web and playwright')

        # 4. steam
        s = put(tmp / 'steam', {'studio.json': '{"build_dir": "."}', 'index.html': ''})
        code, out = cap(steam, s)
        assert code == 2 and 'steam.appid' in out and 'steam.depotid' in out, out
        put(s, {'studio.json': '{"build_dir": ".", "steam": {"appid": 480, "depotid": 481}}',
                'store/header_capsule.png': mkpng(920, 430), 'store/small_capsule.png': mkpng(100, 100),
                'store/main_capsule.png': mkpng(1232, 706), **{f'store/screenshots/{i}.png': mkpng(1920, 1080) for i in range(4)}})
        assert png_size(s / 'store/header_capsule.png') == (920, 430) and png_size(s / 'store/main_capsule.png') == (1232, 706)
        code, out = cap(steam, s)
        vdf = (s / 'steam' / 'app_build.vdf').read_text()
        assert code == 1 and '"Preview" "1"' in vdf and '"481"' in vdf and 'withheld' in out and 'REAL UPLOAD' not in out, out
        assert 'small_capsule.png: 100x100' in out and 'vertical_capsule.png: missing' in out and '4 screenshots' in out, out
        print('ok steam vdf + IHDR')

        # 5. gate, then the only fully passing release
        if not shutil.which('git'):
            print('SKIP gate: git not on PATH')
            return 0
        code, out = cap(gate, put(tmp / 'nonrepo', {'gates.md': '## release\n- [x] final playtest PASS\n'}))
        assert code == 1 and 'not tracked by git' in out, out
        r = put(tmp / 'repo', {'studio.json': '{"build_dir": ".", "itch": "me/game", "steam": {"appid": 480, "depotid": 481}}',
                               'index.html': '<p>hi</p>', **steam_ok,
                               'gates.md': '# Gates\n\n## release\n- [ ] final playtest PASS\n- [ ] I approve this release\n'})
        gx = lambda *a: git(r, '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', *a)
        assert gx('init', '-q') is not None and gx('add', '-A') is not None and gx('commit', '-qm', 'init') is not None
        gates = (r / 'gates.md').read_text()
        (r / 'gates.md').write_text(gates.replace('- [ ] final', '- [x] final'))
        code, out = cap(gate, r)
        assert code == 1 and 'uncommitted tick' in out and 'UNTICKED' in out, out
        assert 'REAL UPLOAD' not in cap(itch, r)[1] and 'REAL UPLOAD' not in cap(steam, r, True)[1]
        gx('commit', '-qam', 'tick 1')
        (r / 'gates.md').write_text(gates.replace('- [ ]', '- [x]'))
        gx('commit', '-qam', 'tick 2')
        code, out = cap(gate, r)
        assert code == 0 and 'by t,' in out and 'GATE PASS' in out, out
        code, out = cap(itch, r)
        assert code == 0 and 'REAL UPLOAD (run it yourself): butler push build/itch.zip me/game:html5 --if-changed' in out, out
        code, out = cap(steam, r)
        assert code == 0 and 'REAL UPLOAD' not in out and '--real' in out, out
        code, out = cap(steam, r, True)
        assert code == 0 and 'REAL UPLOAD (run it yourself): steamcmd' in out, out
        assert '"Preview" "0"' in (r / 'steam' / 'app_build.vdf').read_text()
        print('ok gate blame + real commands only when everything passes')
        return 0
    finally:
        _run = real_run
        STORE['itch'].update(saved)
        shutil.rmtree(tmp, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))


def main(argv=None):
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(errors='replace')
    ap = argparse.ArgumentParser(prog='ship.py', description='playloop release checks; prints, never runs, upload commands.')
    ap.add_argument('cmd', choices=['artgate', 'gate', 'itch', 'steam', 'web', 'selftest'])
    ap.add_argument('game_dir', nargs='?', default='.')
    ap.add_argument('--dirs', help='artgate: comma-separated dirs relative to the game (default: build_dir,store)')
    ap.add_argument('--real', action='store_true', help='steam: write Preview "0" and print the real command if all checks pass')
    a = ap.parse_args(argv)
    if a.cmd == 'selftest': return selftest()
    game = Path(a.game_dir).resolve()
    if not game.is_dir():
        print(f'ERROR game dir not found: {game}')
        return 2
    if a.cmd == 'artgate': return artgate(game, a.dirs.split(',') if a.dirs else None)
    if a.cmd in ('gate', 'web'): return {'gate': gate, 'web': web}[a.cmd](game)
    return {'itch': itch, 'steam': steam}[a.cmd](game, a.real)


if __name__ == '__main__':
    sys.exit(main())
