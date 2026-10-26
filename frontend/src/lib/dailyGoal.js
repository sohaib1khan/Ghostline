/** Device-local tally of today's reviews and new lessons, shown against the daily goal on Home. */

const KEY = "ghostline-daily-goal";

function today() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

export function readDailyCounts() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || "{}");
    if (parsed?.date === today()) {
      return { reviews: Number(parsed.reviews) || 0, lessons: Number(parsed.lessons) || 0 };
    }
  } catch {
    /* ignore */
  }
  return { reviews: 0, lessons: 0 };
}

export function bumpDaily(kind) {
  const counts = readDailyCounts();
  const next = { ...counts, [kind]: (counts[kind] || 0) + 1, date: today() };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}
