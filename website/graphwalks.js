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
      ['SOURCE ROW INDEX', String(task.source_row_index)]
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
    })
    .catch(() => {
      ROOT.innerHTML = '<p class="loading">The explorer data could not be loaded. The source audit is still available through GitHub.</p>';
      COUNT.textContent = 'Unavailable';
    });
})();
