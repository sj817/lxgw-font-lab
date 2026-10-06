"""Build the font lab into dist/.

1. Download the pinned TTFs listed in fonts.json from upstream GitHub Releases
   into .cache/fonts/ and check their sha256.
2. Cut every face into three woff2 tiers:
     a  = everything the page itself shows + Latin/punctuation/symbol blocks
     b1 = GB2312 level 1 minus a
     b2 = GB2312 level 2 minus a and b1
   Mono gets one file: ASCII-ish blocks + the characters inside <pre>/<kbd>.
3. Embed tier a (and mono) into index.html as base64, so the first paint needs
   no extra request; b1/b2 stay as files next to it and load on demand.
"""
import base64
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, '.cache', 'fonts')
DIST = os.path.join(ROOT, 'dist')
TEMPLATE = os.path.join(ROOT, 'src', 'index.html')
LICENSES = os.path.join(ROOT, 'licenses')

FACES = [
    ('wenkai', 300, 'LXGWWenKai-Light.ttf', 'lxgw-wenkai'),
    ('wenkai', 400, 'LXGWWenKai-Regular.ttf', 'lxgw-wenkai'),
    ('wenkai', 500, 'LXGWWenKai-Medium.ttf', 'lxgw-wenkai'),
    ('xihei', 400, 'LXGWNeoXiHei.ttf', 'lxgw-neoxihei'),
    ('zhisong', 400, 'LXGWNeoZhiSong.ttf', 'lxgw-neozhisong'),
]
MONO = ('LXGWWenKaiMono-Regular.ttf', 'lxgw-wenkai-mono')

BASIC_RANGES = [
    (0x20, 0x7E), (0xA0, 0x24F), (0x2B0, 0x2FF), (0x300, 0x36F), (0x370, 0x3FF), (0x400, 0x4FF),
    (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF), (0x2100, 0x214F), (0x2150, 0x218F),
    (0x2190, 0x21FF), (0x2460, 0x24FF), (0x2500, 0x257F), (0x25A0, 0x25FF), (0x2600, 0x26FF),
    (0x3000, 0x303F), (0x3040, 0x30FF), (0x3100, 0x312F), (0x3200, 0x32FF),
    (0xFE10, 0xFE1F), (0xFE30, 0xFE4F), (0xFF00, 0xFFEF),
]
MONO_RANGES = [(0x20, 0x7E), (0xA0, 0xFF), (0x2000, 0x206F), (0x2190, 0x21FF), (0x2500, 0x257F),
               (0x3000, 0x303F), (0xFF00, 0xFFEF)]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch_fonts():
    lock = json.load(open(os.path.join(ROOT, 'fonts.json'), encoding='utf-8'))
    os.makedirs(CACHE, exist_ok=True)
    for repo, rel in lock.items():
        for name, digest in rel['files'].items():
            path = os.path.join(CACHE, name)
            if os.path.exists(path) and sha256(path) == digest:
                continue
            url = f'https://github.com/{repo}/releases/download/{rel["tag"]}/{name}'
            for attempt in range(3):
                try:
                    print(f'download {url}', flush=True)
                    with urllib.request.urlopen(url, timeout=60) as res, open(path + '.part', 'wb') as f:
                        shutil.copyfileobj(res, f, 1 << 20)
                    break
                except OSError as e:
                    if attempt == 2:
                        raise
                    print(f'  retry after {e}', flush=True)
                    time.sleep(3)
            got = sha256(path + '.part')
            if got != digest:
                os.remove(path + '.part')
                sys.exit(f'sha256 mismatch for {name}: got {got}, want {digest}')
            os.replace(path + '.part', path)
    return lock


def gb2312(level):
    rows = range(0xB0, 0xD8) if level == 1 else range(0xD8, 0xF8)
    out = []
    for hi in rows:
        for lo in range(0xA1, 0xFF):
            try:
                out.append(ord(bytes([hi, lo]).decode('gb2312')))
            except UnicodeDecodeError:
                pass
    return out


def expand(ranges):
    s = set()
    for a, b in ranges:
        s.update(range(a, b + 1))
    return s


def cut(job):
    path, cps, out_path = job
    font = TTFont(path)
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['*']
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    opts.notdef_outline = True
    opts.glyph_names = False
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=sorted(cps))
    sub.subset(font)
    font.flavor = 'woff2'
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    with open(out_path, 'wb') as f:
        f.write(data)
    return out_path, len(data)


def build_date():
    epoch = os.environ.get('SOURCE_DATE_EPOCH')
    if epoch:
        return datetime.datetime.fromtimestamp(int(epoch), datetime.timezone.utc).date().isoformat()
    return datetime.date.today().isoformat()


