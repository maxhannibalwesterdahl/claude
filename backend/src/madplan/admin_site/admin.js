'use strict';
// Ingen data i siden selv: alt hentes fra /api/admin efter login. Tekst sættes med
// textContent, aldrig innerHTML.
const $ = (id) => document.getElementById(id);
const msg = (t = '') => { $('msg').textContent = t; };

function el(tag, props = {}, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') e.className = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const k of kids) e.append(k);
  return e;
}

async function api(path, method = 'GET', body) {
  let res;
  try {
    res = await fetch('/api/admin' + path, {
      method, credentials: 'same-origin',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch { throw new Error('Ingen forbindelse'); }
  if (res.status === 404 && path !== '/login') { show('login'); throw new Error('Log ind igen'); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg).join('; ') : 'Fejl ' + res.status);
  }
  return data;
}

const run = (fn) => async (...a) => { msg(); try { await fn(...a); } catch (e) { msg(e.message); } };

let tab = 'households';
function show(name) {
  tab = name;
  for (const id of ['login', 'households', 'recipes', 'catalog']) $(id).hidden = id !== name;
  $('nav').hidden = name === 'login';
  for (const b of document.querySelectorAll('.tab')) b.classList.toggle('on', b.dataset.tab === name);
}

// --- Login ---
$('login-form').addEventListener('submit', run(async (e) => {
  e.preventDefault();
  const f = e.target;
  await api('/login', 'POST', { username: f.username.value, password: f.password.value });
  f.reset();
  await open('households');
}));
$('logout').addEventListener('click', run(async () => { await api('/logout', 'POST').catch(() => {}); show('login'); }));
for (const b of document.querySelectorAll('.tab')) b.addEventListener('click', run(() => open(b.dataset.tab)));

async function open(name) {
  show(name);
  if (name === 'households') await loadHouseholds();
  else if (name === 'recipes') await loadRecipes();
  else await loadCatalog();
}

// --- Familier ---
async function loadHouseholds() {
  const list = await api('/households');
  const box = $('household-list');
  box.replaceChildren();
  if (!list.length) box.append(el('p', { class: 'muted' }, 'Ingen familier endnu.'));
  for (const h of list) box.append(householdCard(h));
}

const reload = () => loadHouseholds();

function householdCard(h) {
  const card = el('div', { class: 'card' });
  const last = h.last_activity ? 'seneste plan ' + h.last_activity.slice(0, 10) : 'ingen planer';
  card.append(el('header', {},
    el('div', {}, el('h2', {}, h.name), el('span', { class: 'muted' }, `${h.recipes} opskrifter · ${h.plans} planer · ${last}`)),
    el('div', { class: 'row' },
      el('button', { class: 'quiet sm', onclick: run(async () => {
        const name = prompt('Nyt navn', h.name);
        if (name && name.trim()) { await api('/households/' + h.id, 'PATCH', { name }); await reload(); }
      }) }, 'Omdøb'),
      el('button', { class: 'quiet sm', onclick: run(async () => {
        const off = !h.members.every((m) => m.disabled || m.is_system_admin);
        if (!confirm((off ? 'Spær alle i ' : 'Åbn for alle i ') + h.name + '?')) return;
        await api(`/households/${h.id}/disabled`, 'POST', { disabled: off }); await reload();
      }) }, 'Spær / åbn alle'),
      el('button', { class: 'danger sm', onclick: run(async () => {
        if (prompt(`Sletter ${h.name} med planer, indkøb og brugere. Skriv familiens navn for at bekræfte.`) !== h.name) return;
        await api('/households/' + h.id, 'DELETE'); await reload();
      }) }, 'Slet'))));
  for (const m of h.members) card.append(memberRow(m));
  const form = el('form', { class: 'row', onsubmit: run(async (e) => {
    e.preventDefault();
    const f = e.target;
    await api(`/households/${h.id}/users`, 'POST', { username: f.u.value, password: f.p.value, role: f.r.value });
    await reload();
  }) },
    el('input', { name: 'u', placeholder: 'Brugernavn', required: '', autocapitalize: 'none', maxlength: '50' }),
    el('input', { name: 'p', type: 'password', placeholder: 'Kodeord (mindst 12 tegn)', required: '', autocomplete: 'new-password' }),
    el('select', { name: 'r' }, el('option', { value: 'admin' }, 'Familie-admin'), el('option', { value: 'medlem' }, 'Medlem')),
    el('button', { type: 'submit', class: 'sm' }, 'Tilføj bruger'));
  card.append(form);
  return card;
}

function memberRow(m) {
  const row = el('div', { class: 'member' + (m.disabled ? ' off' : '') },
    el('span', { class: 'name' }, m.username,
      el('span', { class: 'tag' }, m.role), m.is_system_admin ? el('span', { class: 'tag' }, 'systemadmin') : '',
      m.disabled ? el('span', { class: 'tag' }, 'spærret') : ''),
    el('button', { class: 'quiet sm', onclick: run(async () => {
      const p = prompt('Nyt kodeord til ' + m.username + ' (mindst 12 tegn). Brugeren logges ud overalt.');
      if (p) { await api(`/users/${m.id}/password`, 'POST', { password: p }); msg('Kodeordet er ændret.'); }
    }) }, 'Nyt kodeord'),
    el('button', { class: 'quiet sm', onclick: run(async () => {
      await api(`/users/${m.id}/disabled`, 'POST', { disabled: !m.disabled }); await reload();
    }) }, m.disabled ? 'Åbn' : 'Spær'),
    el('button', { class: 'danger sm', onclick: run(async () => {
      if (!confirm('Slet brugeren ' + m.username + '?')) return;
      await api('/users/' + m.id, 'DELETE'); await reload();
    }) }, 'Slet'));
  return row;
}

$('new-household').addEventListener('submit', run(async (e) => {
  e.preventDefault();
  await api('/households', 'POST', { name: e.target.name.value });
  e.target.reset();
  await reload();
}));

// --- Opskrifter ---
let recipes = [];
async function loadRecipes() { recipes = await api('/recipes'); drawRecipes(); }
function drawRecipes() {
  const q = $('recipe-filter').value.trim().toLowerCase();
  const rows = $('recipe-rows');
  rows.replaceChildren();
  for (const r of recipes.filter((r) => !q || r.title.toLowerCase().includes(q) || (r.owner || '').toLowerCase().includes(q))) {
    rows.append(el('tr', {},
      el('td', {}, r.title), el('td', {}, r.owner || '–'), el('td', {}, String(r.lines)), el('td', {}, String(r.used_in_plans)),
      el('td', {}, el('button', { class: 'danger sm', onclick: run(async () => {
        if (!confirm(`Slet "${r.title}"? Den fjernes fra alle familiers planer.`)) return;
        await api('/recipes/' + r.id, 'DELETE'); await loadRecipes();
      }) }, 'Slet'))));
  }
}
$('recipe-filter').addEventListener('input', drawRecipes);

// --- Varekatalog ---
let catalog = { departments: [], items: [] };
async function loadCatalog() { catalog = await api('/ingredients'); drawCatalog(); }
const num = (v) => (v.trim() === '' ? null : Number(v.replace(',', '.')));

function drawCatalog() {
  const q = $('catalog-filter').value.trim().toLowerCase();
  const box = $('catalog-list');
  box.replaceChildren();
  const shown = catalog.items.filter((i) => !q || i.name.includes(q) || i.aliases.some((a) => a.alias.toLowerCase().includes(q)));
  for (const i of shown.slice(0, 60)) box.append(catalogCard(i));
  if (shown.length > 60) box.append(el('p', { class: 'muted' }, `${shown.length - 60} flere. Søg for at indsnævre.`));
}

function catalogCard(i) {
  const dept = el('select', { name: 'd' }, ...catalog.departments.map((d) => {
    const o = el('option', { value: d.code }, d.name);
    if (d.code === i.department) o.selected = true;
    return o;
  }));
  const form = el('form', { class: 'row', onsubmit: run(async (e) => {
    e.preventDefault();
    const f = e.target;
    await api('/ingredients/' + i.id, 'PUT', { name: f.n.value, department: f.d.value, grams_per_piece: num(f.p.value), grams_per_dl: num(f.l.value) });
    await loadCatalog(); msg('Gemt.');
  }) },
    el('input', { name: 'n', value: i.name, maxlength: '100', required: '' }), dept,
    el('input', { name: 'p', value: i.grams_per_piece ?? '', placeholder: 'g pr. stk', size: '6', inputmode: 'decimal' }),
    el('input', { name: 'l', value: i.grams_per_dl ?? '', placeholder: 'g pr. dl', size: '6', inputmode: 'decimal' }),
    el('button', { type: 'submit', class: 'sm' }, 'Gem'),
    el('button', { type: 'button', class: 'danger sm', onclick: run(async () => {
      if (!confirm('Slet varen ' + i.name + '?')) return;
      await api('/ingredients/' + i.id, 'DELETE'); await loadCatalog();
    }) }, 'Slet'));
  const aliases = el('div', { class: 'muted' }, `Bruges i ${i.used_in} opskrifter. Andre navne: `);
  if (!i.aliases.length) aliases.append('ingen');
  for (const a of i.aliases) {
    aliases.append(el('span', { class: 'tag' }, a.alias + (a.source === 'user' ? ' (lært)' : ''), ' ',
      el('button', { class: 'danger sm', title: 'Fjern alias', onclick: run(async () => {
        await api('/aliases/' + a.id, 'DELETE'); await loadCatalog();
      }) }, '×')));
  }
  return el('div', { class: 'card' }, form, aliases);
}
$('catalog-filter').addEventListener('input', drawCatalog);

// --- Start ---
run(async () => {
  try { await api('/me'); await open('households'); } catch { show('login'); }
})();
