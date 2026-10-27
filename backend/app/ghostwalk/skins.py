"""Ghostwalk language skins: translate Bash, Go, C#, Java, and SQL (PL/pgSQL) into
Python that runs on the Ghostwalk engine (world.py).

Design:
- Learners write real, idiomatic syntax for each language (a well-defined subset).
- transpile() returns Python plus a line map, so the editor highlights the learner's
  own line, not the generated Python line.
- Anything outside the supported subset is rejected with a friendly SkinError that
  names the line, instead of being passed through.
- JavaScript is not translated: it runs natively on world.js (with camelCase aliases).

Pure Python, standard library only. Runs in Pyodide (browser) and in backend tests.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

HERO_COMMANDS = {
    "move",
    "turn_left",
    "turn_right",
    "pick_up",
    "plant",
    "water",
    "harvest",
}
HERO_QUERIES = {"at_goal", "is_blocked", "on_gem", "on_soil", "read_sign", "crops_held"}
HERO_ALL = HERO_COMMANDS | HERO_QUERIES
PY_KEYWORDS = {"and", "or", "not", "is", "in", "None", "True", "False"}
BUILTINS = {"range", "len", "print", "int", "str"}
RESERVED = {
    "def",
    "class",
    "lambda",
    "import",
    "from",
    "global",
    "nonlocal",
    "pass",
    "yield",
    "return",
    "del",
    "with",
    "as",
    "try",
    "except",
    "finally",
    "raise",
    "assert",
    "async",
    "await",
    "elif",
    "while",
    "for",
    "if",
    "else",
    "break",
    "continue",
}
INDENT = "    "


class SkinError(Exception):
    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line


@dataclass
class Transpiled:
    python: str
    line_map: list[int]  # line_map[python_line - 1] == learner's source line

    def source_line(self, python_line: int | None) -> int | None:
        if python_line is None or not 1 <= python_line <= len(self.line_map):
            return None
        return self.line_map[python_line - 1]


def snake(name: str) -> str:
    """turnLeft / TurnLeft / turn_left -> turn_left"""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


# ------------------------------------------------------------------ emitter
@dataclass
class Block:
    kind: str
    src: int
    indent: bool = True
    body: bool = False
    extra: dict = field(default_factory=dict)


class Emitter:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.map: list[int] = []
        self.depth = 0
        self.stack: list[Block] = []
        self.names: set[str] = set()
        self.kinds: dict[str, str] = {}
        self.temp = 0
        self.last_closed: Block | None = None

    def _mark_body(self) -> None:
        for block in reversed(self.stack):
            block.body = True
            if block.indent:
                break

    def emit(self, text: str, src: int) -> None:
        self.lines.append(INDENT * self.depth + text)
        self.map.append(src)
        self._mark_body()
        self.last_closed = None

    def open(self, header: str | None, src: int, kind: str, indent: bool = True, **extra) -> Block:
        if header is not None:
            self.emit(header, src)
        block = Block(kind=kind, src=src, indent=indent, extra=extra)
        self.stack.append(block)
        if indent:
            self.depth += 1
        return block

    def close(self, src: int, expect: set[str] | None = None, what: str = "block") -> Block:
        if not self.stack:
            raise SkinError(f"There is no open {what} to close here.", src)
        block = self.stack[-1]
        if expect and block.kind not in expect:
            raise SkinError(f"This closes a {what}, but the open block is a {block.kind}.", src)
        self.stack.pop()
        if block.indent:
            if not block.body:
                self.lines.append(INDENT * self.depth + "pass")
                self.map.append(src)
            self.depth -= 1
        self.last_closed = block
        return block

    def top(self) -> Block | None:
        return self.stack[-1] if self.stack else None

    def new_temp(self, prefix: str) -> str:
        self.temp += 1
        return f"_{prefix}{self.temp}"

    def declare(self, name: str, src: int, kind: str = "any") -> str:
        if name in RESERVED or name in PY_KEYWORDS or name in BUILTINS or name == "hero":
            raise SkinError(f"`{name}` is a reserved word in Ghostwalk. Pick another name.", src)
        if not re.fullmatch(r"[A-Za-z_]\w*", name) or name.startswith("__"):
            raise SkinError(f"`{name}` is not a valid name.", src)
        self.names.add(name)
        self.kinds[name] = kind
        return name

    def finish(self, lang: str) -> Transpiled:
        if self.stack:
            block = self.stack[-1]
            closer = {
                "bash": "a closing keyword (done, fi, esac, or })",
                "sql": "an END (END LOOP, END IF, END CASE)",
            }.get(lang, "a closing }")
            raise SkinError(f"This {block.kind} is never closed. Add {closer}.", block.src)
        return Transpiled("\n".join(self.lines) + "\n", self.map)


# ------------------------------------------------------------------ strings
STRING_RE = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'')


def protect_strings(text: str, sql: bool = False) -> tuple[str, list[str]]:
    found: list[str] = []

    def keep(match: re.Match) -> str:
        value = match.group(0)
        if sql:
            inner = value[1:-1].replace("''", "'")
            value = repr(inner)
        found.append(value)
        return f" QSTR{len(found) - 1}Q "

    pattern = re.compile(r"'(?:[^']|'')*'") if sql else STRING_RE
    return pattern.sub(keep, text), found


def restore_strings(text: str, found: list[str]) -> str:
    return re.sub(r"\s?QSTR(\d+)Q\s?", lambda m: found[int(m.group(1))], text)


def split_top(text: str, sep: str = ",") -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur).strip())
    return parts


# ------------------------------------------------------------------ expressions (Go, C#, Java, SQL)
def convert_expr(text: str, lang: str, em: Emitter, src: int) -> str:
    sql = lang == "sql"
    body, strings = protect_strings(text.strip(), sql=sql)

    def hero_call(match: re.Match) -> str:
        name = snake(match.group(1))
        if name not in HERO_ALL:
            raise SkinError(f"`{match.group(0).strip()}` is not a Ghostwalk command.", src)
        if lang == "go" and name == "read_sign":
            return '(hero.read_sign() or "")'
        return f"hero.{name}()"

    if sql:
        body = re.sub(r"\bARRAY\s*\[", "[", body, flags=re.I)
        body = re.sub(r"\bIS\s+NOT\s+NULL\b", " is not None ", body, flags=re.I)
        body = re.sub(r"\bIS\s+NULL\b", " is None ", body, flags=re.I)
        body = re.sub(r"\bNULL\b", "None", body, flags=re.I)
        body = re.sub(r"\b(NOT|AND|OR)\b", lambda m: f" {m.group(1).lower()} ", body, flags=re.I)
        body = re.sub(r"\bTRUE\b", "True", body, flags=re.I)
        body = re.sub(r"\bFALSE\b", "False", body, flags=re.I)
        body = body.replace("<>", "!=")
        body = re.sub(r"(?<![<>!=:])=(?!=)", "==", body)

        def sql_call(match: re.Match) -> str:
            name = match.group(1).lower()
            if name in HERO_QUERIES:
                return f"hero.{name}()"
            if name in HERO_COMMANDS:
                raise SkinError(f"{name}() is a procedure. Run it with CALL {name}();", src)
            return match.group(0)

        body = re.sub(r"\b([A-Za-z_]\w*)\s*\(\s*\)", sql_call, body)
    else:
        body = re.sub(r"\bhero\s*\.\s*(\w+)\s*\(\s*\)", hero_call, body)
        if lang == "java":
            body = re.sub(r"\b(\w+)\s*\.\s*run\s*\(\s*\)", r"\1()", body)
            body = re.sub(
                r"(\w+(?:\s*\.\s*\w+)*(?:\s*\([^()]*\))?)\s*\.\s*equals\s*\(([^()]*)\)",
                r"(\1 == \2)",
                body,
            )
            body = convert_java_map(body, src)
            body = re.sub(r"\bnew\s+\w+\s*\[\s*\]\s*\{", "{", body)
        if lang == "csharp":
            body = convert_csharp_dict(body, src)
            body = re.sub(r"\bnew\s*(?:\w+\s*)?\[\s*\]\s*\{", "{", body)
            body = re.sub(r"\bnew\s+List\s*<[^>]*>\s*\{", "{", body)
        if lang == "go":
            body = convert_go_map(body, src)
            body = re.sub(r"\[\s*\]\s*\w+\s*\{", "{", body)
        body = body.strip()
        if body.startswith("{") and body.endswith("}") and ":" not in body:
            body = "[" + body[1:-1] + "]"
        body = re.sub(r"\{([^{}:]*)\}", r"[\1]", body)
        body = body.replace("&&", " and ").replace("||", " or ")
        body = re.sub(r"!(?!=)", " not ", body)
        body = re.sub(r"\btrue\b", "True", body)
        body = re.sub(r"\bfalse\b", "False", body)
        body = re.sub(r"\b(null|nil)\b", "None", body)
        body = re.sub(r"\b(fmt\.Println|Console\.WriteLine|System\.out\.println)\b", "print", body)

    body = re.sub(r"\s+", " ", body).strip()
    check_identifiers(body, em, src)
    return restore_strings(body, strings).strip()


def check_identifiers(body: str, em: Emitter, src: int) -> None:
    for match in re.finditer(r"(?<![\w.])([A-Za-z_]\w*)", body):
        word = match.group(1)
        if re.fullmatch(r"QSTR\d+Q", word):
            continue
        if word in PY_KEYWORDS or word in BUILTINS or word == "hero" or word in em.names:
            continue
        if word.startswith("_sw") or word.startswith("_case"):
            continue
        raise SkinError(f"I don't know what `{word}` is here. Is it declared above?", src)
    for match in re.finditer(r"\.\s*([A-Za-z_]\w*)", body):
        word = match.group(1)
        if word not in HERO_ALL and word not in {"get"}:
            raise SkinError(f"`.{word}` is not supported in Ghostwalk.", src)
    if "__" in body or re.search(r"[;`$\\@]", body):
        raise SkinError("That expression uses characters Ghostwalk does not support.", src)


def convert_java_map(body: str, src: int) -> str:
    def repl(match: re.Match) -> str:
        args = split_top(match.group(1))
        if len(args) % 2:
            raise SkinError("Map.of needs key and value pairs.", src)
        pairs = [f"{args[i]}: {args[i + 1]}" for i in range(0, len(args), 2)]
        return "{" + ", ".join(pairs) + "}"

    return re.sub(r"\bMap\s*\.\s*of\s*\(([^()]*)\)", repl, body)


def convert_csharp_dict(body: str, src: int) -> str:
    def repl(match: re.Match) -> str:
        entries = []
        for item in split_top(match.group(1)):
            m = re.fullmatch(r"\[\s*(.+?)\s*\]\s*=\s*(.+)", item)
            if not m:
                raise SkinError('Write dictionary entries like ["red"] = "left".', src)
            entries.append(f"{m.group(1)}: {m.group(2)}")
        return "{" + ", ".join(entries) + "}"

    return re.sub(r"\bnew\s+Dictionary\s*<[^>]*>\s*(?:\(\s*\))?\s*\{(.*)\}", repl, body)


def convert_go_map(body: str, src: int) -> str:
    return re.sub(r"\bmap\s*\[\s*\w+\s*\]\s*\w+\s*\{", "{", body)


# ------------------------------------------------------------------ brace languages: scanning
def strip_c_comments(code: str) -> str:
    out = []
    for line in code.split("\n"):
        res, i, quote = [], 0, None
        while i < len(line):
            ch = line[i]
            if quote:
                res.append(ch)
                if ch == "\\" and i + 1 < len(line):
                    res.append(line[i + 1])
                    i += 1
                elif ch == quote:
                    quote = None
            elif ch in "\"'`":
                quote = ch
                res.append(ch)
            elif line.startswith("//", i):
                break
            else:
                res.append(ch)
            i += 1
        out.append("".join(res))
    text = "\n".join(out)
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)


def literal_brace(before: str, lang: str) -> bool:
    b = before.rstrip()
    if not b:
        return False
    if b.endswith("->") or b.endswith("=>"):
        return False
    if b.endswith(("=", ">", "(", ",", "[]")):
        return True
    if lang == "go" and (re.search(r"\[\]\w+$", b) or re.search(r"map\[\w+\]\w+$", b)):
        return True
    return False


def scan_braces(code: str, lang: str) -> list[tuple[str, str, int]]:
    """Split code into ('text', s, line), ('open', '{', line), ('close', '}', line)."""
    events: list[tuple[str, str, int]] = []
    buf: list[str] = []
    buf_line = 1
    line = 1
    depth = 0
    i = 0
    n = len(code)

    def flush() -> None:
        nonlocal buf
        text = "".join(buf).strip()
        if text:
            events.append(("text", text, buf_line))
        buf = []

    while i < n:
        ch = code[i]
        if not "".join(buf).strip() and not ch.isspace():
            buf_line = line
        if ch in "\"'`":
            j = i + 1
            while j < n and code[j] != ch:
                if code[j] == "\\":
                    j += 1
                if code[j] == "\n":
                    raise SkinError("A string is missing its closing quote.", line)
                j += 1
            buf.append(code[i : j + 1])
            i = j + 1
            continue
        if ch == "\n":
            line += 1
            if depth == 0:
                flush()
            else:
                buf.append(" ")
            i += 1
            continue
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == ";" and depth == 0 and lang != "go":
            flush()
            i += 1
            continue
        if ch == "{":
            before = "".join(buf)
            pulled = False
            if (
                not before.strip()
                and events
                and events[-1][0] == "text"
                and literal_brace(events[-1][1], lang)
            ):
                _, prev_text, prev_line = events.pop()
                before = prev_text + " "
                buf = [before]
                buf_line = prev_line
                pulled = True
            if pulled or literal_brace(before, lang):
                # consume a literal { ... } (initializer, slice, map, dictionary)
                level = 0
                j = i
                while j < n:
                    c = code[j]
                    if c in "\"'`":
                        k = j + 1
                        while k < n and code[k] != c:
                            k += 1
                        buf.append(code[j : k + 1])
                        j = k + 1
                        continue
                    if c == "\n":
                        line += 1
                        buf.append(" ")
                    else:
                        buf.append(c)
                    if c == "{":
                        level += 1
                    elif c == "}":
                        level -= 1
                        if level == 0:
                            break
                    j += 1
                i = j + 1
                continue
            flush()
            events.append(("open", "{", line))
            i += 1
            continue
        if ch == "}":
            flush()
            events.append(("close", "}", line))
            i += 1
            continue
        buf.append(ch)
        i += 1
    flush()
    return events


# ------------------------------------------------------------------ brace languages: parsing
def range_header(
    var: str, start: str, op: str, end: str, step: str, em: Emitter, lang: str, src: int
) -> str:
    if step not in ("++", "+=1", "+= 1", "=" + var + "+1"):
        raise SkinError("Ghostwalk loops count up by one (i++).", src)
    start_py = convert_expr(start, lang, em, src)
    end_py = convert_expr(end, lang, em, src)
    if op == "<=":
        end_py = f"{end_py} + 1"
    elif op != "<":
        raise SkinError("Use < or <= in the loop condition.", src)
    em.declare(var, src, "int")
    if start_py == "0":
        return f"for {var} in range({end_py}):"
    return f"for {var} in range({start_py}, {end_py}):"


def brace_header(text: str, lang: str, em: Emitter, src: int) -> tuple[str, str] | None:
    """Return (kind, python_header) for a block header, or None if not a header."""
    t = text.strip()
    if lang == "go":
        m = re.fullmatch(r"(\}\s*)?else\s+if\s+(.+)", t)
        if m:
            return "elif", f"elif {convert_expr(m.group(2), lang, em, src)}:"
        if t == "else":
            return "else", "else:"
        m = re.fullmatch(r"if\s+(.+)", t)
        if m:
            return "if", f"if {convert_expr(m.group(1), lang, em, src)}:"
        if t == "for":
            return "loop", "while True:"
        m = re.fullmatch(
            r"for\s+(\w+)\s*:=\s*(.+?)\s*;\s*\1\s*(<=|<)\s*(.+?)\s*;\s*\1\s*(\+\+|\+=\s*1)", t
        )
        if m:
            return "loop", range_header(
                m.group(1),
                m.group(2),
                m.group(3),
                m.group(4),
                m.group(5).replace(" ", ""),
                em,
                lang,
                src,
            )
        m = re.fullmatch(r"for\s+(?:(\w+)\s*(?:,\s*(\w+))?\s*:=\s*)?range\s+(.+)", t)
        if m:
            first, second, target = m.group(1), m.group(2), m.group(3).strip()
            target_py = convert_expr(target, lang, em, src)
            is_int = re.fullmatch(r"\d+", target) or (
                target in em.names and em.kinds.get(target) != "list"
            )
            if is_int:
                var = first if first and first != "_" else "_"
                if var != "_":
                    em.declare(var, src, "int")
                return "loop", f"for {var} in range({target_py}):"
            if second:
                em.declare(second, src)
                if first and first != "_":
                    em.declare(first, src, "int")
                    return "loop", f"for {first}, {second} in enumerate({target_py}):"
                return "loop", f"for {second} in {target_py}:"
            if first and first != "_":
                em.declare(first, src, "int")
                return "loop", f"for {first} in range(len({target_py})):"
            return "loop", f"for _ in {target_py}:"
        m = re.fullmatch(r"for\s+(.+)", t)
        if m and ":=" not in t and ";" not in t:
            return "loop", f"while {convert_expr(m.group(1), lang, em, src)}:"
        m = re.fullmatch(r"switch\s*(.*)", t)
        if m:
            return "switch", m.group(1).strip()
        m = re.fullmatch(r"(\w+)\s*:=\s*func\s*\(\s*\)", t)
        if m:
            em.declare(m.group(1), src, "func")
            return "def", f"def {m.group(1)}():"
        if re.fullmatch(r"func\s+\w+\s*\(\s*\)", t):
            raise SkinError(
                "Inside Ghostwalk your code is already in main(). "
                "Write a closure: hop := func() { ... }",
                src,
            )
        return None

    # C# and Java
    m = re.fullmatch(r"else\s+if\s*\((.+)\)", t)
    if m:
        return "elif", f"elif {convert_expr(m.group(1), lang, em, src)}:"
    if t == "else":
        return "else", "else:"
    m = re.fullmatch(r"if\s*\((.+)\)", t)
    if m:
        return "if", f"if {convert_expr(m.group(1), lang, em, src)}:"
    m = re.fullmatch(r"while\s*\((.+)\)", t)
    if m:
        return "loop", f"while {convert_expr(m.group(1), lang, em, src)}:"
    m = re.fullmatch(
        r"for\s*\(\s*(?:int|var)\s+(\w+)\s*=\s*(.+?)\s*;\s*\1\s*(<=|<)\s*(.+?)\s*;\s*(?:\1\s*(\+\+|\+=\s*1)|\+\+\s*\1)\s*\)",
        t,
    )
    if m:
        return "loop", range_header(
            m.group(1),
            m.group(2),
            m.group(3),
            m.group(4),
            (m.group(5) or "++").replace(" ", ""),
            em,
            lang,
            src,
        )
    if lang == "csharp":
        m = re.fullmatch(r"foreach\s*\(\s*(?:var|int|string|bool)\s+(\w+)\s+in\s+(.+)\)", t)
        if m:
            target = convert_expr(m.group(2), lang, em, src)
            em.declare(m.group(1), src)
            return "loop", f"for {m.group(1)} in {target}:"
        m = re.fullmatch(r"void\s+(\w+)\s*\(\s*\)", t)
        if m:
            em.declare(m.group(1), src, "func")
            return "def", f"def {m.group(1)}():"
    if lang == "java":
        m = re.fullmatch(r"for\s*\(\s*(?:var|int|String|boolean)\s+(\w+)\s*:\s*(.+)\)", t)
        if m:
            target = convert_expr(m.group(2), lang, em, src)
            em.declare(m.group(1), src)
            return "loop", f"for {m.group(1)} in {target}:"
        m = re.fullmatch(r"Runnable\s+(\w+)\s*=\s*\(\s*\)\s*->", t)
        if m:
            em.declare(m.group(1), src, "func")
            return "def", f"def {m.group(1)}():"
    m = re.fullmatch(r"switch\s*\((.+)\)", t)
    if m:
        return "switch", m.group(1)
    return None


def brace_statement(text: str, lang: str, em: Emitter, src: int) -> None:
    t = text.strip().rstrip(";").strip()
    if not t:
        return
    top = em.top()
    in_case = top is not None and top.kind == "case"
    if t == "break":
        if in_case:
            top.extra["ended"] = True
            return
        em.emit("break", src)
        return
    if t == "continue":
        em.emit("continue", src)
        return
    if t == "return":
        em.emit("return", src)
        return
    if in_case and top.extra.get("ended") and lang == "csharp":
        raise SkinError("This code comes after break, so it can never run.", src)
    # hero command or user function call
    m = re.fullmatch(r"hero\s*\.\s*(\w+)\s*\(\s*\)", t)
    if m:
        name = snake(m.group(1))
        if name not in HERO_ALL:
            raise SkinError(f"`hero.{m.group(1)}()` is not a Ghostwalk command.", src)
        expected = {"go": "PascalCase", "csharp": "PascalCase", "java": "camelCase"}[lang]
        if lang == "java" and m.group(1)[0].isupper():
            raise SkinError(
                f"Java methods are camelCase: hero.{m.group(1)[0].lower() + m.group(1)[1:]}()", src
            )
        if lang in ("go", "csharp") and m.group(1)[0].islower():
            raise SkinError(
                f"{'Go' if lang == 'go' else 'C#'} uses {expected}: "
                f"hero.{m.group(1)[0].upper() + m.group(1)[1:]}()",
                src,
            )
        em.emit(f"hero.{name}()", src)
        return
    m = re.fullmatch(r"(\w+)\s*(\.\s*run\s*)?\(\s*\)", t)
    if m and m.group(1) in em.names and em.kinds.get(m.group(1)) == "func":
        if lang == "java" and not m.group(2):
            raise SkinError(f"In Java, run a Runnable with {m.group(1)}.run();", src)
        em.emit(f"{m.group(1)}()", src)
        return
    m = re.fullmatch(r"(fmt\.Println|Console\.WriteLine|System\.out\.println)\s*\((.*)\)", t)
    if m:
        em.emit(f"print({convert_expr(m.group(2), lang, em, src)})", src)
        return
    m = re.fullmatch(r"(\w+)\s*(\+\+|--)", t)
    if m and m.group(1) in em.names:
        em.emit(f"{m.group(1)} {'+' if m.group(2) == '++' else '-'}= 1", src)
        return
    m = re.fullmatch(r"(\w+)\s*([+\-*]=)\s*(.+)", t)
    if m and m.group(1) in em.names:
        em.emit(f"{m.group(1)} {m.group(2)} {convert_expr(m.group(3), lang, em, src)}", src)
        return
    # declarations and assignment
    decl = None
    if lang == "go":
        decl = re.fullmatch(r"(\w+)\s*:=\s*(.+)", t) or re.fullmatch(
            r"var\s+(\w+)(?:\s+[\w\[\]]+)?\s*=\s*(.+)", t
        )
    elif lang == "csharp":
        decl = re.fullmatch(
            r"(?:var|int|string\??|bool|int\[\]|string\[\]|Dictionary\s*<[^>]*>|List\s*<[^>]*>)\s+(\w+)\s*=\s*(.+)",
            t,
        )
    elif lang == "java":
        decl = re.fullmatch(
            r"(?:var|int|String|boolean|int\[\]|String\[\]|Map\s*<[^>]*>|List\s*<[^>]*>)\s+(\w+)\s*=\s*(.+)",
            t,
        )
    if decl:
        value = convert_expr(decl.group(2), lang, em, src)
        raw = decl.group(2).strip()
        kind = (
            "int" if re.fullmatch(r"-?\d+", raw) else ("list" if value.startswith("[") else "any")
        )
        em.declare(decl.group(1), src, kind)
        em.emit(f"{decl.group(1)} = {value}", src)
        return
    m = re.fullmatch(r"(\w+)\s*=\s*(.+)", t)
    if m and m.group(1) in em.names:
        em.emit(f"{m.group(1)} = {convert_expr(m.group(2), lang, em, src)}", src)
        return
    if re.fullmatch(r"hero\.\w+\s*\(.+\)", t):
        raise SkinError("Hero commands take no arguments.", src)
    raise SkinError(f"Ghostwalk does not understand this line yet: {t}", src)


def case_label(text: str, lang: str) -> tuple[str, str | None, str, bool] | None:
    """Return (kind 'case'|'default', values, rest, arrow) for a switch label."""
    t = text.strip()
    m = re.fullmatch(r"case\s+(.+?)\s*->\s*(.*)", t, flags=re.S) if lang == "java" else None
    if m:
        return "case", m.group(1), m.group(2), True
    m = re.fullmatch(r"default\s*->\s*(.*)", t, flags=re.S) if lang == "java" else None
    if m:
        return "default", None, m.group(1), True
    m = re.fullmatch(r"case\s+(.+?)\s*:\s*(.*)", t, flags=re.S)
    if m:
        return "case", m.group(1), m.group(2), False
    m = re.fullmatch(r"default\s*:\s*(.*)", t, flags=re.S)
    if m:
        return "default", None, m.group(1), False
    return None


def close_case(em: Emitter, src: int, lang: str) -> None:
    block = em.close(src, {"case"})
    if lang == "csharp" and block.body and not block.extra.get("ended"):
        raise SkinError(
            "C# needs `break;` at the end of every case (control cannot fall through).", block.src
        )
    if lang == "csharp" and not block.body and not block.extra.get("ended"):
        raise SkinError("C# needs `break;` at the end of every case.", block.src)


def split_inline_header(text: str) -> tuple[str, str] | None:
    """'for (int i = 0; i < 4; i++) hero.Move()' -> ('for (...)', 'hero.Move()')."""
    t = text.strip()
    m = re.match(r"else(?!\s+if\b)\s+(.+)$", t, flags=re.S)
    if m:
        return "else", m.group(1)
    m = re.match(r"(else\s+if|if|while|for|foreach)\s*\(", t)
    if not m:
        return None
    depth = 0
    for index in range(m.end() - 1, len(t)):
        if t[index] == "(":
            depth += 1
        elif t[index] == ")":
            depth -= 1
            if depth == 0:
                rest = t[index + 1 :].strip()
                return (t[: index + 1], rest) if rest else None
    return None


def transpile_braces(code: str, lang: str) -> Transpiled:
    em = Emitter()
    events = scan_braces(strip_c_comments(code), lang)
    i = 0

    def auto_close() -> None:
        while em.top() is not None and em.top().extra.get("auto") and em.top().body:
            em.close(em.top().src)

    def statement(text: str, src: int) -> None:
        nonlocal i
        top = em.top()
        # switch labels
        if top is not None and top.kind in ("switch", "case"):
            label = case_label(text, lang)
            if label is None and top.kind == "switch":
                raise SkinError("Inside a switch, start with a case label.", src)
            if label is not None:
                kind, values, rest, arrow = label
                if top.kind == "case":
                    close_case(em, src, lang)
                sw = em.top()
                var = sw.extra["var"]
                if kind == "default":
                    header = "else:" if sw.extra["branches"] else "if True:"
                else:
                    vals = [convert_expr(v, lang, em, src) for v in split_top(values)]
                    if sw.extra["tagless"]:
                        cond = " or ".join(vals)
                    else:
                        cond = (
                            f"{var} == {vals[0]}"
                            if len(vals) == 1
                            else f"{var} in ({', '.join(vals)},)"
                        )
                    header = f"{'elif' if sw.extra['branches'] else 'if'} {cond}:"
                if sw.extra.get("defaulted"):
                    raise SkinError("Put default last in Ghostwalk switches.", src)
                sw.extra["branches"] += 1
                sw.extra["defaulted"] = kind == "default"
                braced = arrow and rest.strip() == "" and i < len(events) and events[i][0] == "open"
                em.open(header, src, "case", braces=braced, arrow=arrow)
                if braced:
                    i += 1
                elif rest.strip():
                    statement(rest, src)
                return
        header = brace_header(text, lang, em, src)
        if header is None and lang != "go":
            split = split_inline_header(text)
            if split is not None:
                head, rest = split
                statement(head, src)
                if em.top() is None or not em.top().extra.get("auto"):
                    raise SkinError(
                        "Ghostwalk cannot read this line. Try putting the body on its own line.",
                        src,
                    )
                statement(rest, src)
                return
        if header is None:
            brace_statement(text, lang, em, src)
            auto_close()
            return
        kind, py = header
        if kind in ("elif", "else"):
            last = em.last_closed
            if last is None or last.kind not in ("if", "elif"):
                raise SkinError("else needs an if right before it.", src)
        if kind == "switch":
            tagless = py == "" and lang == "go"
            var = em.new_temp("sw")
            if not tagless:
                em.emit(f"{var} = {convert_expr(py, lang, em, src)}", src)
                if lang == "java":
                    em.emit(
                        f"assert {var} is not None, "
                        '"NullPointerException: cannot switch on a null String"',
                        src,
                    )
            if i >= len(events) or events[i][0] != "open":
                raise SkinError("A switch needs { after it.", src)
            if lang == "go" and events[i][2] != src:
                raise SkinError("Go needs { on the same line as the header.", src)
            i += 1
            em.open(
                None,
                src,
                "switch",
                indent=False,
                var=var,
                branches=0,
                tagless=tagless,
                defaulted=False,
            )
            return
        block_kind = "if" if kind in ("if", "elif", "else") else kind
        if i < len(events) and events[i][0] == "open":
            if lang == "go" and events[i][2] != src:
                raise SkinError("Go needs { on the same line as the header.", src)
            i += 1
            em.open(py, src, kind if kind != "else" else "else")
            em.top().kind = kind
        else:
            if lang == "go":
                raise SkinError("Go needs { on the same line as the header.", src)
            em.open(py, src, kind, auto=True)
            if block_kind == "def":
                raise SkinError("A method body needs braces { }.", src)

    while i < len(events):
        kind, text, src = events[i]
        i += 1
        if kind == "text":
            statement(text, src)
        elif kind == "open":
            raise SkinError("This { does not belong to an if, loop, or function.", src)
        else:  # close
            top = em.top()
            if top is None:
                raise SkinError("There is an extra } here.", src)
            if top.kind == "case" and not top.extra.get("braces"):
                close_case(em, src, lang)
                top = em.top()
            if top is not None and top.kind == "switch":
                if not top.extra["branches"]:
                    em.emit("pass", src)
                em.close(src)
                em.last_closed = None
            else:
                em.close(src)
            auto_close()
    return em.finish(lang)


# ------------------------------------------------------------------ Bash
BASH_QUERIES = {
    "blocked": "is_blocked",
    "is_blocked": "is_blocked",
    "at_goal": "at_goal",
    "on_gem": "on_gem",
    "on_soil": "on_soil",
}


def bash_split(line: str, src: int) -> list[str]:
    parts, cur, i, depth, quote = [], [], 0, 0, None
    while i < len(line):
        ch = line[i]
        if quote:
            cur.append(ch)
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
            cur.append(ch)
        elif ch == "#" and depth == 0 and (i == 0 or line[i - 1].isspace()):
            break
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == ";" and depth <= 0:
            if line.startswith(";;", i):
                parts.append("".join(cur))
                parts.append(";;")
                cur = []
                i += 2
                continue
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if quote:
        raise SkinError("A string is missing its closing quote.", src)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def bash_value(word: str, em: Emitter, src: int) -> str:
    w = word.strip()
    if len(w) >= 2 and w[0] == w[-1] == '"':
        inner = w[1:-1]
        if re.fullmatch(r"\$\{?\w+(\[@\])?\}?|\$\(\s*\w+\s*\)", inner):
            return bash_value(inner, em, src)
        return repr(inner)
    if len(w) >= 2 and w[0] == w[-1] == "'":
        return repr(w[1:-1])
    m = re.fullmatch(r"\$\(\s*(\w+)\s*\)", w)
    if m:
        name = BASH_QUERIES.get(m.group(1), m.group(1))
        if name in HERO_QUERIES:
            return f"hero.{name}()"
        raise SkinError(f"$({m.group(1)}) does not print anything Ghostwalk can read.", src)
    m = re.fullmatch(r"\$\{?(\w+)\}?", w)
    if m:
        if m.group(1) not in em.names:
            raise SkinError(f"${m.group(1)} is not set yet.", src)
        return m.group(1)
    if re.fullmatch(r"-?\d+", w):
        return w
    if re.fullmatch(r"[\w.-]+", w):
        if w in em.names:
            return w
        return repr(w)
    raise SkinError(f"Ghostwalk cannot read the value {w}", src)


def bash_condition(text: str, em: Emitter, src: int) -> str:
    t = text.strip()
    parts = re.split(r"\s*(&&|\|\|)\s*", t)
    out = []
    for part in parts:
        if part == "&&":
            out.append("and")
        elif part == "||":
            out.append("or")
        else:
            out.append(bash_simple(part, em, src))
    return " ".join(out)


def bash_simple(text: str, em: Emitter, src: int) -> str:
    t = text.strip()
    if t.startswith("!"):
        return f"not {bash_simple(t[1:], em, src)}"
    if t in ("true", ":"):
        return "True"
    if t == "false":
        return "False"
    m = re.fullmatch(r"hero_(\w+)\s*\(\s*\)", t)
    if m:
        t = m.group(1)
    if t in BASH_QUERIES:
        return f"hero.{BASH_QUERIES[t]}()"
    m = re.fullmatch(r"\[\[?\s*(.+?)\s*\]?\]", t)
    if m:
        inner = m.group(1)
        m2 = re.fullmatch(r"-([nz])\s+(\S+)", inner)
        if m2:
            value = bash_value(m2.group(2), em, src)
            return f"bool({value})" if m2.group(1) == "n" else f"not {value}"
        m2 = re.fullmatch(r"(\S+)\s+(==|=|!=|-eq|-ne|-lt|-le|-gt|-ge)\s+(\S+)", inner)
        if m2:
            ops = {
                "==": "==",
                "=": "==",
                "!=": "!=",
                "-eq": "==",
                "-ne": "!=",
                "-lt": "<",
                "-le": "<=",
                "-gt": ">",
                "-ge": ">=",
            }
            left = bash_value(m2.group(1), em, src)
            right = bash_value(m2.group(3), em, src)
            return f"{left} {ops[m2.group(2)]} {right}"
    m = re.fullmatch(r"\(\(\s*(.+?)\s*\)\)", t)
    if m:
        expr = re.sub(
            r"\$\(\s*(\w+)\s*\)",
            lambda x: f"hero.{BASH_QUERIES.get(x.group(1), x.group(1))}()",
            m.group(1),
        )
        expr = re.sub(r"\$\{?(\w+)\}?", r"\1", expr)
        check_identifiers(expr, em, src)
        return expr
    raise SkinError(
        f"Ghostwalk cannot test `{t}`. Try a check like blocked, at_goal, or on_gem.", src
    )


def bash_command(text: str, em: Emitter, src: int) -> None:
    t = text.strip()
    m = re.fullmatch(r"(.+?)\s*(&&|\|\|)\s*([\w ]+)", t)
    if m and not t.startswith("[["):
        cond = bash_condition(m.group(1), em, src)
        if m.group(2) == "||":
            cond = f"not ({cond})"
        em.open(f"if {cond}:", src, "if")
        bash_command(m.group(3), em, src)
        em.close(src)
        return
    m = re.fullmatch(r"hero_(\w+)\s*\(\s*\)", t)  # older Ghostwalk syntax, still accepted
    if m:
        t = m.group(1)
    if t in HERO_COMMANDS:
        em.emit(f"hero.{t}()", src)
        return
    if t in BASH_QUERIES or t == "read_sign" or t == "crops_held":
        em.emit(f"hero.{BASH_QUERIES.get(t, t)}()", src)
        return
    if t in em.names and em.kinds.get(t) == "func":
        em.emit(f"{t}()", src)
        return
    if t in ("break", "continue"):
        em.emit(t, src)
        return
    m = re.fullmatch(r"echo\s+(.*)", t)
    if m:
        em.emit(
            f"print({bash_value(m.group(1), em, src) if m.group(1).strip() else repr('')})", src
        )
        return
    m = re.fullmatch(r"(?:local\s+)?(\w+)=\((.*)\)", t)
    if m:
        items = [bash_value(w, em, src) for w in m.group(2).split()]
        em.declare(m.group(1), src, "list")
        em.emit(f"{m.group(1)} = [{', '.join(items)}]", src)
        return
    m = re.fullmatch(r"(?:local\s+)?(\w+)=(\S*)", t)
    if m:
        value = bash_value(m.group(2), em, src) if m.group(2) else "''"
        em.declare(m.group(1), src, "int" if re.fullmatch(r"-?\d+", m.group(2)) else "any")
        em.emit(f"{m.group(1)} = {value}", src)
        return
    m = re.fullmatch(r"\(\(\s*(\w+)\s*(\+\+|--)\s*\)\)", t)
    if m and m.group(1) in em.names:
        em.emit(f"{m.group(1)} {'+' if m.group(2) == '++' else '-'}= 1", src)
        return
    if re.fullmatch(r"\w+", t):
        raise SkinError(f"command not found: {t}", src)
    raise SkinError(f"Ghostwalk does not understand this line yet: {t}", src)


def transpile_bash(code: str) -> Transpiled:
    em = Emitter()
    for src, raw in enumerate(code.split("\n"), start=1):
        if raw.strip().startswith("#!"):
            continue
        for piece in bash_split(raw, src):
            bash_piece(piece, em, src)
    return em.finish("bash")


def bash_piece(piece: str, em: Emitter, src: int) -> None:
    t = piece.strip()
    if not t:
        return
    for kw in ("do", "then"):
        if t == kw:
            top = em.top()
            if top is None or top.extra.get("waiting") != kw:
                raise SkinError(f"`{kw}` is in an unexpected place.", src)
            top.extra["waiting"] = None
            return
        if t.startswith(kw + " "):
            bash_piece(kw, em, src)
            bash_piece(t[len(kw) + 1 :], em, src)
            return
    top = em.top()
    if top is not None and top.extra.get("waiting"):
        raise SkinError(f"Missing `{top.extra['waiting']}` before this line.", src)
    if t == ";;":
        if top is None or top.kind != "case":
            raise SkinError(";; only belongs inside a case.", src)
        em.close(src)
        return
    if t in ("done", "fi", "esac", "}"):
        expect = {
            "done": {"loop"},
            "fi": {"if", "elif", "else"},
            "esac": {"case", "switch"},
            "}": {"def"},
        }[t]
        if t == "esac":
            if top is not None and top.kind == "case":
                em.close(src)
            em.close(src, {"switch"}, "case")
            em.last_closed = None
            return
        em.close(src, expect, t)
        return
    if t == "else" or t.startswith("else "):
        em.close(src, {"if", "elif"}, "if")
        em.open("else:", src, "else")
        rest = t[4:].strip()
        if rest:
            bash_piece(rest, em, src)
        return
    m = re.fullmatch(r"elif\s+(.+)", t)
    if m:
        em.close(src, {"if", "elif"}, "if")
        em.open(f"elif {bash_condition(m.group(1), em, src)}:", src, "elif", waiting="then")
        return
    m = re.fullmatch(r"if\s+(.+)", t)
    if m:
        em.open(f"if {bash_condition(m.group(1), em, src)}:", src, "if", waiting="then")
        return
    m = re.fullmatch(r"(while|until)\s+(.+)", t)
    if m:
        cond = bash_condition(m.group(2), em, src)
        if m.group(1) == "until":
            cond = f"not ({cond})" if " " in cond else f"not {cond}"
        em.open(f"while {cond}:", src, "loop", waiting="do")
        return
    m = re.fullmatch(
        r"for\s+\(\(\s*(\w+)\s*=\s*(\S+?)\s*;\s*\1\s*(<=|<)\s*(\S+?)\s*;\s*\1\+\+\s*\)\)", t
    )
    if m:
        start = bash_value(m.group(2), em, src)
        end = bash_value(
            m.group(4) if m.group(4).startswith("$") or m.group(4).isdigit() else "$" + m.group(4),
            em,
            src,
        )
        if m.group(3) == "<=":
            end = f"{end} + 1"
        em.declare(m.group(1), src, "int")
        rng = f"range({end})" if start == "0" else f"range({start}, {end})"
        em.open(f"for {m.group(1)} in {rng}:", src, "loop", waiting="do")
        return
    m = re.fullmatch(r"for\s+(\w+)\s+in\s+(.+)", t)
    if m:
        var, target = m.group(1), m.group(2).strip()
        b = re.fullmatch(r"\{(-?\d+)\.\.(-?\d+)\}", target)
        s = re.fullmatch(r"\$\(\s*seq\s+(\d+)(?:\s+(\d+))?\s*\)", target)
        a = re.fullmatch(r'"?\$\{(\w+)\[@\]\}"?', target)
        if b:
            seq = f"range({b.group(1)}, {int(b.group(2)) + 1})"
        elif s:
            lo, hi = (s.group(1), s.group(2)) if s.group(2) else ("1", s.group(1))
            seq = f"range({lo}, {int(hi) + 1})"
        elif a:
            if a.group(1) not in em.names:
                raise SkinError(f"The array {a.group(1)} is not set yet.", src)
            seq = a.group(1)
        else:
            seq = "[" + ", ".join(bash_value(w, em, src) for w in target.split()) + "]"
        em.declare(var, src, "int")
        em.open(f"for {var} in {seq}:", src, "loop", waiting="do")
        return
    m = re.fullmatch(r"case\s+(.+?)\s+in", t)
    if m:
        var = em.new_temp("case")
        em.emit(f"{var} = {bash_value(m.group(1), em, src)}", src)
        em.open(None, src, "switch", indent=False, var=var, branches=0)
        return
    if top is not None and top.kind in ("switch", "case"):
        m = re.fullmatch(r"\(?([^()]+?)\)\s*(.*)", t)
        if (
            m
            and (top.kind == "switch" or not t.startswith("("))
            and not re.fullmatch(r"\w+\s*\(\s*\)", t)
        ):
            if top.kind == "case":
                em.close(src)
            sw = em.top()
            pattern = m.group(1).strip()
            if pattern == "*":
                header = "else:" if sw.extra["branches"] else "if True:"
            else:
                values = [bash_value(p.strip(), em, src) for p in pattern.split("|")]
                cond = (
                    f"{sw.extra['var']} == {values[0]}"
                    if len(values) == 1
                    else f"{sw.extra['var']} in ({', '.join(values)},)"
                )
                header = f"{'elif' if sw.extra['branches'] else 'if'} {cond}:"
            sw.extra["branches"] += 1
            em.open(header, src, "case")
            if m.group(2).strip():
                bash_piece(m.group(2), em, src)
            return
        if top.kind == "switch":
            raise SkinError("Inside case, start with a pattern like red)", src)
    m = re.fullmatch(r"(?:function\s+)?(\w+)\s*\(\s*\)\s*\{\s*(.*)", t) or re.fullmatch(
        r"function\s+(\w+)\s*\{\s*(.*)", t
    )
    if m:
        em.declare(m.group(1), src, "func")
        em.open(f"def {m.group(1)}():", src, "def")
        if m.group(2).strip():
            bash_piece(m.group(2), em, src)
        return
    if t.endswith("}") and em.top() is not None and em.top().kind == "def" and t != "}":
        bash_piece(t[:-1], em, src)
        bash_piece("}", em, src)
        return
    bash_command(t, em, src)


# ------------------------------------------------------------------ SQL (PL/pgSQL)
def sql_split(line: str) -> list[str]:
    parts, cur, quote = [], [], False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'":
            quote = not quote
            cur.append(ch)
        elif not quote and line.startswith("--", i):
            break
        elif ch == ";" and not quote:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def transpile_sql(code: str) -> Transpiled:
    em = Emitter()
    state = {"declare": False}
    for src, raw in enumerate(code.split("\n"), start=1):
        for piece in sql_split(raw):
            sql_piece(piece, em, src, state)
    return em.finish("sql")


SQL_FILLER = re.compile(r"^(DO\s+\$\$|\$\$|BEGIN|END\s*\$\$|DECLARE)$", re.I)


def sql_piece(piece: str, em: Emitter, src: int, state: dict) -> None:
    t = re.sub(r"\s+", " ", piece.strip())
    u = t.upper()
    if not t:
        return
    m = re.match(r"^DO\s+\$\$\s*(.*)$", t, flags=re.I)
    if m:
        state["declare"] = False
        if m.group(1):
            sql_piece(m.group(1), em, src, state)
        return
    if u == "DECLARE":
        state["declare"] = True
        return
    if u in ("BEGIN", "$$") or re.fullmatch(r"END\s*\$\$( LANGUAGE PLPGSQL)?", u):
        state["declare"] = False
        return
    if state["declare"]:
        m = re.fullmatch(r"(\w+)\s+[\w\[\]]+(?:\s*(?::=|=|DEFAULT)\s*(.+))?", t, flags=re.I)
        if not m:
            raise SkinError("In DECLARE, write: name type := value;", src)
        value = convert_expr(m.group(2), "sql", em, src) if m.group(2) else "None"
        kind = "int" if m.group(2) and re.fullmatch(r"-?\d+", m.group(2).strip()) else "any"
        em.declare(m.group(1).lower(), src, kind)
        em.emit(f"{m.group(1).lower()} = {value}", src)
        return
    m = re.fullmatch(r"(?:CALL|PERFORM|SELECT)\s+(\w+)\s*\(\s*\)", t, flags=re.I)
    if m:
        name = m.group(1).lower()
        if name not in HERO_ALL:
            raise SkinError(f"{m.group(1)}() is not a Ghostwalk procedure.", src)
        em.emit(f"hero.{name}()", src)
        return
    if re.fullmatch(r"\w+\s*\(\s*\)", t) and t.split("(")[0].lower() in HERO_COMMANDS:
        raise SkinError(f"Procedures need CALL in front: CALL {t};", src)
    m = re.fullmatch(r"FOR (\w+) IN (REVERSE )?(.+?)\.\.(.+?) LOOP", t, flags=re.I)
    if m:
        if m.group(2):
            raise SkinError("Ghostwalk FOR loops count up.", src)
        lo = convert_expr(m.group(3), "sql", em, src)
        hi = convert_expr(m.group(4), "sql", em, src)
        em.declare(m.group(1).lower(), src, "int")
        em.open(f"for {m.group(1).lower()} in range({lo}, {hi} + 1):", src, "loop")
        return
    m = re.fullmatch(r"FOREACH (\w+) IN ARRAY (.+?) LOOP", t, flags=re.I)
    if m:
        var = m.group(1).lower()
        if var not in em.names:
            raise SkinError(f"Declare {var} in the DECLARE section before FOREACH uses it.", src)
        em.open(f"for {var} in {convert_expr(m.group(2), 'sql', em, src)}:", src, "loop")
        return
    m = re.fullmatch(r"WHILE (.+?) LOOP", t, flags=re.I)
    if m:
        em.open(f"while {convert_expr(m.group(1), 'sql', em, src)}:", src, "loop")
        return
    if u == "LOOP":
        em.open("while True:", src, "loop")
        return
    m = re.fullmatch(r"EXIT(?: WHEN (.+))?", t, flags=re.I)
    if m:
        if m.group(1):
            em.open(f"if {convert_expr(m.group(1), 'sql', em, src)}:", src, "if")
            em.emit("break", src)
            em.close(src)
        else:
            em.emit("break", src)
        return
    if u in ("END LOOP",):
        em.close(src, {"loop"}, "LOOP")
        return
    m = re.fullmatch(r"IF (.+?) THEN(?: (.+))?", t, flags=re.I)
    if m:
        em.open(f"if {convert_expr(m.group(1), 'sql', em, src)}:", src, "if")
        if m.group(2):
            sql_piece(m.group(2), em, src, state)
        return
    m = re.fullmatch(r"ELSIF (.+?) THEN(?: (.+))?", t, flags=re.I)
    if m:
        em.close(src, {"if", "elif"}, "IF")
        em.open(f"elif {convert_expr(m.group(1), 'sql', em, src)}:", src, "elif")
        if m.group(2):
            sql_piece(m.group(2), em, src, state)
        return
    top = em.top()
    m = re.fullmatch(r"ELSE(?: (.+))?", t, flags=re.I)
    if m:
        if top is not None and top.kind == "case":
            em.close(src)
            sw = em.top()
            sw.extra["has_else"] = True
            em.open("else:" if sw.extra["branches"] else "if True:", src, "case")
        else:
            em.close(src, {"if", "elif"}, "IF")
            em.open("else:", src, "else")
        if m.group(1):
            sql_piece(m.group(1), em, src, state)
        return
    if u == "END IF":
        em.close(src, {"if", "elif", "else"}, "IF")
        return
    m = re.fullmatch(r"CASE (.+)", t, flags=re.I)
    if m:
        var = em.new_temp("case")
        em.emit(f"{var} = {convert_expr(m.group(1), 'sql', em, src)}", src)
        em.open(None, src, "switch", indent=False, var=var, branches=0, has_else=False)
        return
    m = re.fullmatch(r"WHEN (.+?) THEN(?: (.+))?", t, flags=re.I)
    if m:
        if top is None or top.kind not in ("switch", "case"):
            raise SkinError("WHEN belongs inside a CASE.", src)
        if top.kind == "case":
            em.close(src)
        sw = em.top()
        values = [convert_expr(v, "sql", em, src) for v in split_top(m.group(1))]
        cond = (
            f"{sw.extra['var']} == {values[0]}"
            if len(values) == 1
            else f"{sw.extra['var']} in ({', '.join(values)},)"
        )
        em.open(f"{'elif' if sw.extra['branches'] else 'if'} {cond}:", src, "case")
        sw.extra["branches"] += 1
        if m.group(2):
            sql_piece(m.group(2), em, src, state)
        return
    if u == "END CASE":
        if top is not None and top.kind == "case":
            em.close(src)
        sw = em.close(src, {"switch"}, "CASE")
        if not sw.extra.get("has_else"):
            em.emit("else:" if sw.extra["branches"] else "if True:", src)
            em.lines.append(
                INDENT * (em.depth + 1)
                + 'assert False, "case not found: CASE has no WHEN for this value and no ELSE"'
            )
            em.map.append(src)
        em.last_closed = None
        return
    if u == "NULL":
        em.emit("pass", src)
        return
    m = re.fullmatch(r"RAISE NOTICE (.+)", t, flags=re.I)
    if m:
        em.emit(f"print({convert_expr(m.group(1).split(',')[0], 'sql', em, src)})", src)
        return
    m = re.fullmatch(r"(\w+)\s*:=\s*(.+)", t)
    if m:
        name = m.group(1).lower()
        if name not in em.names:
            raise SkinError(f"Declare {name} in the DECLARE section first.", src)
        em.emit(f"{name} = {convert_expr(m.group(2), 'sql', em, src)}", src)
        return
    raise SkinError(f"Ghostwalk does not understand this line yet: {t}", src)


# ------------------------------------------------------------------ entry point
def transpile(language: str, code: str) -> Transpiled:
    lang = (language or "python").lower()
    code = str(code or "").replace("\r\n", "\n").replace("\t", "    ")
    if lang == "python":
        lines = code.split("\n")
        return Transpiled(code, list(range(1, len(lines) + 1)))
    if lang == "bash":
        return transpile_bash(code)
    if lang == "sql":
        return transpile_sql(code)
    if lang in ("go", "csharp", "java"):
        return transpile_braces(code, lang)
    raise SkinError(f"Ghostwalk does not translate {language}.")


def run(world, level: dict, language: str, code: str) -> dict:
    """Translate and run, mapping every line number back to the learner's code."""
    try:
        t = transpile(language, code)
    except SkinError as exc:
        return {
            "ok": False,
            "error": exc.message,
            "error_line": exc.line,
            "trace": [],
            "actions": [],
        }
    result = world.run_learner_code(level, t.python)
    result["error_line"] = t.source_line(result.get("error_line"))
    for step in result.get("trace", []):
        step["line"] = t.source_line(step.get("line"))
    for action in result.get("actions", []):
        if isinstance(action, dict):
            action["line"] = t.source_line(action.get("line"))
    return result


def skin_to_python(language: str, code: str) -> str:
    """Backward-compatible helper for existing callers (admin "Test solution").

    JavaScript is not translated: it runs natively on world.js in the browser.
    """
    if (language or "python").lower() == "javascript":
        raise SkinError("JavaScript solutions are tested in the browser with world.js.")
    return transpile(language, code).python
