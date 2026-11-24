/* Local byte-commitment checks. No uploads, score computation, or attestation. */
(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const form = byId("bundle-form");
  const status = byId("check-status");
  const summary = byId("bundle-summary");
  const results = byId("check-results");
  const submit = byId("check-submit");
  const MAX_BYTES = 16 * 1024 * 1024;
  const SHA256 = /^[a-f0-9]{64}$/;
  const own = (obj, key) => Object.hasOwn(obj, key) ? obj[key] : undefined;
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  let generation = 0;

  function setStatus(message, outcome) {
    status.textContent = message;
    status.dataset.outcome = outcome;
  }
  function resetOutput() {
    generation += 1;
    results.replaceChildren();
    summary.replaceChildren();
    summary.hidden = true;
    submit.disabled = false;
    setStatus("Select a bundle to check its commitments.", "idle");
  }
  function selected(id) { return byId(id).files[0] || null; }
  async function read(file, label) {
    if (!file) throw Error(label + " is required.");
    if (file.size > MAX_BYTES) throw Error(label + " exceeds the 16 MiB browser limit. Use the CLI.");
    return file.arrayBuffer();
  }
  function parse(bytes, label) {
    let obj;
    try { obj = JSON.parse(new TextDecoder("utf-8", {fatal:true, ignoreBOM:true}).decode(bytes)); }
    catch { throw Error(label + " must be valid UTF-8 JSON."); }
    if (!object(obj)) throw Error(label + " must contain a JSON object.");
    return obj;
  }
  function digest(obj, key, label) {
    const value = own(obj, key);
    if (typeof value !== "string" || !SHA256.test(value) || value.length !== 64) {
      throw Error(label + " has an invalid or missing SHA-256 commitment.");
    }
    return value;
  }
  async function hash(bytes) {
    if (!globalThis.crypto?.subtle) throw Error("Web Crypto is unavailable. Use HTTPS or the local CLI.");
    const raw = await crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(raw), x => x.toString(16).padStart(2, "0")).join("");
  }
  function row(label, expected, observed) {
    const match = expected === observed;
    const el = document.createElement("div");
    el.className = "check-row";
    el.dataset.result = match ? "match" : "mismatch";
    const heading = document.createElement("strong");
    heading.textContent = label + " — " + (match ? "MATCH" : "MISMATCH");
    el.append(heading);
    for (const [name, value] of [["Expected",expected],["Observed",observed]]) {
      const code = document.createElement("code");
      code.textContent = name + ": " + value;
      el.append(code);
    }
    return {match, el};
  }
  function skipped(label) {
    const el = document.createElement("div");
    el.className = "check-row";
    el.dataset.result = "unchecked";
    el.textContent = label + " — NOT CHECKED (file not supplied)";
    return el;
  }
  function addSummary(label, value) {
    const dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = typeof value === "string" ? value.slice(0, 512) : "Unspecified";
    summary.append(dt, dd);
  }
  form.addEventListener("change", resetOutput);
  form.addEventListener("reset", resetOutput);
  form.addEventListener("submit", async event => {
    event.preventDefault();
    resetOutput();
    const current = generation;
    submit.disabled = true;
    setStatus("Checking original file bytes…", "busy");
    const files = {
      run: selected("run-file"), claim: selected("claim-file"), results: selected("results-file"),
      tasks: selected("tasks-file"), source: selected("source-file")
    };
    try {
      const run = parse(await read(files.run,"Run manifest"),"Run manifest");
      const version = own(run,"schema_version");
      if (!["1","inspect-v1"].includes(version)) throw Error("Unsupported run schema. Use the CLI.");
      const portable = version === "1";
      const claimBytes = await read(files.claim,"Claim manifest");
      const claim = parse(claimBytes,"Claim manifest");
      if (own(claim,"schema_version") !== "1") throw Error("Unsupported claim schema.");
      const claimId = own(claim,"id");
      if (typeof claimId !== "string" || !claimId || own(run,"claim_id") !== claimId) throw Error("Run and claim IDs do not match.");
      const protocol = own(claim,"protocol");
      if (!object(protocol) || own(protocol,"mode") !== (portable ? "portable-text" : "external")) throw Error("Claim and run formats are incompatible.");
      if (portable && files.source) throw Error("Original Inspect logs are only supported for Inspect v1.");
      if (!portable && files.tasks) throw Error("Task-file checks are only supported for portable-text runs.");
      const rows = [];
      const claimHash = await hash(claimBytes);
      rows.push(row("Claim manifest",digest(run,"manifest_sha256","Run manifest"),claimHash));
      rows.push(row("Recorded results",digest(run,"results_sha256","Run manifest"),await hash(await read(files.results,"Recorded results"))));
      let optionalUnchecked = false;
      if (portable) {
        const benchmark = own(claim,"benchmark");
        if (!object(benchmark)) throw Error("Claim benchmark commitments are missing.");
        const tasksHash = await hash(await read(files.tasks,"Task data"));
        rows.push(row("Task data / run commitment",digest(run,"tasks_sha256","Run manifest"),tasksHash));
        rows.push(row("Task data / claim commitment",digest(benchmark,"sha256","Claim benchmark"),tasksHash));
      } else {
        const expected = digest(run,"source_log_sha256","Run manifest");
        if (files.source) rows.push(row("Original Inspect log",expected,await hash(await read(files.source,"Original Inspect log"))));
        else optionalUnchecked = true;
      }
      // Do not let a superseded async check overwrite a newer selection.
      if (generation !== current) return;
      addSummary("Claim",claimId);
      addSummary("Run format",portable ? "Portable-text v1" : "Inspect v1");
      addSummary("Claim kind",own(claim,"kind"));
      addSummary("Recorded provenance",own(run,"provenance"));
      summary.hidden = false;
      for (const item of rows) results.append(item.el);
      if (optionalUnchecked) results.append(skipped("Original Inspect log"));
      const failures = rows.filter(item => !item.match).length;
      if (failures) setStatus(failures + " commitment mismatch(es). Do not rely on this bundle.", "mismatch");
      else setStatus(rows.length + " supplied file commitments match." + (optionalUnchecked ? " Original Inspect log not checked." : "") + " No score or execution verified.", "match");
    } catch (error) {
      if (generation === current) setStatus(error instanceof Error ? error.message : "Check failed.", "error");
    } finally {
      if (generation === current) submit.disabled = false;
    }
  });
})();
