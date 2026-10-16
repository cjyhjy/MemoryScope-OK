import importlib.util
import io
import tarfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("build_deb", Path(__file__).resolve().parents[1] / "scripts/build_deb.py")
build_deb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_deb)


def members(archive: bytes):
    assert archive[:8] == b"!<arch>\n"
    position, found = 8, []
    while position < len(archive):
        header = archive[position:position + 60]
        assert header[58:60] == b"`\n"
        size = int(header[48:58])
        found.append((header[:16].decode().strip(), archive[position + 60:position + 60 + size]))
        position += 60 + size + size % 2
    return found


def test_deb_container_is_ar_with_root_owned_tar_members():
    data = build_deb.tar_bytes({"opt/x/a.txt": (b"odd", 0o644), "usr/bin/x": (b"#!/bin/sh\n", 0o755)}, "xz")
    control = build_deb.tar_bytes({"control": (b"Package: x\n", 0o644)}, "gz")
    parts = members(build_deb.ar_archive([("debian-binary", b"2.0\n"), ("control.tar.gz", control),
                                          ("data.tar.xz", data)]))
    assert [name for name, _ in parts] == ["debian-binary", "control.tar.gz", "data.tar.xz"]
    assert parts[0][1] == b"2.0\n"
    with tarfile.open(fileobj=io.BytesIO(parts[2][1])) as tar:
        infos = {info.name: info for info in tar.getmembers()}
    assert {"./opt", "./opt/x", "./usr/bin"} <= set(infos) and infos["./opt/x"].isdir()
    assert infos["./usr/bin/x"].mode == 0o755 and all(i.uid == 0 and i.gid == 0 for i in infos.values())


def test_postinst_does_not_need_ensurepip_and_pins_python():
    script = build_deb.POSTINST.format(pyver="3.12", name="memoryscope-ok")
    assert "venv --without-pip" in script and 'WANT="3.12"' in script and "--no-index" in script
