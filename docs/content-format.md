# Content format

Lessons and exercises are stored as rows. The exercise `data` object is also the shape used by the admin editor and by YAML or JSON import/export.

## Track file

```yaml
slug: bash
name: Bash
description: The shell, one command at a time.
modules:
  - title: Looking around
    description: See where you are.
    status: published          # draft | published
    lessons:
      - title: List the files
        summary: Show everything in this folder.
        body_markdown: |
          A short lesson in Markdown. Raw HTML is not rendered.
        status: published      # draft | review | published
        is_demo: false
        source_type: original  # original | adapted | ai_generated
        source_attribution: ""
        source_url: ""         # http or https, or empty
        license_note: ""
        exercises:
          - type: trace        # trace | fill | recall | challenge
            status: published  # draft | published
            prompt: Type the listing command.
            runtime: none      # none | browser_js | pyodide
            code: ls -la
            tokens:
              - match: ls
                explain: Lists the names in a directory.
            blanks: []         # fill only. index starts at 1.
            check:
              mode: either     # answers | rules | either
              accepted_answers:
                - ls -la
              normalize:
                collapse_whitespace: true
                trim: true
                equivalent_quotes: false
                case_sensitive: true
              rules:
                - kind: must_contain
                  value: ls
                  hint: Which command lists directory contents?
            hints:
              - The command is two letters.
            simulated_output: |
              notes.txt
            expected_output: null
            xp: 10
            time_limit_seconds: null
```

`GET /api/admin/export?track=bash` returns this document as YAML. Add `format=json` for JSON. `track=all` returns every track under a `tracks:` list. `lesson=<id>` returns one lesson inside its module, in the same shape, so it can be edited and uploaded on its own.

`POST /api/admin/import` takes `{ "document": "...", "dry_run": true, "mode": "extend" }`.

- `extend` matches a module or lesson by its title and an exercise by its `order`. Matching rows are updated and keep their ids, so learner progress stays. A title that is not already there is added. An exercise with no `order` is added at the end. Nothing is deleted.
- `replace` rebuilds each track in the file. Lessons left out of the file are deleted, and progress on them is cleared.

A dry run checks the file and reports how many lessons would be added or updated. It does not save. Games are not a separate file. Speed Drill, Bug Hunt, Fill Frenzy, and Command Roulette use **published** exercises from these lessons — the full published pool on the track you pick, not a tiny random sample.

Set `publish: true` on `POST /api/admin/import` (or check **Publish for practice** in Content) so every module, lesson, and exercise in the file is stored as published. Draft lessons stay invisible to Learn and Games until you publish them.

## Check rules

Rules run in order on the normalized answer. The first failure supplies the hint.

| Kind | Fields | Passes when |
| --- | --- | --- |
| `exact` | `value`, or the accepted answers when `value` is empty | The answer matches after normalization |
| `must_contain` | `value` | The answer contains the text |
| `must_not_contain` | `value` | The answer does not contain the text |
| `must_contain_any` | `values` | The answer contains one of the texts |
| `must_contain_all` | `values` | The answer contains every text |
| `regex` | `pattern` | The whole answer matches. Nested repetition such as `(a+)+` is rejected |
| `line_count` | `minimum`, `maximum` | The line count is inside the range |
| `output_equals` | uses `expected_output` | The output string from the browser matches |

`check.mode` chooses what is required:

- `answers` — the answer is one of `accepted_answers`
- `rules` — every rule passes
- `either` — the accepted answers match, or every rule passes

Normalization runs before those comparisons. When `case_sensitive` is false, a regex is matched against the lowercased answer, so write the pattern in lowercase.

## Exercise types

- **trace** needs `code`. The learner types over it.
- **fill** needs `code` and at least one `blanks` entry. `index` counts words from 1.
- **recall** shows the prompt. The canonical `code` is kept for authors and hidden from learners.
- **challenge** is recall under pressure. Set `time_limit_seconds` for a timer (short teasers often use 60). Leave it empty or `null` for untimed Daily scripts that rely on progressive hints instead of the clock.

`runtime` stays `none` unless the exercise compares browser output. `browser_js` and `pyodide` require `expected_output`. The server compares that string. It does not run the program.

## Learning path

Each track is a ladder:

1. **Beginner** — basic commands and syntax until they feel familiar  
2. **Intermediate** — more programming (combining ideas, Daily scripts)  
3. **Advanced** — longer scripts and **Projects** you type end-to-end  

The outline API attaches `level` / `level_label` to every module. Early core modules are beginner; later ones intermediate; `Daily scripts` and `Projects` stay intermediate and advanced. Module descriptions are tagged `Beginner — …` / `Intermediate — …` / `Advanced — …`.

Starter modules are short one-liners — teasers that build the habit. Each track can also have a **Daily scripts** module: multi-line programs with progressive hints, taller editors, and usually no timer. That is the guided daily refresh. **Projects** are preconfigured mini-programs you type end-to-end for basic understanding (ghost text, fill, recall). They appear under Learn → Projects and inside each track. Addon files live in `backend/app/seed/addons/` and are imported in `extend` mode when the module title is still missing.
