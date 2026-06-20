"use strict";

async function api(path, body) {
  const opts = body
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : { method: "GET" };
  const r = await fetch(path, opts);
  return r.json();
}

function pokeStr(p) {
  if (!p) return "(none)";
  return `${p.name}#${p.id} HP ${p.hp}/${p.maxHp} ⚡${p.energy}` + (p.tools ? ` 🔧${p.tools}` : "");
}

function renderState(s) {
  if (!s || !s.active_game) {
    document.getElementById("turninfo").textContent = "no active game — press Start";
    return;
  }
  document.getElementById("turninfo").textContent =
    `turn ${s.turn} / yourIndex ${s.yourIndex} / result ${s.result}`;
  for (const idx of [0, 1]) {
    const p = s.players[idx];
    document.getElementById(`p${idx}-active`).textContent = "active: " + pokeStr(p.active);
    document.getElementById(`p${idx}-bench`).textContent =
      "bench: " + (p.bench.length ? p.bench.map(pokeStr).join(" | ") : "-");
    document.getElementById(`p${idx}-info`).textContent =
      `hand ${p.handCount} / prize ${p.prize} / deck ${p.deckCount} / discard ${p.discard}` +
      (p.status.length ? `  [${p.status.join(",")}]` : "");
  }
  document.getElementById("select").textContent = s.select ? JSON.stringify(s.select, null, 1) : "-";
  document.getElementById("logs").textContent = (s.logs || []).map((l) => JSON.stringify(l)).join("\n") || "-";
}

function renderMetrics(m) {
  document.getElementById("m-running").textContent = m.running;
  document.getElementById("m-games").textContent = m.games;
  document.getElementById("m-finished").textContent = m.finished;
  document.getElementById("m-crashes").textContent = m.crashes;
  document.getElementById("m-results").textContent = `${m.p0}/${m.p1}/${m.draw}`;
  document.getElementById("m-move").textContent = (m.max_move_ms || 0).toFixed(1);
  document.getElementById("m-rss").textContent = `${m.rss_start_mb}/${m.rss_mb}`;
  document.getElementById("m-elapsed").textContent = m.elapsed_s;
}

let autoStepTimer = null;

async function refreshMetrics() {
  renderMetrics(await api("/api/metrics"));
}

async function start() {
  renderState(await api("/api/start", { seed: +document.getElementById("seed").value }));
}
async function step() {
  const agent = document.getElementById("agent").value;
  renderState(await api("/api/step", { agent }));
}
async function autoStepToggle() {
  const btn = document.getElementById("btn-auto-step");
  if (autoStepTimer) {
    clearInterval(autoStepTimer); autoStepTimer = null; btn.textContent = "Auto-step ▶";
    return;
  }
  btn.textContent = "Auto-step ⏸";
  autoStepTimer = setInterval(async () => {
    const s = await api("/api/step", { agent: document.getElementById("agent").value });
    renderState(s);
    if (!s.active_game || (s.result !== undefined && s.result !== -1)) {
      clearInterval(autoStepTimer); autoStepTimer = null; btn.textContent = "Auto-step ▶";
    }
  }, 250);
}
async function auto() {
  const n = +document.getElementById("ngames").value;
  await api("/api/auto", { n_games: n, seed: +document.getElementById("seed").value,
                           agent: document.getElementById("agent").value });
  const poll = setInterval(async () => {
    const m = await api("/api/metrics");
    renderMetrics(m);
    if (!m.running) clearInterval(poll);
  }, 400);
}

document.getElementById("btn-start").onclick = start;
document.getElementById("btn-step").onclick = step;
document.getElementById("btn-auto-step").onclick = autoStepToggle;
document.getElementById("btn-auto").onclick = auto;
refreshMetrics();
setInterval(refreshMetrics, 1000);
