#!/usr/bin/env python3
"""Catalog-gap analysis: caravansanat.com categories vs. dashboard workshops.

1. Reads every product category of caravansanat.com (public WordPress API, read-only,
   one page of 100 every ~1.2 s) and caches it in <DATA_DIR>/cats.json.
2. Matches each category name against the products of the dashboard units
   (units_b2b.json + units_d2c.json in DATA_DIR).
3. Writes <DATA_DIR>/gaps.json with:
   - cats : categories that have workshops, their product count on the site (gap A = empty, C = thin)
   - subs : coverage per dashboard sub-category + frequent product phrases with no category (gap B)
   - needs: industrial needs of consumer (D2C) workshops vs. site categories and dashboard suppliers
Only unit ids are written (no names or phones); the page joins them with units_*.json.

Usage:  python3 gaps.py                 fetch categories, then analyse
        python3 gaps.py --no-fetch      reuse cats.json
        python3 gaps.py --cats FILE     use a local category file (testing)
Only the Python standard library is used.
"""
import json, math, os, random, re, sys, time, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone

DATA_DIR = os.environ.get('DATA_DIR', '/usr/share/nginx/html/data')
SITE = os.environ.get('SITE', 'https://caravansanat.com')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'

# How well each dashboard model fits a B2B catalog like caravansanat
FIT = {
    'فروش B2B آنلاین (کاروان صنعت)': 1.0,
    'پلتفرم B2B / سرنخ': 0.8,
    'مارکت‌پلیس خدمات تولیدی (سفارش ساخت)': 0.6,
    'صادرات/B2B منطقه‌ای': 0.6,
    'نمایندگی آنلاین برند خودشون': 0.5,
    'برند خودمون (Private Label)': 0.3,
    'خارج از محدوده': 0.0,
}
B2B_MODELS = {m for m, w in FIT.items() if w >= 0.6}

STOP = set('و با از به در برای یا سایر متفرقه انواع کلیه همه انواعی جهت مخصوص نوع مدل سری تا'.split())
GENERIC = set('لوازم تجهیزات قطعات ابزار ابزارهای دستگاه دستگاههای صنعتی محصولات محصول مواد سیستم یدکی جانبی کیت ست '
              'ماشین الات ماشینالات تولید ساخت انواع خدمات'.split())
# single words too ambiguous to stand alone as a category match
AMBIG = set('تبدیل رابط مغزی کمربند درپوش کپ برس پایه قاب سینی جعبه میز کیف گیره پانچر سه چهار دو تک '
            'فلوتر سوپاپ کر خار قلم پیچ مهره بست کلید شیر فنر چرخ تسمه نوار سیم لوله کابل فیلتر رنگ چسب '
            'پمپ موتور کولر جک گان پدال سیفون پنل لامپ ریسه کود بذر روغن ورق فرز اره دریل مته اتو پرس قالب '
            'برقی خانگی ساختمانی فلزی پلاستیکی دستی شارژی بادی هیدرولیکی هیدرولیک پنوماتیک صنعتی کشاورزی '
            'سنگ جعبه چوب کاغذ اشپزخانه حمام اب گاز هوا برق استیل فولادی چدنی مسی الومینیومی پلی اتیلن'.split())
PHRASE_STOP = STOP | GENERIC | set('انواع تولید ساخت و از با در جهت مختلف کاربرد کاربردی بسته بندی شده های ها '
                                    'سایز رنگی ساده درجه یک دو سه کیلو کیلویی گرم گرمی لیتر لیتری سانتی متر میلی عدد '
                                    'خام نیمه صادراتی داخلی خارجی غیر تجهیز قطعه جنس اقلام فراورده انواعی کلیه سایز مختلف '
                                    'شامل نوع اندازه'.split())

ARABIC = str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ة': 'ه', 'ۀ': 'ه', 'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ؤ': 'و',
                        '‌': ' ', '‏': ' ', '‎': ' ', 'ـ': '',
                        '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'})
NONWORD = re.compile(r'[^0-9a-z؀-ۿ]+')


def norm(s):
    s = (s or '').lower().translate(ARABIC)
    s = re.sub(r'[ً-ٰٟ]', '', s)  # diacritics
    return NONWORD.sub(' ', s).strip()


def stem(t):
    for suf in ('هایی', 'های', 'ها', 'ات'):
        if t.endswith(suf) and len(t) - len(suf) >= 3:
            return t[:-len(suf)]
    return t


def _stems(words):
    return {stem(norm(w)) for w in words} | set(words)


STOP, GENERIC, AMBIG, PHRASE_STOP = _stems(STOP), _stems(GENERIC), _stems(AMBIG), _stems(PHRASE_STOP)


def toks(s):
    out = []
    for t in norm(s).split():
        if t.isdigit():
            continue
        out.append(stem(t))
    return out


