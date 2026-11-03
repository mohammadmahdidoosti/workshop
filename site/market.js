// «فرصت بازار»: reads data/market.json written by market/collect.py on the server.
(function () {
  const root = document.getElementById('market');
  if (!root) return;
  const fmt = d3.format(',');
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const toman = (rial) => (rial ? fmt(Math.round(rial / 10)) : '—'); // marketplace prices are in rial
  const pct = (x) => (x == null ? '—' : Math.round(x * 100) + '%');
  const num = (x) => (x == null ? '—' : fmt(Math.round(x)));
  const status = root.querySelector('.mk-status');
  const tbody = root.querySelector('.mk-body');
  const meta = root.querySelector('.mk-meta');
  let sortKey = 'index', sortDir = -1, rows = [];

  const draw = () => {
    tbody.replaceChildren();
    const ts = window.wpThemeSubs ? window.wpThemeSubs() : null;
    const view = ts ? rows.filter((r) => ts.has(r.sub)) : rows;
    const maxIdx = d3.max(view, (r) => r.index) || 100;
    view.slice().sort((a, b) => {
      const x = a[sortKey], y = b[sortKey];
      if (typeof x === 'string') return x.localeCompare(y, 'fa') * sortDir;
      return ((x ?? -1) - (y ?? -1)) * sortDir;
    }).forEach((r, i) => {
      const tr = el('tr', 'click');
      const tdIdx = el('td', 'num');
      const bar = el('div', 'mk-bar'); bar.style.width = Math.max(2, (r.index || 0) / maxIdx * 100) + '%';
      const lab = el('span', 'mk-idx', r.index == null ? '—' : r.index.toFixed(0));
      tdIdx.append(lab, bar);
      tr.append(el('td', 'num', String(i + 1)), el('td', null, r.sub), tdIdx,
        el('td', 'num', pct(r.c.demand)), el('td', 'num', num(r.bs_sales_week_top)),
        el('td', 'num hide-n', num(r.bs_total)), el('td', 'num hide-n', num(r.bs_vendors_top)),
        el('td', 'num hide-n', toman(r.bs_median_price)), el('td', 'num', num(r.reach)));
      tr.title = 'کلیدواژه‌ها: ' + r.queries.join('، ');
      tr.addEventListener('click', () => {
        if (window.dash) dash.setParams({ sub: r.sub });
        const d = document.getElementById('detail'); if (d) d.scrollIntoView({ behavior: 'smooth' });
      });
      tbody.appendChild(tr);
    });
  };

  root.querySelectorAll('[data-mk-sort]').forEach((b) => b.addEventListener('click', () => {
    const k = b.getAttribute('data-mk-sort');
    sortDir = sortKey === k ? -sortDir : (k === 'sub' ? 1 : -1); sortKey = k; draw();
  }));

  fetch('data/market.json', { cache: 'no-cache' })
    .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then((m) => {
      rows = Object.entries(m.categories).map(([sub, c]) => Object.assign({ sub, c: c.components || {}, demand: (c.components || {}).demand }, c));
      status.hidden = true;
      root.querySelector('.mk-table').hidden = false;
      const w = m.weights || {};
      meta.textContent = 'آخرین به‌روزرسانی: ' + new Date(m.generated_at).toLocaleDateString('fa-IR') +
        ' · وزن‌ها: تقاضا ' + pct(w.demand) + '، رقابت کم ' + pct(w.low_competition) + '، تأمین‌کننده ' + pct(w.supply);
      draw();
      window.addEventListener('dash-params', draw);
      window.addEventListener('dash-data', draw);
    })
    .catch(() => { status.textContent = 'هنوز داده‌ی بازار جمع نشده است. بعد از اولین اجرای خزشگر (market/collect.py) این بخش پر می‌شود.'; });
})();
