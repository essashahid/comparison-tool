/* HTS Chapter 99 PDF Comparison - client-side pipeline.
   Ports pdf_headings.py + generate_meeting_report.py to the browser. */

const TEXT_LEVELS = [46.8, 62.6, 78.5, 94.3, 110.2, 126.0, 141.8];
const LEVEL_TOL = 0.5;

const $ = (id) => document.getElementById(id);

const state = {
  fileOld: null,
  fileNew: null,
  results: null,
  oldCount: 0,
  newCount: 0,
  oldLabel: 'Old',
  newLabel: 'New',
};

/* ---------- helpers ---------- */

const round1 = (n) => Math.round(n * 10) / 10;

const matchLevel = (x1) => {
  for (let i = 0; i < TEXT_LEVELS.length; i++) {
    if (Math.abs(x1 - TEXT_LEVELS[i]) < LEVEL_TOL) return i + 1;
  }
  return -1;
};

const isRomanNumeral = (s) =>
  /^(M{0,3})(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/i.test(s) && s.length > 0;

function simpleHash(s) {
  let h = 5381;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
  }
  return h.toString(16).padStart(8, '0').slice(0, 12);
}

const sleep = () => new Promise((r) => setTimeout(r, 0));

function guessLabel(file) {
  const m = file.name.match(/Rev(\d+)/i);
  return m ? `Rev${m[1]}` : file.name.replace(/\.pdf$/i, '');
}

function setProgress(pct, msg) {
  const bar = $('progressBar');
  const txt = $('progressText');
  bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
  if (msg !== undefined) txt.textContent = msg;
}

/* ---------- PDF extraction (port of pdf_headings.py::update_raw_data) ---------- */

async function extractRawData(pdfDoc, onProgress) {
  const total = pdfDoc.numPages;
  const rawData = [];
  const rawDataByPage = [];
  let lastX1 = 0;
  let lastY2 = 0;
  let cumulateY = 0;

  // Python skips page 0 (title page). PDF.js is 1-indexed.
  for (let pyI = 1; pyI < total; pyI++) {
    onProgress(pyI, total);

    const page = await pdfDoc.getPage(pyI + 1);
    const viewport = page.getViewport({ scale: 1.0 });
    const content = await page.getTextContent();
    const pageH = viewport.height;

    const pageData = [];

    for (const item of content.items) {
      const text = (item.str || '').trim();
      if (!item.str) continue;

      const tx = item.transform[4];
      const ty = item.transform[5];
      const h = item.height || 0;
      const w = item.width || 0;

      const x1 = round1(tx);
      const y1 = round1(pageH - ty - h);
      const x2 = round1(tx + w);
      const y2 = round1(pageH - ty);

      if (y1 > 70) {
        if (
          rawData.length > 0 &&
          Math.abs(lastX1 - x1) < 2 &&
          Math.abs(y1 - lastY2) < 2
        ) {
          const last = rawData[rawData.length - 1];
          last.text += ' ' + text;
          last.y2 = y2 + cumulateY;
        } else {
          const rec = {
            x1,
            y1: y1 + cumulateY,
            x2,
            y2: y2 + cumulateY,
            text,
            value: '',
            level: -1,
            page: pyI + 1,
          };
          rawData.push(rec);
          pageData.push(rec);
        }
        lastX1 = x1;
        lastY2 = y2;
      }
    }

    rawDataByPage.push(pageData);
    cumulateY += pageH;

    if (pyI % 20 === 0) await sleep();
  }

  return { rawData, rawDataByPage };
}

/* ---------- headings identification (port of get_text_blocks + clean_data) ---------- */