# ---------------- categories ----------------
def fetch_categories():
    cats, page, pages = [], 1, 1
    while page <= pages:
        url = f'{SITE}/wp-json/wp/v2/product_cat?per_page=100&page={page}&_fields=id,name,parent,count'
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    pages = int(r.headers.get('X-WP-TotalPages') or 1)
                    cats += json.loads(r.read().decode('utf-8'))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    raise
                print('retry', page, e, flush=True)
                time.sleep(5)
        if page % 20 == 0:
            print(f'categories page {page}/{pages}', flush=True)
        page += 1
        time.sleep(random.uniform(1.0, 1.5))
    for c in cats:  # WordPress returns HTML entities in names
        c['name'] = c['name'].replace('&amp;', '&').replace('&#8211;', '–')
    return cats


def load_units():
    units = []
    for f in ('units_b2b.json', 'units_d2c.json'):
        p = os.path.join(DATA_DIR, f)
        if os.path.exists(p):
            units += json.load(open(p, encoding='utf-8'))
    return [u for u in units if FIT.get(u.get('model'), 0) > 0]


def required_tokens(name):
    ts = [t for t in toks(name) if t not in STOP and len(t) >= 2]
    core = [t for t in ts if t not in GENERIC]
    if not core:
        return None
    if len(core) == 1 and (core[0] in AMBIG or len(core[0]) < 3):
        # ambiguous single word: keep the generic words too ("پمپ" alone is useless, "دستگاه پرکن" is fine)
        if len(ts) == 1:
            return None
        core = ts
    return core


