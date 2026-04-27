/* HTS Chapter 99 — item-level diff (same rules as compare.js).
 * Compares two flattened item[] arrays from HTSExtract.extractItems(tree).
 */
(function (global) {
  'use strict';

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

  /**
   * @param {Array<{normalized_path, path, heading, text, hash}>} oldItems
   * @param {Array<...>} newItems
   * @returns {Array<{type: 'added'|'removed'|'modified', path, old_path?, old_text, new_text, similarity?}>}
   */
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
            normalized_path: norm,
            heading: newItem.heading,
          });
        }
      }
    }

    for (const it of newItems) {
      if (!matchedNew.has(it)) {
        results.push({
          type: 'added',
          path: it.path,
          old_text: null,
          new_text: it.text,
          normalized_path: it.normalized_path,
          heading: it.heading,
        });
      }
    }
    for (const it of oldItems) {
      if (!matchedOld.has(it)) {
        results.push({
          type: 'removed',
          path: it.path,
          old_text: it.text,
          new_text: null,
          normalized_path: it.normalized_path,
          heading: it.heading,
        });
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

  global.HTSCompare = Object.freeze({
    textSimilarity,
    compareData,
  });
})(typeof window !== 'undefined' ? window : globalThis);
