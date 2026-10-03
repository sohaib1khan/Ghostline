"""How-to guides, language examples, and progressive hints for practice games."""

from __future__ import annotations

import re

TRACKS = ("bash", "python", "go", "javascript", "sql", "csharp", "java")

TRACK_NAMES = {
    "bash": "Bash",
    "python": "Python",
    "go": "Go",
    "javascript": "JavaScript",
    "sql": "SQL",
    "csharp": "C#",
    "java": "Java",
}

# Short worked examples per game × language so learners always see a pattern.
EXAMPLES: dict[str, dict[str, dict[str, str]]] = {
    "speed_drill": {
        "bash": {"sample": "ls -la", "note": "Type the faded line exactly."},
        "python": {"sample": "print('hi')", "note": "Match spacing and quotes."},
        "go": {"sample": "fmt.Println(\"hi\")", "note": "Include the package prefix."},
        "javascript": {"sample": "console.log('hi')", "note": "Watch the quotes."},
        "sql": {"sample": "SELECT title FROM books;", "note": "Keywords can be upper or lower."},
        "csharp": {"sample": "Console.WriteLine(\"hi\");", "note": "Include the semicolon."},
        "java": {"sample": "System.out.println(\"hi\");", "note": "Match the package path and semicolon."},
    },
    "ghost_race": {
        "bash": {"sample": "cat notes.txt", "note": "Beat your own best WPM on this snippet."},
        "python": {"sample": "nums.append(3)", "note": "Same snippet — race your ghost."},
        "go": {"sample": "defer f.Close()", "note": "Accuracy still counts."},
        "javascript": {"sample": "const n = 1", "note": "Steady rhythm beats frantic typos."},
        "sql": {"sample": "SELECT * FROM books", "note": "Type cleanly; the ghost is just a pace marker."},
        "csharp": {"sample": "var n = 1;", "note": "Same snippet — race your ghost."},
        "java": {"sample": "int n = 1;", "note": "Accuracy still counts."},
    },
    "bug_hunt": {
        "bash": {
            "sample": "Broken: ls -l  →  Fix: ls -la",
            "note": "Find the missing piece; do not copy the red line.",
        },
        "python": {
            "sample": "Broken: if x == 1  →  Fix: if x == 1:",
            "note": "Often a colon, operator, or range bound.",
        },
        "go": {
            "sample": "Broken: defer f.Close  →  Fix: defer f.Close()",
            "note": "Look for a missing call or keyword tweak.",
        },
        "javascript": {
            "sample": "Broken: const n = 1  vs  let n = 1",
            "note": "One keyword or operator was mutated.",
        },
        "sql": {
            "sample": "Broken: HAVING year = 1965  →  Fix: WHERE year = 1965",
            "note": "Clause names get swapped sometimes.",
        },
        "csharp": {
            "sample": "Broken: Console.WriteLine(\"hi\")  →  Fix: Console.WriteLine(\"hi\");",
            "note": "Often a missing semicolon or brace.",
        },
        "java": {
            "sample": "Broken: System.out.println(\"hi\")  →  Fix: System.out.println(\"hi\");",
            "note": "Look for a missing semicolon or parenthesis.",
        },
    },
    "fill_frenzy": {
        "bash": {"sample": "___ -la  →  ls -la", "note": "Only fill the blank(s)."},
        "python": {"sample": "nums._____ (3)  →  append", "note": "Think of the method name."},
        "go": {"sample": "_____ f.Close()  →  defer", "note": "One keyword completes the line."},
        "javascript": {"sample": "_____ x = 1  →  const", "note": "Declaration keyword in the gap."},
        "sql": {"sample": "SELECT title _____ books  →  FROM", "note": "Clause word in the blank."},
        "csharp": {"sample": "_____.WriteLine(\"hi\");  →  Console", "note": "Type that writes to the console."},
        "java": {"sample": "System.____.println(\"hi\");  →  out", "note": "The print stream name."},
    },
    "command_roulette": {
        "bash": {"sample": "Prompt: list hidden files → ls -la", "note": "Study the example, then answer from memory."},
        "python": {"sample": "Prompt: add to a list → nums.append(3)", "note": "Use the worked example first if shown."},
        "go": {"sample": "Prompt: run cleanup later → defer …", "note": "Timer is soft — hints still help."},
        "javascript": {"sample": "Prompt: declare a constant → const …", "note": "Short answers are fine."},
        "sql": {"sample": "Prompt: filter rows → … WHERE …", "note": "Name the clause or full query."},
        "csharp": {"sample": "Prompt: print a line → Console.WriteLine(…);", "note": "Short answers are fine."},
        "java": {"sample": "Prompt: print a line → System.out.println(…);", "note": "Timer is soft — hints still help."},
    },
    "code_hangman": {
        "bash": {
            "sample": "Clue: long listing with hidden names → chmod is wrong; think ls flags like -la",
            "note": "Guess letters. Wrong letters fade the ghost.",
        },
        "python": {
            "sample": "Clue: add an item to a list → a p p e n d",
            "note": "Letter keyboard only — answers are words/flags with letters.",
        },
        "go": {
            "sample": "Clue: run this when the function returns → d e f e r",
            "note": "Use a hint if stuck; finishing with no hints earns a bonus.",
        },
        "javascript": {
            "sample": "Clue: declare a binding that cannot be reassigned → c o n s t",
            "note": "Symbols-only tokens are skipped so rounds stay fair.",
        },
        "sql": {
            "sample": "Clue: keep only rows that match a test → W H E R E",
            "note": "Length and first letter come as progressive hints.",
        },
        "csharp": {
            "sample": "Clue: write a line to the console → W r i t e L i n e",
            "note": "Guess letters. Wrong letters fade the ghost.",
        },
        "java": {
            "sample": "Clue: print a line → p r i n t l n",
            "note": "Letter keyboard only — answers are words with letters.",
        },
    },
    "codele": {
        "bash": {"sample": "chmod → green/yellow letter feedback", "note": "Exactly 5 letters. Six tries."},
        "python": {"sample": "break / range / print (when 5 letters)", "note": "Green = right spot; yellow = elsewhere."},
        "go": {"sample": "defer / const / range", "note": "Same rules as Wordle, code keywords only."},
        "javascript": {"sample": "const / async / await (5-letter picks)", "note": "Use the clue under the grid."},
        "sql": {"sample": "WHERE / ORDER / GROUP (filtered to 5 letters)", "note": "Guess the whole word each time."},
        "csharp": {"sample": "class / using / break (when 5 letters)", "note": "Same rules as Wordle, code keywords only."},
        "java": {"sample": "class / final / break (5-letter picks)", "note": "Use the clue under the grid."},
    },
    "memory_match": {
        "bash": {"sample": "ls  ↔  Lists names in a directory", "note": "Flip two cards; matched pairs stay up."},
        "python": {"sample": "append  ↔  Adds an item to a list", "note": "Short rounds — good on a phone."},
        "go": {"sample": "defer  ↔  Runs when the function returns", "note": "Match keyword to explanation."},
        "javascript": {"sample": "const  ↔  Declares a constant binding", "note": "Wrong pairs flip back gently."},
        "sql": {"sample": "WHERE  ↔  Filters rows by a condition", "note": "Finish when every pair is matched."},
        "csharp": {"sample": "WriteLine  ↔  Prints a line to the console", "note": "Match keyword to explanation."},
        "java": {"sample": "println  ↔  Prints a line to standard output", "note": "Wrong pairs flip back gently."},
    },
    "code_crossword": {
        "bash": {"sample": "Clue (2): Lists directory names → ls", "note": "Length of the blank matches the keyword."},
        "python": {"sample": "Clue (6): Add to a list → append", "note": "One answer per clue, then Check."},
        "go": {"sample": "Clue (5): Delayed cleanup → defer", "note": "Spelling must match the lesson token."},
        "javascript": {"sample": "Clue (5): Immutable binding → const", "note": "Use hints for the first letter if stuck."},
        "sql": {"sample": "Clue (5): Row filter → WHERE", "note": "Answers can be upper or lower case."},
        "csharp": {"sample": "Clue (5): Delayed cleanup style keyword → using", "note": "Spelling must match the lesson token."},
        "java": {"sample": "Clue (5): Starts a class → class", "note": "Use hints for the first letter if stuck."},
    },
    "tic_tac_toe": {
        "bash": {"sample": "Cell: fill blank in `___ -la` → ls", "note": "Correct answer claims the cell; wrong gives it to the computer."},
        "python": {"sample": "Cell: what does print(1+1) show? → 2", "note": "Three correct cells in a row wins."},
        "go": {"sample": "Cell: keyword for delayed call → defer", "note": "Each cell is a mini lesson question."},
        "javascript": {"sample": "Cell: output of `1 + '2'` style prompts", "note": "Read carefully before claiming."},
        "sql": {"sample": "Cell: clause that filters rows → WHERE", "note": "Skip if stuck — another cell awaits."},
        "csharp": {"sample": "Cell: type that writes lines → Console", "note": "Correct answer claims the cell."},
        "java": {"sample": "Cell: print stream → out", "note": "Each cell is a mini lesson question."},
    },
    "syntax_snake": {
        "bash": {"sample": "ls → -la", "note": "Tap tokens left-to-right in statement order."},
        "python": {"sample": "nums → . → append → ( → 3 → )", "note": "A wrong path? Clear and try again."},
        "go": {"sample": "defer → f → . → Close → ()", "note": "Decoys are there on purpose."},
        "javascript": {"sample": "const → name → = → value", "note": "Build the full statement, then it checks."},
        "sql": {"sample": "SELECT → title → FROM → books", "note": "Eat only the next correct token."},
        "csharp": {"sample": "Console → . → WriteLine → ( → \"hi\" → ) → ;", "note": "A wrong path? Clear and try again."},
        "java": {"sample": "System → . → out → . → println → ( → \"hi\" → ) → ;", "note": "Build the full statement, then it checks."},
    },
    "predict_output": {
        "bash": {"sample": "echo hi  →  hi", "note": "Pick the result; distractors come from other lessons."},
        "python": {"sample": "print(2+2)  →  4", "note": "Read the code before choosing."},
        "go": {"sample": "fmt.Println(1+1)  →  2", "note": "Watch types and formatting."},
        "javascript": {"sample": "console.log(1 + '2')  →  12", "note": "Coercion surprises are fair game."},
        "sql": {"sample": "SELECT 1+1  →  2", "note": "Match the result table or value shown."},
        "csharp": {"sample": "Console.WriteLine(1+1);  →  2", "note": "Read the code before choosing."},
        "java": {"sample": "System.out.println(1+1);  →  2", "note": "Watch types and formatting."},
    },
    "code_scramble": {
        "bash": {"sample": "Shuffle lines of a small script; restore order", "note": "Use ↑ ↓ to reorder, then Check."},
        "python": {"sample": "def greet(): / print('hi')", "note": "Indentation must stay on each line."},
        "go": {"sample": "func main() { / … / }", "note": "Braces and order both matter."},
        "javascript": {"sample": "function / body / closing brace", "note": "Keep each line’s spaces intact."},
        "sql": {"sample": "SELECT … / FROM … / WHERE …", "note": "Clause order is the puzzle."},
        "csharp": {"sample": "class Program / Main / body / }", "note": "Braces and order both matter."},
        "java": {"sample": "public class / main / body / }", "note": "Keep each line’s spaces intact."},
    },
    "query_detective": {
        "bash": {"sample": "(Prefer the SQL track for this game.)", "note": "Write a query that yields the shown result."},
        "python": {"sample": "(Prefer the SQL track for this game.)", "note": "Same idea — result in, query out."},
        "go": {"sample": "(Prefer the SQL track for this game.)", "note": "Use lesson SQL when the track allows."},
        "javascript": {"sample": "(Prefer the SQL track for this game.)", "note": "Match columns and row values."},
        "sql": {
            "sample": "Result: Dune | 1965  →  SELECT title, year FROM books WHERE title = 'Dune'",
            "note": "Accepted answers use the same checker as lessons.",
        },
        "csharp": {"sample": "(Prefer the SQL track for this game.)", "note": "Write a query that yields the shown result."},
        "java": {"sample": "(Prefer the SQL track for this game.)", "note": "Same idea — result in, query out."},
    },
    "boss_battle": {
        "bash": {"sample": "Mix of fills, traces, and recalls", "note": "Correct answers damage the boss; hints cost your HP."},
        "python": {"sample": "Chain of 5–8 mixed questions", "note": "Pass the chain to feel the module click."},
        "go": {"sample": "One question at a time", "note": "Stay calm — Skip exists if a round is unfair."},
        "javascript": {"sample": "Output picks + fills + typing", "note": "No-hint clears earn bonus XP."},
        "sql": {"sample": "Queries, outputs, and keywords", "note": "Use progressive hints when stuck."},
        "csharp": {"sample": "Mix of fills, traces, and recalls", "note": "Correct answers damage the boss; hints cost your HP."},
        "java": {"sample": "Chain of mixed questions", "note": "Pass the chain to feel the module click."},
    },
}

