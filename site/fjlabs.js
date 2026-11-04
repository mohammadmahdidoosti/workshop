// «مارکت‌پلیس‌های جهانی»: FJ Labs portfolio marketplaces grouped by business model, with Iran verdict.
(function () {
  const root = document.getElementById('fjlabs');
  if (!root) return;
  const V = {
    B: { label: '🟢 بکر / کم‌رقیب', cls: 'fj-b' },
    M: { label: '🟡 بازیگر دارد، جا هست', cls: 'fj-m' },
    S: { label: '🔴 اشباع', cls: 'fj-s' },
    N: { label: '⚫ نامناسب', cls: 'fj-n' },
    U: { label: '⚪ نیاز به بررسی', cls: 'fj-u' },
  };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const chips = root.querySelector('.fj-chips');
  const tbody = root.querySelector('.fj-body');
  const meta = root.querySelector('.fj-meta');
  const search = root.querySelector('.fj-q');
  let data = null, verdict = 'B', open = null;

  const drawChips = () => {
    chips.replaceChildren();
    const counts = {};
    data.archetypes.forEach((a) => { counts[a.verdict] = (counts[a.verdict] || 0) + a.n; });
    [['ALL', 'همه'], ...Object.entries(V).map(([k, v]) => [k, v.label])].forEach(([k, label]) => {
      const n = k === 'ALL' ? data.marketplaces : (counts[k] || 0);
      const b = el('button', 'fj-chip' + (verdict === k ? ' on' : ''), label + ' (' + n + ')');
      b.type = 'button';
      b.addEventListener('click', () => { verdict = k; open = null; draw(); });
      chips.appendChild(b);
    });
  };

  const draw = () => {
    drawChips();
    tbody.replaceChildren();
    const q = (search.value || '').trim().toLowerCase();
    data.archetypes
      .filter((a) => verdict === 'ALL' || a.verdict === verdict)
      .filter((a) => !q || a.model.includes(q) || a.iran.includes(q) ||
        a.companies.some((c) => c.name.toLowerCase().includes(q) || c.industry.toLowerCase().includes(q)))
      .forEach((a) => {
        const tr = el('tr', 'click' + (open === a.code ? ' on' : ''));
        const tdV = el('td', null); tdV.appendChild(el('span', 'fj-tag ' + V[a.verdict].cls, V[a.verdict].label));
        const names = a.companies.map((c) => c.name);
        tr.append(el('td', null, a.model), tdV, el('td', 'num', String(a.n)),
          el('td', 'hide-n', names.slice(0, 6).join('، ') + (names.length > 6 ? '…' : '')),
          el('td', null, a.iran), el('td', 'hide-n', a.note));
        tr.addEventListener('click', () => { open = open === a.code ? null : a.code; draw(); });
        tbody.appendChild(tr);
        if (open === a.code) {
          const dr = el('tr', 'fj-detail'); const td = el('td'); td.colSpan = 6;
          const list = el('div', 'fj-list');
          a.companies.forEach((c) => list.appendChild(el('span', 'fj-co', c.name + ' · ' + c.industry + ' · ' + c.country)));
          td.appendChild(list); dr.appendChild(td); tbody.appendChild(dr);
        }
      });
  };

  search.addEventListener('input', () => { open = null; draw(); });
  fetch('fjlabs.json', { cache: 'no-cache' }).then((r) => r.json()).then((d) => {
    data = d;
    meta.textContent = 'منبع: ' + d.source + ' · ' + d.fetched + ' · ' + d.total_portfolio.toLocaleString('en') + ' شرکت در پورتفوی، ' + d.marketplaces + ' مارکت‌پلیس';
    root.querySelector('.fj-table').hidden = false;
    root.querySelector('.fj-status').hidden = true;
    draw();
  }).catch(() => { root.querySelector('.fj-status').textContent = 'بارگذاری داده‌ی FJ Labs ناموفق بود.'; });
})();
