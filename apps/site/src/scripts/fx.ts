// Page-level behaviour: reveal, dissolve, parallax, scroll bar, section dots, counters,
// clock, TOC highlight, click sparks, mobile menu. Everything respects the FX toggle and reduced-motion.
import { fxOn, dissolveEl, sparks, wipeCover } from './pixelfx';
import { setTheme, toggleEffects } from './theme';
import { themes, DEFAULT_THEME } from '../lib/themes';

const $$ = <T extends HTMLElement = HTMLElement>(s: string, root: ParentNode = document) => [...root.querySelectorAll<T>(s)];

/* ---------- reveal on scroll (stepped pop-in) ---------- */
function reveal() {
  const els = $$('[data-reveal]');
  els.forEach((el) => {
    const sibs = [...(el.parentElement?.children ?? [])].filter((c) => c.hasAttribute('data-reveal'));
    el.style.setProperty('--i', String(Math.max(0, sibs.indexOf(el))));
  });
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      (e.target as HTMLElement).classList.add('is-in');
      io.unobserve(e.target);
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
  els.forEach((el) => io.observe(el));
}

/* ---------- pixel dissolve for image frames ---------- */
function dissolve() {
  const io = new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (!e.isIntersecting) return;
      dissolveEl(e.target as HTMLElement);
      io.unobserve(e.target);
    });
  }, { threshold: 0.3 });
  $$('[data-dissolve]').forEach((el) => io.observe(el));
}

/* ---------- parallax (movement snaps to a 4px grid so it feels like sprites) ---------- */
function parallax() {
  const els = $$('[data-parallax],[data-parallax-x]');
  if (!els.length) return;
  const vis = new Set<HTMLElement>();
  const io = new IntersectionObserver((es) => es.forEach((e) => (e.isIntersecting ? vis.add(e.target as HTMLElement) : vis.delete(e.target as HTMLElement))), { rootMargin: '30% 0px' });
  els.forEach((el) => io.observe(el));
  const snap = (n: number) => Math.round(n / 4) * 4;
  let queued = false;
  const update = () => {
    queued = false;
    const on = fxOn();
    vis.forEach((el) => {
      if (!on) { el.style.setProperty('--py', '0px'); el.style.setProperty('--px', '0px'); return; }
      const host = (el.closest('.sec') ?? el.parentElement!) as HTMLElement;
      const r = host.getBoundingClientRect();
      const off = r.top + r.height / 2 - innerHeight / 2;
      const sy = parseFloat(el.dataset.parallax ?? '0'), sx = parseFloat(el.dataset.parallaxX ?? '0');
      el.style.setProperty('--py', `${snap(-off * sy)}px`);
      el.style.setProperty('--px', `${snap(-off * sx)}px`);
    });
  };
  const req = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
  addEventListener('scroll', req, { passive: true });
  addEventListener('resize', req);
  window.addEventListener('benki:fx', req);
  req();
}

/* ---------- segmented scroll bar ---------- */
function scrollbar() {
  const bar = document.getElementById('scrollbar');
  if (!bar) return;
  const upd = () => {
    const max = document.documentElement.scrollHeight - innerHeight;
    bar.style.setProperty('--p', max > 0 ? String(Math.min(1, scrollY / max)) : '0');
  };
  addEventListener('scroll', upd, { passive: true }); addEventListener('resize', upd); upd();
}

/* ---------- section dots (desktop) ---------- */
function secnav() {
  const nav = document.getElementById('secnav');
  const secs = $$('[data-title]');
  if (!nav || secs.length < 2) return;
  secs.forEach((s, i) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'secdot'; b.setAttribute('aria-label', `Go to ${s.dataset.title}`);
    b.innerHTML = `<span class="lbl">${s.dataset.title}</span><i></i>`;
    b.addEventListener('click', () => s.scrollIntoView({ behavior: fxOn() ? 'smooth' : 'auto', block: 'start' }));
    nav.append(b);
    s.dataset.dot = String(i);
  });
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    [...nav.children].forEach((c, i) => c.toggleAttribute('data-on', i === Number((e.target as HTMLElement).dataset.dot)));
  }), { threshold: 0.5 });
  secs.forEach((s) => io.observe(s));
  nav.hidden = false;
}

