#!/usr/bin/env python3
"""Move handmade / gift workshops into their own model: «دست‌ساز (هدیه و صنایع دستی)».

Reads the original dashboard files (copied once to <DATA_DIR>/orig_before_handmade/),
re-labels matching units into new handmade subs and rewrites:
  units_d2c.json, units_b2b.json, subs.json, totals.json, clusters.json

Safe to run again: it always starts from the saved originals.

Note: subs/totals/clusters also count unreachable units (no phone), whose products we
do not have. Those stay in their old sub; only reachable units are moved.

Usage:  python3 handmade.py [--dry]          (DATA_DIR env, default /usr/share/nginx/html/data)
"""
import collections
import json
import os
import re
import shutil
import sys

DATA_DIR = os.environ.get('DATA_DIR', '/usr/share/nginx/html/data')
ORIG = os.path.join(DATA_DIR, 'orig_before_handmade')
FILES = ['units_d2c.json', 'units_b2b.json', 'subs.json', 'totals.json', 'clusters.json']

MODEL = 'دست‌ساز (هدیه و صنایع دستی)'
GROUP = 'دست‌ساز و هدیه'
ALLP, ALLM = 'همه استان‌ها', 'همه مدل‌ها'
SCORE, B2B = 4, 1
ANGLE = 'تأمین‌کننده‌ی پروژه‌ی دست‌ساز: تست طرح در باسلام و اینستاگرام، تولید در تیراژ کم'

_B, _E = r'(?:^|[\s،,()\-/])', r'(?:ی|ها|های|ای|جات)?(?=$|[\s،,()\-/.])'


def rx(words):
    return re.compile(_B + '(?:' + '|'.join(words) + ')' + _E)


# (new sub, include words, exclude regex) - first match wins
RULES = [
    ('جواهر و زیورآلات',
     rx(['جواهر', 'جواهرآلات', 'جواهرات', 'زیورآلات', 'زيورآلات', 'بدلیجات', 'بدلی', 'گردنبند', 'دستبند', 'انگشتر',
         'گوشواره', 'زرگری', 'مصنوعات طلا', 'مصنوعات نقره', 'سنگ های قیمتی', 'سنگ‌های قیمتی', 'سنگ قیمتی',
         'نیمه قیمتی']),
     re.compile('جعبه جواهر|ماشین|استخراج')),
    ('سفال، سرامیک و شیشه‌ی دستی',
     rx(['سفال', 'ظروف سفالی', 'گلدان', 'کریستال', 'شیشه گری', 'شیشه‌گری', 'کاشی هفت رنگ', 'میناکاری',
         'ظروف تزئینی', 'سرامیک تزئینی']),
     re.compile('بلوک|آجر|لوله سفالی|سفال بام|سفال ماشینی|ماشینی|چینی بهداشتی|کاسه توالت|جعبه دنده|سقف|سنگ چینی|نشاء|خورشیدی')),
    ('منبت، خاتم و صنایع دستی',
     rx(['منبت', 'منبت کاری', 'خاتم', 'معرق', 'مشبک کاری', 'ملیله', 'ملیله کاری', 'قلمزنی', 'مسگری', 'صنایع دستی',
         'تزئینات چوبی', 'اشیای تزئینی', 'لوازم تزئینی', 'مجسمه', 'قاب عکس', 'جعبه جواهر', 'خراطی']),
     re.compile('مس اسیدی|کابینت|کمد|درب|مبلمان|میز')),
    ('شمع و صابون دست‌ساز',
     rx(['شمع', 'صابون گلیسیرینه', 'صابون آرایشی', 'صابون با عصاره', 'صابون دست ساز', 'صابون دست‌ساز']),
     re.compile('مکانیکی|خودرو|موتور|احتراق|صنعتی|پودر|سازه|رخت شویی|ژاول|شامپو|اسید|ظرف شویی')),
    ('چرم دستی (کیف، کمربند، کیف پول)',
     rx(['کیف پول', 'کمربند چرمی', 'کیف و ساک', 'کیف دستی', 'کیف چرم', 'کیف چرمی', 'جاکلیدی', 'محصولات چرمی']),
     None),
    ('بافتنی، شال، روسری و جوراب',
     rx(['بافتنی', 'شال', 'روسری', 'قلاب بافی', 'قلاب‌بافی', 'گلدوزی', 'سوزن دوزی', 'سوزن‌دوزی', 'پته', 'ترمه',
         'جوراب', 'کاموا']),
     re.compile('صنعتی|طبی|پزشکی|کاور پلاستیکی')),
    ('عروسک و اسباب‌بازی',
     rx(['عروسک', 'اسباب بازی', 'اسباب‌بازی']),
     re.compile('بادی|چرخ دار|سواری|کالسکه')),
]
NEW_SUBS = [r[0] for r in RULES]


def classify(products):
    t = ' ' + (products or '') + ' '
    for sub, inc, exc in RULES:
        if inc.search(t) and not (exc and exc.search(t)):
            return sub
    return None


def load(d, f):
    with open(os.path.join(d, f), encoding='utf-8') as fh:
        return json.load(fh)


