/* Read-only explorer generated from independently hash-verified source bytes. */
(() => {
  'use strict';
  const ROOT = document.getElementById('task-matrix');
  const RECORD = document.getElementById('record');
  const SEARCH = document.getElementById('task-search');
  const COUNT = document.getElementById('result-count');
  const FILTERS = document.querySelectorAll('.filter');
  const fmt = value => Number(value).toLocaleString('en-US');
  let filter = 'all';
  let query = '';
  let selected = null;
  let tasks = [];
  let controlById = new Map();
  let providerById = new Map();

  function showTask(task) {
    selected = task.id;
    ROOT.querySelectorAll('button.task-dot').forEach(el => {
      const on = el.dataset.id === selected;
      el.classList.toggle('selected', on);
      el.setAttribute('aria-pressed', String(on));
    });
    // Only bounded, authored markup. Dynamic source fields enter via textContent.
    RECORD.replaceChildren();
    const layout = document.createElement('div');
    layout.className = 'record-grid';
    const left = document.createElement('div');
    const label = document.createElement('small');
    label.textContent = 'SELECTED SOURCE RECORD';
    const title = document.createElement('div');
    title.className = 'record-title';
    title.textContent = task.id;
    const detail = document.createElement('div');
    detail.className = 'record-meta';
    for (const [name, val] of [
      ['ORIGINAL PROMPT LENGTH', `${fmt(task.prompt_chars)} characters`],
      ['REFERENCE ANSWER SIZE', `${fmt(task.answer_node_count)} nodes`],
      ['SOURCE ROW INDEX', String(task.source_row_index)],
      ...(providerById.has(task.id) ? [
        ['GEMINI INPUT TOKENS / LIVE PROVIDER', fmt(providerById.get(task.id).tokens)],
        ['GEMINI INPUT FEASIBILITY', providerById.get(task.id).fits ? 'WITHIN INPUT LIMIT' : 'EXCEEDS INPUT LIMIT']
      ] : [['GEMINI INPUT FEASIBILITY', 'Provider receipt unavailable']])
    ]) {
      const block = document.createElement('div');
      const l = document.createElement('small');
      l.textContent = name;
      const strong = document.createElement('strong');
      strong.textContent = val;
      block.append(l, strong);
      detail.append(block);
    }
    left.append(label, title, detail);
    const right = document.createElement('div');
    const hashLabel = document.createElement('small');
    hashLabel.textContent = 'SOURCE PROMPT SHA-256';
    const hash = document.createElement('div');
    hash.className = 'hash';
    hash.textContent = task.prompt_sha256;
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'record-action';
    copy.textContent = 'Copy digest';
    copy.addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(task.prompt_sha256); copy.textContent = 'Copied'; }
      catch { copy.textContent = 'Select digest above to copy'; }
    });
    right.append(hashLabel, hash, copy);
    const measured = controlById.get(task.id);
    if (measured) {
      const evidence = document.createElement('div');
      evidence.className = 'control-task';
      const title = document.createElement('small');
      title.textContent = 'DETERMINISTIC BFS CONTROL / NOT A MODEL SCORE';
      const result = document.createElement('strong');
      result.textContent = `F1 ${Number(measured.f1).toFixed(3)} · ${fmt(measured.edge_count)} edges`;
      const detail = document.createElement('p');
      detail.textContent = `BFS depth ${measured.depth}; result verified against the pinned public reference answer.`;
      evidence.append(title, result, detail);
      right.append(evidence);
    }
    layout.append(left, right);
    RECORD.append(layout);
  }

  function draw() {
    const matches = tasks.filter(t =>
      (filter === 'all' || (filter === 'short' ? t.prompt_chars < 1000000 : t.prompt_chars >= 1000000)) &&
      (!query || t.id.includes(query) || String(t.source_row_index).includes(query))
    );
    COUNT.textContent = `${matches.length} / ${tasks.length} tasks`;
    const fragment = document.createDocumentFragment();
    for (const task of matches) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `task-dot ${task.prompt_chars < 1000000 ? 'short' : 'long'}`;
      btn.dataset.id = task.id;
      btn.setAttribute('aria-label', `${task.id}, ${fmt(task.prompt_chars)} prompt characters`);
      btn.setAttribute('aria-pressed', String(selected === task.id));
      btn.title = `${task.id} · ${fmt(task.prompt_chars)} characters`;
      if (selected === task.id) btn.classList.add('selected');
      btn.addEventListener('click', () => showTask(task));
      fragment.append(btn);
    }
    ROOT.replaceChildren(fragment);
    if (!matches.length) {
      const empty = document.createElement('p');
      empty.className = 'loading';
      empty.textContent = 'No tasks match this selection.';
      ROOT.append(empty);
    }
    if (!matches.some(t => t.id === selected)) {
      selected = null;
      RECORD.innerHTML = '<div class="record-placeholder">Select one of the marks to inspect its source record.</div>';
    }
  }

  for (const button of FILTERS) {
    button.addEventListener('click', () => {
      filter = button.dataset.filter;
      for (const item of FILTERS) {
        item.classList.toggle('active', item === button);
        item.setAttribute('aria-pressed', String(item === button));
      }
      draw();
    });
  }
  SEARCH.addEventListener('input', () => { query = SEARCH.value.trim().toLowerCase(); draw(); });

  fetch('./graphwalks-audit.json')
    .then(res => { if (!res.ok) throw Error(`HTTP ${res.status}`); return res.json(); })
    .then(data => {
      if (data.schema_version !== 'graphwalks-public-explorer-v1' ||
          data.tasks?.length !== 200 || data.summary?.bfs_tasks !== 200 ||
          data.source?.reference_index_sha256 !== '250d80874ad9bc8edf278cf3bf7aa145da3f2b34967c5504b8fa8703358480ee') {
        throw Error('Unexpected dataset receipt');
      }
      tasks = data.tasks;
      draw();
      const controlEvidence = fetch('./graphwalks-control.json')
        .then(response => { if (!response.ok) throw Error('Missing control evidence'); return response.json(); })
        .then(control => {
          if (control.schema_version !== 'graphwalks-algorithmic-control-v1' ||
              control.reference_index_sha256 !== data.source.reference_index_sha256 ||
              control.source_parquet_sha256 !== data.source.parquet_sha256_verified ||
              control.source_task_count !== 200 || control.graded !== 200 ||
              control.parse_failures !== 0 || control.mean_f1_full_cohort !== 1 ||
              !Array.isArray(control.tasks) || control.tasks.length !== 200) {
            throw Error('Unexpected algorithmic control receipt');
          }
          const byId = new Map(control.tasks.map(row => [row.id, row]));
          if (byId.size !== 200 || tasks.some(task => {
            const result = byId.get(task.id);
            return !result || result.prompt_sha256 !== task.prompt_sha256 ||
              result.status !== 'graded' || result.f1 !== 1;
          })) throw Error('Control records do not match public source index');
          controlById = byId;
          const selectedTask = tasks.find(row => row.id === selected);
          if (selectedTask) showTask(selectedTask);
        })
        .catch(() => { controlById = new Map(); });
      const providerEvidence = fetch('./graphwalks-gemini-feasibility.json')
        .then(response => { if (!response.ok) throw Error('Missing provider feasibility receipt'); return response.json(); })
        .then(proof => {
          const counts = proof.input_token_counts_in_pinned_index_order;
          if (proof.schema_version !== 'graphwalks-gemini-source-bound-feasibility-v1' ||
              proof.model !== 'gemini-4-neon' ||
              proof.source_dataset_revision !== data.source.revision ||
              proof.source_parquet_sha256 !== data.source.parquet_sha256_verified ||
              proof.reference_index_sha256 !== data.source.reference_index_sha256 ||
              proof.original_token_plan_sha256 !== '4d6d9167c14a4dd15dc50506c848259ec2d66a8c779232ca0234d1987da97a83' ||
              proof.original_model_capabilities_sha256 !== '6825572fc93ff41c7a74ce3b19cdf01b6640d741890554765c591b59f5158069' ||
              proof.provider_input_token_limit !== 1048576 ||
              proof.provider_output_token_limit !== 65536 ||
              proof.reserved_future_output_tokens !== 8192 ||
              proof.candidate_source_task_count !== 200 ||
              proof.fits_context_with_output_allowance !== 100 ||
              proof.exceeds_provider_input_limit !== 100 ||
              proof.model_generation_performed !== false ||
              proof.published_claim_reproduced !== false ||
              !Array.isArray(counts) || counts.length !== 200 ||
              counts.some((n, i) => !Number.isSafeInteger(n) || n <= 0 ||
                (i < 100 ? n + 8192 > 1048576 : n <= 1048576))) {
            throw Error('Provider feasibility receipt does not match the pinned public source and limits');
          }
          providerById = new Map(tasks.map((task, i) =>
            [task.id, {tokens: counts[i], fits: counts[i] + 8192 <= 1048576}]));
          const current = tasks.find(task => task.id === selected);
          if (current) showTask(current);
        })
        .catch(() => {
          providerById = new Map();
          const current = tasks.find(task => task.id === selected);
          if (current) showTask(current);
        });
      return Promise.all([controlEvidence, providerEvidence]);
    })
    .catch(() => {
      ROOT.innerHTML = '<p class="loading">The explorer data could not be loaded. The source audit is still available through GitHub.</p>';
      COUNT.textContent = 'Unavailable';
    });
})();
