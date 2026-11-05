#!/usr/bin/env python3
"""Read the product-category menu of competitor shops (home page only, one request per site).

Usage:  python3 menus.py domain1 domain2 ...      (or: python3 menus.py --file domains.txt)
Writes  <DATA_DIR>/menus.json  {domain: {"title":..., "cats":[...], "spam":bool, "error":...}}
Only the Python standard library is used. Polite: 3-5 s between sites.
"""
import json, os, random, re, sys, time, urllib.request
from html.parser import HTMLParser

DATA_DIR = os.environ.get('DATA_DIR', '/usr/share/nginx/html/data')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'
BAD = re.compile(r'ورود|ثبت|سبد|تماس|درباره|بلاگ|وبلاگ|مقال|صفحه اصلی|خانه|حساب|رمز|قوانین|سوالات|پیگیری|همکاری|اخبار|'
                 r'گالری|ویدیو|^\d|تومان|راهنما|فروشگاه$|منو|جستجو|ارتباط|نمایندگی|کاتالوگ|مشاهده|بیشتر|حریم|شرایط|'
                 r'instagram|whatsapp|youtube|telegram|facebook|twitter|linkedin|pinterest|aparat|english|\{', re.I)
SPAM = re.compile(r'casino|gamstop|bet|slot|porn|sex|کازینو', re.I)
CAT_HREF = re.compile(r'product-category|/category/|/cat/|/product-cat|/shop/|/categories/|/c/|/collections/', re.I)


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.a, self.out, self.title, self.in_title = [], None, [], '', False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get('class') or '') + ' ' + (a.get('id') or '')
        menu = tag in ('nav', 'header') or 'menu' in cls.lower() or 'nav' in cls.lower()
        if tag not in ('br', 'img', 'meta', 'link', 'input', 'hr', 'source'):
            self.stack.append(menu)
        if tag == 'a':
            href = a.get('href') or ''
            self.a = {'href': href, 'menu': any(self.stack) or bool(CAT_HREF.search(href)), 'text': ''}
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'a' and self.a is not None:
            t = re.sub(r'\s+', ' ', self.a['text']).strip()
            if self.a['menu'] and 1 < len(t) < 45:
                self.out.append((t, self.a['href']))
            self.a = None
        if tag == 'title':
            self.in_title = False
        if tag not in ('br', 'img', 'meta', 'link', 'input', 'hr', 'source') and self.stack:
            self.stack.pop()

    def handle_data(self, d):
        if self.a is not None:
            self.a['text'] += d
        if self.in_title:
            self.title += d


def read(domain):
    url = domain if domain.startswith('http') else 'https://' + domain + '/'
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'fa,en;q=0.5'})
    with urllib.request.urlopen(req, timeout=25) as r:
        html = r.read(3_000_000).decode('utf-8', 'ignore')
    p = P()
    p.feed(html)
    spam = any(SPAM.search(t) for t, _ in p.out)
    cats, seen = [], set()
    for t, h in p.out:
        if BAD.search(t) or SPAM.search(t) or t in seen:
            continue
        seen.add(t)
        cats.append(t)
    return {'title': p.title.strip()[:80], 'cats': cats[:150], 'spam': spam}


def main():
    args = sys.argv[1:]
    if args[:1] == ['--file']:
        args = [l.strip() for l in open(args[1]) if l.strip()]
    out_path = os.path.join(DATA_DIR, 'menus.json')
    res = json.load(open(out_path)) if os.path.exists(out_path) else {}
    for i, d in enumerate(args):
        try:
            res[d] = read(d)
        except Exception as e:  # noqa: BLE001
            res[d] = {'error': str(e)[:120]}
        print(f'{i + 1}/{len(args)} {d}: {len(res[d].get("cats", []))} cats {res[d].get("error", "")}', flush=True)
        json.dump(res, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
        time.sleep(random.uniform(3, 5))


if __name__ == '__main__':
    main()
