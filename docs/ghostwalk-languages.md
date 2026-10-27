# Ghostwalk languages

Each language is its own game: story, ghost, look, and the idioms that language is known for. Python (Hollow House) and Ghostfarm keep the classic hero API. Other languages go through `skins.py` into the shared Python engine; JavaScript runs natively on `world.js`.

| Language | Game | Ghost |
| --- | --- | --- |
| Python | Hollow House | Wisp |
| Bash | Night Shift | Cron |
| SQL | The Midnight Archive | Ledger |
| Go | The Lantern Mines | Burrow |
| C# | Starship Spectre | Echo |
| Java | The Midnight Roastery | Bean |
| JavaScript | Starlight Arcade | Pixel |

## How code runs

1. **Python** — Pyodide loads `world.py` and calls `run_learner_code`.
2. **Bash / Go / C# / Java / SQL** — Pyodide loads `world.py` + `skins.py`, then `skins.run(world, level, language, code)`. The skin returns Python plus a line map so traces and errors highlight the learner’s line.
3. **JavaScript** — `world.js` in a worker; camelCase methods (`hero.turnLeft()`) alias snake_case; line numbers come from the call stack.

The server never executes learner source. Submit sends the action list; `replay()` must agree.

## Syntax this game understands

### Bash

`move`, `turn_left`, `turn_right`, `pick_up`, `plant`, `water`, `harvest`; checks `blocked`, `at_goal`, `on_gem`, `on_soil`; `$(read_sign)`; `;`; `for i in {1..N}` / `$(seq N)` / `"${arr[@]}"` / `((i = 0; i < n; i++))`; `while` / `until … do … done`; `if … then … elif … else … fi`; `[[ … ]]` and `(( … ))` tests; `a && b`, `a || b`; `case … in pattern) … ;; esac`; `name() { … }`; `arr=(1 2 3)`; `x=…`; `echo`; `break`, `continue`. Older `hero_move()` style is still accepted.

### SQL

`CALL move();` and the other procedures; queries `at_goal()`, `is_blocked()`, `on_gem()`, `on_soil()`, `read_sign()`, `crops_held()`; `DO $$ DECLARE … BEGIN … END $$;`; `name type := value;`; `FOR i IN a..b LOOP`; `FOREACH x IN ARRAY arr LOOP`; `WHILE … LOOP`; `LOOP … EXIT WHEN …; END LOOP;`; `IF … THEN … ELSIF … ELSE … END IF;`; `CASE x WHEN … THEN … ELSE … END CASE;`; `x := …;`; `NULL;`; `RAISE NOTICE '…';`.

### Go

`hero.Move()` and the other methods in PascalCase; `for i := 0; i < n; i++ {`; `for range n {`; `for _, v := range s {`; `for cond {`; `for {`; `if … { } else if … { } else { }`; `switch x {` / tagless `switch {` with `case …:` and `default:`; `x := …`; `[]int{…}`; `map[string]string{…}`; `name := func() { … }`; `x++`; `break`, `continue`; `fmt.Println`.

### C#

`hero.Move();` in PascalCase; Allman or same-line braces; braceless single-statement `if`/`else`/loops; `for (int i = 0; i < n; i++)`; `foreach (var x in arr)`; `while (…)`; `switch (x) { case …: … break; default: … break; }`; `void Name() { … }`; `var`/`int`/`string` declarations; `new[] { … }`, `int[] a = { … }`; `new Dictionary<string, string> { ["k"] = "v" }`; `x++`; `Console.WriteLine`.

### Java

`hero.move();` in camelCase; `for (int i = 0; i < n; i++)`; `for (int x : arr)`; `while (…)`; `if`/`else if`/`else`; `switch (x) { case "a" -> …; default -> …; }` (and classic `case:` with `break`); `Runnable r = () -> { … };` with `r.run();`; `var`/`int`/`String` declarations; `int[] a = {…}`; `Map.of(…)` with `.get(k)`; `a.equals(b)`; `null`; `System.out.println`.

### JavaScript

Real JavaScript, run natively. Hero methods in camelCase (snake_case also works).

## Seeds and Studio

- `backend/app/seed/ghostwalk/levels.yaml` — Python maze levels.
- `backend/app/seed/ghostwalk/levels_multilang.yaml` — other languages + Ghostfarm (`only_missing` by slug).
- Studio export includes `language`. Re-importing keeps each level’s language.
