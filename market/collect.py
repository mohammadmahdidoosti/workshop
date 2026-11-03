#!/usr/bin/env python3
"""Market collector for the workshops dashboard.

Searches Digikala and Basalam for a fixed list of keywords per category (slowly,
one request every few seconds), then computes an opportunity index per category
from demand, competition, brand gap and how many reachable suppliers we have.

Writes  <DATA_DIR>/market.json   (raw numbers per keyword + index per category)
Usage:  python3 collect.py           full run (~15-20 min)
        python3 collect.py --test    one keyword per site, prints what came back
Only the Python standard library is used.
"""
import json, math, os, random, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', '/usr/share/nginx/html/data')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
DELAY = (float(os.environ.get('DELAY_MIN', '4')), float(os.environ.get('DELAY_MAX', '7')))


def get_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def median(xs):
    xs = sorted(x for x in xs if x)
    return xs[len(xs) // 2] if xs else None


# ---------------- Digikala ----------------
def digikala(q):
    j = get_json('https://api.digikala.com/v1/search/?page=1&q=' + urllib.parse.quote(q))
    d = j.get('data') or {}
    ps = d.get('products') or []

    def var(p):
        v = p.get('default_variant')
        return v if isinstance(v, dict) else {}
    prices = [(var(p).get('price') or {}).get('selling_price') for p in ps]
    sellers = {(var(p).get('seller') or {}).get('title') for p in ps} - {None}
    brands_top = [((p.get('data_layer') or {}).get('brand') or '') for p in ps]
    n = len(ps) or 1
    return {
        'total': (d.get('pager') or {}).get('total_items'),
        'brands': len(((d.get('filters') or {}).get('brands') or {}).get('options') or []),
        'n_top': len(ps),
        'median_price': median(prices),
        'reviews_top': sum(((p.get('rating') or {}).get('count') or 0) for p in ps),
        'sellers_top': len(sellers),
        'nobrand_share': round(sum(1 for b in brands_top if b in ('', 'متفرقه', 'نامشخص')) / n, 3),
        'dk_seller_share': round(sum(1 for p in ps if (var(p).get('seller') or {}).get('title') == 'دیجی‌کالا') / n, 3),
    }


# ---------------- Basalam ----------------
BASALAM_URL = 'https://search.basalam.com/ai-engine/api/v2.0/product/search?from=0&size=24&q='


def _first(d, *keys):
    for k in keys:
        cur = d
        for part in k.split('.'):
            cur = cur.get(part) if isinstance(cur, dict) else None
        if cur is not None:
            return cur
    return None


def basalam(q):
    j = get_json(BASALAM_URL + urllib.parse.quote(q))
    ps = _first(j, 'products', 'data.products', 'data') or []
    if not isinstance(ps, list):
        ps = []
    total = _first(j, 'meta.count', 'meta.total', 'total', 'count', 'data.total')
    prices = [_first(p, 'price', 'primaryPrice') for p in ps]
    vendors = {_first(p, 'vendor.id', 'vendor.identifier', 'vendor.name') for p in ps} - {None}
    sales = [(_first(p, 'rating.signals', 'rating.count', 'salesCount') or 0) for p in ps]
    return {
        'total': total,
        'n_top': len(ps),
        'median_price': median(prices),
        'vendors_top': len(vendors),
        'reviews_top': sum(s for s in sales if isinstance(s, (int, float))),
    }


def run_site(fn, q, retries=2):
    for a in range(retries + 1):
        try:
            return fn(q)
        except Exception as e:  # noqa: BLE001 - keep going, record the failure
            err = f'{type(e).__name__}: {e}'
            time.sleep(10 * (a + 1))
    return {'error': err}


def log1p(x):
    return math.log1p(x or 0)


def scale(vals):
    """min-max to 0..1 over the non-null values."""
    xs = [v for v in vals.values() if v is not None]
    lo, hi = (min(xs), max(xs)) if xs else (0, 1)
    return {k: (None if v is None else (0.5 if hi == lo else (v - lo) / (hi - lo))) for k, v in vals.items()}


def build_index(per_q, queries, subs_rows):
    supply = {}
    for r in subs_rows:
        if r.get('province') == 'همه استان‌ها':
            supply[r['sub']] = r
    cat = {}
    for sub, qs in queries.items():
        dk = [per_q[q]['digikala'] for q in qs if 'error' not in per_q[q]['digikala']]
        bs = [per_q[q]['basalam'] for q in qs if 'error' not in per_q[q]['basalam']]
        avg = lambda rows, k: (sum(r[k] or 0 for r in rows) / len(rows)) if rows and any(r.get(k) is not None for r in rows) else None
        cat[sub] = {
            'queries': qs,
            'dk_total': avg(dk, 'total'), 'dk_brands': avg(dk, 'brands'), 'dk_reviews_top': avg(dk, 'reviews_top'),
            'dk_nobrand_share': avg(dk, 'nobrand_share'), 'dk_median_price': median([r['median_price'] for r in dk]),
            'bs_total': avg(bs, 'total'), 'bs_vendors_top': avg(bs, 'vendors_top'), 'bs_reviews_top': avg(bs, 'reviews_top'),
            'bs_median_price': median([r['median_price'] for r in bs]),
            'units': (supply.get(sub) or {}).get('n'), 'reach': (supply.get(sub) or {}).get('reach'),
        }
    # components (0..1, higher = better opportunity)
    demand = scale({s: (log1p(c['dk_reviews_top']) + log1p(c['bs_reviews_top'])) if (c['dk_reviews_top'] is not None or c['bs_reviews_top'] is not None) else None for s, c in cat.items()})
    compet = scale({s: log1p(c['dk_brands']) if c['dk_brands'] is not None else None for s, c in cat.items()})
    gap = {s: c['dk_nobrand_share'] for s, c in cat.items()}
    supp = scale({s: log1p(c['reach']) if c['reach'] is not None else None for s, c in cat.items()})
    W = {'demand': 0.35, 'low_competition': 0.25, 'brand_gap': 0.15, 'supply': 0.25}
    for s, c in cat.items():
        parts = {'demand': demand[s], 'low_competition': None if compet[s] is None else 1 - compet[s],
                 'brand_gap': gap[s], 'supply': supp[s]}
        got = {k: v for k, v in parts.items() if v is not None}
        wsum = sum(W[k] for k in got)
        c['components'] = {k: (None if v is None else round(v, 3)) for k, v in parts.items()}
        c['index'] = round(100 * sum(W[k] * v for k, v in got.items()) / wsum, 1) if wsum else None
    return cat, W


def main():
    queries = json.load(open(os.path.join(HERE, 'queries.json'), encoding='utf-8'))
    if '--test' in sys.argv:
        q = 'عسل'
        print('digikala', json.dumps(run_site(digikala, q, 0), ensure_ascii=False))
        try:
            raw = get_json(BASALAM_URL + urllib.parse.quote(q))
            print('basalam keys', list(raw)[:20])
            print('basalam sample', json.dumps(raw, ensure_ascii=False)[:800])
        except Exception as e:  # noqa: BLE001
            print('basalam error', e)
        print('basalam parsed', json.dumps(run_site(basalam, q, 0), ensure_ascii=False))
        return
    allq = list(dict.fromkeys(q for qs in queries.values() for q in qs))
    per_q = {}
    for i, q in enumerate(allq, 1):
        per_q[q] = {'digikala': run_site(digikala, q)}
        time.sleep(random.uniform(*DELAY))
        per_q[q]['basalam'] = run_site(basalam, q)
        time.sleep(random.uniform(*DELAY))
        print(f'[{i}/{len(allq)}] {q}', flush=True)
    subs_path = os.path.join(DATA_DIR, 'subs.json')
    subs_rows = json.load(open(subs_path, encoding='utf-8')) if os.path.exists(subs_path) else []
    cat, weights = build_index(per_q, queries, subs_rows)
    out = {'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
           'weights': weights, 'categories': cat, 'keywords': per_q}
    tmp = os.path.join(DATA_DIR, 'market.json.tmp')
    json.dump(out, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False)
    os.replace(tmp, os.path.join(DATA_DIR, 'market.json'))
    errs = sum(1 for v in per_q.values() for s in v.values() if 'error' in s)
    print(f'done: {len(allq)} keywords, {errs} failed requests -> market.json')


if __name__ == '__main__':
    main()
