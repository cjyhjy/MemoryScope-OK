#!/usr/bin/env python3
"""Build an offline-installable .deb of MemoryScope-OK using only the Python standard library + pip.

Runs on the target (openKylin/Debian) or cross-builds elsewhere (e.g. macOS), because it writes the ar/tar
archive itself instead of calling dpkg-deb. Dependency wheels are downloaded for the *target* platform and
Python version, so the package installs without network access.

    python3 scripts/build_deb.py                         # native arch and python3 version
    python3 scripts/build_deb.py --arch arm64 --python 3.12   # cross-build for openKylin 3.0 ARM64

postinst creates /opt/memoryscope-ok/.venv with ``python3 -m venv --without-pip`` and installs pip from the
bundled wheel, so it does not depend on python3-venv/ensurepip (missing on a default openKylin 3.0 install).
Agents (codex/dsh) are not bundled: see scripts/setup_openkylin.sh.
"""

import argparse
import gzip
import hashlib
import io
import lzma
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "memoryscope-ok"
PLATFORMS = {
    "arm64": ["manylinux_2_28_aarch64", "manylinux_2_17_aarch64", "manylinux2014_aarch64"],
    "amd64": ["manylinux_2_28_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64"],
}
PAYLOAD = ["src", "configs", "datasets", "docs", "pyproject.toml", "README.md", "LICENSE", ".env.example"]

POSTINST = """#!/bin/sh
set -e
APP=/opt/memoryscope-ok
if [ "$1" = configure ]; then
  WANT="{pyver}"
  HAVE=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
  if [ "$HAVE" != "$WANT" ]; then
    echo "MemoryScope-OK: this package was built for Python $WANT, system python3 is $HAVE." >&2
    echo "Rebuild on this machine: python3 scripts/build_deb.py" >&2
    exit 1
  fi
  rm -rf "$APP/.venv"
  python3 -m venv --without-pip "$APP/.venv" || {{
    echo "python3 venv module unavailable; install python3-venv and retry: sudo dpkg --configure -a" >&2; exit 1; }}
  PIP_WHL=$(ls "$APP"/wheels/pip-*.whl | head -n 1)
  "$APP/.venv/bin/python" "$PIP_WHL/pip" install --quiet --no-index --no-cache-dir \\
    --find-links "$APP/wheels" pip {name}
  echo "MemoryScope-OK installed. Run: memoryscope-ok --help   or   memoryscope-ok all configs/demo-smoke.yaml"
fi
"""

PRERM = """#!/bin/sh
set -e
rm -rf /opt/memoryscope-ok/.venv
"""

LAUNCHER = r"""#!/bin/sh
# MemoryScope-OK launcher. Per-user workspace: ${MEMORYSCOPE_HOME:-~/memoryscope-ok}.
#   memoryscope-ok <command> ...             same as `memoryscope`
#   memoryscope-ok all [config]              validate + run + report + HTML view (default configs/agents.yaml)
set -e
APP=/opt/memoryscope-ok
WS=${MEMORYSCOPE_HOME:-$HOME/memoryscope-ok}
if [ ! -f "$WS/pyproject.toml" ]; then
  mkdir -p "$WS"
  cp -r "$APP/configs" "$APP/datasets" "$APP/pyproject.toml" "$WS/"
  cp "$APP/.env.example" "$WS/.env.example"
  [ -f "$WS/.env" ] || { cp "$APP/.env.example" "$WS/.env"; chmod 600 "$WS/.env"; }
  echo "已创建工作目录 $WS；真实 Agent 评测前请在 $WS/.env 中填入 DEEPSEEK_API_KEY" >&2
fi
export PATH="$HOME/.local/bin:$PATH"
MS="$APP/.venv/bin/memoryscope"
cd "$WS"
if [ "$1" = all ]; then
  CONFIG=${2:-configs/agents.yaml}
  "$MS" validate datasets/golden
  "$MS" check-config "$CONFIG"
  OUT=$(mktemp)
  set +e
  "$MS" run "$CONFIG" --json > "$OUT"
  STATUS=$?
  set -e
  RUN_DIR=$("$APP/.venv/bin/python" -c 'import json,sys; print((json.load(open(sys.argv[1])).get("data") or {}).get("run_dir") or "")' "$OUT" 2>/dev/null || true)
  rm -f "$OUT"
  [ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/results.json" ] || { echo "评测没有生成结果（退出码 $STATUS）" >&2; exit 1; }
  "$MS" report "$RUN_DIR" --reuse >/dev/null
  "$MS" view "$RUN_DIR" >/dev/null
  sed -n '/## 六维得分/,/## Agent 信息/p' "$RUN_DIR/report/report.md"
  echo "运行目录：$RUN_DIR"
  echo "雷达图：$RUN_DIR/report/radar.png"
  echo "HTML 结果页：$RUN_DIR/view.html"
  if command -v xdg-open >/dev/null && [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    xdg-open "$RUN_DIR/view.html" >/dev/null 2>&1 || true
  fi
  exit "$STATUS"
fi
exec "$MS" "$@"
"""


def native_arch() -> str:
    machine = platform.machine().lower()
    return {"aarch64": "arm64", "arm64": "arm64", "x86_64": "amd64", "amd64": "amd64"}[machine]


def version() -> str:
    return re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)


