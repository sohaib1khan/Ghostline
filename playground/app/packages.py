"""Manager-side package download. Workers stay NetworkDisabled."""

from __future__ import annotations

import asyncio
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app import docker_api

# Strict names only — no URLs, no VCS, no path tricks.
_PIP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$")
_PIP_SPEC = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]{0,80})"
    r"(?P<op>==|>=|<=|~=)?(?P<ver>[A-Za-z0-9._*]{0,40})?$"
)
_NPM_NAME = re.compile(
    r"^(?:@[A-Za-z0-9][A-Za-z0-9._-]{0,40}/)?[A-Za-z0-9][A-Za-z0-9._-]{0,80}$"
)
_NPM_SPEC = re.compile(
    r"^(?P<name>(?:@[A-Za-z0-9][A-Za-z0-9._-]{0,40}/)?[A-Za-z0-9][A-Za-z0-9._-]{0,80})"
    r"(?:@(?P<ver>[A-Za-z0-9._-]{1,40}))?$"
)

_PIP_HOSTS = frozenset({"pypi.org", "files.pythonhosted.org"})
_NPM_HOSTS = frozenset({"registry.npmjs.org"})

MAX_PACKAGES = 8
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024
DOWNLOAD_TIMEOUT = 60.0
INSTALL_TIMEOUT = 90


class PackageError(Exception):
    def __init__(self, detail: str, status: int = 400):
        self.detail = detail
        self.status = status
        super().__init__(detail)


def _assert_url_host(url: str, allowed: frozenset[str]) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in allowed:
        raise PackageError("Download host is not allowed")


async def install_packages(
    container_id: str,
    *,
    ecosystem: str,
    packages: list[str],
) -> dict:
    eco = (ecosystem or "").strip().lower()
    if eco not in {"pip", "npm"}:
        raise PackageError("Ecosystem must be pip or npm")
    cleaned = [item.strip() for item in packages if item and item.strip()]
    if not cleaned:
        raise PackageError("Name at least one package")
    if len(cleaned) > MAX_PACKAGES:
        raise PackageError(f"At most {MAX_PACKAGES} packages per request")

    if eco == "pip":
        return await _install_pip(container_id, cleaned)
    return await _install_npm(container_id, cleaned)


async def _install_pip(container_id: str, specs: list[str]) -> dict:
    for spec in specs:
        if not _PIP_SPEC.match(spec) or "://" in spec or "/" in spec:
            raise PackageError(f"Invalid pip package: {spec}")
        name = _PIP_SPEC.match(spec).group("name")
        if not _PIP_NAME.match(name):
            raise PackageError(f"Invalid pip package: {spec}")

    with tempfile.TemporaryDirectory(prefix="glpg-pip-") as tmp:
        dest = Path(tmp)
        # DECISION: resolve + download on the manager (has network). The worker
        # never opens a socket — install is --no-index from injected wheels.
        proc = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "pip",
            "download",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "-d",
            str(dest),
            *specs,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=DOWNLOAD_TIMEOUT)
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise PackageError("Package download timed out", 408) from exc
        log = (out_b or b"").decode("utf-8", errors="replace")[-4000:]
        if proc.returncode != 0:
            raise PackageError(f"Could not download packages:\n{log}", 502)

        files = [path for path in dest.iterdir() if path.is_file()]
        total = sum(path.stat().st_size for path in files)
        if total <= 0:
            raise PackageError("No packages were downloaded", 502)
        if total > MAX_DOWNLOAD_BYTES:
            raise PackageError("Downloaded packages exceed the size limit")

        await docker_api.exec_run(
            container_id,
            ["mkdir", "-p", "/tmp/pg-wheels", "/tmp/pg-vendor"],
            timeout_seconds=5,
        )
        for path in files:
            await docker_api.write_bytes(
                container_id,
                f"/tmp/pg-wheels/{path.name}",
                path.read_bytes(),
            )

        # Install every downloaded artifact (deps included), not only the top-level name.
        install_cmd = (
            "python3 -m pip install --no-index --find-links=/tmp/pg-wheels "
            "-t /tmp/pg-vendor --disable-pip-version-check --no-cache-dir "
            "/tmp/pg-wheels/*"
        )
        result = await docker_api.exec_run(
            container_id,
            ["bash", "-c", install_cmd],
            timeout_seconds=INSTALL_TIMEOUT,
        )
        await docker_api.exec_run(
            container_id, ["rm", "-rf", "/tmp/pg-wheels"], timeout_seconds=5
        )
        if result["exit_code"] != 0:
            raise PackageError(
                f"Offline install failed:\n{result['output'][-3000:]}",
                502,
            )
        return {
            "ecosystem": "pip",
            "packages": specs,
            "target": "/tmp/pg-vendor",
            "hint": "Packages are installed under /tmp (hidden from Files). PYTHONPATH is set on Run.",
            "bytes": total,
            "output": (log + "\n" + result["output"])[-5000:],
        }