def main():
    lock = fetch_fonts()
    html = open(TEMPLATE, encoding='utf-8').read()
    for repo, rel in lock.items():
        # The license cards on the page spell out each version; keep them in step with fonts.json.
        if rel['tag'] not in html:
            sys.exit(f'src/index.html does not mention {repo} {rel["tag"]}: update the license section')

    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(os.path.join(DIST, 'fonts'))

    page = {ord(c) for c in html if ord(c) >= 0x20}
    mono_text = ''.join(re.findall(r'<pre[^>]*>(.*?)</pre>', html, re.S) + re.findall(r'<kbd>(.*?)</kbd>', html))
    mono_text = re.sub(r'<[^>]+>', '', mono_text)

    basic = expand(BASIC_RANGES)
    l1, l2 = set(gb2312(1)), set(gb2312(2))
    want_a = basic | page
    want_b1 = l1 - want_a
    want_b2 = l2 - want_a - want_b1
    print(f'page chars {len(page)}, want a {len(want_a)} b1 {len(want_b1)} b2 {len(want_b2)}')

    date = build_date()
    manifest = {'generated': date, 'files': {}, 'fonts': {}}
    jobs = []
    cmaps = {}
    for key, w, fname, prefix in FACES:
        path = os.path.join(CACHE, fname)
        if key not in cmaps:
            cmaps[key] = set(TTFont(path, lazy=True).getBestCmap())
        cmap = cmaps[key]
        tiers = {'a': want_a & cmap, 'b1': want_b1 & cmap, 'b2': want_b2 & cmap}
        if key not in manifest['fonts']:
            manifest['fonts'][key] = {
                'cmap': len(cmap),
                'tiers': {t: ''.join(chr(c) for c in sorted(v)) for t, v in tiers.items()},
            }
        for t, cps in tiers.items():
            fid = f'{key}-{w}-{t}'
            rel = f'fonts/{fid}.woff2'
            jobs.append((path, cps, os.path.join(DIST, rel)))
            manifest['files'][fid] = {'file': rel, 'family': f'{prefix}-{t}', 'weight': w, 'chars': len(cps)}

    mono_path = os.path.join(CACHE, MONO[0])
    mono_cmap = set(TTFont(mono_path, lazy=True).getBestCmap())
    mono_cps = (expand(MONO_RANGES) | {ord(c) for c in mono_text}) & mono_cmap
    jobs.append((mono_path, mono_cps, os.path.join(DIST, 'fonts', 'mono-400-a.woff2')))
    manifest['files']['mono-400-a'] = {'file': 'fonts/mono-400-a.woff2', 'family': MONO[1], 'weight': 400, 'chars': len(mono_cps)}

    with ProcessPoolExecutor(max_workers=min(6, os.cpu_count() or 1)) as ex:
        sizes = {os.path.basename(p): n for p, n in ex.map(cut, jobs)}
    for fid, meta in manifest['files'].items():
        meta['bytes'] = sizes[os.path.basename(meta['file'])]
        print(f'{fid:20s} {meta["chars"]:6d} chars {meta["bytes"] / 1048576:7.2f} MB')
    total = sum(m['bytes'] for m in manifest['files'].values())
    print(f'total {total / 1048576:.2f} MB')

    # Tier a and mono ride inside the HTML; b1/b2 stay as files next to it.
    embed = {}
    for fid, meta in manifest['files'].items():
        if fid.endswith('-a'):
            path = os.path.join(DIST, meta['file'])
            embed[fid] = base64.b64encode(open(path, 'rb').read()).decode('ascii')
            os.remove(path)
    data = json.dumps({'manifest': manifest, 'embed': embed}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    assert html.count('__FONT_DATA__') == 1
    out_html = html.replace('__FONT_DATA__', data).replace('__BUILD_DATE__', date)
    with open(os.path.join(DIST, 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
        f.write(out_html)

    # The OFL and IPA licenses both ask for the license text to travel with the font files.
    for name in sorted(os.listdir(LICENSES)):
        shutil.copy(os.path.join(LICENSES, name), os.path.join(DIST, 'fonts', name))

    print(f'index.html {len(out_html.encode()) / 1048576:.2f} MB, embedded {len(embed)} faces')
    for k in cmaps:
        missing = ''.join(chr(c) for c in sorted((page - basic) - cmaps[k]) if c > 0x2E7F)
        if missing:
            print(f'page CJK chars missing in {k}: {missing[:80]}')


if __name__ == '__main__':
    sys.exit(main())
