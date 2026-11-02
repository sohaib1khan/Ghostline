"""Ghostline step-through recorder (Thonny-style "Step" view).

Runs INSIDE the browser sandbox (Pyodide), never on the server.
Copy to frontend/public/sandbox/tracer.py and call `record(...)` from the
sandbox runner. Stdlib only.

record() runs the program once and returns every step as plain JSON-able
data. The UI then lets the learner move forward and back through the steps;
nothing re-runs while they step.
"""

from __future__ import annotations

import builtins
import contextlib
import io
import sys
import types

FILENAME = "<lesson>"
MAX_STEPS = 600
MAX_REPR = 80


def _short(value) -> str:
    if isinstance(value, types.FunctionType):
        return f"function {value.__name__}"
    if isinstance(value, type):
        return f"class {value.__name__}"
    if isinstance(value, types.GeneratorType):
        return f"generator {value.__name__}"
    try:
        text = repr(value)
    except Exception:  # noqa: BLE001 - a learner's __repr__ may be broken
        text = f"<{type(value).__name__}>"
    return text if len(text) <= MAX_REPR else text[: MAX_REPR - 1] + "…"


def _visible(namespace: dict) -> dict[str, str]:
    shown = {}
    for name, value in namespace.items():
        if name.startswith("__") or isinstance(value, types.ModuleType):
            continue
        shown[name] = _short(value)
    return shown


class _StepLimit(Exception):
    pass


def record(program: str, setup: str = "", stdin: list[str] | None = None, max_steps: int = MAX_STEPS) -> dict:
    """Run `program` and return {steps, stdout, error, truncated}.

    Each step is the state just BEFORE `line` runs (like Thonny's highlight),
    except `return` steps, which show the value a function hands back.
    """
    out = io.StringIO()
    answers = list(stdin or [])

    def fake_input(prompt: str = "") -> str:
        if not answers:
            raise EOFError("The walkthrough ran out of typed input.")
        answer = str(answers.pop(0))
        out.write(f"{prompt}{answer}\n")  # echo like a real terminal
        return answer

    safe_builtins = dict(vars(builtins), input=fake_input)
    namespace: dict = {"__name__": "__main__", "__builtins__": safe_builtins}
    steps: list[dict] = []
    error = None

    def snapshot(frame, line: int, event: str, value=None) -> None:
        if len(steps) >= max_steps:
            raise _StepLimit
        scopes = []
        f = frame
        while f is not None and f.f_code.co_filename == FILENAME:
            if f.f_code.co_name != "<module>":
                scopes.append({"name": f.f_code.co_name, "vars": _visible(f.f_locals)})
            f = f.f_back
        step = {
            "line": line,
            "event": event,
            "globals": _visible(namespace),
            "frames": list(reversed(scopes)),  # outermost call first
            "stdout_len": len(out.getvalue()),
        }
        if event in ("return", "yield"):
            step["returned"] = _short(value)
        steps.append(step)

    def local_tracer(frame, event, arg):
        if event == "line":
            snapshot(frame, frame.f_lineno, "line")
        elif event == "return" and frame.f_code.co_name != "<module>":
            # A generator fires "return" each time it pauses at yield; show that as a yield step.
            pausing = bool(frame.f_code.co_flags & 0x20) and _is_yield(frame)
            snapshot(frame, frame.f_lineno, "yield" if pausing else "return", arg)
        return local_tracer

    def global_tracer(frame, event, arg):
        code = frame.f_code
        if code.co_filename != FILENAME:
            return None
        # Comprehensions, generator expressions and lambdas run as part of their line.
        if code.co_name.startswith("<") and code.co_name != "<module>":
            return None
        return local_tracer

    with contextlib.redirect_stdout(out):
        try:
            if setup:
                exec(compile(setup, "<setup>", "exec"), namespace)  # noqa: S102 - browser sandbox only
            compiled = compile(program, FILENAME, "exec")
            sys.settrace(global_tracer)
            try:
                exec(compiled, namespace)  # noqa: S102 - browser sandbox only
            finally:
                sys.settrace(None)
        except _StepLimit:
            pass
        except SyntaxError as exc:
            error = {"type": "SyntaxError", "message": exc.msg, "line": exc.lineno}
        except BaseException as exc:  # noqa: BLE001 - report every learner error
            tb = exc.__traceback__
            line = None
            while tb is not None:
                if tb.tb_frame.f_code.co_filename == FILENAME:
                    line = tb.tb_lineno
                tb = tb.tb_next
            error = {"type": type(exc).__name__, "message": str(exc), "line": line}

    if error and steps:
        steps.append({**steps[-1], "event": "exception", "line": error["line"] or steps[-1]["line"],
                      "error": f"{error['type']}: {error['message']}"})
    return {
        "steps": steps,
        "stdout": out.getvalue(),
        "error": error,
        "truncated": len(steps) >= max_steps,
    }


def _is_yield(frame) -> bool:
    """True when a generator frame is pausing at `yield`, not finishing."""
    import dis

    # Python 3.11/3.12 stop on YIELD_VALUE; 3.13 on the RESUME after it. A real
    # return always stops on a RETURN_* instruction, so test for that instead.
    for ins in dis.get_instructions(frame.f_code):
        if ins.offset == frame.f_lasti:
            return not ins.opname.startswith("RETURN_")
    return False
