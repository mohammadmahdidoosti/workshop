// Minimal stand-in for the dashboard runtime: loads JSON files, keeps filters in the URL, redraws.
(function () {
  const FILES = {
    subs: 'data/subs.json', totals: 'data/totals.json', clusters: 'data/clusters.json',
    units_b2b: 'data/units_b2b.json', units_d2c: 'data/units_d2c.json',
    themes: 'themes.json',
  };
  const DEFAULTS = { province: 'همه استان‌ها', model: 'همه مدل‌ها', sub: null, q: '', theme: null };
  const store = {};
  const draws = new Map();
  const onDataFns = [];
  let params = Object.assign({}, DEFAULTS);
  try {
    const u = new URLSearchParams(location.hash.slice(1));
    for (const k of Object.keys(DEFAULTS)) if (u.has(k)) params[k] = u.get(k) || null;
  } catch (e) { /* ignore */ }

  const saveHash = () => {
    const u = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v && v !== DEFAULTS[k]) u.set(k, v);
    history.replaceState(null, '', u.toString() ? '#' + u.toString() : location.pathname);
  };

  let queued = false;
  const render = () => {
    if (queued) return; queued = true;
    requestAnimationFrame(() => {
      queued = false;
      onDataFns.forEach((fn) => { try { fn(); } catch (e) { console.error(e); } });
      draws.forEach((fn, name) => {
        document.querySelectorAll(`[data-draw="${name}"]`).forEach((el) => {
          if (el.closest('[hidden]')) return;
          try { fn(el); } catch (e) { console.error(name, e); }
        });
      });
    });
  };

  const load = (id) => {
    if (store[id]) return;
    store[id] = { status: 'loading', data: [] };
    fetch(FILES[id], { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((d) => { store[id] = { status: 'ok', data: d }; render(); window.dispatchEvent(new Event('dash-data')); })
      .catch((e) => { store[id] = { status: 'error', data: [], message: String(e) }; render(); });
  };

  window.dash = {
    data(id) { load(id); return store[id]; },
    params() { return Object.assign({}, params); },
    setParams(p) { params = Object.assign({}, params, p); saveHash(); render(); window.dispatchEvent(new Event('dash-params')); },
    resetParams() { params = Object.assign({}, DEFAULTS); saveHash(); render(); window.dispatchEvent(new Event('dash-params')); },
    onData(fn) { onDataFns.push(fn); render(); },
    draw(name, fn) { if (fn) draws.set(name, fn); render(); },
    colors: ['#2f6fdb', '#d9822b', '#3a9d5d', '#b5487a', '#7a5cc4', '#c4a72f', '#4aa3b5', '#8a8a8a'],
    setLink() {},
  };
  let rt; window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(render, 150); });
})();
