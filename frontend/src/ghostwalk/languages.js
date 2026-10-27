/** Ghostwalk language skins — transpile learner code into JS hero API calls. */

export const GHOSTWALK_LANGUAGES = [
  { id: "python", label: "Python", runtime: "ghostwalk" },
  { id: "javascript", label: "JavaScript", runtime: "ghostwalk_js" },
  { id: "bash", label: "Bash", runtime: "ghostwalk_js" },
  { id: "go", label: "Go", runtime: "ghostwalk_js" },
  { id: "sql", label: "SQL", runtime: "ghostwalk_js" },
  { id: "csharp", label: "C#", runtime: "ghostwalk_js" },
  { id: "java", label: "Java", runtime: "ghostwalk_js" },
];

const SNAKES = [
  "turn_left",
  "turn_right",
  "pick_up",
  "at_goal",
  "is_blocked",
  "on_gem",
  "on_soil",
  "crops_held",
  "read_sign",
  "harvest",
  "plant",
  "water",
  "move",
];

function toPascal(snake) {
  return snake
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

function stripLineComments(code, patterns) {
  return code
    .split("\n")
    .map((line) => {
      let out = line;
      for (const pattern of patterns) {
        out = out.replace(pattern, "");
      }
      return out;
    })
    .join("\n");
}

function mapPascalHeroCalls(text) {
  let out = text;
  for (const snake of SNAKES) {
    const pascal = toPascal(snake);
    out = out.replace(new RegExp(`hero\\.${pascal}\\s*\\(\\s*\\)`, "g"), `hero.${snake}()`);
  }
  return out;
}

/** Convert language-flavored hero calls into JavaScript hero.method() form. */
export function transpileGhostwalk(language, code) {
  const lang = String(language || "javascript").toLowerCase();
  if (lang === "python") {
    return { runtime: "ghostwalk", code };
  }
  if (lang === "javascript") {
    return { runtime: "ghostwalk_js", code };
  }

  let text = String(code || "");

  if (lang === "bash") {
    text = stripLineComments(text, [/#(?!\!).*$/]);
    text = text.replace(/\bhero_([a-z_]+)\s*\(\s*\)/gi, (_, name) => `hero.${String(name).toLowerCase()}()`);
    text = text.replace(/\bfor\s+_\s+in\s+\$\(seq\s+(\d+)\)\s*;\s*do/gi, "for (let _ = 0; _ < $1; _++) {");
    text = text.replace(/\bdone\b/g, "}");
    text = text.replace(/\bwhile\s+!\s+hero_at_goal\s*\(\s*\)\s*;\s*do/gi, "while (!hero.at_goal()) {");
  } else if (lang === "go") {
    text = stripLineComments(text, [/\/\/.*$/]);
    text = mapPascalHeroCalls(text);
    text = text.replace(
      /\bfor\s+(\w+)\s*:=\s*0;\s*\1\s*<\s*(\d+);\s*\1\+\+\s*\{/g,
      "for (let $1 = 0; $1 < $2; $1++) {",
    );
    text = text.replace(/\bif\s+hero\.is_blocked\s*\(\s*\)\s*\{/g, "if (hero.is_blocked()) {");
    text = text.replace(/\bif\s+hero\.on_gem\s*\(\s*\)\s*\{/g, "if (hero.on_gem()) {");
    text = text.replace(/\belse\s*\{/g, "else {");
    text = text.replace(/\bwhile\s+!\s*hero\.at_goal\s*\(\s*\)\s*\{/g, "while (!hero.at_goal()) {");
  } else if (lang === "java" || lang === "csharp") {
    text = stripLineComments(text, [/\/\/.*$/]);
    text = mapPascalHeroCalls(text);
    text = text.replace(/\bfor\s*\(\s*int\s+(\w+)\s*=\s*0;\s*\1\s*<\s*(\d+);\s*\1\+\+\s*\)/g, "for (let $1 = 0; $1 < $2; $1++)");
    text = text.replace(/\bwhile\s*\(\s*!\s*hero\.at_goal\s*\(\s*\)\s*\)/g, "while (!hero.at_goal())");
  } else if (lang === "sql") {
    text = stripLineComments(text, [/--.*$/]);
    text = text.replace(/\b(?:CALL|SELECT)\s+([a-z_]+)\s*\(\s*\)\s*;?/gi, (_, name) => {
      return `hero.${String(name).toLowerCase()}();`;
    });
  }

  text = text.replace(/while\s+not\s+hero\.at_goal\s*\(\s*\)/gi, "while (!hero.at_goal())");

  return { runtime: "ghostwalk_js", code: text };
}

export function languageLabel(id) {
  return GHOSTWALK_LANGUAGES.find((item) => item.id === id)?.label || id;
}
