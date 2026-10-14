#!/usr/bin/env python3
"""playbench ship: artgate, gate, itch, steam, web, theme, demo.
Prints upload commands for the human. Only with --real, and only when artgate, every gates.md stage and the
boot check pass, does it run butler / steamcmd / netlify (resolved through `which`). It never runs git push.
Exit codes: 0 pass, 1 blocked, 2 usage or environment error; a --real run returns the tool's exit code."""
import argparse, contextlib, fnmatch, html, io, json, os, posixpath, re, shutil, struct, subprocess, sys, tempfile, zipfile, zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import studio  # noqa: E402  the one list of playbench-owned paths
which = shutil.which  # the one binary resolver for butler/steamcmd/netlify; the selftest swaps it for stubs
STORE = {
    'itch': {'max_files': 1000, 'max_total_mb': 500, 'max_file_mb': 200, 'max_path': 240},
    'steam': {'capsules': {'header_capsule.png': (920, 430), 'small_capsule.png': (462, 174),
                           'main_capsule.png': (1232, 706), 'vertical_capsule.png': (748, 896)},
              'library': {'library_capsule.png': (600, 900), 'library_header.png': (920, 430),
                          'library_hero.png': (3840, 1240)},
              'library_logo': ('library_logo.png', (1280, 720)),  # width == 1280 or height == 720, neither larger, transparent
              'screenshots_min': 5, 'screenshot_px': (1920, 1080), 'aspect': 16 / 9, 'aspect_tol': 0.01},
    'AS_OF': '2026-10-13',
    'SOURCES': {'itch': 'https://itch.io/docs/creators/html5', 'butler': 'https://itch.io/docs/butler/pushing.html',
                'steam_assets': 'https://partner.steamgames.com/doc/store/assets/standard',
                'steam_library': 'https://partner.steamgames.com/doc/store/assets/libraryassets',
                'nextfest': 'https://partner.steamgames.com/doc/marketing/upcoming_events/nextfest',
                'steampipe': 'https://partner.steamgames.com/doc/sdk/uploading'}}
SIG = b'\x89PNG\r\n\x1a\n'
GEN = re.compile(rb'midjourney|dall-?e|stable.?diffusion|novelai|firefly|comfyui', re.I)
TAG = re.compile(r'_(placeholder|ai|wip)(?=\.[^.]+$)', re.I)
KEYS = {b'parameters', b'prompt', b'workflow'}
ABS = re.compile(r"""(?:src|href)\s*=\s*["']/(?!/)|url\(\s*["']?/(?!/)|fetch\(\s*["']/(?!/)""")
ASSET = re.compile(r"""["']([\w./-]+\.(?:png|jpe?g|webp|gif|svg|ogg|mp3|wav|json|csv|js|css|wasm|pck|html))["']""")
# excluded only when build_dir is the game root, so playbench state and dotfiles (.env) never reach an upload
SKIP = {p.split('/')[0] for p in studio.NOT_GAME}  # 'build/upload/' skips all of build/
SKIP_FILES = set(studio.NOT_GAME_FILES) | {'gates.md', 'disclosure.md', 'art/bible.md'}  # studio drops every .md itself
SKIP_EXT = ('.ase', '.aseprite')  # Aseprite sources stay out of uploads
MB = 1_000_000  # ponytail: decimal MB, the stricter reading of itch's limits


def _run(build, mode='boot'):
    """Hook for playtest.run; the selftest swaps in a fake."""
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
    return sorted(f for f in out if not (at_root and (f in SKIP_FILES or f.lower().endswith(SKIP_EXT))))


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
    f = game / 'art' / 'PLACEHOLDERS.json'
    try:  # a broken list must stop the gate, not silently un-list every placeholder in it
        ph = json.loads(f.read_text(encoding='utf-8-sig')).get('placeholders', []) if f.exists() else []
        names = {posixpath.basename(p.get('path', '').replace('\\', '/')) for p in ph} - {''}
    except (OSError, ValueError, AttributeError, TypeError) as e:
        print(f'ERROR {relto(f, game)} is unreadable ({e}); it must be {{"placeholders": [{{"path": "art/x_placeholder.png", ...}}]}}')
        raise SystemExit(2)
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
def gate(game, all_stages=False):
    """Audits the last `## <stage>`; all_stages (for --real) audits every stage."""
    p = game / 'gates.md'
    lines = p.read_text(encoding='utf-8-sig').splitlines() if p.exists() else []
    heads = [i for i, l in enumerate(lines) if l.startswith('## ')]
    if not heads:
        print('GATE BLOCKED: no gates.md with a "## <stage>" section (run studio init)')
        return 1
    tracked = git(game, 'ls-files', '--error-unmatch', '--', 'gates.md') is not None
    ok = tracked
    if not tracked: print('WARN gates.md is not tracked by git: ticks cannot be attributed')
    for n in range(heads[0 if all_stages else -1], len(lines)):
        if lines[n].startswith('## '):
            print(f'Gate audit: ## {lines[n][3:].strip()}')
            continue
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


