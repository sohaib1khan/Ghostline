"""Docker Engine client over the unix socket."""

from __future__ import annotations

import asyncio
import base64
import json
import time

import httpx

SOCKET = "/var/run/docker.sock"
WORKSPACE = "/workspace"


class DockerError(Exception):
    def __init__(self, status: int, detail: str):
        self.status = status
        self.detail = detail
        super().__init__(detail)


def _client() -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(uds=SOCKET)
    return httpx.AsyncClient(transport=transport, base_url="http://docker", timeout=60.0)


async def ping() -> bool:
    try:
        async with _client() as client:
            response = await client.get("/_ping")
            return response.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


async def create_and_start(
    *,
    name: str,
    image: str,
    memory_mb: int,
    cpus: float,
    workspace_mb: int,
    labels: dict[str, str],
) -> str:
    body = {
        "Image": image,
        "Hostname": "playground",
        "User": "1000:1000",
        "WorkingDir": WORKSPACE,
        "NetworkDisabled": True,
        "HostConfig": {
            "Memory": memory_mb * 1024 * 1024,
            "MemorySwap": memory_mb * 1024 * 1024,
            "NanoCpus": int(cpus * 1_000_000_000),
            "PidsLimit": 64,
            "ReadonlyRootfs": True,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Tmpfs": {
                WORKSPACE: f"rw,exec,nosuid,size={workspace_mb}m,uid=1000,gid=1000",
                "/tmp": "rw,nosuid,size=16m,uid=1000,gid=1000",
            },
            "AutoRemove": False,
        },
        "Labels": labels,
        "Cmd": ["sleep", "infinity"],
    }
    async with _client() as client:
        created = await client.post("/containers/create", params={"name": name}, json=body)
        if created.status_code == 404:
            pull = await client.post("/images/create", params={"fromImage": image})
            if pull.status_code not in {200, 201}:
                raise DockerError(502, "Worker image is missing and could not be pulled")
            created = await client.post("/containers/create", params={"name": name}, json=body)
        if created.status_code not in {200, 201}:
            raise DockerError(created.status_code, _message(created) or "Could not create worker")
        container_id = created.json()["Id"]
        started = await client.post(f"/containers/{container_id}/start")
        if started.status_code not in {204, 304}:
            await client.delete(f"/containers/{container_id}", params={"force": "true"})
            raise DockerError(started.status_code, _message(started) or "Could not start worker")
        return container_id


async def destroy(container_id: str) -> None:
    async with _client() as client:
        await client.delete(f"/containers/{container_id}", params={"force": "true", "v": "true"})


async def inspect_running(container_id: str) -> bool:
    async with _client() as client:
        response = await client.get(f"/containers/{container_id}/json")
        if response.status_code != 200:
            return False
        return bool(response.json().get("State", {}).get("Running"))


async def exec_run(
    container_id: str,
    cmd: list[str],
    *,
    timeout_seconds: int,
    workdir: str = WORKSPACE,
) -> dict:
    async with _client() as client:
        created = await client.post(
            f"/containers/{container_id}/exec",
            json={
                "AttachStdout": True,
                "AttachStderr": True,
                "Cmd": cmd,
                "WorkingDir": workdir,
                "User": "1000:1000",
            },
        )
        if created.status_code not in {200, 201}:
            raise DockerError(created.status_code, _message(created) or "Could not start command")
        exec_id = created.json()["Id"]
        started = await client.post(
            f"/exec/{exec_id}/start",
            json={"Detach": False, "Tty": False},
            timeout=timeout_seconds + 2,
        )
        if started.status_code != 200:
            raise DockerError(started.status_code, _message(started) or "Command failed to start")
        output = _demux(started.content)
        # Wait until Docker marks the exec finished before reading ExitCode.
        exit_code = 1
        deadline = time.time() + max(1, timeout_seconds)
        while time.time() < deadline:
            inspected = await client.get(f"/exec/{exec_id}/json")
            if inspected.status_code != 200:
                break
            body = inspected.json()
            if not body.get("Running", False):
                exit_code = int(body.get("ExitCode") if body.get("ExitCode") is not None else 1)
                break
            await asyncio.sleep(0.05)
        return {"exit_code": exit_code, "output": output[:50_000]}


