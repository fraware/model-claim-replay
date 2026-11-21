/* Static, privacy-preserving presentation. All demonstration answers are fixtures. */
(() => {
  "use strict";
  const records = [
    { id: "claude-fable-5-2-chartography", kind: "published", title: "Claude Fable 5.2 / Chartography", subtitle: "73.4% publisher-reported score. Independent reproduction pending.", state: "IMPORTER READY", source: "https://www.anthropic.com/claude-fable-and-mythos-5-2", manifest: "https://github.com/fraware/model-claim-replay/blob/main/claims/claude-fable-5-2-chartography.json", dossier: "https://github.com/fraware/model-claim-replay/blob/main/docs/CHARTOGRAPHY.md", score: "73.4%", detail: "The official Inspect AI log importer is implemented and tested. The published 73.4% still has no independent reproduction. Full dataset rights, matching evaluation settings, model identity and budget remain unresolved." },
    { id: "gemini-4-neon-graphwalks-bfs-long", kind: "published", title: "Gemini 4 Neon / GraphWalks", subtitle: "200 verified BFS tasks. Independent deterministic control: 100% F1. Gemini model reproduction pending.", state: "SOURCE + CONTROL VERIFIED", source: "https://deepmind.google/models/model-cards/gemini-4-neon/", manifest: "https://github.com/fraware/model-claim-replay/blob/main/claims/gemini-4-neon-graphwalks-bfs-long.json", dossier: "https://github.com/fraware/model-claim-replay/blob/main/docs/GRAPHWALKS.md", explorer: "./graphwalks.html", score: "95.2%", detail: "Google reports its own evaluation over 200 tasks with 256K–1M tokens. The candidate MIT-licensed Parquet is SHA-256 verified. A deterministic graph algorithm scored F1=1.0 on all 200 pinned public BFS tasks with zero model API calls. This is an algorithmic control, not a model result. Google's exact dataset revision and model settings remain unverified; no Gemini reproduction has been performed." },
    { id: "demo-text-exact-match", kind: "synthetic", title: "Three-task exact-match fixture", subtitle: "A complete, runnable scoring demonstration. No real model score.", state: "SYNTHETIC FIXTURE", source: "https://github.com/fraware/model-claim-replay/blob/main/examples/demo-tasks.jsonl", manifest: "https://github.com/fraware/model-claim-replay/blob/main/claims/demo-text-exact-match.json", score: "2 / 3", detail: "Three artificial tasks and predefined responses test CLI validation, exact-match scoring, integrity checks and reports. This is not a published frontier-model evaluation." }
  ];
  const items = document.getElementById("claim-items");
  const detail = document.getElementById("claim-detail");
  let currentFilter = "all";
  let selectedId = null;
  const escape = value => String(value).replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"})[char]);
  function renderClaims() {
    const chosen = records.filter(record => currentFilter === "all" || record.kind === currentFilter);
    items.innerHTML = "";
    chosen.forEach((record, index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "claim-row" + (selectedId === record.id ? " selected" : "");
      button.style.cssText = "width:100%;text-align:left;border-left:0;border-right:0;border-top:0;color:inherit;font:inherit";
      button.setAttribute("aria-expanded", String(selectedId === record.id));
      button.innerHTML = `<span class="claim-marker">${String(index+1).padStart(2,"0")}</span><span><span class="tag">${record.kind === "published" ? "PUBLISHED CLAIM" : "SYNTHETIC FIXTURE"}</span><h3>${escape(record.title)}</h3><p>${escape(record.subtitle)}</p></span><span class="claim-status">${escape(record.state)} <span aria-hidden="true">↗</span></span>`;
      button.addEventListener("click", () => { selectedId = selectedId === record.id ? null : record.id; renderClaims(); });
      items.appendChild(button);
    });
    const record = records.find(item => item.id === selectedId && chosen.includes(item));
    detail.hidden = !record;
    detail.innerHTML = record ? `<div class="detail-grid"><div><strong>RECORDED VALUE</strong><p>${escape(record.score)} · ${record.kind === "published" ? "Vendor-reported, not reproduced" : "Predefined demonstration"}</p><strong>REPRODUCTION STATUS</strong><p>${escape(record.detail)}</p></div><div><strong>INSPECT THE EVIDENCE</strong><p><a href="${record.source}" target="_blank" rel="noopener noreferrer">Original source ↗</a></p><p><a href="${record.manifest}" target="_blank" rel="noopener noreferrer">Machine-readable claim record ↗</a></p>${record.dossier ? `<p><a href="${record.dossier}" target="_blank" rel="noopener noreferrer">Reproduction dossier ↗</a></p>` : ""}${record.explorer ? `<p><a href="${record.explorer}">Explore the 200 verified tasks ↗</a></p>` : ""}</div></div>` : "";
  }
  document.querySelectorAll(".filter").forEach(button => button.addEventListener("click", () => {
    currentFilter = button.dataset.filter;
    selectedId = null;
    document.querySelectorAll(".filter").forEach(other => { other.classList.toggle("active", other === button); other.setAttribute("aria-pressed", String(other === button)); });
    renderClaims();
  }));
  renderClaims();

  const tasks = [
    {prompt:"Answer with exactly the word alpha.", expected:"alpha", response:"alpha"},
    {prompt:"Answer with exactly the word beta.", expected:"beta", response:"incorrect"},
    {prompt:"Answer with exactly the word gamma.", expected:"gamma", response:"gamma"}
  ];
  const byId = id => document.getElementById(id);
  const button = byId("next-step");
  const reset = byId("reset-demo");
  let step = 0, revealed = false;
  function update() {
    const task = tasks[Math.min(step, tasks.length - 1)];
    byId("step-counter").textContent = `${String(Math.min(step+1,3)).padStart(2,"0")} / 03`;
    byId("task-prompt").textContent = task.prompt;
    byId("expected").textContent = task.expected;
    byId("response").textContent = revealed ? task.response : "—";
    const verdict = byId("verdict");
    verdict.className = "verdict";
    verdict.textContent = "Awaiting replay";
    if (revealed) {
      const pass = task.response.trim() === task.expected.trim();
      verdict.textContent = pass ? "✓ PASS — exact match" : "✕ FAIL — response differs from expected";
      verdict.classList.add(pass ? "pass" : "fail");
    }
    const assessed = Math.min(step + (revealed ? 1 : 0), 3);
    const successful = tasks.slice(0,assessed).filter(item => item.response.trim() === item.expected.trim()).length;
    byId("score-display").innerHTML = assessed === 0 ? "—<span> / 3</span>" : `${successful}<span> / 3</span>`;
    byId("assessed-display").textContent = `${assessed} of 3`;
    byId("progress-fill").style.width = `${assessed/3*100}%`;
    button.disabled = step === 2 && revealed;
    button.innerHTML = !revealed ? "Reveal response <span>→</span>" : step === 2 ? "Replay complete ✓" : "Next task <span>→</span>";
  }
  button.addEventListener("click", () => { if(!revealed) revealed = true; else if (step < 2) { step++; revealed = false; } update(); });
  reset.addEventListener("click", () => { step=0; revealed=false; update(); });
  update();
  const scenarios = {
    matched: {
      score: "3 <small>/ 3 correct</small>", width: "100%",
      label: "PAIRED DIAGNOSTIC", delta: "+33.3 percentage points",
      description: "The task IDs, judge, and trial design match. The synthetic difference is reportable as a paired diagnostic, not proof about a published model claim.",
      ids: "MATCH", judge: "MATCH", protocol: "MATCH"
    },
    judge: {
      score: "3 <small>/ 3 correct</small>", width: "100%",
      label: "COMPARISON BLOCKED", delta: "No defensible difference",
      description: "The two runs used different judges. Identical tasks and different-looking scores do not repair the incompatible scoring protocol.",
      ids: "MATCH", judge: "MISMATCH", protocol: "MISMATCH"
    },
    missing: {
      score: "2 <small>/ 2 assessed</small>", width: "66.666%",
      label: "COMPARISON BLOCKED", delta: "No defensible difference",
      description: "The second run is missing one task. Comparing only the completed tasks would silently change the sample and inflate or suppress the observed difference.",
      ids: "MISMATCH", judge: "MATCH", protocol: "MATCH"
    }
  };
  document.querySelectorAll(".scenario").forEach(control => control.addEventListener("click", () => {
    const scenario = scenarios[control.dataset.scenario];
    if (!scenario) return;
    document.querySelectorAll(".scenario").forEach(item => {
      item.classList.toggle("active", item === control);
      item.setAttribute("aria-pressed", String(item === control));
    });
    // Values are fixed authored fixtures. The site never evaluates external results.
    byId("pair-second-value").innerHTML = scenario.score;
    byId("pair-second-bar").style.width = scenario.width;
    byId("pair-status-label").textContent = scenario.label;
    byId("pair-delta").textContent = scenario.delta;
    byId("pair-description").textContent = scenario.description;
    byId("pair-task-check").textContent = scenario.ids;
    byId("pair-judge-check").textContent = scenario.judge;
    byId("pair-protocol-check").textContent = scenario.protocol;
    byId("pair-status-label").classList.toggle("blocked", control.dataset.scenario !== "matched");
  }));
  byId("copy-command").addEventListener("click", async () => {
    const value = byId("install-code").textContent;
    try { await navigator.clipboard.writeText(value); byId("copy-command").textContent="Copied ✓"; }
    catch { byId("copy-command").textContent="Select commands to copy"; }
  });
})();