/* ---------- stepped counters ---------- */
function counters() {
  const els = $$('[data-count]');
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    io.unobserve(e.target);
    const el = e.target as HTMLElement, to = Number(el.dataset.count || 0);
    if (!fxOn() || to < 2) { el.textContent = String(to); return; }
    let i = 0; const steps = 10;
    const tm = setInterval(() => { i++; el.textContent = String(Math.round((to * i) / steps)); if (i >= steps) clearInterval(tm); }, 70);
  }), { threshold: 0.6 });
  els.forEach((el) => io.observe(el));
}

/* ---------- clock + toc ---------- */
function clock() {
  const els = $$('[data-clock]');
  if (!els.length) return;
  const t = () => els.forEach((el) => (el.textContent = new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })));
  t(); setInterval(t, 20000);
}
function toc() {
  const links = $$<HTMLAnchorElement>('[data-toc] a[href^="#"]');
  if (!links.length) return;
  const map = new Map<Element, HTMLAnchorElement>();
  links.forEach((a) => { const h = document.getElementById(decodeURIComponent(a.hash.slice(1))); if (h) map.set(h, a); });
  const io = new IntersectionObserver((es) => es.forEach((e) => {
    if (!e.isIntersecting) return;
    links.forEach((l) => l.removeAttribute('data-on'));
    map.get(e.target)?.setAttribute('data-on', '');
  }), { rootMargin: '-15% 0px -70% 0px' });
  map.forEach((_, h) => io.observe(h));
}

/* ---------- mobile menu: full-screen, pixel-wipe in and out ---------- */
function menu() {
  const btn = document.getElementById('menu-btn') as HTMLButtonElement | null;
  const panel = document.getElementById('mobile-menu') as HTMLElement | null;
  if (!btn || !panel) return;
  let open = false, busy = false;
  const bg = () => themes.find((t) => t.id === document.documentElement.dataset.theme)?.bg ?? '#1F1F28';
  const acc = () => themes.find((t) => t.id === document.documentElement.dataset.theme)?.accent;

  async function toggle(next: boolean, href?: string) {
    if (busy || next === open) return;
    busy = true;
    const reveal = await wipeCover(bg(), acc(), 320);
    open = next;
    panel!.hidden = !next;
    panel!.classList.toggle('open', next);
    document.documentElement.classList.toggle('menu-open', next);
    btn!.setAttribute('aria-expanded', String(next));
    btn!.setAttribute('aria-label', next ? 'Close menu' : 'Open menu');
    if (href) { location.href = href; return; } // new page loads under the pixel cover
    await reveal();
    busy = false;
    if (next) panel!.querySelector<HTMLElement>('a')?.focus();
  }
  btn.addEventListener('click', () => toggle(!open));
  panel.querySelectorAll<HTMLAnchorElement>('a[data-menu-link]').forEach((a) =>
    a.addEventListener('click', (e) => {
      if (e.metaKey || e.ctrlKey) return;
      e.preventDefault();
      const here = new URL(a.href).pathname === location.pathname;
      toggle(false, here ? undefined : a.href);
    }));
  addEventListener('keydown', (e) => { if (e.key === 'Escape' && open) toggle(false); });
  matchMedia('(min-width: 768px)').addEventListener('change', (m) => { if (m.matches && open) { panel!.hidden = true; open = false; document.documentElement.classList.remove('menu-open'); btn!.setAttribute('aria-expanded', 'false'); } });
}

/* ---------- theme + fx buttons ---------- */
function controls() {
  const sync = () => {
    const cur = document.documentElement.dataset.theme || DEFAULT_THEME;
    $$('[data-theme-set]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.themeSet === cur)));
    $$('[data-theme-label]').forEach((el) => (el.textContent = cur));
    $$('[data-fx-state]').forEach((b) => (b.textContent = document.documentElement.dataset.fx === 'off' ? 'off' : 'on'));
  };
  $$('[data-theme-set]').forEach((b) => b.addEventListener('click', () => setTheme(b.dataset.themeSet!)));
  $$('[data-fx-toggle]').forEach((b) => b.addEventListener('click', () => toggleEffects()));
  window.addEventListener('benki:theme', sync); window.addEventListener('benki:fx', sync); sync();
}

/* ---------- init ---------- */
function init() {
  reveal(); dissolve(); parallax(); scrollbar(); secnav(); counters(); clock(); toc(); menu(); controls();
  addEventListener('pointerdown', (e) => sparks(e.clientX, e.clientY));
}
init();