HOW_TO: dict[str, str] = {
    "speed_drill": "Type the ghost text. Finish cleanly — accuracy matters as much as speed.",
    "ghost_race": "Same as a speed drill, but your past best WPM is the pace to beat.",
    "bug_hunt": "The red line has one mutation. Type the corrected line (never paste the typo).",
    "fill_frenzy": "Only the blanks are editable. Leave the rest of the line alone.",
    "command_roulette": "Read the prompt (and example if shown), then answer before the timer ends.",
    "code_hangman": "Read the clue. Guess letters to reveal a keyword from your lessons. Wrong letters fade the ghost.",
    "codele": "Guess a 5-letter keyword. Green = exact spot, yellow = in the word elsewhere.",
    "memory_match": "Flip two cards. Pair each keyword with what it does until all pairs are found.",
    "code_crossword": "Each clue is a token explanation. Type the matching keyword (length shown).",
    "tic_tac_toe": "Answer the mini-question to claim a cell. Misses go to the computer.",
    "syntax_snake": "Tap tokens in the order that rebuilds the statement. Clear the path if you slip.",
    "predict_output": "Read the snippet, then choose what it prints or returns.",
    "code_scramble": "Reorder the shuffled lines (and keep indentation) so the snippet is correct again.",
    "query_detective": "Look at the result table, then write a query that produces it.",
    "boss_battle": "A mixed chain of questions. Correct answers damage the boss; hints cost your health.",
}