async def _install_npm(container_id: str, specs: list[str]) -> dict:
    resolved: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    total = 0
    with tempfile.TemporaryDirectory(prefix="glpg-npm-") as tmp:
        dest = Path(tmp)
        async with httpx.AsyncClient(timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
            queue = list(specs)
            while queue:
                if len(resolved) >= 30:
                    raise PackageError("Dependency tree is too large")
                spec = queue.pop(0)
                match = _NPM_SPEC.match(spec)
                if not match or "://" in spec:
                    raise PackageError(f"Invalid npm package: {spec}")
                name = match.group("name")
                if not _NPM_NAME.match(name):
                    raise PackageError(f"Invalid npm package: {spec}")
                wanted = match.group("ver")
                key = f"{name}@{wanted or 'latest'}"
                if key in seen or name in {item[0] for item in resolved}:
                    continue
                seen.add(key)

                meta_url = f"https://registry.npmjs.org/{name}"
                _assert_url_host(meta_url, _NPM_HOSTS)
                meta_resp = await client.get(meta_url)
                if meta_resp.status_code != 200:
                    raise PackageError(f"Package not found: {name}", 404)
                meta = meta_resp.json()
                version = wanted or meta.get("dist-tags", {}).get("latest")
                versions = meta.get("versions") or {}
                if version not in versions:
                    raise PackageError(f"Unknown version for {name}: {version}", 404)
                info = versions[version]
                tarball = (info.get("dist") or {}).get("tarball") or ""
                _assert_url_host(tarball, _NPM_HOSTS)
                file_resp = await client.get(tarball)
                if file_resp.status_code != 200:
                    raise PackageError(f"Could not download {name}@{version}", 502)
                payload = file_resp.content
                total += len(payload)
                if total > MAX_DOWNLOAD_BYTES:
                    raise PackageError("Downloaded packages exceed the size limit")
                safe_file = f"{name.replace('/', '__')}__{version}.tgz"
                (dest / safe_file).write_bytes(payload)
                resolved.append((name, version, safe_file))
                for dep, dep_ver in (info.get("dependencies") or {}).items():
                    if not isinstance(dep, str) or not _NPM_NAME.match(dep):
                        continue
                    # Ranges are ignored — pin to whatever the registry serves as latest
                    # when the user did not request an exact nested version.
                    del dep_ver
                    queue.append(dep)

        await docker_api.exec_run(
            container_id,
            ["mkdir", "-p", "/tmp/pg-npm", "/tmp/pg-node_modules"],
            timeout_seconds=5,
        )
        for name, version, safe_file in resolved:
            data = (dest / safe_file).read_bytes()
            await docker_api.write_bytes(container_id, f"/tmp/pg-npm/{safe_file}", data)
            # Unpack without running lifecycle scripts.
            folder = name.split("/")[-1] if name.startswith("@") else name
            if name.startswith("@"):
                scope = name.split("/")[0]
                await docker_api.exec_run(
                    container_id,
                    ["mkdir", "-p", f"/tmp/pg-node_modules/{scope}"],
                    timeout_seconds=5,
                )
                target = f"/tmp/pg-node_modules/{name}"
            else:
                target = f"/tmp/pg-node_modules/{folder}"
            script = (
                "import tarfile,os,shutil\n"
                f"src='/tmp/pg-npm/{safe_file}'\n"
                f"target={target!r}\n"
                "shutil.rmtree(target, ignore_errors=True)\n"
                "os.makedirs(os.path.dirname(target) or '.', exist_ok=True)\n"
                "with tarfile.open(src,'r:gz') as tf:\n"
                "  tf.extractall('/tmp/pg-npm/extract')\n"
                "shutil.move('/tmp/pg-npm/extract/package', target)\n"
                "shutil.rmtree('/tmp/pg-npm/extract', ignore_errors=True)\n"
            )
            result = await docker_api.exec_run(
                container_id,
                ["python3", "-c", script],
                timeout_seconds=30,
            )
            if result["exit_code"] != 0:
                raise PackageError(
                    f"Could not unpack {name}@{version}:\n{result['output'][-2000:]}",
                    502,
                )

        await docker_api.exec_run(
            container_id, ["rm", "-rf", "/tmp/pg-npm"], timeout_seconds=5
        )
        installed = [f"{name}@{version}" for name, version, _ in resolved]
        return {
            "ecosystem": "npm",
            "packages": specs,
            "installed": installed,
            "target": "/tmp/pg-node_modules",
            "hint": "Packages are installed under /tmp (hidden from Files). NODE_PATH is set on Run.",
            "bytes": total,
            "output": "Installed:\n" + "\n".join(installed),
        }
