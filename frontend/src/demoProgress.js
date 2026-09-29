const STORAGE_KEY = "ghostline-demo-progress";

export function readDemoProgress() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
    if (!parsed || typeof parsed !== "object") {
      return {};
    }
    return parsed;
  } catch {
    return {};
  }
}

export function markDemoComplete(exerciseId) {
  const current = readDemoProgress();
  current[exerciseId] = "completed";
  localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
}

export function withDemoProgress(lesson) {
  const saved = readDemoProgress();
  return {
    ...lesson,
    exercises: lesson.exercises.map((item) => ({
      ...item,
      progress: saved[item.id] === "completed" ? { status: "completed" } : null,
    })),
  };
}