def normalize_track(slug: str | None) -> str:
    key = (slug or "").strip().lower()
    if key in TRACK_NAMES:
        return key
    if key in {"js", "node"}:
        return "javascript"
    if key in {"golang"}:
        return "go"
    if key in {"shell", "zsh", "sh"}:
        return "bash"
    if key in {"c#", "cs", "c-sharp"}:
        return "csharp"
    if key in {"jdk"}:
        return "java"
    return key or "bash"


def track_label(slug: str | None) -> str:
    key = normalize_track(slug)
    return TRACK_NAMES.get(key, key.upper() if key else "Code")


def is_hangman_token(match: str) -> bool:
    """Letter keyboard cannot guess pure symbols like `>` — skip those."""
    text = (match or "").strip()
    if len(text) < 2:
        return False
    letters = sum(1 for ch in text if ch.isalpha())
    return letters >= 2


def hangman_tokens(tokens: list[dict]) -> list[dict]:
    return [row for row in tokens if is_hangman_token(row.get("match", ""))]


def crossword_tokens(tokens: list[dict]) -> list[dict]:
    # Same fairness filter — one-character operators make terrible clues.
    return hangman_tokens(tokens)


def guide_for(game: str, track_slug: str | None) -> dict:
    track = normalize_track(track_slug)
    examples = EXAMPLES.get(game) or {}
    example = examples.get(track) or examples.get("bash") or {
        "sample": "Use a hint if you get stuck.",
        "note": "Hints cost XP; finishing with none earns a bonus.",
    }
    return {
        "title": "How to play",
        "how": HOW_TO.get(game, "Answer using what you learned in published lessons."),
        "track": track_label(track),
        "example": example.get("sample", ""),
        "example_note": example.get("note", ""),
        "tip": "Hints are progressive and cost points. Skip is always OK — no harsh fail screen.",
    }