def save(f, data):
    p = os.path.join(DATA_DIR, f)
    with open(p + '.tmp', 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(',', ':'))
    os.replace(p + '.tmp', p)


def main():
    dry = '--dry' in sys.argv
    if not os.path.isdir(ORIG):
        if dry:
            src = DATA_DIR
        else:
            os.makedirs(ORIG)
            for f in FILES:
                shutil.copy2(os.path.join(DATA_DIR, f), os.path.join(ORIG, f))
            src = ORIG
    else:
        src = ORIG

    d2c, b2b = load(src, 'units_d2c.json'), load(src, 'units_b2b.json')
    subs, totals, clusters = load(src, 'subs.json'), load(src, 'totals.json'), load(src, 'clusters.json')

    moved = []  # (unit, old_sub, old_model)
    keep_d2c, keep_b2b = [], []
    for lst, keep in ((d2c, keep_d2c), (b2b, keep_b2b)):
        for u in lst:
            ns = classify(u.get('products'))
            if ns:
                moved.append((dict(u), u['sub'], u['model']))
                u = dict(u, sub=ns, model=MODEL)
                keep_d2c.append(u)
            else:
                keep.append(u)

    mob = lambda u: 1 if u.get('mobile') else 0

    # ---- subs: subtract from old (province, sub) and ALLP rows, add new rows
    sidx = {(s['province'], s['sub']): s for s in subs}
    for u, osub, _ in moved:
        for p in (u['province'], ALLP):
            s = sidx.get((p, osub))
            if s:
                s['n'] -= 1; s['reach'] -= 1; s['mob'] -= mob(u)
    newrows = {}
    parks = collections.defaultdict(collections.Counter)
    for u, _, _ in moved:
        ns = classify(u['products'])
        for p in (u['province'], ALLP):
            r = newrows.setdefault((p, ns), dict(province=p, sub=ns, group=GROUP, model=MODEL, score=SCORE, b2b=B2B,
                                                 angle=ANGLE, n=0, reach=0, mob=0, top_park=''))
            r['n'] += 1; r['reach'] += 1; r['mob'] += mob(u)
            parks[(p, ns)][u['park']] += 1
    for k, r in newrows.items():
        r['top_park'] = parks[k].most_common(1)[0][0]
    subs = [s for s in subs if s['n'] > 0] + sorted(newrows.values(), key=lambda r: (r['province'], -r['n']))

    # ---- totals: rebuild per (province, model) from subs
    agg = collections.defaultdict(lambda: dict(n=0, reach=0, mob=0, cats=0))
    for s in subs:
        for m in (s['model'], ALLM):
            a = agg[(s['province'], m)]
            a['n'] += s['n']; a['reach'] += s['reach']; a['mob'] += s['mob']; a['cats'] += 1
    old_t = {(t['province'], t['model']): t for t in totals}
    new_t = []
    for (p, m), a in agg.items():
        t = dict(old_t.get((p, m), {}), province=p, model=m, n=a['n'], reach=a['reach'], mob=a['mob'], cats=a['cats'])
        if m == ALLM and (p, m) in old_t:  # keep original grand totals (subs may not list every unit)
            t.update(n=old_t[(p, m)]['n'], reach=old_t[(p, m)]['reach'], mob=old_t[(p, m)]['mob'])
        new_t.append(t)
    totals = sorted(new_t, key=lambda t: (t['province'], t['model']))

    # ---- clusters: subtract moved units, add handmade park clusters (n >= 5)
    cidx = {(c['province'], c['park'], c['sub']): c for c in clusters}
    for u, osub, _ in moved:
        c = cidx.get((u['province'], u['park'], osub))
        if c:
            c['n'] -= 1; c['reach'] -= 1
    clusters = [c for c in clusters if c['n'] >= 5]
    cc = collections.Counter((u['province'], u['park'], classify(u['products'])) for u, _, _ in moved)
    nid = max([c['cid'] for c in clusters] + [0]) + 1
    for (p, park, ns), n in cc.most_common():
        if n >= 5:
            clusters.append(dict(cid=nid, province=p, park=park, sub=ns, model=MODEL, b2b=B2B, score=SCORE, n=n, reach=n))
            nid += 1
    clusters.sort(key=lambda c: -c['n'])

    # ---- report
    print('moved units:', len(moved))
    print('by new sub:', collections.Counter(classify(u['products']) for u, _, _ in moved).most_common())
    print('from old model:', collections.Counter(m for _, _, m in moved).most_common())
    print('from old sub:', collections.Counter(s for _, s, _ in moved).most_common(12))
    print('handmade clusters:', [(c['park'], c['sub'], c['n']) for c in clusters if c['model'] == MODEL][:10])
    if dry:
        print('(dry run, nothing written)')
        return
    save('units_d2c.json', keep_d2c); save('units_b2b.json', keep_b2b)
    save('subs.json', subs); save('totals.json', totals); save('clusters.json', clusters)
    print('written to', DATA_DIR, '(originals in', ORIG + ')')


if __name__ == '__main__':
    main()
