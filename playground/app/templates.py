"""Seeded starter projects under templates/."""

from __future__ import annotations

README = """# Ghostline playground

Temporary workspace — destroyed after 12 hours unless you extend.

## Templates

Each starter lives in its own folder:

| Folder | What |
|---|---|
| `templates/python-hello` | Plain Python |
| `templates/python-flask` | Flask test client (install `flask` first) |
| `templates/javascript-hello` | Node.js |
| `templates/bash-hello` | Bash |
| `templates/web-hello` | HTML/CSS/JS — open **Browser** |

Installed packages stay outside the file tree (`/tmp`). The worker has no network and no published ports.
"""

PYTHON_HELLO = 'print("hello from the playground")\n'

PYTHON_FLASK = '''"""Flask demo using the test client — no listening port.

Install: Packages → pip → flask → Install, then Run this file.

Do NOT call app.run() / flask run. The worker has no published ports, and a
server will hang until killed (and can leave "Address already in use").
"""

from flask import Flask

app = Flask(__name__)


@app.get("/")
def home():
    return {"ok": True, "message": "hello from flask"}


@app.get("/greet/<name>")
def greet(name: str):
    return {"hello": name}


if __name__ == "__main__":
    # In-process requests only — never binds a TCP port.
    client = app.test_client()
    root = client.get("/")
    greet_resp = client.get("/greet/playground")
    print("GET /", root.status_code, root.get_json())
    print("GET /greet/playground", greet_resp.status_code, greet_resp.get_json())
'''

JAVASCRIPT_HELLO = 'console.log("hello from the playground");\n'

BASH_HELLO = '#!/usr/bin/env bash\necho "hello from the playground"\n'

WEB_INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Playground</title>
  <link rel="stylesheet" href="style.css" />
</head>
<body>
  <main>
    <h1>Hello from the playground</h1>
    <p>Edit files in <code>templates/web-hello</code>, then refresh Browser.</p>
    <button type="button" id="go">Click me</button>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""

WEB_STYLE = """html, body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #f4f1ea;
  color: #1c1917;
}
main {
  max-width: 36rem;
  margin: 3rem auto;
  padding: 1.5rem;
}
h1 { font-size: 1.75rem; margin-bottom: 0.5rem; }
button {
  margin-top: 1rem;
  padding: 0.5rem 1rem;
  border: 0;
  border-radius: 0.5rem;
  background: #0f766e;
  color: #fff;
  cursor: pointer;
}
"""

WEB_APP = """const btn = document.getElementById("go");
if (btn) {
  btn.addEventListener("click", () => {
    btn.textContent = "It works";
  });
}
"""

# path → content
SEED_FILES: dict[str, str] = {
    "README.md": README,
    "templates/python-hello/main.py": PYTHON_HELLO,
    "templates/python-flask/app.py": PYTHON_FLASK,
    "templates/javascript-hello/main.js": JAVASCRIPT_HELLO,
    "templates/bash-hello/main.sh": BASH_HELLO,
    "templates/web-hello/index.html": WEB_INDEX,
    "templates/web-hello/style.css": WEB_STYLE,
    "templates/web-hello/app.js": WEB_APP,
}

DEFAULT_OPEN = "templates/python-hello/main.py"
WEB_PREVIEW = "templates/web-hello/index.html"
