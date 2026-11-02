/** Pure helpers for post-pass quiz question picking and option shuffle. */

const STORAGE_KEY = "ghostline-quiz-seen";

export function shuffle(list) {
  const out = [...list];
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/** Stable id: exercise id + question text + code. */
export function quizQuestionId(exerciseId, item) {
  const q = String(item?.q || "");
  const code = String(item?.code || "");
  return `${exerciseId}|${q}|${code}`;
}

export function readSeenMap() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function markSeen(questionId, at = Date.now()) {
  try {
    const map = readSeenMap();
    map[questionId] = at;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore quota / private mode
  }
}

/**
 * Pick next quiz item. Prefer unseen; else oldest seen; never the same id as lastId.
 * pool items: { exerciseId, item }
 */
export function pickQuizQuestion(pool, { lastId = null, seen = null, now = Date.now() } = {}) {
  const list = (pool || []).filter((entry) => entry?.item?.q && entry?.exerciseId);
  if (!list.length) return null;
  const seenMap = seen || readSeenMap();
  const withIds = list.map((entry) => ({
    ...entry,
    id: quizQuestionId(entry.exerciseId, entry.item),
  }));
  const candidates = withIds.filter((entry) => entry.id !== lastId);
  const usable = candidates.length ? candidates : withIds;
  const unseen = usable.filter((entry) => seenMap[entry.id] == null);
  if (unseen.length) {
    return unseen[Math.floor(Math.random() * unseen.length)];
  }
  usable.sort((a, b) => Number(seenMap[a.id] || now) - Number(seenMap[b.id] || now));
  return usable[0] || null;
}

export function optionsForItem(item) {
  const answer = String(item?.answer ?? "");
  const wrong = (item?.wrong || []).map((value) => String(value));
  return shuffle([answer, ...wrong]);
}

export function hasQuiz(exercise) {
  return (exercise?.quiz || []).length > 0;
}
