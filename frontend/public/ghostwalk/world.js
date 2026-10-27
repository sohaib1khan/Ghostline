/* Ghostwalk maze engine (JS) — mirrors backend/app/ghostwalk/world.py for non-Python languages. */
(function (root) {
  const KNOWN = new Set([
    "move",
    "turn_left",
    "turn_right",
    "pick_up",
    "at_goal",
    "is_blocked",
    "on_gem",
    "read_sign",
    "plant",
    "water",
    "harvest",
    "on_soil",
    "crops_held",
  ]);
  const FACINGS = ["N", "E", "S", "W"];
  const DELTA = { N: [-1, 0], E: [0, 1], S: [1, 0], W: [0, -1] };
  const MAX_CODE = 12000;
  const BUDGET = 50000;
  const SOIL = "~";
  const SEED = "s";
  const CROP = "c";
  const BARN = "B";

  function normalizeGrid(raw) {
    const rows = (raw || []).map((line) =>
      typeof line === "string" ? [...line] : line.map(String),
    );
    if (!rows.length) throw new Error("Grid is empty");
    const width = rows[0].length;
    if (!width || rows.some((row) => row.length !== width)) {
      throw new Error("Grid must be rectangular");
    }
    return rows;
  }

  function findChar(grid, needle) {
    for (let r = 0; r < grid.length; r += 1) {
      for (let c = 0; c < grid[r].length; c += 1) {
        if (grid[r][c] === needle) return [r, c];
      }
    }
    return null;
  }

  function cell(grid, row, col) {
    if (row < 0 || col < 0 || row >= grid.length || col >= grid[0].length) return "#";
    return grid[row][col];
  }

  function facingName(facing) {
    return { N: "north", E: "east", S: "south", W: "west" }[facing] || facing;
  }

  function snapshot(state, line, message, kind) {
    return {
      row: state.row,
      col: state.col,
      facing: state.facing,
      gems_held: state.gemsHeld,
      gems_total: state.gemsTotal,
      crops_held: state.cropsHeld,
      crops_total: state.cropsTotal,
      steps: state.steps,
      line,
      message,
      kind,
      grid: state.grid.map((row) => row.join("")),
    };
  }

  function fail(state, message, line) {
    state.error = message;
    state.errorLine = line == null ? null : line;
    state.trace.push(snapshot(state, state.errorLine, message, "error"));
  }

  function tick(state) {
    state.instructions += 1;
    if (state.instructions > BUDGET) {
      fail(state, "That ran too long. Check for an infinite loop.");
      return false;
    }
    return !state.error;
  }

  function requireCmd(state, command, line) {
    if (!state.allowed.has(command)) {
      fail(state, `\`hero.${command}()\` is not unlocked on this level.`, line);
      return false;
    }
    return true;
  }

  function buildState(level) {
    const grid = normalizeGrid(JSON.parse(JSON.stringify(level.grid || [])));
    const start = level.start || {};
    let facing = String(start.facing || level.facing || "E").toUpperCase();
    if (!FACINGS.includes(facing)) facing = "E";
    const sPos = findChar(grid, "S");
    const row = Number(start.row != null ? start.row : sPos ? sPos[0] : 0);
    const col = Number(start.col != null ? start.col : sPos ? sPos[1] : 0);
    if (cell(grid, row, col) === "S") grid[row][col] = ".";
    let allowed = new Set(
      (level.allowed || []).map(String).filter((item) => KNOWN.has(item)),
    );
    if (!allowed.size) allowed = new Set(KNOWN);
    const goal = { ...(level.goal || { reach_goal: true }) };
    const gemsTotal = grid.flat().filter((ch) => ch === "*").length;
    const soil = grid.flat().filter((ch) => ch === SOIL).length;
    const cropsNeeded = Number(goal.collect_crops || 0);
    return {
      grid,
      row,
      col,
      facing,
      gemsTotal,
      gemsHeld: 0,
      cropsTotal: cropsNeeded || soil,
      cropsHeld: 0,
      steps: 0,
      maxSteps: Number(level.max_steps || 500),
      goal,
      allowed,
      actions: [],
      trace: [],
      error: null,
      errorLine: null,
      instructions: 0,
    };
  }

  function ahead(state) {
    const [dr, dc] = DELTA[state.facing];
    return [state.row + dr, state.col + dc];
  }

  function atGoalCell(state) {
    const ch = cell(state.grid, state.row, state.col);
    return ch === "G" || ch === BARN;
  }

  function doMove(state, line) {
    if (!tick(state) || !requireCmd(state, "move", line)) return false;
    if (state.steps >= state.maxSteps) {
      fail(state, "Too many steps. Simplify the path.", line);
      return false;
    }
    const [nr, nc] = ahead(state);
    if (cell(state.grid, nr, nc) === "#") {
      fail(state, "Bonk — a wall is ahead. Check with hero.is_blocked().", line);
      return false;
    }
    state.row = nr;
    state.col = nc;
    state.steps += 1;
    state.actions.push({ op: "move", line });
    state.trace.push(
      snapshot(
        state,
        line,
        `Moved ${facingName(state.facing)} to row ${state.row}, column ${state.col}`,
        "move",
      ),
    );
    return true;
  }

  function doTurn(state, direction, line) {
    const cmd = direction === "left" ? "turn_left" : "turn_right";
    if (!tick(state) || !requireCmd(state, cmd, line)) return false;
    const idx = FACINGS.indexOf(state.facing);
    state.facing =
      direction === "left" ? FACINGS[(idx + 3) % 4] : FACINGS[(idx + 1) % 4];
    state.actions.push({ op: cmd, line });
    state.trace.push(
      snapshot(state, line, `Turned ${direction}, now facing ${facingName(state.facing)}`, "turn"),
    );
    return true;
  }

  function doPickUp(state, line) {
    if (!tick(state) || !requireCmd(state, "pick_up", line)) return false;
    if (cell(state.grid, state.row, state.col) !== "*") {
      fail(state, "Nothing to pick up here. Check hero.on_gem() first.", line);
      return false;
    }
    state.grid[state.row][state.col] = ".";
    state.gemsHeld += 1;
    state.actions.push({ op: "pick_up", line });
    state.trace.push(
      snapshot(
        state,
        line,
        `Picked up a gem (${state.gemsHeld}/${state.gemsTotal})`,
        "pick_up",
      ),
    );
    return true;
  }

  function doPlant(state, line) {
    if (!tick(state) || !requireCmd(state, "plant", line)) return false;
    if (cell(state.grid, state.row, state.col) !== SOIL) {
      fail(state, "Plant only works on empty soil (~).", line);
      return false;
    }
    state.grid[state.row][state.col] = SEED;
    state.actions.push({ op: "plant", line });
    state.trace.push(snapshot(state, line, "Planted a seed.", "plant"));
    return true;
  }

  function doWater(state, line) {
    if (!tick(state) || !requireCmd(state, "water", line)) return false;
    if (cell(state.grid, state.row, state.col) !== SEED) {
      fail(state, "Water only works on a planted seed.", line);
      return false;
    }
    state.grid[state.row][state.col] = CROP;
    state.actions.push({ op: "water", line });
    state.trace.push(snapshot(state, line, "Watered the seed — crop ready!", "water"));
    return true;
  }

  function doHarvest(state, line) {
    if (!tick(state) || !requireCmd(state, "harvest", line)) return false;
    if (cell(state.grid, state.row, state.col) !== CROP) {
      fail(state, "Nothing ripe to harvest here.", line);
      return false;
    }
    state.grid[state.row][state.col] = SOIL;
    state.cropsHeld += 1;
    state.actions.push({ op: "harvest", line });
    state.trace.push(
      snapshot(
        state,
        line,
        `Harvested a crop (${state.cropsHeld}/${state.cropsTotal})`,
        "harvest",
      ),
    );
    return true;
  }

  function goalsMet(state) {
    const goal = state.goal || {};
    if (goal.collect_all_gems && state.gemsHeld < state.gemsTotal) return false;
    const need = Number(goal.collect_crops || 0);
    if (need && state.cropsHeld < need) return false;
    if (goal.reach_goal !== false && !atGoalCell(state)) return false;
    return true;
  }

  function result(state, okForce) {
    const success = okForce != null ? okForce : !state.error && goalsMet(state);
    const out = {
      ok: success,
      error: state.error,
      error_line: state.errorLine,
      trace: state.trace,
      actions: state.actions,
      steps: state.steps,
      gems_held: state.gemsHeld,
      gems_total: state.gemsTotal,
      crops_held: state.cropsHeld,
      crops_total: state.cropsTotal,
      row: state.row,
      col: state.col,
      facing: state.facing,
    };
    if (!success && !state.error) {
      const need = Number(state.goal.collect_crops || 0);
      if (state.goal.collect_all_gems && state.gemsHeld < state.gemsTotal) {
        out.error = `Still missing gems (${state.gemsHeld}/${state.gemsTotal}).`;
      } else if (need && state.cropsHeld < need) {
        out.error = `Still missing crops (${state.cropsHeld}/${need}).`;
      } else {
        out.error = "The ghost did not reach the goal.";
      }
    }
    return out;
  }

  function makeHero(state) {
    // Which learner line called the hero? new Function code appears in stack traces as
    // "<anonymous>:LINE" (Chrome/Node) or "> Function:LINE" (Firefox). The wrapper adds
    // two header lines plus the "use strict" line, so subtract 3.
    // Prefer the frame that called the hero method so we ignore host anonymous scripts.
    // Lookbehind avoids matching host frames like "evalmachine.<anonymous>:N".
    const line = () => {
      const frameRe = /(?:> Function|(?<![\w.])<anonymous>):(\d+):\d+/;
      const frames = (new Error().stack || "").split("\n");
      const heroIdx = frames.findIndex((frame) =>
        /(?:^|\s)at Object\.(?:move|turn_left|turn_right|pick_up|plant|water|harvest|at_goal|is_blocked|on_gem|on_soil|crops_held|read_sign)\b/.test(
          frame,
        ),
      );
      const read = (frame) => {
        const match = frameRe.exec(frame || "");
        return match ? Math.max(1, Number(match[1]) - 3) : null;
      };
      if (heroIdx >= 0) {
        const fromCaller = read(frames[heroIdx + 1]);
        if (fromCaller != null) return fromCaller;
      }
      for (const frame of frames) {
        const value = read(frame);
        if (value != null) return value;
      }
      return null;
    };
    const boom = () => {
      if (state.error) throw new Error(state.error);
    };
    return {
      move() {
        doMove(state, line());
        boom();
      },
      turn_left() {
        doTurn(state, "left", line());
        boom();
      },
      turn_right() {
        doTurn(state, "right", line());
        boom();
      },
      pick_up() {
        doPickUp(state, line());
        boom();
      },
      plant() {
        doPlant(state, line());
        boom();
      },
      water() {
        doWater(state, line());
        boom();
      },
      harvest() {
        doHarvest(state, line());
        boom();
      },
      at_goal() {
        if (!tick(state) || !requireCmd(state, "at_goal", line())) boom();
        return atGoalCell(state);
      },
      is_blocked() {
        if (!tick(state) || !requireCmd(state, "is_blocked", line())) boom();
        const [nr, nc] = ahead(state);
        return cell(state.grid, nr, nc) === "#";
      },
      on_gem() {
        if (!tick(state) || !requireCmd(state, "on_gem", line())) boom();
        return cell(state.grid, state.row, state.col) === "*";
      },
      on_soil() {
        if (!tick(state) || !requireCmd(state, "on_soil", line())) boom();
        const ch = cell(state.grid, state.row, state.col);
        return ch === SOIL || ch === SEED || ch === CROP;
      },
      crops_held() {
        if (!tick(state) || !requireCmd(state, "crops_held", line())) boom();
        return state.cropsHeld;
      },
      read_sign() {
        if (!tick(state) || !requireCmd(state, "read_sign", line())) boom();
        const ch = cell(state.grid, state.row, state.col);
        if (ch === "r") return "red";
        if (ch === "b") return "blue";
        return null;
      },
    };
  }

  function runLearnerCode(level, code) {
    if (typeof code !== "string") {
      return { ok: false, error: "Code must be a string.", error_line: null, trace: [], actions: [] };
    }
    if (code.length > MAX_CODE) {
      return { ok: false, error: "That program is too long.", error_line: null, trace: [], actions: [] };
    }
    let state;
    try {
      state = buildState(level);
    } catch (err) {
      return { ok: false, error: String(err.message || err), error_line: null, trace: [], actions: [] };
    }
    state.trace.push(snapshot(state, null, "Ready.", "start"));
    const hero = makeHero(state);
    for (const key of Object.keys(hero)) {
      const camel = key.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
      if (camel !== key) hero[camel] = hero[key];
    }
    try {
      // eslint-disable-next-line no-new-func
      const runner = new Function(
        "hero",
        `"use strict";\n${code}\n`,
      );
      runner(hero);
    } catch (err) {
      if (!state.error) fail(state, String(err && err.message ? err.message : err));
      return result(state, false);
    }
    return result(state);
  }

  root.GhostwalkWorld = { runLearnerCode, KNOWN };
})(typeof self !== "undefined" ? self : globalThis);
