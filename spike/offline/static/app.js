// Indkøbsliste der virker offline.
// - Varer og ventende ændringer ligger i localStorage.
// - Afkrydsning gemmes lokalt med det samme og sendes til serveren, når der
//   er forbindelse. Serveren beholder den seneste ændring pr. vare.
const KEY_ITEMS = "madplan.items";
const KEY_PENDING = "madplan.pending";
const SYNC_EVERY_MS = 20000;
const TIMEOUT_MS = 6000;

const $list = document.getElementById("list");
const $status = document.getElementById("status");
const $login = document.getElementById("login");

function load(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}
function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* fuld eller blokeret */ }
}

let items = load(KEY_ITEMS, []);
let pending = load(KEY_PENDING, {}); // id -> {checked, ts}
let syncing = false;

function isChecked(item) {
  return item.id in pending ? pending[item.id].checked : item.checked;
}

function render() {
  const groups = new Map();
  for (const it of items) {
    if (!groups.has(it.department)) groups.set(it.department, []);
    groups.get(it.department).push(it);
  }
  $list.replaceChildren();
  for (const [dept, list] of groups) {
    const h = document.createElement("h2");
    h.textContent = dept;
    $list.append(h);
    for (const it of list) {
      const label = document.createElement("label");
      label.className = "item" + (isChecked(it) ? " done" : "");
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = isChecked(it);
      box.addEventListener("change", () => toggle(it.id, box.checked));
      const text = document.createElement("span");
      text.textContent = it.name;
      label.append(box, text);
      $list.append(label);
    }
  }
}

function setStatus(text, offline = false) {
  $status.textContent = text;
  $status.classList.toggle("offline", offline);
}

function toggle(id, checked) {
  pending[id] = { checked, ts: Date.now() };
  save(KEY_PENDING, pending);
  render();
  sync();
}

async function post(path, body) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  try {
    return await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
      signal: ctrl.signal,
    });
  } finally {
    clearTimeout(timer);
  }
}

async function sync() {
  if (syncing) return;
  syncing = true;
  const sent = { ...pending };
  const changes = Object.entries(sent).map(([id, c]) => ({ id: Number(id), ...c }));
  try {
    const res = await post("/api/sync", { changes });
    if (res.status === 401) {
      $login.hidden = false;
      setStatus(`Log ind igen. ${changes.length} ændringer gemt på telefonen.`, true);
      return;
    }
    if (!res.ok) throw new Error(res.status);
    const data = await res.json();
    items = data.items;
    // Fjern kun ændringer, der ikke er ændret igen, mens vi ventede.
    for (const [id, c] of Object.entries(sent)) {
      if (pending[id] && pending[id].ts === c.ts) delete pending[id];
    }
    save(KEY_ITEMS, items);
    save(KEY_PENDING, pending);
    $login.hidden = true;
    const t = new Date().toLocaleTimeString("da-DK", { hour: "2-digit", minute: "2-digit" });
    setStatus(`Synkroniseret ${t}`);
  } catch {
    const n = Object.keys(pending).length;
    setStatus(n ? `Offline – ${n} ændringer venter` : "Offline – viser gemt liste", true);
  } finally {
    syncing = false;
    render();
  }
}

document.getElementById("reset").addEventListener("click", async () => {
  pending = {};
  save(KEY_PENDING, pending);
  try {
    const res = await post("/api/reset", {});
    if (res.ok) { items = (await res.json()).items; save(KEY_ITEMS, items); }
  } catch { /* offline: nulstil når der er forbindelse */ }
  render();
});

window.addEventListener("online", sync);
document.addEventListener("visibilitychange", () => { if (!document.hidden) sync(); });
setInterval(sync, SYNC_EVERY_MS);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js");
render();
sync();