def release_reasons(game, verdict=None, all_stages=False):
    print('\n== artgate ==')
    reasons = ['artgate BLOCKED'] if artgate(game) else []
    print('\n== gate ==')
    if gate(game, all_stages):
        reasons.append(f'gate{" (every stage, for --real)" if all_stages else ""} not fully ticked, committed and tracked')
    if verdict in ('FAIL', 'SKIP'): reasons.append(f'boot check {verdict}')
    return reasons


def build_of(game, c):
    b = (game / c.get('build_dir', '.')).resolve()
    if b.is_dir(): return b
    print(f'ERROR build_dir not found: {b} (set "build_dir" in studio.json)')
    raise SystemExit(2)


def upload_dir(game, build):
    """build_dir itself, or for the game root a fresh copy of the upload files only (as in the itch zip), so a
    Netlify site or Steam depot never publishes playtest notes, telemetry, design docs or .git."""
    if build != game.resolve(): return build
    out = game / 'build' / 'upload'
    try:  # a locked file left behind would ship a file already deleted from the game
        if out.exists(): shutil.rmtree(out)
    except OSError as e:
        print(f'ERROR cannot clear {out} ({e}); close whatever holds it open and rerun')
        raise SystemExit(2)
    out.mkdir(parents=True)
    gi = out.parent / '.gitignore'
    if not gi.exists(): gi.write_text('# playbench: staged copy, rebuilt by every ship run\nupload/\n', encoding='utf-8')
    for rel in walk(build, game):
        (out / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(build / rel, out / rel)
    print(f'staged {out} (build_dir is the game root: the game files only, without playbench state, notes or telemetry)')
    return out


def verdict_line(reasons, real_cmd, what='upload', run=None, cwd=None):
    """Prints the real command, or with run=[tool, *args] (--real) executes it once every check passed."""
    print()
    if reasons:
        print(f'Real {what} command withheld: {"; ".join(reasons)}')
        return 1
    exe = which(run[0]) if run else None
    if not exe:
        print(f'REAL {what.upper()} (run it yourself): {real_cmd}')
        if run: print(f'{run[0]} not found on PATH, so nothing ran')
        return 0
    cmd = [exe, *run[1:]]  # the resolved path: CreateProcess ignores PATHEXT for a bare name
    print(f'RAN {subprocess.list2cmdline(cmd)}', flush=True)
    code = subprocess.run(cmd, cwd=cwd).returncode  # inherited stdio: steamcmd may ask for a password or Steam Guard
    print(f'UPLOAD_EXIT={code}')
    return code


def itch(game, real=False):
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
    if not which('butler'): print('install butler: https://itch.io/docs/butler/installing.html')
    print('Manual steps (itch dashboard, Edit game):\n  1. Kind of project: HTML.\n'
          '  2. On the upload, tick "This file will be played in the browser".\n'
          '  3. Embed: set the viewport to your canvas size, enable the fullscreen button, disable scrollbars.\n'
          '  4. SharedArrayBuffer support: enable only for threaded builds.\n'
          '  5. Edit theme: colors, banner, fonts; add 3-5 screenshots and a GIF; put the controls first.')
    if c.get('context') == 'jam':
        print('Jam checklist:\n  [ ] submit to the jam page before the deadline\n  [ ] cover image and screenshots added\n'
              '  [ ] controls written in the description\n  [ ] uploaded page tested in a private window')
    reasons = release_reasons(game, verdict, real) + ([] if c.get('itch') else ['studio.json has no "itch": "user/game"'])
    push = ['push', 'build/itch.zip', f'{target}:html5', '--if-changed']
    return verdict_line(reasons, subprocess.list2cmdline(['butler', *push]), run=['butler', *push] if real else None, cwd=game)


def web(game, host=None, real=False):
    if real and host != 'netlify':
        print('ERROR --real needs --host netlify (GitHub Pages is a git push, which you always run yourself)')
        return 2
    build = build_of(game, cfg(game))
    pub = upload_dir(game, build) if host in (None, 'netlify') else build  # check what ships, not the game root
    errs, rel = limits(pub, walk(pub, game), itch=False), relto(build, game)
    q = lambda s: subprocess.list2cmdline([s])  # quotes a build_dir with spaces in the printed commands
    print('\n'.join(f'BLOCKED {e}' for e in errs) or 'index.html and URLs PASS')
    verdict = boot(pub)
    if host in (None, 'pages'):
        print('\nGitHub Pages (run it yourself; ship.py never runs git push):')
        if rel == '.':
            print('  (a) push this repo, then Settings > Pages > Source: main, / (root).')
        else:
            print(f'  (a) gh-pages branch: commit the build, then `git subtree push --prefix {q(rel)} origin gh-pages`,\n'
                  '      then Settings > Pages > Source: gh-pages branch.')
            print(f'  (b) docs/ folder: `mkdir -p docs && cp -r {q(rel + "/.")} docs/`, commit and push main,\n'
                  '      then Settings > Pages > Source: main, /docs.')
    if host in (None, 'netlify'):
        rel, toml = relto(pub, game), game / 'netlify.toml'
        cli = ' (CLI deploys only: rerun ship.py web first, a git-connected site has no build/upload)' if pub != build else ''
        if host and not toml.exists():
            toml.write_text(f'# playbench: netlify deploy publishes this folder{cli}; edit freely, ship.py never overwrites it\n'
                            f'[build]\n  publish = {json.dumps(rel)}\n', encoding='utf-8')  # a JSON string is a valid TOML string
            print(f'\nwrote {toml}')
        print(f'\nNetlify dry run (draft URL, check it first): netlify deploy --dir {q(rel)}')
    reasons = (['index.html / root-absolute URL problems'] if errs else []) + release_reasons(game, verdict, real)
    if host == 'pages': return verdict_line(reasons, 'the GitHub Pages steps above', 'deploy')
    prod = ['deploy', '--dir', rel, '--prod']
    return verdict_line(reasons, subprocess.list2cmdline(['netlify', *prod]), 'deploy', ['netlify', *prod] if real else None, game)


def png_size(p):
    with open(p, 'rb') as f: d = f.read(24)
    return struct.unpack('>II', d[16:24]) if d[:8] == SIG and d[12:16] == b'IHDR' else None


def png_alpha(p):
    """Color type 4/6 (gray/RGB + alpha), or a tRNS chunk before the image data."""
    d, i = p.read_bytes(), 8
    if len(d) > 25 and d[25] in (4, 6): return True
    while i + 8 <= len(d):
        n, t = struct.unpack('>I4s', d[i:i + 8])
        if t == b'tRNS': return True
        if t in (b'IDAT', b'IEND'): return False
        i += 12 + n
    return False


def store_errs(game):
    S, errs = STORE['steam'], []
    for name, want in {**S['capsules'], **S['library']}.items():
        p = game / 'store' / name
        got = (png_size(p) or 'not a PNG') if p.exists() else 'missing'
        if got != want: errs.append(f'store/{name}: {got if isinstance(got, str) else "%dx%d" % got} (need {want[0]}x{want[1]} PNG)')
    name, (lw, lh) = S['library_logo']
    p = game / 'store' / name
    wh = png_size(p) if p.exists() else None
    if not wh or wh[0] > lw or wh[1] > lh or (wh[0] != lw and wh[1] != lh):
        errs.append(f'store/{name}: {"%dx%d" % wh if wh else "missing or not a PNG"} (need width {lw} or height {lh}, neither larger)')
    elif not png_alpha(p):
        errs.append(f'store/{name}: needs transparency (an RGBA or gray+alpha PNG, or a tRNS chunk)')
    shots, (mw, mh) = sorted((game / 'store' / 'screenshots').glob('*.png')), S['screenshot_px']
    if len(shots) < S['screenshots_min']:
        errs.append(f'{len(shots)} screenshots in store/screenshots (need at least {S["screenshots_min"]})')
    for p in shots:
        wh = png_size(p)
        if not wh or wh[0] < mw or wh[1] < mh or abs(wh[0] / wh[1] / S['aspect'] - 1) > S['aspect_tol']:
            errs.append(f'store/screenshots/{p.name}: {wh} (need >= {mw}x{mh}, 16:9)')
    return errs


def write_vdf(vdf, appid, depot, build, preview):
    vdf.parent.mkdir(exist_ok=True)
    vdf.write_text(f'"AppBuild"\n{{\n "AppID" "{appid}"\n "Desc" "playbench build"\n "Preview" "{preview}"\n'
                   f' "ContentRoot" "{build.as_posix()}"\n "BuildOutput" "{vdf.parent.as_posix()}/output/"\n'
                   f' "Depots"\n {{\n  "{depot}"\n  {{\n'
                   '   "FileMapping" { "LocalPath" "*" "DepotPath" "." "recursive" "1" }\n  }\n }\n}\n', encoding='utf-8')


def steamcmd_line(user, vdf):
    return f'steamcmd +login {user or "<your_steam_user>"} +run_app_build "{vdf}" +quit'


def steam(game, real=False):
    c = cfg(game)
    s = c.get('steam') or {}
    miss = [f'steam.{k}' for k in ('appid', 'depotid') if not s.get(k)]
    if miss:
        print(f'ERROR studio.json is missing {", ".join(miss)}; add "steam": {{"appid": <app id>, "depotid": <depot id>}}')
        return 2
    build, vdf = upload_dir(game, build_of(game, c)), (game / 'steam' / 'app_build.vdf').resolve()
    write_vdf(vdf, s['appid'], s['depotid'], build, 1)
    print(f'wrote {vdf} (Preview "1": checks the build, uploads nothing)')
    errs = store_errs(game)
    print('\n'.join(f'BLOCKED {e}' for e in errs) or 'store and library assets PASS',
          f'({STORE["SOURCES"]["steam_assets"]}, {STORE["SOURCES"]["steam_library"]}, as of {STORE["AS_OF"]})')
    reasons = (['store assets'] if errs else []) + release_reasons(game, all_stages=real)
    user, cmd = s.get('builder'), steamcmd_line(s.get('builder'), vdf)
    if real and not reasons:
        write_vdf(vdf, s['appid'], s['depotid'], build, 0)
        code = verdict_line([], cmd, run=['steamcmd', '+login', user, '+run_app_build', str(vdf), '+quit'] if user else None)
        if not user: print('studio.json has no steam.builder (your Steam build account), so nothing ran')
        print('Then set the build live on a branch in Steamworks (App Admin > SteamPipe > Builds).')
        return code
    print(f'\nPreview (run it yourself): {cmd}')
    verdict_line(reasons or ['rerun with --real'], cmd)
    return 1 if reasons else 0


DEMO = """Steam Playtest (free, separate from a demo):
  [ ] In Steamworks, the base app's 'Steam Playtest' section creates a separate Playtest app id
  [ ] Pick the access mode: open signup from your store page (you let players in, in batches) or keys/invites only
  [ ] The Playtest app has its own depot and build: upload to it like any app (its own appid/depot in a vdf)
  [ ] Turn signups on and off as you go; collect feedback with a sheet or survey from /playbench:playtest
Next Fest demo:
  [ ] Request a demo app from the base app in Steamworks (it gets its own app id and depot)
  [ ] The base game's Coming Soon store page is live
  [ ] Demo store page and demo build submitted for review well before the event
  [ ] Registered for the Next Fest edition before its registration deadline
  [ ] Press preview window planned (press and creators play the demo before the fest)
  [ ] Optional: a trailer, a livestream during the fest
  [ ] Wishlists are the goal: the demo ends with a clear 'wishlist the full game' call"""


def demo(game):
    c = cfg(game)
    s = c.get('steam') or {}
    print(DEMO)
    print(f'Check {STORE["SOURCES"]["nextfest"]} for current dates (as of {STORE["AS_OF"]}).\n')
    for k in ('playtest_appid', 'demo_appid', 'demo_depotid'):
        print(f'STEAM_{k.upper()}={s.get(k) or "unset"}')
    if not (s.get('demo_appid') and s.get('demo_depotid')):
        print('Add "demo_appid" and "demo_depotid" under "steam" in studio.json to get steam/demo_build.vdf.')
        return 0
    vdf = (game / 'steam' / 'demo_build.vdf').resolve()
    write_vdf(vdf, s['demo_appid'], s['demo_depotid'], upload_dir(game, build_of(game, c)), 1)
    print(f'wrote {vdf} (Preview "1": checks the build, uploads nothing)')
    print(f'Preview (run it yourself): {steamcmd_line(s.get("builder"), vdf)}')
    return 0


# ---------- itch theme ----------
def bible(game):
    """Contract C6: `- name: #rrggbb` under ## Palette, `- heading:` / `- body:` under ## Fonts; the rest is ignored."""
    sec, pal, fonts = '', {}, {}
    for l in (game / 'art' / 'bible.md').read_text(encoding='utf-8-sig').splitlines():
        if l.startswith('## '): sec = l[3:].strip().lower()
        m = re.match(r'\s*- ([^:]+?)\s*:\s*(.+?)\s*$', l)
        if m and sec == 'palette' and re.match(r'#[0-9a-f]{6}\b', m.group(2), re.I): pal[m.group(1).lower()] = m.group(2)[:7].lower()
        elif m and sec == 'fonts': fonts[m.group(1).lower()] = re.sub(r'[^\w \-]', '', m.group(2)).strip()
    return pal, fonts


def contrast(a, b):
    """WCAG 2 contrast ratio of two #rrggbb colors."""
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def theme(game, css=False):
    if not (game / 'art' / 'bible.md').exists():
        print('ERROR no art/bible.md: run /playbench:art to write art/bible.md')
        return 2
    pal, fonts = bible(game)
    miss = [r for r in ('bg', 'text', 'link', 'button') if r not in pal]
    if miss:
        print(f'ERROR art/bible.md ## Palette is missing {", ".join(miss)} (add lines like "- {miss[0]}: #rrggbb")')
        return 2
    head, body = fonts.get('heading') or 'sans-serif', fonts.get('body') or 'sans-serif'
    checks = [f'- {k} on bg: {r:.1f}:1 {"PASS" if r >= 4.5 else "WARN under 4.5:1 (WCAG AA): hard to read"}'
              for k, r in ((k, contrast(pal[k], pal['bg'])) for k in ('text', 'link'))]
    extra = [f'{k} {v}' for k, v in pal.items() if k not in ('bg', 'text', 'link', 'button')]
    out = game / 'store'
    out.mkdir(exist_ok=True)
    (out / 'itch-theme.md').write_text(
        f'# itch page theme (from art/bible.md)\n\nOn itch: your game page > **Edit theme**. Field names in itch\'s editor '
        f'may differ slightly (as of {STORE["AS_OF"]}).\n\n- [ ] Background color: {pal["bg"]}\n- [ ] Text color: {pal["text"]}\n'
        f'- [ ] Link color: {pal["link"]}\n- [ ] Button color: {pal["button"]}\n- [ ] Header font: {head}\n- [ ] Body font: {body}\n'
        + (f'\nOther palette colors (banner, secondary background): {", ".join(extra)}\n' if extra else '')
        + '\n## Contrast (WCAG)\n' + '\n'.join(checks) + '\n\nOffline preview: store/itch-theme.html\n', encoding='utf-8')
    ff = lambda f: f'"{f}", system-ui, sans-serif'
    title = html.escape(game.name)
    (out / 'itch-theme.html').write_text(f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}: itch theme preview</title><style>
body{{margin:0;background:{pal["bg"]};color:{pal["text"]};font-family:{ff(body)}}}
h1{{font-family:{ff(head)}}} a{{color:{pal["link"]}}} main{{max-width:960px;margin:0 auto;padding:16px}}
.banner{{height:160px;display:flex;align-items:center;justify-content:center;font:bold 40px {ff(head)};background:linear-gradient(135deg,{pal["button"]},{pal["bg"]})}}
.button{{display:inline-block;background:{pal["button"]};color:{pal["text"]};padding:10px 20px;border-radius:4px;text-decoration:none;font-weight:bold}}
.shots{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin:24px 0}}
.shots div{{aspect-ratio:16/9;border:2px dashed;opacity:.6;display:flex;align-items:center;justify-content:center}}
</style></head><body><div class="banner">{title}</div><main><h1>{title}</h1>
<p>Arrow keys to move, Space to jump. A mock of your itch page in the art bible's colors and fonts
(fonts show only if installed on this computer; itch loads them for you).</p><p><a href="#">A link in the description</a></p>
<a class="button" href="#">Play in browser</a><div class="shots"><div>screenshot 1</div><div>screenshot 2</div><div>screenshot 3</div></div>
<p><small>Offline preview by playbench ship theme. Nothing here loads from the network.</small></p></main></body></html>
''', encoding='utf-8')
    print(f'wrote {out / "itch-theme.md"}\nwrote {out / "itch-theme.html"}')
    print('\n'.join(checks))
    if css:
        (out / 'itch-custom.css').write_text(
            f'/* playbench: generic rules from art/bible.md. itch\'s page markup can change: check it in the theme editor. */\n'
            f'body, .inner_column {{ background: {pal["bg"]}; color: {pal["text"]}; font-family: {ff(body)}; }}\n'
            f'.inner_column a {{ color: {pal["link"]}; }}\n'
            f'.inner_column h1, .inner_column h2, .inner_column h3 {{ font-family: {ff(head)}; }}\n'
            f'.inner_column .button {{ background: {pal["button"]}; border-color: {pal["button"]}; color: {pal["text"]}; }}\n',
            encoding='utf-8')
        print(f'wrote {out / "itch-custom.css"}')
        print('itch must enable custom CSS for your account first (ask itch support); paste it in the theme editor and check it there.')
    return 0


# ---------- selftest ----------
def mkpng(w=1, h=1, extra=(), ct=2):
    ch = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d))
    # ponytail: IDAT is a valid 1x1 RGB image; larger sizes and other color types only need a correct IHDR here
    return (SIG + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0)) + b''.join(ch(t, d) for t, d in extra)
            + ch(b'IDAT', zlib.compress(b'\0\0\0\0')) + ch(b'IEND', b''))


def stub(dirpath, name, body):
    """Contract C7: fake executable `name` in dirpath that runs python source `body` with this interpreter."""
    py = dirpath / f'{name}_stub.py'
    py.write_text(body, 'utf-8')
    if os.name == 'nt':
        exe = dirpath / f'{name}.cmd'
        exe.write_text(f'@"{sys.executable}" "{py}" %*\n', 'utf-8')
    else:
        exe = dirpath / name
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{py}" "$@"\n', 'utf-8')
        exe.chmod(0o755)
    return exe


def selftest():
    global _run, which
    real_run, real_which, saved = _run, which, dict(STORE['itch'])
    _run = lambda build, mode='boot': {'verdict': 'PASS', 'summary': 'PASS: fake boot'}
    which = lambda name: None  # no real butler/steamcmd/netlify can ever run from the selftest
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
                'store/library_capsule.png': mkpng(600, 900), 'store/library_header.png': mkpng(920, 430),
                'store/library_hero.png': mkpng(3840, 1240), 'store/library_logo.png': mkpng(1280, 400, ct=6),
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
        for bad in ('[]', '{"placeholders": "x"}', '{oops'):  # malformed list: setup error, never a silent pass
            bp = put(tmp / 'badph', {'studio.json': '{"build_dir": "."}', 'index.html': '', 'art/PLACEHOLDERS.json': bad})
            try:
                cap(artgate, bp)
                code = None
            except SystemExit as e:
                code = e.code
            assert code == 2, bad
        print('ok artgate malformed PLACEHOLDERS.json')

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
                              'design/design.md': '', 'art/PLACEHOLDERS.json': '{}', 'feedback/x.md': '',
                              'telemetry/e.jsonl': '', 'art/bible.md': '', 'art/hero.aseprite': 'x', 'netlify.toml': ''})
        code, out = cap(itch, z)
        names = zipfile.ZipFile(z / 'build' / 'itch.zip').namelist()
        assert 'index.html' in names and 'js/game.js' in names and not any(n.startswith('build/') for n in names), names
        assert not {'.env', 'studio.json', 'gates.md', 'design/design.md', 'art/PLACEHOLDERS.json', 'feedback/x.md',
                    'telemetry/e.jsonl', 'art/bible.md', 'art/hero.aseprite', 'netlify.toml'} & set(names), names
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
        assert '/build/upload"' in vdf and not (s / 'build' / 'upload' / 'studio.json').exists(), vdf  # depot gets game files only
        assert 'small_capsule.png: 100x100' in out and 'vertical_capsule.png: missing' in out and '4 screenshots' in out, out
        print('ok steam vdf + IHDR')
        lib = put(tmp / 'lib', dict(steam_ok))
        assert store_errs(lib) == [], store_errs(lib)
        put(lib, {'store/library_hero.png': mkpng(1920, 620)})
        assert ['library_hero.png: 1920x620' in e for e in store_errs(lib)] == [True], store_errs(lib)
        put(lib, {'store/library_hero.png': mkpng(3840, 1240), 'store/library_logo.png': mkpng(1280, 720)})
        assert ['needs transparency' in e for e in store_errs(lib)] == [True], store_errs(lib)
        put(lib, {'store/library_logo.png': mkpng(1280, 720, [(b'tRNS', b'\0\0\0\0\0\0')])})
        assert store_errs(lib) == [], store_errs(lib)
        put(lib, {'store/library_logo.png': mkpng(1400, 720, ct=6)})
        assert ['library_logo.png: 1400x720' in e for e in store_errs(lib)] == [True], store_errs(lib)
        print('ok steam library assets')

        # 4b. itch theme from art/bible.md
        bib = '# Art bible: t\n## Palette\n- BG: #1B1B2F\n- text: #f5f5f5\n- link: #ffcc00\n- button: #e94560\n## Fonts\n' \
              '- heading: Press Start 2P\n- body: Inter\n## Pixel density\n- tile: 16\n'
        t = put(tmp / 'theme', {'studio.json': '{"build_dir": "."}', 'index.html': ''})
        code, out = cap(theme, t)
        assert code == 2 and '/playbench:art' in out, out
        put(t, {'art/bible.md': bib})
        code, out = cap(theme, t, True)
        md, page = (t / 'store/itch-theme.md').read_text(), (t / 'store/itch-theme.html').read_text()
        assert code == 0 and all(h in md for h in ('#1b1b2f', '#f5f5f5', '#ffcc00', '#e94560', 'Press Start 2P', 'Inter')), md
        assert '#1b1b2f' in page and 'http' not in page and 'WARN' not in out, (page, out)
        assert (t / 'store/itch-custom.css').exists() and 'ask itch support' in out, out
        put(t, {'art/bible.md': bib.replace('#ffcc00', '#2a2a40')})
        code, out = cap(theme, t)
        assert code == 0 and 'link on bg' in out and 'WARN' in out, out
        put(t, {'art/bible.md': bib.replace('- button: #e94560\n', '')})
        code, out = cap(theme, t)
        assert code == 2 and 'button' in out, out
        assert round(contrast('#000000', '#ffffff'), 1) == 21.0 and round(contrast('#777777', '#ffffff'), 2) == 4.48
        print('ok theme')

        # 4c. web hosts (dry run) and demo
        w = put(tmp / 'web', {'studio.json': '{"build_dir": "."}', 'index.html': '<p>hi</p>', 'playtests/a-human.md': 'notes',
                              'telemetry/t.jsonl': '{}'})
        booted, fake = [], _run
        _run = lambda build, mode='boot': booted.append(build) or fake(build, mode)
        cap(web, w, 'netlify')
        _run = fake
        assert booted == [str(w / 'build' / 'upload')], booted  # boot checks the staged copy that ships, not the root
        assert 'publish = "build/upload"' in (w / 'netlify.toml').read_text() and 'CLI deploys only' in (w / 'netlify.toml').read_text()
        assert 'upload/' in (w / 'build' / '.gitignore').read_text()  # the staged copy never lands in git
        assert sorted(f.name for f in (w / 'build' / 'upload').rglob('*')) == ['index.html']  # no notes or telemetry
        (w / 'netlify.toml').write_text('# mine\n')
        code, out = cap(web, w, 'netlify')
        assert (w / 'netlify.toml').read_text() == '# mine\n' and 'netlify deploy --dir build/upload' in out and 'git subtree' not in out, out
        wp = put(tmp / 'webp', {'studio.json': '{"build_dir": "my public"}', 'my public/index.html': '<p>hi</p>'})
        code, out = cap(web, wp, 'pages')
        assert 'git subtree push --prefix "my public" origin gh-pages' in out and 'run it yourself' in out, out
        assert 'cp -r "my public/." docs/' in out, out
        assert not (wp / 'netlify.toml').exists() and cap(web, wp, 'pages', True)[0] == 2
        d = put(tmp / 'demo', {'studio.json': '{"build_dir": ".", "steam": {"appid": 480, "depotid": 481}}', 'index.html': ''})
        code, out = cap(demo, d)
        assert code == 0 and 'Next Fest' in out and 'STEAM_DEMO_APPID=unset' in out and not (d / 'steam').exists(), out
        put(d, {'studio.json': '{"build_dir": ".", "steam": {"appid": 480, "depotid": 481, "demo_appid": 490, "demo_depotid": 491}}'})
        code, out = cap(demo, d)
        vdf = (d / 'steam' / 'demo_build.vdf').read_text()
        assert code == 0 and '"AppID" "490"' in vdf and '"491"' in vdf and '"Preview" "1"' in vdf and 'demo_build.vdf' in out, out
        print('ok web hosts + demo')

        # 5. gate, then the only fully passing release
        if not shutil.which('git'):
            print('SKIP gate: git not on PATH')
            return 0
        code, out = cap(gate, put(tmp / 'nonrepo', {'gates.md': '## release\n- [x] final playtest PASS\n'}))
        assert code == 1 and 'not tracked by git' in out, out
        r = put(tmp / 'repo', {'studio.json': '{"build_dir": ".", "itch": "me/game", "steam": {"appid": 480, "depotid": 481}}',
                               'index.html': '<p>hi</p>', **steam_ok,
                               'gates.md': '# Gates\n\n## playable\n- [ ] it runs\n\n'
                                           '## release\n- [ ] final playtest PASS\n- [ ] I approve this release\n'})
        gx = lambda *a: git(r, '-c', 'user.name=t', '-c', 'user.email=t@t', '-c', 'commit.gpgsign=false', *a)
        assert gx('init', '-q') is not None and gx('add', '-A') is not None and gx('commit', '-qm', 'init') is not None
        gates = (r / 'gates.md').read_text()
        (r / 'gates.md').write_text(gates.replace('- [ ] final', '- [x] final'))
        code, out = cap(gate, r)
        assert code == 1 and 'uncommitted tick' in out and 'UNTICKED' in out, out
        assert 'REAL UPLOAD' not in cap(itch, r)[1] and 'REAL UPLOAD' not in cap(steam, r, True)[1]
        gx('commit', '-qam', 'tick 1')
        (r / 'gates.md').write_text(gates.replace('- [ ] final', '- [x] final').replace('- [ ] I', '- [x] I'))
        gx('commit', '-qam', 'tick 2')
        code, out = cap(gate, r)
        assert code == 0 and 'by t,' in out and 'GATE PASS' in out, out
        # --real against stubs only: each appends its argv to log
        log, bindir = tmp / 'stub.log', tmp / 'bin'
        bindir.mkdir()
        stubs = {n: stub(bindir, n, f'import sys\nopen({str(log)!r}, "a").write(" ".join(sys.argv[1:]) + "\\n")\n')
                 for n in ('butler', 'steamcmd', 'netlify')}
        which = lambda name: str(stubs[name]) if name in stubs else None
        code, out = cap(itch, r, True)  # release stage passes, the earlier playable box is still unticked
        assert code == 1 and 'withheld' in out and 'every stage' in out and not log.exists(), out
        (r / 'gates.md').write_text(gates.replace('- [ ]', '- [x]'))
        gx('commit', '-qam', 'tick 3')
        code, out = cap(itch, r, True)
        assert code == 0 and 'RAN ' in out and 'UPLOAD_EXIT=0' in out, out
        assert 'push build/itch.zip me/game:html5 --if-changed' in log.read_text(), log.read_text()
        log.unlink()
        put(r, {'studio.json': '{"build_dir": ".", "itch": "me/game", "steam": {"appid": 480, "depotid": 481, "builder": "bob"}}'})
        code, out = cap(steam, r, True)
        assert code == 0 and '+login bob +run_app_build' in log.read_text() and 'UPLOAD_EXIT=0' in out, (out, log.read_text())
        assert '"Preview" "0"' in (r / 'steam' / 'app_build.vdf').read_text()
        log.unlink()
        code, out = cap(web, r, 'netlify', True)
        assert code == 0 and 'deploy --dir build/upload --prod' in log.read_text(), (out, log.read_text())
        log.unlink()
        which = lambda name: None
        code, out = cap(itch, r, True)
        assert code == 0 and 'REAL UPLOAD (run it yourself): butler push' in out and 'butler not found on PATH, so nothing ran' in out, out
        assert not log.exists()
        print('ok --real runs stubs only when every stage, artgate and boot pass')
        put(r, {'studio.json': '{"build_dir": ".", "itch": "me/game", "steam": {"appid": 480, "depotid": 481}}'})
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
        _run, which = real_run, real_which
        STORE['itch'].update(saved)
        shutil.rmtree(tmp, onerror=lambda f, p, e: (os.chmod(p, 0o700), f(p)))


def main(argv=None):
    with contextlib.suppress(AttributeError):
        sys.stdout.reconfigure(errors='replace')
    ap = argparse.ArgumentParser(prog='ship.py', description='playbench release checks; prints upload commands, runs them only with --real.')
    ap.add_argument('cmd', choices=['artgate', 'gate', 'itch', 'steam', 'web', 'theme', 'demo', 'selftest'])
    ap.add_argument('game_dir', nargs='?', default='.')
    ap.add_argument('--dirs', help='artgate: comma-separated dirs relative to the game (default: build_dir,store)')
    ap.add_argument('--host', choices=['pages', 'netlify'], help='web: one host (default: print both)')
    ap.add_argument('--css', action='store_true', help='theme: also write store/itch-custom.css')
    ap.add_argument('--real', action='store_true', help='itch, steam, web --host netlify: run the upload when artgate, '
                                                        'every gates.md stage and the boot check pass')
    a = ap.parse_args(argv)
    if a.cmd == 'selftest': return selftest()
    game = Path(a.game_dir).resolve()
    if not game.is_dir():
        print(f'ERROR game dir not found: {game}')
        return 2
    if a.cmd == 'artgate': return artgate(game, a.dirs.split(',') if a.dirs else None)
    if a.cmd == 'web': return web(game, a.host, a.real)
    if a.cmd == 'theme': return theme(game, a.css)
    if a.cmd in ('gate', 'demo'): return {'gate': gate, 'demo': demo}[a.cmd](game)
    return {'itch': itch, 'steam': steam}[a.cmd](game, a.real)


if __name__ == '__main__':
    sys.exit(main())