def fetch_wheels(dest: Path, arch: str, pyver: str) -> None:
    pip = [sys.executable, "-m", "pip"]
    subprocess.run(pip + ["wheel", "--no-deps", "--wheel-dir", str(dest), str(ROOT)], check=True)
    tags = sum((["--platform", tag] for tag in PLATFORMS[arch]), [])
    abi = "cp" + pyver.replace(".", "")
    subprocess.run(pip + ["download", "--dest", str(dest), "--only-binary=:all:", *tags,
                          "--python-version", pyver, "--implementation", "cp", "--abi", abi, "--abi", "abi3",
                          "--abi", "none", "pip", str(ROOT)], check=True)
    # pip download also stores the project itself as an sdist/wheel; keep our freshly built wheel only.
    for extra in dest.glob("memoryscope_ok-*.tar.gz"):
        extra.unlink()


def tar_bytes(files: dict[str, tuple[bytes, int]], compress: str) -> bytes:
    """files: archive path -> (content, mode); directories implied and owned by root."""
    buffer = io.BytesIO()
    now = int(time.time())
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.GNU_FORMAT) as tar:
        seen: set[str] = set()
        for path in sorted(files):
            parts = path.split("/")
            for depth in range(1, len(parts)):
                directory = "/".join(parts[:depth])
                if directory not in seen and directory != ".":
                    seen.add(directory)
                    info = tarfile.TarInfo("./" + directory.removeprefix("./") + "/")
                    info.type, info.mode, info.mtime = tarfile.DIRTYPE, 0o755, now
                    tar.addfile(info)
            content, mode = files[path]
            info = tarfile.TarInfo("./" + path.removeprefix("./"))
            info.size, info.mode, info.mtime = len(content), mode, now
            tar.addfile(info, io.BytesIO(content))
    raw = buffer.getvalue()
    return gzip.compress(raw, mtime=now) if compress == "gz" else lzma.compress(raw)


def ar_archive(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(b"!<arch>\n")
    now = int(time.time())
    for name, data in members:
        header = f"{name:<16}{now:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n".encode("ascii")
        assert len(header) == 60
        out += header + data
        if len(data) % 2:
            out += b"\n"
    return bytes(out)


def build(arch: str, pyver: str, out_dir: Path) -> Path:
    ver = version()
    stage = Path(tempfile.mkdtemp(prefix="msok-deb-"))
    try:
        wheels = stage / "wheels"
        wheels.mkdir()
        fetch_wheels(wheels, arch, pyver)
        data: dict[str, tuple[bytes, int]] = {}
        for item in PAYLOAD:
            source = ROOT / item
            paths = [source] if source.is_file() else sorted(p for p in source.rglob("*") if p.is_file())
            for path in paths:
                rel = path.relative_to(ROOT).as_posix()
                if "__pycache__" in rel or ".egg-info" in rel or path.name.startswith("._") or path.name == ".DS_Store":
                    continue
                data[f"opt/{NAME}/{rel}"] = (path.read_bytes(), 0o644)
        for wheel in sorted(wheels.glob("*.whl")):
            data[f"opt/{NAME}/wheels/{wheel.name}"] = (wheel.read_bytes(), 0o644)
        data[f"usr/bin/{NAME}"] = (LAUNCHER.encode(), 0o755)

        minor = int(pyver.split(".")[1])
        control = (f"Package: {NAME}\nVersion: {ver}\nSection: devel\nPriority: optional\nArchitecture: {arch}\n"
                   f"Depends: python3 (>= {pyver}), python3 (<< 3.{minor + 1})\nRecommends: fonts-noto-cjk, xdg-utils\n"
                   f"Installed-Size: {sum(len(c) for c, _ in data.values()) // 1024}\n"
                   "Maintainer: MemoryScope-OK <memoryscope-ok@users.noreply.local>\n"
                   "Description: Long-term memory benchmark for AI agents (MemoryScope-OK)\n"
                   " Six-dimension, evidence-based evaluation of agent long-term memory:\n"
                   " retention, retrieval, dynamic update, disambiguation, boundary and reuse.\n"
                   f" Offline install; dependency wheels for Python {pyver}/{arch} bundled. Command: {NAME}\n")
        md5sums = "".join(f"{hashlib.md5(c).hexdigest()}  {p}\n" for p, (c, _) in sorted(data.items()))
        control_files = {"control": (control.encode(), 0o644), "md5sums": (md5sums.encode(), 0o644),
                         "postinst": (POSTINST.format(pyver=pyver, name=NAME).encode(), 0o755),
                         "prerm": (PRERM.encode(), 0o755)}
        package = ar_archive([("debian-binary", b"2.0\n"),
                              ("control.tar.gz", tar_bytes(control_files, "gz")),
                              ("data.tar.xz", tar_bytes(data, "xz"))])
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"{NAME}_{ver}_{arch}.deb"
        target.write_bytes(package)
        return target
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--arch", choices=sorted(PLATFORMS), default=None)
    parser.add_argument("--python", default=None, help="target Python X.Y (default: this interpreter)")
    parser.add_argument("--out", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    pyver = args.python or "%d.%d" % sys.version_info[:2]
    if not re.fullmatch(r"3\.\d+", pyver) or int(pyver.split(".")[1]) < 10:
        parser.error("target Python must be 3.10 or newer")
    target = build(args.arch or native_arch(), pyver, args.out)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"built {target} ({target.stat().st_size} bytes) sha256={digest}")


if __name__ == "__main__":
    main()
