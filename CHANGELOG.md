# Changelog

## 1.6.0 — 2026-11-07

In-app bug reports and support messages.

- Learners and admins report bugs via a breezy modal (auto page/context capture + category chips + short note); each ticket gets a `BUG-…` id.
- Messages inbox for replies; unread badge in the nav; Studio → Tickets desk for super admin replies and status.

## 1.5.2 — 2026-11-07

Ghostwalk play layout.

- Sticky scene + Run/Step/Reset dock so the world stays in view on phones.
- Real Step advances one move at a time; slower default pacing.
- Dropped 3D/Top-down/Reset view toggles — one flexible orbit playground that scales by viewport.

## 1.5.1 — 2026-11-05

Review polish.

- Pass feedback on `/review` uses green success styling (and XP pop) instead of the red fail chrome; longer pause before the next item.
- Review queue only includes courses the learner has actually started or completed — not every assigned track.

## 1.5.0 — 2026-11-01

Real post-pass quizzes.

- `quiz` on exercises (output/concept); practice payload includes questions; Studio Quiz editor.
- `QuizCheck` replaces token-based ExplainBack when quiz exists; soft miss journal + spaced review; +2 XP once on first-try correct.
- Seed output quizzes verified by running the snippet (skipped until YAML is imported).

## 1.4.0 — 2026-11-01

Python step-through (Thonny-style).

- `walkthrough` field on exercises; `GET /api/exercises/{id}/walkthrough` after pass (or for trace/fill).
- Browser `tracer.py` records steps once; `StepThrough` UI with variables, output, notes, and predict-value prompts.
- Admin Walkthrough editor + Preview; import **replace** updates exercises in place so progress stays attached.

## 1.3.0 — 2026-10-27

Ghostwalk languages, skins, and Ghostfarm.

- Real language skins (`skins.py`) for Bash, Go, C#, Java, and SQL with learner line maps; JavaScript stays on `world.js` with camelCase and stack-based line numbers.
- Nested Python instrumentation so `error_line` / trace lines point at statements inside loops and functions.
- Six themed games on the level map (Hollow House, Night Shift, Midnight Archive, Lantern Mines, Starship Spectre, Midnight Roastery, Starlight Arcade) plus Ghostfarm plots.
- Seed packs: Python house levels + multilang YAML (45 language levels + farm); Studio export keeps `language`.
- Runtime endpoints with ETag for `world.py` / `skins.py`; syntax panel and docs.

## 1.2.0 — 2026-10-26

Ghostwalk maze mini-game.

- Shared `world.py` engine for browser (Pyodide) runs and server-side action replay; unit tests for solutions, wall bumps, gems, and forged moves.
- Levels and progress tables; ten seeded published levels; learner API (`/api/ghostwalk`) with lock order, hidden solutions on free levels, stars/XP on submit.
- Play UI with R3F 3D/top-down scene, sandbox `ghostwalk` runtime, map + level routes, nav between Playground and Games.
- Studio Ghostwalk editor with grid preview, solution test, publish gate, YAML export.
- Review free replays, mistake journal (`source=ghostwalk`), Python lesson practice links, Home continue card.

## 1.1.0 — 2026-10-25

Learning enforcement and low-vision UI.

- Accessibility preferences (text/code scale, contrast, ghost strength, cursor, focus ring, wrap, dyslexia spacing) synced to the account; reflowing nav and editor at 200%/400% zoom.
- Spaced review queue with Home card, `/review` player, and scheduling unit tests.
- Module mastery gates (80% recall unlock), module bosses, certificates require every boss; admin module unlock with audit.
- Mistake journal (`attempt_log`) with “usual slips” on Progress and learner delete.
- Learning styles: fading ghost traces, confidence ratings on review, daily goals, Parsons mode, predict/reveal, explain-it-back, retention on track cards, partial credit, weekly reflection API.

## 1.0.0 — 2026-09-28

First release of Ghostline.

- Accounts: first-run setup, signup with admin approval, sessions, and profile.
- Lessons for Bash, Python, Go, and JavaScript, with a ghost editor, fill-the-gap, and checks that stay on the answer string.
- Public demo, games, XP, streaks, and stats.
- Admin content tools, notifications, and AI lesson drafts that stay unpublished until reviewed.
- Installable app with offline reading of lessons that were already opened.
- Production Compose limits, log rotation, backup and restore scripts, browser tests for the main paths, and image scans with no high or critical findings.