def _dedupe(hints: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for hint in hints:
        text = str(hint or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def progressive_token_hints(
    *,
    word: str,
    explain: str,
    track_slug: str | None,
    game: str,
) -> list[str]:
    track = normalize_track(track_slug)
    label = track_label(track)
    example = (EXAMPLES.get(game) or {}).get(track) or {}
    hints = [
        f"This is a {label} keyword from your published lessons.",
        f"Think about: {explain}" if explain else f"Recall a common {label} token.",
    ]
    if example.get("sample"):
        hints.append(f"Example pattern on this track: {example['sample']}")
    letters_only = re.sub(r"[^A-Za-z]", "", word)
    hints.append(f"It has {len(word)} character{'s' if len(word) != 1 else ''}"
                 + (f" ({len(letters_only)} letters)." if letters_only and len(letters_only) != len(word) else "."))
    if letters_only:
        hints.append(f"It starts with `{letters_only[0]}`.")
        if len(letters_only) >= 3:
            hints.append(f"It ends with `{letters_only[-1]}`.")
    # Soft middle reveal before full answer.
    if len(letters_only) >= 4:
        mid = letters_only[:2] + "…" + letters_only[-1]
        hints.append(f"Shape: `{mid}`.")
    hints.append(f"The keyword is `{word}`.")
    return _dedupe(hints)[:8]


def merge_hints(*groups: list[str], limit: int = 8) -> list[str]:
    merged: list[str] = []
    for group in groups:
        merged.extend(group or [])
    return _dedupe(merged)[:limit]


def starter_hints(game: str, track_slug: str | None) -> list[str]:
    """Always-available soft guidance before expensive reveals."""
    guide = guide_for(game, track_slug)
    hints = [guide["how"]]
    if guide.get("example"):
        hints.append(f"Example ({guide['track']}): {guide['example']}")
    if guide.get("example_note"):
        hints.append(guide["example_note"])
    return _dedupe(hints)[:4]
