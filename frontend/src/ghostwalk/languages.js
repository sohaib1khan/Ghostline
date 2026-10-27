/** Ghostwalk language list — non-JS languages run through skins.py in Pyodide. */

export const GHOSTWALK_LANGUAGES = [
  { id: "python", label: "Python", runtime: "ghostwalk" },
  { id: "javascript", label: "JavaScript", runtime: "ghostwalk_js" },
  { id: "bash", label: "Bash", runtime: "ghostwalk" },
  { id: "go", label: "Go", runtime: "ghostwalk" },
  { id: "sql", label: "SQL", runtime: "ghostwalk" },
  { id: "csharp", label: "C#", runtime: "ghostwalk" },
  { id: "java", label: "Java", runtime: "ghostwalk" },
];

export function languageLabel(id) {
  return GHOSTWALK_LANGUAGES.find((item) => item.id === id)?.label || id;
}

export function ghostwalkRuntime(language) {
  const lang = String(language || "python").toLowerCase();
  return lang === "javascript" ? "ghostwalk_js" : "ghostwalk";
}
