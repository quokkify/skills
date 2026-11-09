/* discussion-card engine: config-driven interactivity for the generated card.
   Reads only #card-config and the DOM. User and source text is written with textContent only. */
(() => {
  'use strict';
  const root = document.documentElement;
  let cfg = {};
  try { cfg = JSON.parse(document.getElementById('card-config').textContent) || {}; } catch (e) { cfg = {}; }
  const L = cfg.labels || {};
  const t = (k) => L[k] || k;
  const KEY = cfg.storageKey || 'discussion-card:card:v1';
  const MODE_KEY = KEY + ':mode';
  const THEME_KEY = KEY + ':theme';
  const STATUSES = ['ok', 'change', 'discuss'];
  const GLYPH = { ok: '✓', change: '!', discuss: '?' };
  const CAP = { comment: 4000, who: 80, names: 500, decision: 4000, action: 500, owner: 80, id: 80 };
  const QUESTIONS = Array.isArray(cfg.questions) ? cfg.questions : [];
  const BLOCKS = cfg.blocks || {};
  const PRESENT_MIN_PX = 1000;
  const TOAST_MS = 3200;
  const NS = 'http://www.w3.org/2000/svg';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function btn(cls, text, attrs = {}) {
    const b = el('button', cls, text);
    b.type = 'button';
    for (const k in attrs) b.setAttribute(k, attrs[k]);
    return b;
  }
  function S(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }
  const uid = () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  const clean = (s) => String(s || '').replace(/\s+/g, ' ').trim();
  const short = (s, n = 140) => (s.length > n ? s.slice(0, n - 1) + '…' : s);

  /* ---------- storage: every access may throw (private mode, blocked site data) ---------- */
  let storageOk = true;
  function sget(k) {
    try { return localStorage.getItem(k); } catch (e) { storageFailed(); return null; }
  }
  function sset(k, v) {
    try { localStorage.setItem(k, v); return true; } catch (e) { storageFailed(); return false; }
  }
  function storageFailed() {
    storageOk = false;
    toast(t('storage_off'));
  }

  /* ---------- state ---------- */
  const knownSpots = new Set($$('[data-spot]').map((n) => n.dataset.spot));
  for (const pre of $$('pre.mermaid-runtime[data-node-spots]')) {
    try {
      const m = JSON.parse(pre.dataset.nodeSpots);
      for (const k in m) if (typeof m[k] === 'string') knownSpots.add(m[k]);
    } catch (e) { /* no node spots for this diagram */ }
  }
  const blank = () => ({ vote: { for: 0, against: 0, forNames: '', againstNames: '' }, spots: {}, questions: {}, actions: [] });
  const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
  const num = (v) => (Number.isFinite(v) && v >= 0 ? Math.floor(v) : 0);
  const str = (v, n) => (typeof v === 'string' ? v.slice(0, n) : '');
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

  function sanitize(s) {
    const b = blank();
    if (!isObj(s)) return b;
    if (isObj(s.vote)) {
      b.vote.for = num(s.vote.for);
      b.vote.against = num(s.vote.against);
      b.vote.forNames = str(s.vote.forNames, CAP.names);
      b.vote.againstNames = str(s.vote.againstNames, CAP.names);
    }
    if (isObj(s.spots)) {
      for (const id of Object.keys(s.spots)) {
        const v = s.spots[id];
        if (!knownSpots.has(id) || !isObj(v)) continue;
        const status = STATUSES.includes(v.status) ? v.status : null;
        const comments = (Array.isArray(v.comments) ? v.comments : [])
          .filter((c) => isObj(c) && typeof c.text === 'string' && c.text.trim())
          .map((c) => ({ id: str(c.id, CAP.id) || uid(), text: str(c.text, CAP.comment), who: str(c.who, CAP.who), t: num(c.t) }));
        if (status || comments.length) b.spots[id] = { status, comments };
      }
    }
    if (isObj(s.questions)) {
      for (const q of QUESTIONS) {
        const v = has(s.questions, q.id) ? s.questions[q.id] : null;
        if (!isObj(v)) continue;
        const opts = Array.isArray(q.options) ? q.options : [];
        b.questions[q.id] = { pick: opts.includes(v.pick) ? v.pick : null, decision: str(v.decision, CAP.decision) };
      }
    }
    if (Array.isArray(s.actions)) {
      b.actions = s.actions
        .filter((a) => isObj(a) && typeof a.text === 'string' && a.text.trim())
        .map((a) => ({ id: str(a.id, CAP.id) || uid(), text: str(a.text, CAP.action), owner: str(a.owner, CAP.owner), done: a.done === true }));
    }
    return b;
  }
  function load() {
    const raw = sget(KEY);
    if (!raw) return blank();
    try { return sanitize(JSON.parse(raw)); } catch (e) { return blank(); }
  }
  function save() {
    if (!sset(KEY, JSON.stringify(state))) return;
    storageOk = true;
  }

  /* ---------- chrome: bar, toc, drawer, toast ---------- */
  const title = clean(($('.card-header h1') || {}).textContent || document.title);
  const bar = el('div', 'dc-bar');
  const r1 = el('div', 'dc-row');
  r1.appendChild(el('span', 'dc-title', title));
  const pnav = el('div', 'dc-pnav');
  pnav.id = 'dc-pnav';
  const pPrev = btn('dc-btn dc-icon', '‹', { id: 'dc-prev', 'aria-label': t('prev') });
  const pPos = el('span', 'dc-pos');
  const dots = el('div', 'dc-dots');
  dots.id = 'dc-dots';
  const pNext = btn('dc-btn dc-icon', '›', { id: 'dc-next', 'aria-label': t('next') });
  pnav.append(pPrev, dots, pNext, pPos);
  r1.appendChild(pnav);
  if (BLOCKS.verdict) {
    const tally = el('span', 'dc-tally');
    tally.append(el('span', 'dc-pill dc-for'), el('span', 'dc-pill dc-against'));
    r1.appendChild(tally);
  }
  const modeBtn = btn('dc-btn', '', { id: 'dc-mode', 'aria-pressed': 'false' });
  r1.appendChild(modeBtn);
  const menu = el('div', 'dc-menu');
  const menuBtn = btn('dc-btn', t('menu'), { id: 'dc-menu-btn', 'aria-expanded': 'false', 'aria-haspopup': 'true' });
  const pop = el('div', 'dc-pop');
  pop.id = 'dc-menu';
  pop.hidden = true;
  const loadLabel = el('label', 'dc-load', t('load_json'));
  const loadInput = el('input');
  loadInput.type = 'file';
  loadInput.id = 'dc-load-json';
  loadInput.accept = 'application/json,.json';
  loadLabel.appendChild(loadInput);
  const resetBtn = btn('dc-danger', t('reset'), { id: 'dc-reset' });
  pop.append(
    btn('', t('export_md'), { id: 'dc-export-md' }),
    btn('', t('save_json'), { id: 'dc-save-json' }),
    loadLabel,
    btn('', t('theme'), { id: 'dc-theme' }),
    resetBtn
  );
  menu.append(menuBtn, pop);
  r1.appendChild(menu);
  const r2 = el('div', 'dc-row dc-hotrow');
  r2.appendChild(el('span', 'dc-hot-h', t('hotspots')));
  const hot = el('ul', 'dc-hot');
  hot.id = 'dc-hot';
  const hotEmpty = el('span', 'dc-hot-empty', t('hot_empty'));
  r2.append(hot, hotEmpty);
  bar.append(r1, r2);
  document.body.insertBefore(bar, document.body.firstChild);

  const main = $('#card-main') || $('main');
  const layout = el('div', 'dc-layout');
  const toc = el('nav', 'dc-toc');
  toc.id = 'dc-toc';
  toc.setAttribute('aria-label', t('toc'));
  const tocList = el('ol');
  toc.appendChild(tocList);
  main.parentNode.insertBefore(layout, main);
  layout.append(toc, main);

  const drawer = el('aside', 'dc-drawer');
  drawer.id = 'dc-drawer';
  drawer.hidden = true;
  drawer.setAttribute('aria-live', 'polite');
  const drHead = el('div', 'dc-dr-head');
  const drMeta = el('div');
  const drChapter = el('div', 'dc-eyebrow');
  const drTitle = el('div', 'dc-dr-title');
  drTitle.id = 'dc-dr-title';
  drMeta.append(drChapter, drTitle);
  drHead.append(drMeta, btn('dc-x', '✕', { id: 'dc-dr-close', 'aria-label': t('close') }));
  const drBody = el('div', 'dc-dr-body');
  const sts = el('div', 'dc-statuses');
  for (const s of STATUSES) sts.appendChild(btn('dc-st', t('status_' + s), { 'data-s': s, 'aria-pressed': 'false' }));
  const comments = el('ul', 'dc-comments');
  comments.id = 'dc-comments';
  const noComments = el('p', 'dc-empty', t('no_comments'));
  const cForm = el('form', 'dc-c-form');
  const cText = el('textarea');
  cText.id = 'dc-c-text';
  cText.rows = 3;
  cText.placeholder = t('comment_placeholder');
  cText.maxLength = CAP.comment;
  const cRow = el('div', 'dc-c-row');
  const cWho = el('input');
  cWho.id = 'dc-c-who';
  cWho.placeholder = t('author_placeholder');
  cWho.maxLength = CAP.who;
  const cAdd = el('button', 'dc-btn dc-primary', t('add_comment'));
  cAdd.type = 'submit';
  cAdd.id = 'dc-c-add';
  cRow.append(cWho, cAdd);
  cForm.append(cText, cRow);
  drBody.append(sts, el('div', 'dc-eyebrow', t('comments')), comments, noComments, cForm);
  drawer.append(drHead, drBody);
  document.body.appendChild(drawer);

  const pnextBox = el('div', 'dc-pnext');
  const pnextBtn = btn('dc-btn dc-primary', '', { id: 'dc-pnext' });
  pnextBox.appendChild(pnextBtn);
  document.body.appendChild(pnextBox);
  const toastEl = el('div', 'dc-toast');
  toastEl.id = 'dc-toast';
  toastEl.hidden = true;
  toastEl.setAttribute('role', 'status');
  document.body.appendChild(toastEl);
  let toastTimer;
  function toast(msg) {
    toastEl.textContent = msg;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, TOAST_MS);
  }

  /* ---------- blocks: verdict, questions, actions ---------- */
  function buildVerdict() {
    const sec = $('[data-block="verdict"]');
    if (!sec) return;
    sec.appendChild(el('h2', null, t('verdict')));
    const row = el('div', 'dc-vote');
    for (const side of ['for', 'against']) {
      const box = el('div', 'dc-vside dc-' + side);
      const count = el('span', 'dc-vcount', '0');
      count.id = 'dc-v-' + side;
      const names = el('input');
      names.id = 'dc-v-' + side + '-names';
      names.placeholder = t('names_placeholder');
      names.maxLength = CAP.names;
      names.dataset.names = side;
      box.append(
        el('span', 'dc-vlabel', t('vote_' + side)),
        btn('dc-step', '−', { 'data-vote': side, 'data-d': '-1', 'aria-label': t('vote_' + side) + ' -1' }),
        count,
        btn('dc-step', '+', { 'data-vote': side, 'data-d': '1', 'aria-label': t('vote_' + side) + ' +1' }),
        names
      );
      row.appendChild(box);
    }
    sec.appendChild(row);
  }
  function buildQuestions() {
    for (const card of $$('article.question[data-qid]')) {
      const q = QUESTIONS.find((x) => x.id === card.dataset.qid);
      if (!q) continue;
      const opts = Array.isArray(q.options) ? q.options : [];
      if (opts.length) {
        const g = el('div', 'dc-opts');
        g.setAttribute('role', 'group');
        g.setAttribute('aria-label', t('pick'));
        for (const o of opts) g.appendChild(btn('dc-opt', o, { 'data-q': q.id, 'data-opt': o, 'aria-pressed': 'false' }));
        card.appendChild(g);
      }
      const f = el('div', 'dc-field');
      const lab = el('label', null, t('decision'));
      const ta = el('textarea');
      ta.id = 'dc-dec-' + q.id;
      ta.rows = 1;
      ta.maxLength = CAP.decision;
      ta.dataset.dec = q.id;
      lab.htmlFor = ta.id;
      f.append(lab, ta);
      card.appendChild(f);
    }
  }
  let actList, actEmpty;
  function buildActions() {
    const sec = $('[data-block="actions"]');
    if (!sec) return;
    sec.appendChild(el('h2', null, t('actions')));
    actList = el('ul', 'dc-actions');
    actList.id = 'dc-act-list';
    actEmpty = el('p', 'dc-empty', t('none'));
    const form = el('form', 'dc-add-row');
    form.id = 'dc-act-form';
    const text = el('input');
    text.id = 'dc-act-text';
    text.placeholder = t('action_text');
    text.maxLength = CAP.action;
    const owner = el('input');
    owner.id = 'dc-act-owner';
    owner.placeholder = t('action_owner');
    owner.maxLength = CAP.owner;
    const add = el('button', 'dc-btn', t('add_action'));
    add.type = 'submit';
    add.id = 'dc-act-add';
    form.append(text, owner, add);
    sec.append(actList, actEmpty, form);
  }

  /* ---------- spots registry: rebuilt after runtime diagrams render ---------- */
  const chapterTitle = new Map((cfg.chapters || []).map((c) => [c.id, c.title]));
  const spots = new Map();
  const CORNER = 'pre, aside.callout, article.intro-card, article.question';
  function registerSpot(node) {
    const id = node.dataset.spot;
    if (!id || spots.has(id)) return;
    const svg = node instanceof SVGElement;
    const ch = node.closest('[data-chapter]');
    const chapter = ch ? ch.id : '';
    const textSrc = node.querySelector(':scope > .question-text') || node;
    const label = short(clean(textSrc.textContent)) || id;
    let badges;
    if (svg) {
      badges = S('g', { class: 'dc-sbadges' }, node);
    } else {
      const host = node.tagName === 'TR' ? node.lastElementChild || node : node;
      badges = el('span', 'dc-badges' + (node.matches(CORNER) ? ' dc-corner' : ''));
      badges.setAttribute('aria-hidden', 'true');
      host.appendChild(badges);
    }
    node.classList.add('dc-spot');
    node.setAttribute('tabindex', '0');
    node.setAttribute('role', 'button');
    node.setAttribute('aria-label', label);
    spots.set(id, { id, node, label, chapter, chapterName: chapter ? chapterTitle.get(chapter) || chapter : t('intro'), badges, svg, box: null });
  }
  function registerAll() { $$('[data-spot]').forEach(registerSpot); }

  async function renderRuntimeDiagrams() {
    const pres = $$('pre.mermaid-runtime');
    if (!pres.length || typeof window.mermaid === 'undefined') return;
    try {
      window.mermaid.initialize({ startOnLoad: false, securityLevel: 'strict', theme: 'default', themeVariables: { fontSize: '16px' } });
    } catch (e) { return; }
    let k = 0;
    for (const pre of pres) {
      k += 1;
      const rid = 'dc-r' + k;
      let map = {};
      try { map = JSON.parse(pre.dataset.nodeSpots || '{}') || {}; } catch (e) { map = {}; }
      try {
        const out = await window.mermaid.render(rid, pre.textContent);
        const parsed = new DOMParser().parseFromString(out.svg, 'text/html').querySelector('svg');
        if (!parsed) continue;
        const svg = document.importNode(parsed, true);
        svg.style.removeProperty('max-width');
        const vb = svg.viewBox && svg.viewBox.baseVal;
        if (vb && vb.width) svg.setAttribute('width', String(vb.width));
        const prefix = rid + '-flowchart-';
        for (const g of svg.querySelectorAll('g.node')) {
          if (!g.id.startsWith(prefix)) continue;
          const nid = g.id.slice(prefix.length).replace(/-\d+$/, '');
          const sid = has(map, nid) ? map[nid] : null;
          if (typeof sid !== 'string') continue;
          g.setAttribute('data-spot', sid);
          g.setAttribute('tabindex', '0');
          g.setAttribute('role', 'button');
        }
        pre.replaceWith(svg);
      } catch (e) {
        pre.classList.add('dc-render-failed');
      }
    }
  }

  /* ---------- rendering ---------- */
  let state = blank();
  let openId = null;
  const marked = (v) => !!v && (!!v.status || v.comments.length > 0);
  function svgBox(s) {
    if (s.box && s.box.width) return s.box;
    s.badges.remove();
    try { const b = s.node.getBBox(); s.box = { x: b.x, y: b.y, width: b.width }; } catch (e) { s.box = null; }
    s.node.appendChild(s.badges);
    return s.box;
  }
  function renderSvgBadges(s, v) {
    const g = s.badges;
    while (g.firstChild) g.firstChild.remove();
    if (!marked(v)) return;
    const b = svgBox(s);
    if (!b || !b.width) return;
    let x = b.x + b.width + 4;
    const y = b.y;
    const n = v.comments.length;
    if (n) {
      const w = 12 + String(n).length * 7;
      S('rect', { class: 'dc-sb-cm', x: x - w, y: y - 9, width: w, height: 18, rx: 9 }, g);
      S('text', { class: 'dc-sb-t', x: x - w / 2, y: y + 4, 'text-anchor': 'middle' }, g).textContent = String(n);
      x -= w + 3;
    }
    if (v.status) {
      S('circle', { class: 'dc-sb-' + v.status, cx: x - 9, cy: y, r: 9 }, g);
      S('text', { class: 'dc-sb-t', x: x - 9, y: y + 4, 'text-anchor': 'middle' }, g).textContent = GLYPH[v.status];
    }
  }
  function renderSpots() {
    for (const [id, s] of spots) {
      const v = state.spots[id];
      if (v && v.status) s.node.dataset.heat = v.status; else delete s.node.dataset.heat;
      s.node.classList.toggle('dc-marked', marked(v));
      s.node.classList.toggle('dc-active', id === openId);
      if (s.svg) { renderSvgBadges(s, v); continue; }
      s.badges.textContent = '';
      if (v && v.status) {
        const b = el('span', 'dc-bdg dc-' + v.status, v.status === 'ok' ? GLYPH.ok : t('status_' + v.status));
        b.title = t('status_' + v.status);
        s.badges.appendChild(b);
      }
      if (v && v.comments.length) {
        const b = el('span', 'dc-bdg dc-cm', '\u{1F4AC} ' + v.comments.length);
        b.title = t('comments') + ': ' + v.comments.length;
        s.badges.appendChild(b);
      }
    }
  }
  function syncInput(node, val) {
    if (node && document.activeElement !== node && node.value !== val) node.value = val;
  }
  function renderVote() {
    if (!BLOCKS.verdict) return;
    const v = state.vote;
    for (const side of ['for', 'against']) {
      const c = $('#dc-v-' + side);
      if (c) c.textContent = String(v[side]);
      syncInput($('#dc-v-' + side + '-names'), v[side + 'Names']);
      const pill = $('.dc-pill.dc-' + side, bar);
      if (pill) pill.textContent = t('vote_' + side) + ' ' + v[side];
    }
  }
  const weight = (v) => (v.status === 'change' ? 3 : v.status === 'discuss' ? 2 : 0) + v.comments.length;
  function renderHot() {
    const order = [...spots.keys()];
    const items = Object.entries(state.spots)
      .filter(([id, v]) => spots.has(id) && (v.status === 'change' || v.status === 'discuss' || v.comments.length))
      .sort((a, b) => weight(b[1]) - weight(a[1]) || order.indexOf(a[0]) - order.indexOf(b[0]));
    hot.textContent = '';
    hotEmpty.hidden = items.length > 0;
    for (const [id, v] of items) {
      const s = spots.get(id);
      const li = el('li');
      const b = btn(v.status ? 'dc-' + v.status : '', null, { 'data-goto': id });
      b.title = s.chapterName + ' · ' + s.label + (v.status ? ' · ' + t('status_' + v.status) : '');
      b.append(el('span', 'dc-dot'), el('span', 'dc-hl', s.label));
      if (v.comments.length) b.appendChild(el('span', 'dc-cmn', '\u{1F4AC}' + v.comments.length));
      li.appendChild(b);
      hot.appendChild(li);
    }
  }
  function renderQuestions() {
    for (const q of QUESTIONS) {
      const v = state.questions[q.id] || {};
      $$('.dc-opt').filter((b) => b.dataset.q === q.id)
        .forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.opt === v.pick)));
      syncInput(document.getElementById('dc-dec-' + q.id), v.decision || '');
    }
  }
  function renderActions() {
    if (!actList) return;
    actList.textContent = '';
    actEmpty.hidden = state.actions.length > 0;
    for (const a of state.actions) {
      const li = el('li', a.done ? 'dc-done' : null);
      const cb = el('input');
      cb.type = 'checkbox';
      cb.checked = a.done;
      cb.dataset.act = a.id;
      cb.setAttribute('aria-label', t('done'));
      li.append(cb, el('span', 'dc-atext', a.text), el('span', 'dc-aowner', a.owner || '—'),
        btn('dc-x', '✕', { 'data-act-del': a.id, 'aria-label': t('delete') }));
      actList.appendChild(li);
    }
  }
  function marksIn(test) {
    let n = 0, change = 0, discuss = 0;
    for (const [id, s] of spots) {
      const v = state.spots[id];
      if (!marked(v) || !test(s)) continue;
      n += 1;
      if (v.status === 'change') change += 1; else if (v.status === 'discuss') discuss += 1;
    }
    return { n, cls: change ? 'dc-change' : discuss ? 'dc-discuss' : '' };
  }
  const tocLinks = new Map();
  function buildToc() {
    for (const c of cfg.chapters || []) {
      if (!document.getElementById(c.id)) continue;
      const li = el('li');
      const a = el('a');
      a.href = '#' + c.id;
      a.dataset.chapterLink = c.id;
      a.appendChild(el('span', null, c.label || c.title));
      const count = el('span', 'dc-tc');
      count.hidden = true;
      a.appendChild(count);
      li.appendChild(a);
      tocList.appendChild(li);
      tocLinks.set(c.id, { a, count });
    }
  }
  function renderToc() {
    for (const [id, { count }] of tocLinks) {
      const m = marksIn((s) => s.chapter === id);
      count.hidden = m.n === 0;
      count.textContent = String(m.n);
      count.className = 'dc-tc ' + m.cls;
    }
  }
  function renderDrawer() {
    if (!openId) return;
    const s = spots.get(openId);
    const v = state.spots[openId] || { status: null, comments: [] };
    drChapter.textContent = s.chapterName;
    drTitle.textContent = s.label;
    $$('.dc-st', drawer).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.s === v.status)));
    comments.textContent = '';
    noComments.hidden = v.comments.length > 0;
    for (const c of v.comments) {
      const li = el('li');
      const meta = el('div', 'dc-c-meta');
      meta.appendChild(el('b', null, c.who || t('anonymous')));
      if (c.t) meta.appendChild(el('span', null, new Date(c.t).toLocaleTimeString(cfg.ui || undefined, { hour: '2-digit', minute: '2-digit' })));
      meta.appendChild(btn('dc-x', '✕', { 'data-cdel': c.id, 'aria-label': t('delete') }));
      li.append(meta, el('div', 'dc-c-text', c.text));
      comments.appendChild(li);
    }
  }

  /* ---------- presenter mode ---------- */
  const slides = (cfg.slides || [])
    .map((s) => ({ ...s, el: document.getElementById(s.id), chEl: document.getElementById(s.chapter) }))
    .filter((s) => s.el && s.chEl);
  let presenting = false;
  let cur = 0;
  function slideOf(node) {
    const parts = slides.map((s, i) => [s, i]).filter(([s]) => s.id !== s.chapter && s.el.contains(node));
    if (parts.length) return parts[0][1];
    const i = slides.findIndex((s) => s.id === s.chapter && s.el.contains(node));
    return i >= 0 ? i : -1;
  }
  function buildDots() {
    slides.forEach((s, i) => dots.appendChild(btn('', null, { 'data-dot': String(i), 'aria-label': s.title })));
  }
  function renderDots() {
    slides.forEach((s, i) => {
      const d = dots.children[i];
      if (!d) return;
      const m = marksIn((sp) => slideOf(sp.node) === i);
      d.setAttribute('aria-current', String(i === cur));
      d.className = m.cls;
      d.title = (i + 1) + '. ' + s.title + (m.n ? ' · ' + t('marks') + ': ' + m.n : '');
    });
  }
  function setActiveToc(chapter) {
    for (const [k, v] of tocLinks) v.a.setAttribute('aria-current', String(k === chapter));
  }
  function showSlide(i, keepScroll) {
    if (!slides.length) return;
    cur = Math.min(slides.length - 1, Math.max(0, i));
    const s = slides[cur];
    const part = s.id !== s.chapter;
    for (const x of slides) {
      x.chEl.classList.toggle('dc-cur', x.chEl === s.chEl);
      x.chEl.classList.toggle('dc-part-view', x.chEl === s.chEl && part);
      if (x.id !== x.chapter) x.el.classList.toggle('dc-cur-part', x === s);
    }
    if (presenting && s.chEl.tagName === 'DETAILS') s.chEl.open = true;
    root.classList.toggle('dc-first', cur === 0);
    root.classList.toggle('dc-last', cur === slides.length - 1);
    pPos.textContent = (cur + 1) + '/' + slides.length + ' · ' + s.title;
    pPrev.disabled = cur === 0;
    pNext.disabled = cur === slides.length - 1;
    const nx = slides[cur + 1];
    pnextBox.hidden = !nx;
    pnextBtn.textContent = nx ? t('next') + ': ' + nx.title + ' ›' : '';
    renderDots();
    setActiveToc(s.chapter);
    if (presenting) {
      if (!keepScroll) window.scrollTo(0, 0);
      try { history.replaceState(null, '', '#' + s.id); } catch (e) { /* position is cosmetic */ }
    }
  }
  function setMode(on, remember) {
    presenting = on && slides.length > 0;
    root.classList.toggle('dc-present', presenting);
    modeBtn.textContent = presenting ? t('page_mode') : t('presenter');
    modeBtn.setAttribute('aria-pressed', String(presenting));
    if (remember) sset(MODE_KEY, presenting ? 'present' : 'page');
    if (presenting) showSlide(cur);
    else if (slides[cur] && remember) slides[cur].el.scrollIntoView({ block: 'start' });
  }
  function slideFromHash() {
    let h = '';
    try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { h = ''; }
    return h ? slides.findIndex((s) => s.id === h) : -1;
  }
  const canScroll = (dir) => (dir > 0
    ? window.scrollY + window.innerHeight < document.documentElement.scrollHeight - 4
    : window.scrollY > 4);
  function page(dir) {
    if (canScroll(dir)) { window.scrollBy(0, dir * Math.round(window.innerHeight * 0.8)); return; }
    closeDrawer();
    showSlide(cur + dir);
  }
  function go(i) { closeDrawer(); showSlide(i); }

  /* ---------- drawer ---------- */
  function openDrawer(id) {
    if (!spots.has(id)) return;
    openId = id;
    drawer.hidden = false;
    root.classList.add('dc-drawer-open');
    renderSpots();
    renderDrawer();
    cText.focus({ preventScroll: true });
  }
  function closeDrawer() {
    if (!openId) return;
    const n = spots.get(openId);
    openId = null;
    drawer.hidden = true;
    root.classList.remove('dc-drawer-open');
    renderSpots();
    if (n) n.node.focus({ preventScroll: true });
  }
  function goTo(id) {
    const s = spots.get(id);
    if (!s) return;
    if (presenting) { const i = slideOf(s.node); if (i >= 0 && i !== cur) showSlide(i); }
    const det = s.node.closest('details');
    if (det) det.open = true;
    s.node.scrollIntoView({ block: 'center', inline: 'nearest' });
    openDrawer(id);
  }
  const spotState = (id) => state.spots[id] || (state.spots[id] = { status: null, comments: [] });
  function prune(id) { if (!marked(state.spots[id])) delete state.spots[id]; }

  function renderAll() { renderSpots(); renderVote(); renderHot(); renderQuestions(); renderActions(); renderToc(); renderDots(); renderDrawer(); }
  function commit() { save(); renderAll(); }

  /* ---------- markdown export ---------- */
  const oneLine = (s) => String(s).replace(/\s*\n\s*/g, ' ');
  function toMarkdown() {
    const out = ['# ' + title, '', '_' + new Date().toLocaleString(cfg.ui || undefined) + '_', ''];
    if (BLOCKS.verdict) {
      const v = state.vote;
      out.push('## ' + t('verdict'), '',
        '- ' + t('vote_for') + ': ' + v.for + (v.forNames ? ' (' + oneLine(v.forNames) + ')' : ''),
        '- ' + t('vote_against') + ': ' + v.against + (v.againstNames ? ' (' + oneLine(v.againstNames) + ')' : ''), '');
    }
    if (QUESTIONS.length) {
      out.push('## ' + t('questions'), '');
      QUESTIONS.forEach((q, i) => {
        const a = state.questions[q.id] || {};
        out.push((i + 1) + '. **' + oneLine(q.text) + '**');
        if ((q.options || []).length) out.push('   - ' + t('pick') + ': ' + (a.pick || '—'));
        out.push('   - ' + t('decision') + ': ' + (a.decision ? oneLine(a.decision) : '—'));
      });
      out.push('');
    }
    const byChapter = new Map();
    for (const [id, s] of spots) {
      const v = state.spots[id];
      if (!marked(v)) continue;
      if (!byChapter.has(s.chapterName)) byChapter.set(s.chapterName, []);
      byChapter.get(s.chapterName).push([s, v]);
    }
    out.push('## ' + t('marks'), '');
    if (!byChapter.size) out.push(t('no_marks'), '');
    for (const [name, rows] of byChapter) {
      out.push('### ' + name, '');
      for (const [s, v] of rows) {
        out.push('- **' + s.label + '**' + (v.status ? ' — ' + t('status_' + v.status) : ''));
        v.comments.forEach((c) => out.push('  - ' + (c.who ? oneLine(c.who) + ': ' : '') + oneLine(c.text)));
      }
      out.push('');
    }
    if (BLOCKS.actions) {
      out.push('## ' + t('actions'), '');
      if (!state.actions.length) out.push(t('none'));
      state.actions.forEach((a) => out.push('- [' + (a.done ? 'x' : ' ') + '] ' + oneLine(a.text) + (a.owner ? ' — ' + oneLine(a.owner) : '')));
      out.push('');
    }
    return out.join('\n');
  }
  function download(name, text, type) {
    const url = URL.createObjectURL(new Blob([text], { type }));
    const a = el('a');
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const fileBase = () => KEY.replace(/^discussion-card:/, '').replace(/:v\d+$/, '').replace(/[^\w-]+/g, '-') + '-' + new Date().toISOString().slice(0, 10);

  /* ---------- menu, theme, reset ---------- */
  let armed = false;
  function disarm() { armed = false; resetBtn.textContent = t('reset'); }
  function toggleMenu(force) {
    const open = force == null ? pop.hidden : force;
    pop.hidden = !open;
    menuBtn.setAttribute('aria-expanded', String(open));
    if (!open) disarm();
  }
  function toggleTheme() {
    const dark = root.dataset.theme ? root.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    root.dataset.theme = dark ? 'light' : 'dark';
    sset(THEME_KEY, root.dataset.theme);
  }

  /* ---------- events ---------- */
  document.addEventListener('click', (e) => {
    const tg = e.target;
    if (!(tg instanceof Element)) return;
    if (tg.closest('#dc-menu-btn')) { toggleMenu(); return; }
    if (!tg.closest('.dc-menu')) toggleMenu(false);
    const id = (sel) => tg.closest(sel);
    if (id('#dc-export-md')) { download(fileBase() + '.md', toMarkdown(), 'text/markdown'); toggleMenu(false); return; }
    if (id('#dc-save-json')) { download(fileBase() + '.json', JSON.stringify(state, null, 2), 'application/json'); toggleMenu(false); return; }
    if (id('#dc-theme')) { toggleTheme(); return; }
    if (id('#dc-reset')) {
      if (!armed) { armed = true; resetBtn.textContent = t('reset_confirm'); return; }
      state = blank(); closeDrawer(); commit(); toggleMenu(false); toast(t('reset_done'));
      return;
    }
    const step = id('.dc-step');
    if (step) { const k = step.dataset.vote; state.vote[k] = Math.max(0, state.vote[k] + Number(step.dataset.d)); commit(); return; }
    const opt = id('.dc-opt');
    if (opt) {
      const q = state.questions[opt.dataset.q] || (state.questions[opt.dataset.q] = { pick: null, decision: '' });
      q.pick = q.pick === opt.dataset.opt ? null : opt.dataset.opt;
      commit();
      return;
    }
    const st = id('.dc-st');
    if (st && openId) { const v = spotState(openId); v.status = v.status === st.dataset.s ? null : st.dataset.s; prune(openId); commit(); return; }
    const cdel = id('[data-cdel]');
    if (cdel && openId) { const v = spotState(openId); v.comments = v.comments.filter((c) => c.id !== cdel.dataset.cdel); prune(openId); commit(); return; }
    const adel = id('[data-act-del]');
    if (adel) { state.actions = state.actions.filter((a) => a.id !== adel.dataset.actDel); commit(); return; }
    const dot = id('[data-dot]');
    if (dot) { go(Number(dot.dataset.dot)); return; }
    if (id('#dc-prev')) { go(cur - 1); return; }
    if (id('#dc-next, #dc-pnext')) { go(cur + 1); return; }
    if (id('#dc-mode')) { setMode(!presenting, true); return; }
    const gt = id('[data-goto]');
    if (gt) { goTo(gt.dataset.goto); return; }
    const tl = id('[data-chapter-link]');
    if (tl && presenting) {
      e.preventDefault();
      const i = slides.findIndex((s) => s.id === tl.dataset.chapterLink);
      if (i >= 0) go(i);
      return;
    }
    if (id('#dc-dr-close')) { closeDrawer(); return; }
    if (id('#dc-drawer, input, textarea, select, button, label, a, summary')) return;
    const sp = id('[data-spot]');
    if (sp) openDrawer(sp.dataset.spot);
  });
  document.addEventListener('keydown', (e) => {
    const tg = e.target instanceof Element ? e.target : null;
    if (e.key === 'Escape') { if (!pop.hidden) toggleMenu(false); else closeDrawer(); return; }
    const typing = tg && tg.closest('input, textarea, select, [contenteditable=""], [contenteditable="true"]');
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'p' || e.key === 'P' || e.key === 'з' || e.key === 'З') { e.preventDefault(); setMode(!presenting, true); return; }
    const sp = tg && tg.closest('[data-spot]');
    if (sp && tg === sp && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); openDrawer(sp.dataset.spot); return; }
    if (!presenting) return;
    const onControl = tg && tg.closest('button, a, summary, [role="button"]');
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { e.preventDefault(); go(cur + (e.key === 'ArrowRight' ? 1 : -1)); return; }
    if (e.key === 'PageDown' || e.key === 'PageUp') { e.preventDefault(); page(e.key === 'PageDown' ? 1 : -1); return; }
    if (e.key === ' ' && !onControl) { e.preventDefault(); page(e.shiftKey ? -1 : 1); return; }
    if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); go(e.key === 'Home' ? 0 : slides.length - 1); }
  });
  document.addEventListener('change', (e) => {
    const cb = e.target.closest && e.target.closest('[data-act]');
    if (cb) { const a = state.actions.find((x) => x.id === cb.dataset.act); if (a) { a.done = cb.checked; commit(); } }
  });
  let inputTimer;
  document.addEventListener('input', (e) => {
    const tg = e.target;
    if (!(tg instanceof Element)) return;
    if (tg.dataset.names) state.vote[tg.dataset.names + 'Names'] = tg.value.slice(0, CAP.names);
    else if (tg.dataset.dec) {
      const q = state.questions[tg.dataset.dec] || (state.questions[tg.dataset.dec] = { pick: null, decision: '' });
      q.decision = tg.value.slice(0, CAP.decision);
    } else return;
    clearTimeout(inputTimer);
    inputTimer = setTimeout(save, 250);
  });
  function addComment() {
    if (!openId) return;
    const text = cText.value.trim();
    if (!text) { toast(t('empty_text')); return; }
    spotState(openId).comments.push({ id: uid(), text: text.slice(0, CAP.comment), who: cWho.value.trim().slice(0, CAP.who), t: Date.now() });
    cText.value = '';
    commit();
  }
  cForm.addEventListener('submit', (e) => { e.preventDefault(); addComment(); });
  cText.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); addComment(); } });
  document.addEventListener('submit', (e) => {
    if (e.target.id !== 'dc-act-form') return;
    e.preventDefault();
    const text = $('#dc-act-text');
    const owner = $('#dc-act-owner');
    if (!text.value.trim()) { toast(t('empty_text')); return; }
    state.actions.push({ id: uid(), text: text.value.trim().slice(0, CAP.action), owner: owner.value.trim().slice(0, CAP.owner), done: false });
    text.value = '';
    owner.value = '';
    commit();
    text.focus();
  });
  loadInput.addEventListener('change', async () => {
    const f = loadInput.files && loadInput.files[0];
    loadInput.value = '';
    if (!f) return;
    try {
      state = sanitize(JSON.parse(await f.text()));
      closeDrawer();
      commit();
      if (storageOk) toast(t('loaded'));
    } catch (err) {
      toast(t('load_failed'));
    }
    toggleMenu(false);
  });
  window.addEventListener('hashchange', () => {
    if (!presenting) return;
    const i = slideFromHash();
    if (i >= 0 && i !== cur) showSlide(i);
  });

  /* ---------- init ---------- */
  async function init() {
    const th = sget(THEME_KEY);
    if (th === 'dark' || th === 'light') root.dataset.theme = th;
    buildVerdict();
    buildQuestions();
    buildActions();
    buildToc();
    buildDots();
    const setBarH = () => root.style.setProperty('--bar-h', bar.offsetHeight + 'px');
    setBarH();
    if (window.ResizeObserver) new ResizeObserver(setBarH).observe(bar);
    await renderRuntimeDiagrams();
    registerAll();
    state = load();
    const fromHash = slideFromHash();
    if (fromHash >= 0) cur = fromHash;
    const saved = sget(MODE_KEY);
    const on = saved === 'present' || saved === 'page' ? saved === 'present' : window.innerWidth >= PRESENT_MIN_PX;
    showSlide(cur, true);
    setMode(on, false);
    if (!on && fromHash >= 0) slides[fromHash].el.scrollIntoView({ block: 'start' });
    renderAll();
    root.classList.add('dc-ready');
  }
  init();
})();
