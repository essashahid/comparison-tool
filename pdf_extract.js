/* HTS Chapter 99 — client-side PDF → structured JSON extractor.
 *
 * Pure module. Runs entirely in the browser using PDF.js.
 * Algorithm mirrors pdf_headings.py and the extractor inside compare.js.
 *
 * Public surface (attached to window.HTSExtract):
 *
 *   await HTSExtract.extractStructuredJson(arrayBuffer, onProgress)
 *     -> { tree, items, stats }
 *
 *   onProgress({ stage, fraction, message }) is optional; callers can use it
 *   to drive a progress bar. fraction is in [0, 1].
 */
(function (global) {
  'use strict';

  const TEXT_LEVELS = [46.8, 62.6, 78.5, 94.3, 110.2, 126.0, 141.8];
  const LEVEL_TOL = 0.5;

  const round1 = (n) => Math.round(n * 10) / 10;

  const matchLevel = (x1) => {
    for (let i = 0; i < TEXT_LEVELS.length; i++) {
      if (Math.abs(x1 - TEXT_LEVELS[i]) < LEVEL_TOL) return i + 1;
    }
    return -1;
  };

  const isRomanNumeral = (s) =>
    /^(M{0,3})(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$/i.test(s) &&
    s.length > 0;

  function simpleHash(s) {
    let h = 5381;
    for (let i = 0; i < s.length; i++) {
      h = ((h << 5) + h + s.charCodeAt(i)) >>> 0;
    }
    return h.toString(16).padStart(8, '0').slice(0, 12);
  }

  const sleep = () => new Promise((r) => setTimeout(r, 0));

  function emit(onProgress, stage, fraction, message) {
    if (typeof onProgress !== 'function') return;
    try {
      onProgress({ stage, fraction, message });
    } catch (_) {
      /* progress callback errors are non-fatal */
    }
  }

  /* ---------- raw text extraction (port of update_raw_data) ---------- */

  async function extractRawData(pdfDoc, onProgress) {
    const total = pdfDoc.numPages;
    const rawData = [];
    const rawDataByPage = [];
    let lastX1 = 0;
    let lastY2 = 0;
    let cumulateY = 0;

    // Python skips page 0 (title page); PDF.js is 1-indexed.
    for (let pyI = 1; pyI < total; pyI++) {
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

      emit(onProgress, 'extract', pyI / total, `Reading page ${pyI + 1} of ${total}`);
      if (pyI % 20 === 0) await sleep();
    }

    return { rawData, rawDataByPage };
  }

  /* ---------- heading detection (port of get_text_blocks + clean_data) ---------- */

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

  /* ---------- hierarchy (port of format_data) ---------- */

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
      } catch (_) {
        /* matches Python's broad except: skip malformed rows */
      }
    }

    return result;
  }

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

  /* ---------- public entry point ---------- */

  async function extractStructuredJson(arrayBuffer, onProgress) {
    if (!global.pdfjsLib) {
      throw new Error('PDF.js is not loaded — include pdf.min.js before pdf_extract.js.');
    }

    emit(onProgress, 'open', 0.02, 'Opening PDF…');
    const pdf = await global.pdfjsLib.getDocument({ data: arrayBuffer }).promise;

    emit(onProgress, 'extract', 0.05, `Reading ${pdf.numPages} pages…`);
    const { rawData, rawDataByPage } = await extractRawData(pdf, ({ fraction, message }) => {
      emit(onProgress, 'extract', 0.05 + fraction * 0.75, message);
    });

    emit(onProgress, 'headings', 0.82, 'Detecting headings…');
    await sleep();
    const allData = buildTextBlocks(rawData, rawDataByPage);

    emit(onProgress, 'tree', 0.92, 'Building hierarchy…');
    await sleep();
    const tree = formatData(allData);

    emit(onProgress, 'flatten', 0.97, 'Flattening items…');
    await sleep();
    const items = extractItems(tree);

    const stats = {
      pages: pdf.numPages,
      subchapters: tree.length,
      headings: items.length,
    };

    emit(onProgress, 'done', 1, 'Done.');
    return { tree, items, stats };
  }

  global.HTSExtract = Object.freeze({
    TEXT_LEVELS,
    LEVEL_TOL,
    extractStructuredJson,
    extractRawData,
    buildTextBlocks,
    formatData,
    extractItems,
  });
})(typeof window !== 'undefined' ? window : globalThis);
