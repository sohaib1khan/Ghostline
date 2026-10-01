/** Keep in sync with playground/app/templates.py PYTHON_FLASK. */
export const PYTHON_FLASK_STARTER = `"""Flask demo using the test client — no listening port.

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
`;
