/** Fading ghost text for repeated traces: full → 60% tokens → first letters → none. */

function tokensWithSpans(text) {
  const parts = [];
  const re = /(\S+|\s+)/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    parts.push(match[0]);
  }
  return parts;
}

/**
 * @param {string} text
 * @param {0|1|2|3} stage
 */
export function fadeGhost(text, stage) {
  if (!text || stage >= 3) {
    return "";
  }
  if (stage <= 0) {
    return text;
  }
  const parts = tokensWithSpans(text);
  if (stage === 1) {
    let wordIndex = 0;
    return parts
      .map((part) => {
        if (/^\s+$/.test(part)) {
          return part;
        }
        const keep = wordIndex % 5 < 3; // ~60% of tokens
        wordIndex += 1;
        return keep ? part : " ".repeat(part.length);
      })
      .join("");
  }
  // stage 2: first letter of each token
  return parts
    .map((part) => {
      if (/^\s+$/.test(part)) {
        return part;
      }
      if (part.length <= 1) {
        return part;
      }
      return part[0] + " ".repeat(part.length - 1);
    })
    .join("");
}

/**
 * @param {number} stage
 * @param {number} missRatio 0–1 share of wrong characters
 */
export function nextFadeStage(stage, missRatio) {
  if (missRatio > 0.2) {
    return 0;
  }
  return Math.min(3, Math.max(0, Number(stage) || 0) + 1);
}

export function loadFadeStage(exerciseId) {
  try {
    const raw = sessionStorage.getItem(`ghostline-fade:${exerciseId}`);
    const n = Number(raw);
    return Number.isFinite(n) ? Math.min(3, Math.max(0, n)) : 0;
  } catch {
    return 0;
  }
}

export function saveFadeStage(exerciseId, stage) {
  try {
    sessionStorage.setItem(`ghostline-fade:${exerciseId}`, String(stage));
  } catch {
    /* ignore */
  }
}