def main():
    args = sys.argv[1:]
    cache = os.path.join(DATA_DIR, 'cats.json')
    if '--cats' in args:
        cats = json.load(open(args[args.index('--cats') + 1], encoding='utf-8'))
    elif '--no-fetch' in args and os.path.exists(cache):
        cats = json.load(open(cache, encoding='utf-8'))
    else:
        cats = fetch_categories()
        json.dump(cats, open(cache, 'w', encoding='utf-8'), ensure_ascii=False)
    print('categories:', len(cats), flush=True)

    by = {c['id']: c for c in cats}
    def path(c):
        p, x, guard = [], c, 0
        while x.get('parent') in by and guard < 10:
            x = by[x['parent']]; p.append(x['name']); guard += 1
        return ' › '.join(reversed(p))
    def root(c):
        x, guard = c, 0
        while x.get('parent') in by and guard < 10:
            x = by[x['parent']]; guard += 1
        return x['name']

    units = load_units()
    print('units in scope:', len(units), flush=True)
    utok = []
    index = defaultdict(set)
    for i, u in enumerate(units):
        ts = toks(u.get('products', ''))
        s = set(ts)
        s |= {a + b for a, b in zip(ts, ts[1:])}  # "چند لایه" also as "چندلایه"
        utok.append(s)
        for t in s:
            index[t].add(i)

    def has_mobile(i):
        return bool(units[i].get('mobile'))

    # ---- match categories
    cat_units = {}
    unit_cats = defaultdict(list)
    seen_keys = set()
    # parents first, so a duplicate name keeps the broader category
    depth = {}
    for c in cats:
        d, x = 0, c
        while x.get('parent') in by and d < 10:
            x = by[x['parent']]; d += 1
        depth[c['id']] = d
    for c in sorted(cats, key=lambda c: (depth[c['id']], -c.get('count', 0))):
        if root(c) in ('برندها و خطوط محصول', 'بدون دسته بندی'):
            continue
        if re.search(r'[0-9۰-۹]', c['name']):
            continue  # size/model variant ("سیم افشان 1 در 10"); its parent covers it
        req = required_tokens(c['name'])
        if not req:
            continue
        key = frozenset(req)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        sets = sorted((index.get(t, set()) for t in req), key=len)
        hit = set(sets[0]).intersection(*sets[1:]) if sets else set()
        if hit:
            cat_units[c['id']] = hit
            for i in hit:
                unit_cats[i].append(c['id'])

    out_cats = []
    for cid, hit in cat_units.items():
        c = by[cid]
        if len(hit) < 3:
            continue
        subs = Counter(units[i]['sub'] for i in hit)
        fitn = sum(FIT.get(units[i]['model'], 0) for i in hit)
        cnt = c.get('count', 0)
        gap = 'A' if cnt == 0 else ('C' if cnt < 10 else 'OK')
        ids = sorted(hit, key=lambda i: (not has_mobile(i), i))
        out_cats.append({
            'id': cid, 'name': c['name'], 'path': path(c), 'root': root(c), 'count': cnt, 'gap': gap,
            'units': len(hit), 'fit': round(fitn, 1),
            'provinces': len({units[i]['province'] for i in hit}),
            'subs': [[s, n] for s, n in subs.most_common(3)],
            'score': round(fitn / math.sqrt(1 + cnt), 2),
            'ids': [units[i]['id'] for i in ids[:60]],
        })
    out_cats.sort(key=lambda x: -x['score'])

    # ---- coverage per dashboard sub + phrases with no category (gap B)
    by_sub = defaultdict(list)
    for i, u in enumerate(units):
        by_sub[u['sub']].append(i)
    out_subs = []
    for sub, idx in by_sub.items():
        model = Counter(units[i]['model'] for i in idx).most_common(1)[0][0]
        covered = [i for i in idx if any(by[c].get('count', 0) > 0 for c in unit_cats.get(i, []))]
        cset = set(covered)
        empty_only = [i for i in idx if unit_cats.get(i) and i not in cset]
        cov = set(covered) | set(empty_only)
        unmatched = [i for i in idx if i not in cov]
        uni, bi, ids_of = Counter(), Counter(), defaultdict(list)
        for i in unmatched:
            ts = [t for t in toks(units[i].get('products', '')) if t not in PHRASE_STOP and len(t) >= 3]
            seen = set()
            for t in ts:
                if t not in seen:
                    seen.add(t); uni[t] += 1; ids_of[t].append(i)
            for a, b in zip(ts, ts[1:]):
                p = a + ' ' + b
                if p not in seen:
                    seen.add(p); bi[p] += 1; ids_of[p].append(i)
        phrases = []
        for p, n in bi.most_common(60):
            if n < 3:
                break
            a, b = p.split()
            # skip fragments of a longer phrase already picked ("ریخته گری" + "گری چدن")
            if any((a in q.split() or b in q.split()) and n >= 0.6 * m for q, m in phrases):
                continue
            phrases.append([p, n])
        used = {w for p, _ in phrases for w in p.split()}
        for t, n in uni.most_common(40):
            if n >= 3 and t not in used:
                phrases.append([t, n])
        phrases.sort(key=lambda x: -x[1])
        phrases = phrases[:15]
        fit = FIT.get(model, 0)
        out_subs.append({
            'sub': sub, 'model': model, 'fit': fit, 'units': len(idx),
            'covered': len(covered), 'empty_only': len(empty_only), 'unmatched': len(unmatched),
            'coverage': round(100 * len(covered) / len(idx), 1) if idx else 0,
            'score': round(fit * (len(idx) - len(covered)), 1),
            'phrases': [[p, n, [units[i]['id'] for i in sorted(ids_of[p], key=lambda i: (not has_mobile(i), i))[:40]]]
                        for p, n in phrases],
        })
    out_subs.sort(key=lambda x: -x['score'])

    # ---- industrial needs of consumer workshops
    needs_map = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'needs.json'), encoding='utf-8'))
    cat_norm = [(c, ' ' + norm(c['name']) + ' ') for c in cats]
    b2b_units = [i for i, u in enumerate(units) if u['model'] in B2B_MODELS]
    out_needs = []
    for sub, needs in needs_map.items():
        n_ws = len(by_sub.get(sub, []))
        rows = []
        for need in needs:
            k = ' ' + norm(need) + ' '
            mc = [c for c, nm in cat_norm if k in nm]
            prod = sum(c.get('count', 0) for c in mc)
            kt = [stem(t) for t in norm(need).split()]
            sup = [i for i in b2b_units if all(t in utok[i] for t in kt)]
            rows.append({
                'need': need, 'site_cats': len(mc), 'site_products': prod,
                'cat_names': [c['name'] for c in sorted(mc, key=lambda c: -c.get('count', 0))[:4]],
                'suppliers': len(sup),
                'ids': [units[i]['id'] for i in sorted(sup, key=lambda i: (not has_mobile(i), i))[:40]],
            })
        out_needs.append({'sub': sub, 'workshops': n_ws, 'needs': rows})
    out_needs.sort(key=lambda x: -x['workshops'])

    total_products = sum(c.get('count', 0) for c in cats)
    summary = {
        'generated': datetime.now(timezone.utc).isoformat(timespec='minutes'),
        'site': SITE, 'categories': len(cats),
        'categories_with_products': sum(1 for c in cats if c.get('count', 0) > 0),
        'category_product_links': total_products,
        'units_in_scope': len(units),
        'units_matched': len(unit_cats),
        'units_covered': sum(1 for i, cs in unit_cats.items() if any(by[c].get('count', 0) > 0 for c in cs)),
        'cats_with_workshops': len(out_cats),
        'gap_A': sum(1 for c in out_cats if c['gap'] == 'A'),
        'gap_C': sum(1 for c in out_cats if c['gap'] == 'C'),
    }
    res = {'summary': summary, 'cats': out_cats, 'subs': out_subs, 'needs': out_needs}
    dst = os.path.join(DATA_DIR, 'gaps.json')
    json.dump(res, open(dst + '.tmp', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    os.replace(dst + '.tmp', dst)
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print('top A/C:')
    for c in [c for c in out_cats if c['gap'] != 'OK'][:25]:
        print(f"  [{c['gap']}] {c['name']} ({c['root']}) products={c['count']} units={c['units']} score={c['score']}")
    print('top subs (low coverage):')
    for s in out_subs[:15]:
        print(f"  {s['sub']}: units={s['units']} covered={s['coverage']}% phrases={[p for p, _, _ in s['phrases'][:5]]}")


if __name__ == '__main__':
    main()
