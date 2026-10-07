#!/usr/bin/env python3
"""Validate installed harness adapters and repository integration."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import time
import tempfile
from contextlib import contextmanager, redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
SYNC_SCRIPT = ROOT / "scripts" / "sync_harness_adapters.py"
REQUIRED_REPO_FILES = (
    ROOT / "scripts" / "harness_paths.py",
    ROOT / "harness" / "manifest.json",
    ROOT / "harness" / "core" / "shared.md",
    ROOT / "harness" / "runtime" / "claude.md",
    ROOT / "harness" / "runtime" / "codex.md",
    ROOT / "harness" / "runtime" / "chatgpt.md",
    SYNC_SCRIPT,
    Path(__file__),
    ROOT / "scripts" / "run_harness_dogfood.ps1",
)
SECRET_SCANNER = ROOT / "plugins" / "ping-personal" / "skills" / "personal-loop" / "lib" / "secrets_scan.py"


def fail(message: str) -> None:
    print(f"HARNESS SYNC CHECK FAIL: {message}")
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(command: list[str], match: str) -> None:
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    require(result.returncode == 0, f"command failed: {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    require(match in result.stdout, f"command output lacks {match}: {' '.join(command)}")


@contextmanager
def transaction_sandbox(sync, root: Path):
    names = (
        "STATE_ROOT",
        "INSTALL_STATE_PATH",
        "LEGACY_MANIFEST",
        "STAGING_ROOT",
        "EXPORT_ROOT",
        "CLAUDE_TARGET",
        "CODEX_TARGET",
        "CUSTOM_EXPORT",
        "PROJECT_EXPORT",
        "TRANSACTION_FAULT_INJECTOR",
    )
    saved = {name: getattr(sync, name) for name in names}
    home = root / "home"
    harness = home / ".ping-harness"
    try:
        sync.STATE_ROOT = harness
        sync.INSTALL_STATE_PATH = harness / "install-state.json"
        sync.LEGACY_MANIFEST = harness / "manifest.json"
        sync.STAGING_ROOT = harness / "staging"
        sync.EXPORT_ROOT = harness / "exports"
        sync.CLAUDE_TARGET = home / ".claude" / "CLAUDE.md"
        sync.CODEX_TARGET = home / ".codex" / "AGENTS.md"
        sync.CUSTOM_EXPORT = sync.EXPORT_ROOT / "chatgpt-custom-instructions.md"
        sync.PROJECT_EXPORT = sync.EXPORT_ROOT / "chatgpt-project-brief.md"
        sync.TRANSACTION_FAULT_INJECTOR = None
        yield
    finally:
        for name, value in saved.items():
            setattr(sync, name, value)


def initialize_transaction_sandbox(sync) -> tuple[dict[str, bytes], list[Path], list[bytes]]:
    outputs = {
        "claude-global.md": b"new claude adapter\n",
        "codex-global.md": b"new codex adapter\n",
        "chatgpt-custom-instructions.md": b"new custom instructions\n",
        "chatgpt-project-brief.md": b"new project brief\n",
    }
    targets = [path for _, path in sync.transaction_targets()]
    old_target_bytes = [
        b"old claude adapter\r\n\x00",
        b"old codex adapter\r\n\x00",
        b"old custom instructions\r\n\x00",
        b"old project brief\r\n\x00",
    ]
    for path, data in zip(targets[:4], old_target_bytes):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    installation_names = [name for name, _ in sync.transaction_targets()[:4]]
    state = {
        "installation": {
            "installed_at": "2026-01-01T00:00:00Z",
            "targets": {
                name: {
                    "path": str(path.resolve()),
                    "sha256": sha256(data),
                    "size": len(data),
                }
                for name, path, data in zip(installation_names, targets[:4], old_target_bytes)
            },
        }
    }
    state_bytes = (json.dumps(state, indent=2, sort_keys=True) + "\n").encode("ascii")
    sync.INSTALL_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    sync.INSTALL_STATE_PATH.write_bytes(state_bytes)
    before = old_target_bytes + [state_bytes]
    return outputs, targets, before


def fault_at(expected_boundary: int):
    def inject(boundary: int, name: str, path: Path) -> None:
        if boundary == expected_boundary:
            raise RuntimeError(f"fault after replacement {boundary}: {name}: {path.name}")

    return inject


def check_transaction_path_guard(sync) -> None:
    with tempfile.TemporaryDirectory(prefix="harness-adapter-path-") as temporary:
        with transaction_sandbox(sync, Path(temporary)):
            try:
                with redirect_stdout(io.StringIO()):
                    sync.transaction_path("../escape.bin")
            except SystemExit as exc:
                require(exc.code == 1, "transaction path guard exited with the wrong status")
            else:
                fail("transaction path guard accepted traversal")


def check_transaction_rollback_boundaries(sync) -> None:
    for expected_boundary in range(1, len(sync.transaction_targets()) + 1):
        with tempfile.TemporaryDirectory(prefix=f"harness-adapter-rollback-{expected_boundary}-") as temporary:
            with transaction_sandbox(sync, Path(temporary)):
                outputs, targets, before = initialize_transaction_sandbox(sync)
                sync.TRANSACTION_FAULT_INJECTOR = fault_at(expected_boundary)
                try:
                    sync.install(outputs)
                except RuntimeError as exc:
                    require(
                        f"fault after replacement {expected_boundary}" in str(exc),
                        f"unexpected rollback fault at boundary {expected_boundary}: {exc}",
                    )
                else:
                    fail(f"rollback fault did not fire at boundary {expected_boundary}")
                finally:
                    sync.TRANSACTION_FAULT_INJECTOR = None
                require(
                    [path.read_bytes() for path in targets] == before,
                    f"rollback was not byte-preserving at boundary {expected_boundary}",
                )
                require(
                    not sync.transaction_journal_path().exists(),
                    f"rollback left a journal at boundary {expected_boundary}",
                )
                require(
                    not sync.transaction_root().exists(),
                    f"rollback left transaction artifacts at boundary {expected_boundary}",
                )


def check_abandoned_transaction_boundaries(sync) -> None:
    for expected_boundary in range(1, len(sync.transaction_targets()) + 1):
        with tempfile.TemporaryDirectory(prefix=f"harness-adapter-abandon-{expected_boundary}-") as temporary:
            with transaction_sandbox(sync, Path(temporary)):
                outputs, targets, before = initialize_transaction_sandbox(sync)
                sync.TRANSACTION_FAULT_INJECTOR = fault_at(expected_boundary)
                try:
                    sync._install(outputs, recover_on_error=False)
                except RuntimeError as exc:
                    require(
                        f"fault after replacement {expected_boundary}" in str(exc),
                        f"unexpected abandoned fault at boundary {expected_boundary}: {exc}",
                    )
                else:
                    fail(f"abandoned fault did not fire at boundary {expected_boundary}")
                finally:
                    sync.TRANSACTION_FAULT_INJECTOR = None

                require(
                    sync.transaction_journal_path().is_file(),
                    f"abandoned transaction lacks journal at boundary {expected_boundary}",
                )
                partial = [path.read_bytes() for path in targets]
                for index, (actual, original) in enumerate(zip(partial, before), start=1):
                    if index <= expected_boundary:
                        require(actual != original, f"replacement {index} did not land before abandonment")
                    else:
                        require(actual == original, f"replacement {index} landed past abandonment boundary")

                sync.install(outputs)
                expected_outputs = [
                    outputs["claude-global.md"],
                    outputs["codex-global.md"],
                    outputs["chatgpt-custom-instructions.md"],
                    outputs["chatgpt-project-brief.md"],
                ]
                require(
                    [path.read_bytes() for path in targets[:4]] == expected_outputs,
                    f"next invocation did not install all outputs after boundary {expected_boundary}",
                )
                state = json.loads(sync.INSTALL_STATE_PATH.read_text(encoding="ascii"))
                records = state.get("installation", {}).get("targets", {})
                for name, path, data in zip(
                    [name for name, _ in sync.transaction_targets()[:4]], targets[:4], expected_outputs
                ):
                    record = records.get(name, {})
                    require(record.get("path") == str(path.resolve()), f"recovered manifest path differs: {name}")
                    require(record.get("sha256") == sha256(data), f"recovered manifest hash differs: {name}")
                    require(record.get("size") == len(data), f"recovered manifest size differs: {name}")
                require(
                    not sync.transaction_journal_path().exists(),
                    f"next invocation left a journal at boundary {expected_boundary}",
                )
                require(
                    not sync.transaction_root().exists(),
                    f"next invocation left transaction artifacts at boundary {expected_boundary}",
                )


def check_corrupt_prestate_retains_journal(sync) -> None:
    with tempfile.TemporaryDirectory(prefix="harness-adapter-corrupt-") as temporary:
        with transaction_sandbox(sync, Path(temporary)):
            outputs, targets, _ = initialize_transaction_sandbox(sync)
            sync.TRANSACTION_FAULT_INJECTOR = fault_at(2)
            try:
                sync._install(outputs, recover_on_error=False)
            except RuntimeError:
                pass
            else:
                fail("corrupt-prestate setup fault did not fire")
            finally:
                sync.TRANSACTION_FAULT_INJECTOR = None

            partial = [path.read_bytes() for path in targets]
            corrupt = sync.transaction_path("prestate/04-install_state.bin")
            corrupt.write_bytes(corrupt.read_bytes() + b"corrupt")
            try:
                with redirect_stdout(io.StringIO()):
                    sync.recover_abandoned_transaction()
            except SystemExit as exc:
                require(exc.code == 1, "corrupt-prestate recovery exited with the wrong status")
            else:
                fail("corrupt transaction prestate passed recovery validation")
            require(
                [path.read_bytes() for path in targets] == partial,
                "corrupt prestate caused writes before full validation",
            )
            require(
                sync.transaction_journal_path().is_file(),
                "failed recovery removed its transaction journal",
            )


def check_adapter_transaction_recovery(sync) -> None:
    check_transaction_path_guard(sync)
    check_transaction_rollback_boundaries(sync)
    check_abandoned_transaction_boundaries(sync)
    check_corrupt_prestate_retains_journal(sync)
    check_repeat_install_idempotency(sync)
    check_first_install(sync)
    print("HARNESS ADAPTER RECOVERY SELF-TEST PASS")


def check_first_install(sync) -> None:
    """A machine with no install state backs up its existing adapters, then installs."""
    outputs = {
        "claude-global.md": b"new claude adapter\n",
        "codex-global.md": b"new codex adapter\n",
        "chatgpt-custom-instructions.md": b"new custom instructions\n",
        "chatgpt-project-brief.md": b"new project brief\n",
    }
    for existing_claude in (b"hand-written rules\r\n", None):
        with tempfile.TemporaryDirectory(prefix="harness-adapter-first-") as temporary:
            with transaction_sandbox(sync, Path(temporary)):
                if existing_claude is not None:
                    sync.CLAUDE_TARGET.parent.mkdir(parents=True, exist_ok=True)
                    sync.CLAUDE_TARGET.write_bytes(existing_claude)
                with redirect_stdout(io.StringIO()):
                    sync._install(outputs, recover_on_error=True)
                require(sync.CLAUDE_TARGET.read_bytes() == outputs["claude-global.md"], "first install did not install")
                state = json.loads(sync.INSTALL_STATE_PATH.read_text(encoding="ascii"))
                record = state.get("backups", {}).get("claude", {})
                if existing_claude is None:
                    require(record.get("existed") is False, "first install invented a backup")
                else:
                    backup = sync.STATE_ROOT / record.get("relative_path", "missing")
                    require(backup.read_bytes() == existing_claude, "first install did not back up the old adapter")
                require("installation" in state, "first install did not record the installation")


def check_repeat_install_idempotency(sync) -> None:
    with tempfile.TemporaryDirectory(prefix="harness-adapter-idempotency-") as temporary:
        with transaction_sandbox(sync, Path(temporary)):
            outputs, targets, _ = initialize_transaction_sandbox(sync)
            sync._install(outputs, recover_on_error=True)
            first = [path.read_bytes() for path in targets]
            time.sleep(1.1)
            sync._install(outputs, recover_on_error=True)
            require(
                [path.read_bytes() for path in targets] == first,
                "identical install changed one or more transaction targets",
            )
            require(not sync.transaction_journal_path().exists(), "idempotent install created a journal")
            require(not sync.transaction_root().exists(), "idempotent install left transaction artifacts")


def check_adapters() -> None:
    sync = load_module(SYNC_SCRIPT, "harness_sync_source")
    check_adapter_transaction_recovery(sync)
    outputs = sync.compose_adapters()
    targets = {
        "claude": (HOME / ".claude" / "CLAUDE.md", "claude-global.md"),
        "codex": (HOME / ".codex" / "AGENTS.md", "codex-global.md"),
        "chatgpt_custom_instructions": (
            sync.EXPORT_ROOT / "chatgpt-custom-instructions.md",
            "chatgpt-custom-instructions.md",
        ),
        "chatgpt_project_brief": (
            sync.EXPORT_ROOT / "chatgpt-project-brief.md",
            "chatgpt-project-brief.md",
        ),
    }
    state = sync.load_install_state()
    installation = (state or {}).get("installation")
    require(isinstance(installation, dict), "install state lacks installation record")
    records = installation.get("targets", {})
    for name, (path, output_key) in targets.items():
        require(path.is_file(), f"installed target is missing: {path}")
        actual = path.read_bytes()
        expected = outputs[output_key]
        require(actual == expected, f"installed target drifted: {name}")
        record = records.get(name, {})
        require(record.get("path") == str(path.resolve()), f"manifest target path differs: {name}")
        require(record.get("sha256") == sha256(actual), f"manifest target hash differs: {name}")
        require(record.get("size") == len(actual), f"manifest target size differs: {name}")
        require(all(byte < 128 for byte in actual), f"installed target is not ASCII: {name}")

    claude = targets["claude"][0].read_text(encoding="ascii")
    codex = targets["codex"][0].read_text(encoding="ascii")
    custom = targets["chatgpt_custom_instructions"][0].read_text(encoding="ascii")
    claude_overlay = sync.read_ascii(sync.CLAUDE_OVERLAY_PATH).strip()
    require(claude_overlay in claude, "Claude adapter lacks its runtime overlay")
    require(claude_overlay not in codex, "Claude overlay leaked into Codex")
    require("ping-personal plugin" in codex, "Codex adapter lacks plugin routing")
    require(len(custom) <= 1500, "ChatGPT Custom Instructions exceed 1500 characters")
    for marker in ("EXTRACTED", "INFERRED", "SUGGESTION", "UNKNOWN", "## TL;DR"):
        require(marker in custom, f"ChatGPT Custom Instructions lack marker: {marker}")
    print("HARNESS ADAPTER CHECK PASS")


def check_repo() -> None:
    scanner_module = load_module(SECRET_SCANNER, "harness_repo_secrets")
    scanner = scanner_module.scan
    for path in REQUIRED_REPO_FILES:
        require(path.is_file(), f"required repository artifact is missing: {path}")
        data = path.read_bytes()
        require(all(byte < 128 for byte in data), f"repository artifact is not ASCII: {path}")
        require(not scanner(data.decode("ascii")), f"hardened secret scanner found a match in {path}")
    run([sys.executable, "scripts/check_dual_runtime.py"], "DUAL RUNTIME CHECK PASS")
    print("HARNESS REPO CHECK PASS")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--adapters", action="store_true")
    mode.add_argument("--repo-only", action="store_true")
    mode.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.adapters or args.check:
        check_adapters()
    if args.repo_only or args.check:
        check_repo()
    if args.check:
        print("HARNESS SYNC CHECK PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