function getHeadingText(h, rawDataByPage) {
  let ret = '';
  const hx2 = h.x2;
  const hy1 = h.y1;
  const hy2 = h.y2;
  const hpage = h.page;
  const n = hpage - 2;
  const m = rawDataByPage.length;

  const start = Math.max(0, n);
  const end = n + Math.min(10, m - n);
  let found = false;

  for (let i = start; i < end && i < m; i++) {
    const dataPage = rawDataByPage[i]
      .slice()
      .sort((a, b) => a.y1 - b.y1 || a.x1 - b.x1);

    for (const d of dataPage) {
      const { x1: dx1, y1: dy1, y2: dy2, page: dpage, text } = d;
      const m2 = /^(\d+\.($|\s*\()|\([^.]{1,5}\))/.test(text);

      let isFirst = true;

      if (dy1 > 10) {
        const vOverlap = (dy1 <= hy1 && hy1 <= dy2) || (dy1 <= hy2 && hy2 <= dy2);
        const isRight = d.x1 > hx2;
        if (vOverlap && isRight && hpage === dpage) {
          ret += text;
          isFirst = false;
        }
      }

      const isLevelX = TEXT_LEVELS.some((lvl) => Math.abs(dx1 - lvl) < LEVEL_TOL);
      if (isLevelX && m2 && dy1 > hy2 + 10) {
        found = true;
        break;
      }

      if (dy2 > hy1 && isFirst && ret !== '') {
        ret += '\n' + text;
      }
    }

    if (found) break;
  }

  return ret;
}

function buildTextBlocks(rawData, rawDataByPage) {
  const allData = [];
  const pageHeadingRe = /^(\d+\.($|\s*\()|\([^.]{1,5}\))/;
  const subchapterRe = /^(?:.?SUBCHAPTER (.*?) deleted.?|SUBCHAPTER\s*(.*))$/;

  for (const d of rawData) {
    const text = d.text.trim();
    const l = text.length;
    const x1 = round1(d.x1);
    const i = d.page;

    if (
      pageHeadingRe.test(text) &&
      l < 10 &&
      x1 < 200 &&
      !text.includes(':') &&
      !text.includes('(con.)')
    ) {
      let level = matchLevel(x1);
      if (i === 758) level -= 1;
      else if (i === 760) level -= 2;

      allData.push({
        x1,
        y1: d.y1,
        x2: d.x2,
        y2: d.y2,
        text: `${text}/page:${i}`,
        value: getHeadingText(d, rawDataByPage),
        level,
        page: i,
      });
      continue;
    }

    const sm = text.match(subchapterRe);
    if (sm) {
      const result = sm[1] || sm[2];
      allData.push({
        x1,
        y1: d.y1,
        x2: d.x2,
        y2: d.y2,
        text: result,
        value: '',
        level: 0,
        page: i,
      });
    }
  }

  return cleanData(allData);
}

function cleanData(allData) {
  const ret = [];
  for (const d of allData) {
    const text = d.text;
    const m1 = text.match(/(\(.*?\))\s*(\(.*?\))/);
    const m2 = text.match(/(\d+\.)\s(\(.*?\))/);

    if (m1) {
      const tmp1 = { ...d, text: m1[1], value: '' };
      const tmp2 = { ...d, text: m1[2], level: d.level + 1 };
      const idx = TEXT_LEVELS.findIndex((l) => Math.abs(l - tmp2.x1) < LEVEL_TOL);
      if (idx >= 0 && idx + 1 < TEXT_LEVELS.length) tmp2.x1 = TEXT_LEVELS[idx + 1];
      ret.push(tmp1, tmp2);
    } else if (m2) {
      const tmp1 = { ...d, text: m2[1], value: '' };
      const tmp2 = { ...d, text: m2[2], level: d.level + 1 };
      const idx = TEXT_LEVELS.findIndex((l) => Math.abs(l - tmp2.x1) < LEVEL_TOL);
      if (idx >= 0 && idx + 1 < TEXT_LEVELS.length) tmp2.x1 = TEXT_LEVELS[idx + 1];
      ret.push(tmp1, tmp2);
    } else {
      ret.push(d);
    }
  }
  return ret;
}

/* ---------- hierarchical tree (port of format_data) ---------- */

function insertAtLevel(result, template, level) {
  if (result.length === 0) return false;
  let parent = result[result.length - 1];
  for (let i = 0; i < level - 1; i++) {
    if (!parent.data || parent.data.length === 0) return false;
    parent = parent.data[parent.data.length - 1];
  }
  if (!parent.data) parent.data = [];
  parent.data.push(template);
  return true;
}

function formatData(allData) {
  const result = [];
  let lastLevel = -1;
  let subchapter = '';

  for (const data of allData) {
    const template = { heading: data.text, 'heading text': data.value, data: [] };

    try {
      if (data.level === 0 && isRomanNumeral(data.text)) {
        result.push({ SUBCHAPTER: data.text, data: [] });
        subchapter = data.text.trim();
        lastLevel = 0;
        continue;
      }

      if (!['XX', 'XXI', 'XXII'].includes(subchapter)) {
        let inserted = false;
        if (data.level >= 1 && data.level <= 7 && lastLevel >= data.level - 1) {
          inserted = insertAtLevel(result, template, data.level);
          if (inserted) lastLevel = data.level;
        } else if (data.level === 4 && lastLevel === 2) {
          inserted = insertAtLevel(result, template, 3);
          if (inserted) lastLevel = 3;
        } else if (data.level === 5 && lastLevel === 3) {
          inserted = insertAtLevel(result, template, 4);
          if (inserted) lastLevel = 4;
        }
      } else if (subchapter === 'XX') {
        if (Math.abs(data.x1 - TEXT_LEVELS[0]) < LEVEL_TOL) {
          result[result.length - 1].data.push({ ...template });
          lastLevel = 1;
        }
      } else if (subchapter === 'XXI') {
        if (Math.abs(data.x1 - TEXT_LEVELS[1]) < LEVEL_TOL) {
          result[result.length - 1].data.push({ ...template });
          lastLevel = 1;
        }
      } else if (subchapter === 'XXII') {
        if (Math.abs(data.x1 - TEXT_LEVELS[2]) < LEVEL_TOL) {
          result[result.length - 1].data.push({ ...template });
          lastLevel = 1;
        } else if (Math.abs(data.x1 - TEXT_LEVELS[3]) < LEVEL_TOL) {
          const last = result[result.length - 1];
          last.data[last.data.length - 1].data.push({ ...template });
          lastLevel = 2;
        }
      }
    } catch (e) {
      // swallow and continue (matches Python's except block)
    }
  }

  return result;
}

/* ---------- item extraction & comparison (port of generate_meeting_report.py) ---------- */

function extractItems(data, path = '', items = []) {
  if (Array.isArray(data)) {
    for (const item of data) extractItems(item, path, items);
  } else if (data && typeof data === 'object') {
    const subchapter = data.SUBCHAPTER || '';
    const heading = data.heading || '';
    const headingText = data['heading text'] || '';

    let currentPath = path;
    if (subchapter) currentPath = `SUBCHAPTER_${subchapter}`;
    if (heading) currentPath = currentPath ? `${currentPath}/${heading}` : heading;

    if (headingText) {
      items.push({
        path: currentPath,
        normalized_path: currentPath.replace(/\/page:\d+/g, ''),
        heading,
        text: headingText,
        hash: simpleHash(headingText),
      });
    }

    if (data.data) extractItems(data.data, currentPath, items);
  }
  return items;
}

function textSimilarity(a, b) {
  if (!a || !b) return 0;
  const w1 = new Set(a.toLowerCase().split(/\s+/).filter(Boolean));
  const w2 = new Set(b.toLowerCase().split(/\s+/).filter(Boolean));
  if (!w1.size || !w2.size) return 0;
  let inter = 0;
  for (const w of w1) if (w2.has(w)) inter++;
  const union = w1.size + w2.size - inter;
  return union > 0 ? inter / union : 0;
}

function compareData(oldItems, newItems) {
  const oldByNorm = new Map();
  for (const it of oldItems) {
    if (!oldByNorm.has(it.normalized_path)) oldByNorm.set(it.normalized_path, []);
    oldByNorm.get(it.normalized_path).push(it);
  }
  const newByNorm = new Map();
  for (const it of newItems) {
    if (!newByNorm.has(it.normalized_path)) newByNorm.set(it.normalized_path, []);
    newByNorm.get(it.normalized_path).push(it);
  }

  const results = [];
  const matchedOld = new Set();
  const matchedNew = new Set();

  for (const [norm, newList] of newByNorm) {
    const oldList = oldByNorm.get(norm) || [];
    for (const newItem of newList) {
      let bestMatch = null;
      let bestScore = 0;
      let exact = false;

      for (const oldItem of oldList) {
        if (matchedOld.has(oldItem)) continue;

        if (newItem.hash === oldItem.hash) {
          matchedOld.add(oldItem);
          matchedNew.add(newItem);
          exact = true;
          break;
        } else {
          const sim = textSimilarity(oldItem.text, newItem.text);
          if (sim > bestScore && sim > 0.5) {
            bestScore = sim;
            bestMatch = oldItem;
          }
        }
      }

      if (!exact && bestMatch && !matchedOld.has(bestMatch)) {
        matchedOld.add(bestMatch);
        matchedNew.add(newItem);
        results.push({
          type: 'modified',
          path: newItem.path,
          old_path: bestMatch.path,
          old_text: bestMatch.text,
          new_text: newItem.text,
          similarity: bestScore,
        });
      }
    }
  }

  for (const it of newItems) {
    if (!matchedNew.has(it)) {
      results.push({ type: 'added', path: it.path, old_text: null, new_text: it.text });
    }
  }
  for (const it of oldItems) {
    if (!matchedOld.has(it)) {
      results.push({ type: 'removed', path: it.path, old_text: it.text, new_text: null });
    }
  }

  const order = { added: 0, removed: 1, modified: 2 };
  results.sort(
    (a, b) =>
      (order[a.type] ?? 3) - (order[b.type] ?? 3) ||
      a.path.localeCompare(b.path),
  );

  return results;
}

/* ---------- processing pipeline ---------- */

async function processFile(file, label, progStart, progEnd) {
  const span = progEnd - progStart;
  setProgress(progStart, `[${label}] reading file…`);
  const buf = await file.arrayBuffer();

  setProgress(progStart + span * 0.05, `[${label}] opening PDF…`);
  const pdf = await pdfjsLib.getDocument({ data: buf }).promise;

  const { rawData, rawDataByPage } = await extractRawData(pdf, (i, total) => {
    const frac = i / total;
    setProgress(progStart + span * (0.05 + frac * 0.7), `[${label}] page ${i + 1}/${total}`);
  });

  setProgress(progStart + span * 0.8, `[${label}] building headings…`);
  await sleep();
  const allData = buildTextBlocks(rawData, rawDataByPage);

  setProgress(progStart + span * 0.9, `[${label}] building hierarchy…`);
  await sleep();
  const tree = formatData(allData);

  setProgress(progStart + span * 0.95, `[${label}] flattening items…`);
  await sleep();
  const items = extractItems(tree);

  return { tree, items };
}

async function runComparison() {
  if (!state.fileOld || !state.fileNew) {
    alert('Please select two PDF files first.');
    return;
  }

  $('runBtn').disabled = true;
  $('progressPanel').hidden = false;
  $('resultsPanel').hidden = true;

  try {
    const oldRes = await processFile(state.fileOld, state.oldLabel, 0, 45);
    const newRes = await processFile(state.fileNew, state.newLabel, 45, 90);

    setProgress(92, 'Comparing…');
    await sleep();
    const results = compareData(oldRes.items, newRes.items);

    state.results = results;
    state.oldCount = oldRes.items.length;
    state.newCount = newRes.items.length;

    setProgress(100, 'Done.');
    setTimeout(() => {
      $('progressPanel').hidden = true;
    }, 600);

    renderResults();
  } catch (err) {
    console.error(err);
    setProgress(0, 'Error: ' + (err.message || err));
    alert('Something went wrong while processing:\n' + (err.message || err));
  } finally {
    $('runBtn').disabled = false;
  }
}

/* ---------- rendering ---------- */

const esc = (s) =>
  (s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

function truncate(s, n = 1500) {
  if (!s) return '';
  return s.length > n
    ? esc(s.slice(0, n)) + '<span class="dim">… [truncated]</span>'
    : esc(s);
}

function renderResults() {
  const { results, oldCount, newCount, oldLabel, newLabel } = state;

  const stats = {
    added: results.filter((r) => r.type === 'added').length,
    removed: results.filter((r) => r.type === 'removed').length,
    modified: results.filter((r) => r.type === 'modified').length,
    total: results.length,
  };

  $('statTotal').textContent = stats.total.toLocaleString();
  $('statAdded').textContent = stats.added.toLocaleString();
  $('statRemoved').textContent = stats.removed.toLocaleString();
  $('statModified').textContent = stats.modified.toLocaleString();
  $('statOldCount').textContent = oldCount.toLocaleString();
  $('statNewCount').textContent = newCount.toLocaleString();
  $('statOldLabel').textContent = `Items in ${oldLabel}`;
  $('statNewLabel').textContent = `Items in ${newLabel}`;
  $('reportSubtitle').textContent = `${oldLabel} → ${newLabel}`;

  const filterCounts = {
    all: stats.total,
    added: stats.added,
    removed: stats.removed,
    modified: stats.modified,
  };
  for (const key of Object.keys(filterCounts)) {
    const el = document.querySelector(`.filter-btn[data-filter="${key}"] .count`);
    if (el) el.textContent = filterCounts[key];
  }

  const container = $('diffContainer');
  const chunks = [];
  for (const item of results) {
    const oldText = truncate(item.old_text);
    const newText = truncate(item.new_text);

    let pathDisplay = esc(item.path);
    if (item.type === 'modified' && item.old_path && item.old_path !== item.path) {
      pathDisplay = `<span class="path-old">${esc(item.old_path)}</span> → ${esc(item.path)}`;
    }

    const simBadge =
      item.type === 'modified' && typeof item.similarity === 'number'
        ? `<span class="similarity-badge">${Math.round(item.similarity * 100)}% similar</span>`
        : '';

    chunks.push(`
      <div class="diff-card ${item.type}" data-type="${item.type}">
        <div class="diff-header" onclick="this.parentElement.classList.toggle('expanded')">
          <span class="diff-path">${pathDisplay}</span>
          ${simBadge}
          <span class="diff-badge ${item.type}">${item.type.toUpperCase()}</span>
          <span class="chevron">▼</span>
        </div>
        <div class="diff-body">
          <div class="diff-grid">
            <div class="diff-panel old">
              <div class="panel-header">${esc(oldLabel)} (Previous)</div>
              <div class="panel-content">${oldText || `<em class="dim">Not present in ${esc(oldLabel)}</em>`}</div>
            </div>
            <div class="diff-panel new">
              <div class="panel-header">${esc(newLabel)} (New)</div>
              <div class="panel-content">${newText || `<em class="dim">Not present in ${esc(newLabel)}</em>`}</div>
            </div>
          </div>
        </div>
      </div>
    `);
  }

  container.innerHTML = chunks.join('') || '<div class="empty-state">No changes found.</div>';
  $('resultsPanel').hidden = false;
  applyFilters();
  window.scrollTo({ top: $('resultsPanel').offsetTop - 20, behavior: 'smooth' });
}

function applyFilters() {
  const activeBtn = document.querySelector('.filter-btn.active');
  const filter = activeBtn ? activeBtn.dataset.filter : 'all';
  const term = $('searchBox').value.toLowerCase();
  const cards = document.querySelectorAll('#diffContainer .diff-card');

  cards.forEach((card) => {
    const type = card.dataset.type;
    const matchesFilter = filter === 'all' || type === filter;
    const matchesSearch = !term || card.textContent.toLowerCase().includes(term);
    card.style.display = matchesFilter && matchesSearch ? 'block' : 'none';
  });
}

function setFilter(filter) {
  document.querySelectorAll('.filter-btn').forEach((b) => {
    b.classList.toggle('active', b.dataset.filter === filter);
  });
  applyFilters();
}

let allExpanded = false;
function toggleExpandAll() {
  allExpanded = !allExpanded;
  document.querySelectorAll('#diffContainer .diff-card').forEach((card) => {
    if (card.style.display !== 'none') card.classList.toggle('expanded', allExpanded);
  });
  $('expandBtn').textContent = allExpanded ? 'Collapse All' : 'Expand All';
}

function exportHtml() {
  if (!state.results) return;
  const report = $('resultsPanel').cloneNode(true);
  report.hidden = false;
  report.querySelectorAll('.report-toolbar, .no-print').forEach((n) => n.remove());

  const styles = Array.from(document.styleSheets)
    .map((s) => {
      try {
        return Array.from(s.cssRules).map((r) => r.cssText).join('\n');
      } catch {
        return '';
      }
    })
    .join('\n');

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>HTS Comparison: ${esc(state.oldLabel)} → ${esc(state.newLabel)}</title>
<style>${styles}</style></head><body>${report.outerHTML}
<script>
document.querySelectorAll('.diff-header').forEach(h => {
  h.addEventListener('click', () => h.parentElement.classList.toggle('expanded'));
});
</script>
</body></html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `hts_compare_${state.oldLabel}_vs_${state.newLabel}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

/* ---------- file wiring ---------- */

function attachDropZone(zoneId, inputId, slot /* 'old' | 'new' */) {
  const zone = $(zoneId);
  const input = $(inputId);

  const handle = (file) => {
    if (!file || !/\.pdf$/i.test(file.name)) {
      alert('Please select a PDF file.');
      return;
    }
    if (slot === 'old') {
      state.fileOld = file;
      state.oldLabel = guessLabel(file);
    } else {
      state.fileNew = file;
      state.newLabel = guessLabel(file);
    }
    zone.querySelector('.drop-filename').textContent = file.name;
    zone.querySelector('.drop-filesize').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;
    zone.classList.add('filled');
    updateRunState();
  };

  zone.addEventListener('click', () => input.click());
  input.addEventListener('change', (e) => handle(e.target.files[0]));
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragging');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragging');
    handle(e.dataTransfer.files[0]);
  });
}

function updateRunState() {
  $('runBtn').disabled = !(state.fileOld && state.fileNew);
}

/* ---------- init ---------- */

window.addEventListener('DOMContentLoaded', () => {
  if (typeof pdfjsLib === 'undefined') {
    alert('PDF.js failed to load. Check your internet connection and refresh.');
    return;
  }
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';

  attachDropZone('dropOld', 'fileOld', 'old');
  attachDropZone('dropNew', 'fileNew', 'new');

  $('runBtn').addEventListener('click', runComparison);
  $('searchBox').addEventListener('input', applyFilters);
  $('expandBtn').addEventListener('click', toggleExpandAll);
  $('exportBtn').addEventListener('click', exportHtml);
  document.querySelectorAll('.filter-btn').forEach((b) => {
    b.addEventListener('click', () => setFilter(b.dataset.filter));
  });
});