async def write_file(container_id: str, rel_path: str, content: str) -> None:
    safe = _safe_rel(rel_path)
    data = content.encode("utf-8")
    if len(data) > 200_000:
        raise DockerError(400, "File is too large for the playground")
    parent = "/".join(safe.split("/")[:-1])
    if parent:
        await mkdir(container_id, parent)
    encoded = base64.b64encode(data).decode("ascii")
    # DECISION: put_archive fails when the container rootfs is read-only, even
    # with a writable tmpfs workspace. Write through exec instead.
    script = (
        "import base64,sys\n"
        f"path={WORKSPACE!r}+'/'+{safe!r}\n"
        f"open(path,'wb').write(base64.b64decode({encoded!r}))\n"
    )
    result = await exec_run(container_id, ["python3", "-c", script], timeout_seconds=5)
    if result["exit_code"] != 0:
        raise DockerError(400, result["output"] or "Could not write file")


async def read_file(container_id: str, rel_path: str) -> str:
    safe = _safe_rel(rel_path)
    result = await exec_run(
        container_id,
        ["python3", "-c", _read_script(safe)],
        timeout_seconds=5,
    )
    if result["exit_code"] != 0:
        raise DockerError(404, "File not found")
    raw = result["output"].strip()
    try:
        return base64.b64decode(raw).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise DockerError(400, "File is not valid text") from exc


async def list_tree(container_id: str) -> list[dict]:
    script = (
        "import json,os\n"
        "root='/workspace'\n"
        "out=[]\n"
        "for dirpath,_,files in os.walk(root):\n"
        "  rel=os.path.relpath(dirpath, root)\n"
        "  if rel=='.': rel=''\n"
        "  if rel and not rel.startswith('.'):\n"
        "    out.append({'path':rel.replace(chr(92),'/'),'type':'dir'})\n"
        "  for name in files:\n"
        "    if name.startswith('.'): continue\n"
        "    path=(rel+'/'+name if rel else name).replace(chr(92),'/')\n"
        "    out.append({'path':path,'type':'file'})\n"
        "print(json.dumps(out))\n"
    )
    result = await exec_run(container_id, ["python3", "-c", script], timeout_seconds=5)
    if result["exit_code"] != 0:
        raise DockerError(500, "Could not list files")
    try:
        return json.loads(result["output"].strip() or "[]")
    except json.JSONDecodeError as exc:
        raise DockerError(500, "Could not list files") from exc


async def mkdir(container_id: str, rel_path: str) -> None:
    safe = _safe_rel(rel_path)
    result = await exec_run(
        container_id,
        ["mkdir", "-p", f"{WORKSPACE}/{safe}"],
        timeout_seconds=5,
    )
    if result["exit_code"] != 0:
        raise DockerError(400, result["output"] or "Could not create folder")


async def delete_path(container_id: str, rel_path: str) -> None:
    safe = _safe_rel(rel_path)
    if safe in {"", ".", "main.py", "README.md"}:
        # Allow deleting main later; block empty path.
        if safe in {"", "."}:
            raise DockerError(400, "Cannot delete the workspace root")
    result = await exec_run(
        container_id,
        ["rm", "-rf", f"{WORKSPACE}/{safe}"],
        timeout_seconds=5,
    )
    if result["exit_code"] != 0:
        raise DockerError(400, result["output"] or "Could not delete path")


def _safe_rel(path: str) -> str:
    cleaned = (path or "").replace("\\", "/").strip()
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")
    if cleaned.startswith("workspace/"):
        cleaned = cleaned[len("workspace/") :]
    parts = [part for part in cleaned.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise DockerError(400, "Path is not allowed")
    if any(part.startswith(".") for part in parts):
        raise DockerError(400, "Hidden paths are not allowed")
    joined = "/".join(parts)
    if len(joined) > 180:
        raise DockerError(400, "Path is too long")
    return joined


def _read_script(safe: str) -> str:
    return (
        "import base64,sys\n"
        f"path={WORKSPACE!r}+'/'+{safe!r}\n"
        "data=open(path,'rb').read()\n"
        "sys.stdout.write(base64.b64encode(data).decode())\n"
    )


def _message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(payload, dict):
        return str(payload.get("message") or payload.get("detail") or "")[:300]
    return str(payload)[:300]


def _demux(payload: bytes) -> str:
    """Decode Docker multiplexed stdout/stderr streams into text."""
    if not payload:
        return ""
    # When Tty is false, Docker prefixes 8-byte headers per chunk.
    if len(payload) >= 8 and payload[0] in {0, 1, 2}:
        chunks: list[bytes] = []
        offset = 0
        while offset + 8 <= len(payload):
            size = int.from_bytes(payload[offset + 4 : offset + 8], "big")
            start = offset + 8
            end = start + size
            chunks.append(payload[start:end])
            offset = end
        text = b"".join(chunks)
    else:
        text = payload
    return text.decode("utf-8", errors="replace")
