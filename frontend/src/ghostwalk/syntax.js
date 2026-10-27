/** "Syntax this game understands" cheat sheets — mirrors skins.py subsets. */

export const SYNTAX_PANELS = {
  python: [
    "`hero.move()`, `turn_left()`, `turn_right()`, `pick_up()`, `plant()`, `water()`, `harvest()`",
    "Checks: `at_goal()`, `is_blocked()`, `on_gem()`, `on_soil()`, `read_sign()`, `crops_held()`",
    "`for`, `while`, `if` / `elif` / `else`, functions with `def`",
  ],
  bash: [
    "`move`, `turn_left`, `turn_right`, `pick_up`, `plant`, `water`, `harvest` (no parentheses)",
    "Checks: `blocked`, `at_goal`, `on_gem`, `on_soil`; `$(read_sign)`",
    "`;` · `for i in {1..N}` / `$(seq N)` / `((i = 0; i < n; i++))` · `while` / `until … do … done`",
    "`if … then … elif … else … fi` · `[[ … ]]` · `a && b` · `case … esac` · `name() { … }`",
  ],
  sql: [
    "`CALL move();` and other procedures; queries `at_goal()`, `is_blocked()`, …",
    "`DO $$ DECLARE … BEGIN … END $$;`",
    "`FOR i IN a..b LOOP` · `FOREACH x IN ARRAY arr LOOP` · `WHILE` · `LOOP … EXIT WHEN`",
    "`IF … THEN … ELSIF … ELSE … END IF;` · `CASE … END CASE;` (use `ELSE NULL;`)",
  ],
  go: [
    "`hero.Move()` and other methods in PascalCase",
    "`for i := 0; i < n; i++ {` · `for range n {` · `for _, v := range s {` · `for cond {` · `for {`",
    "`if … { } else if … { } else { }` · `switch` / tagless `switch {` (no break needed)",
    "`x := …` · slices · `name := func() { … }` · `break`, `continue`",
  ],
  csharp: [
    "`hero.Move();` in PascalCase; Allman or same-line braces",
    "Braceless single-statement `if` / `else` / loops",
    "`for` · `foreach` · `while` · `switch` **requires** `break;`",
    "`void Name() { … }` · `var` / arrays / `Dictionary` · `Console.WriteLine`",
  ],
  java: [
    "`hero.move();` in camelCase (PascalCase is rejected)",
    "`for` · enhanced `for` · `while` · `if` / `else if` / `else`",
    "`switch` with `->` or classic `case:` + `break`",
    "`Runnable r = () -> { … };` · `Map.of` · `.equals()` · `null` checks",
  ],
  javascript: [
    "Real JavaScript, run natively in the browser",
    "Hero methods in camelCase (`hero.turnLeft()`); snake_case also works",
    "`&&` as a tiny if · arrow functions · `for…of` · optional chaining `?.()`",
  ],
};

export function syntaxFor(language) {
  return SYNTAX_PANELS[language] || SYNTAX_PANELS.python;
}
