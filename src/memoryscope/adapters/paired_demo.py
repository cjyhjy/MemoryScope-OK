"""Audited, offline synthetic fixture; does not invoke a model or subprocess.

The inherited responder reads only ``memory`` and the public probe. The entire
filesystem under the arm's sandbox is disposable; it is never a retrieval path.
This contract applies to this exact fixture, not arbitrary Demo subclasses.
"""

import shutil
from pathlib import Path
from typing import Any

from memoryscope.adapters.demo import DemoAgent
from memoryscope.io import sha256_bytes

STATE_SURFACES = {"conversation_history": "context", "MEMORY.md": "sandbox_files",
                  "workspace": "sandbox_files", "home": "sandbox_files",
                  "cache": "sandbox_files", "session_database": "sandbox_files"}


class PairedDemoAgent(DemoAgent):
    def start(self, run_id: str, agent_id: str, sandbox: Path) -> None:
        super().start(run_id, agent_id, sandbox)
        self.sandbox = sandbox

    @staticmethod
    def paired_isolation_support() -> dict[str, Any]:
        return {"status": "supported", "scope": "controlled_synthetic_only",
                "memory_backend": "demo_memory_list", "effective_model": None,
                "algorithm": "demo_character_bigrams_latest_tie",
                "permissions": "no tools, subprocesses, network or host-state retrieval",
                "host_home_cache_database": "not accessed by this fixture; no OS isolation claim"}

    def _state(self) -> dict[str, Any]:
        files = []
        # Do not follow links, including a directory symlink to a host surface.
        def walk(directory: Path) -> None:
            for path in sorted(directory.iterdir()):
                item = {"path": path.relative_to(self.sandbox).as_posix()}
                if path.is_symlink():
                    files.append({**item, "kind": "symlink"})
                elif path.is_dir():
                    files.append({**item, "kind": "directory"})
                    walk(path)
                elif path.is_file():
                    data = path.read_bytes()
                    files.append({**item, "kind": "file", "size": len(data), "sha256": sha256_bytes(data)})
                else:
                    raise ValueError("unsupported special file in paired sandbox")
        walk(self.sandbox)
        return {"context": [dict(message) for message in self.context],
                "memory": list(self.memory), "sandbox_files": files,
                "surfaces": dict(STATE_SURFACES)}

    def isolate_paired_session(self, session_id: str, *, memory_enabled: bool) -> dict[str, Any]:
        self._require_active()
        before = self._state()
        self.reset_session(session_id)
        if not memory_enabled:
            self.memory.clear()
        # Both arms discard all files, including hidden files, home, caches,
        # MEMORY.md and DBs. No files are retained, even in the memory-on arm.
        for path in self.sandbox.iterdir():
            if path.is_symlink() or not path.is_dir():
                path.unlink()
            else:
                shutil.rmtree(path)
        after = self._state()
        verified = (not after["context"] and not after["sandbox_files"]
                    and after["memory"] == (before["memory"] if memory_enabled else []))
        return {"status": "verified" if verified else "unknown", "before": before, "after": after,
                "memory_enabled": memory_enabled, "retained_workspace_files": [],
                "retained_state": ["demo_memory_list"] if memory_enabled else [],
                "proof_scope": "controlled_synthetic_state_inventory"}
