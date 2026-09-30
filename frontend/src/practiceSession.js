const STORAGE_KEY = "ghostline-practice-session";

function emptySession(lessonId) {
  return {
    lessonId: String(lessonId),
    index: 0,
    exercises: {},
    updatedAt: Date.now(),
  };
}

export function readPracticeSession() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (!parsed || typeof parsed !== "object" || !parsed.lessonId) {
      return null;
    }
    return {
      lessonId: String(parsed.lessonId),
      index: Math.max(0, Number(parsed.index) || 0),
      exercises:
        parsed.exercises && typeof parsed.exercises === "object" ? parsed.exercises : {},
      updatedAt: Number(parsed.updatedAt) || 0,
    };
  } catch {
    return null;
  }
}

export function writePracticeSession(session) {
  if (!session?.lessonId) {
    return;
  }
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      ...session,
      updatedAt: Date.now(),
    }),
  );
}

export function clearPracticeSession() {
  localStorage.removeItem(STORAGE_KEY);
}

export function sessionForLesson(lessonId) {
  const session = readPracticeSession();
  if (!session || session.lessonId !== String(lessonId)) {
    return null;
  }
  return session;
}

export function exerciseHasWork(state) {
  if (!state || typeof state !== "object") {
    return false;
  }
  if (String(state.draft || "").length > 0) {
    return true;
  }
  if (state.blanks && Object.values(state.blanks).some((value) => String(value || "").length > 0)) {
    return true;
  }
  if (Number(state.hintsShown) > 0) {
    return true;
  }
  if (state.result?.passed) {
    return true;
  }
  return false;
}

export function sessionHasWork(session, fallbackIndex = 0) {
  if (!session) {
    return false;
  }
  if (session.index !== fallbackIndex) {
    return true;
  }
  return Object.values(session.exercises || {}).some(exerciseHasWork);
}

export function readExerciseState(lessonId, exerciseId) {
  const session = sessionForLesson(lessonId);
  if (!session) {
    return null;
  }
  const state = session.exercises?.[String(exerciseId)];
  return state && typeof state === "object" ? state : null;
}

export function upsertExerciseState(lessonId, index, exerciseId, patch) {
  const current = sessionForLesson(lessonId) || emptySession(lessonId);
  const key = String(exerciseId);
  const previous = current.exercises[key] || {};
  current.index = index;
  current.exercises[key] = {
    ...previous,
    ...patch,
  };
  writePracticeSession(current);
  return current;
}

export function setSessionIndex(lessonId, index) {
  const current = sessionForLesson(lessonId) || emptySession(lessonId);
  current.index = index;
  writePracticeSession(current);
  return current;
}
