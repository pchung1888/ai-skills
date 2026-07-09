#!/usr/bin/env python3
"""Validate that ping-personal is packaged consistently for Claude Code and Codex."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ping-personal"
PERSONAS = {
    "amanda": ("amanda.md", "opus"),
    "bunny": ("bunny.md", "sonnet"),
    "dora": ("dora.md", "sonnet"),
    "iris": ("iris.md", "sonnet"),
    "maggie": ("maggie.md", "opus"),
    "ms-mario": ("ms-mario.md", "opus"),
    "rhea": ("rhea.md", "sonnet"),
    "vex": ("vex.md", "sonnet"),
}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing file: {rel(path)}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON: {rel(path)}: {exc}")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def fail(message: str) -> None:
    print(f"FAIL {message}")
    raise SystemExit(1)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)
    print(f"PASS {message}")


def marketplace_plugin(marketplace: dict, plugin_name: str) -> dict:
    plugins = marketplace.get("plugins")
    require(isinstance(plugins, list), "marketplace has plugins list")
    matches = [p for p in plugins if p.get("name") == plugin_name]
    require(len(matches) == 1, f"marketplace has exactly one {plugin_name} entry")
    return matches[0]


def main() -> int:
    claude_market = load_json(ROOT / ".claude-plugin" / "marketplace.json")
    claude_plugin = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    codex_market = load_json(ROOT / ".codex-plugin" / "marketplace.json")
    codex_plugin = load_json(PLUGIN / ".codex-plugin" / "plugin.json")

    require(claude_market.get("name") == "ping-personal", "Claude marketplace name is ping-personal")
    require(codex_market.get("name") == "ping-personal", "Codex marketplace name is ping-personal")
    require(claude_plugin.get("name") == "ping-personal", "Claude plugin name is ping-personal")
    require(codex_plugin.get("name") == "ping-personal", "Codex plugin name is ping-personal")

    versions = {
        "claude plugin": claude_plugin.get("version"),
        "claude marketplace metadata": claude_market.get("metadata", {}).get("version"),
        "claude marketplace plugin": marketplace_plugin(claude_market, "ping-personal").get("version"),
        "codex plugin": codex_plugin.get("version"),
    }
    require(len(set(versions.values())) == 1, f"all manifest versions match ({versions})")

    claude_entry = marketplace_plugin(claude_market, "ping-personal")
    codex_entry = marketplace_plugin(codex_market, "ping-personal")
    require(claude_entry.get("source") == "./plugins/ping-personal", "Claude marketplace points to shared plugin path")
    require(codex_entry.get("source", {}).get("path") == "./plugins/ping-personal", "Codex marketplace points to shared plugin path")
    require(codex_plugin.get("skills") == "./skills/", "Codex plugin exposes shared skills directory")

    skill_dirs = [p for p in (PLUGIN / "skills").iterdir() if (p / "SKILL.md").is_file()]
    require(len(skill_dirs) >= 34, f"top-level skill count is at least 34 ({len(skill_dirs)})")

    allowed_models = {"haiku", "sonnet", "opus", "inherit"}
    for skill_dir in sorted(skill_dirs):
        text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        match = re.search(r"(?m)^model:\s*([A-Za-z0-9_.-]+)\s*$", text)
        if match:
            model = match.group(1)
            require(model in allowed_models, f"{skill_dir.name} model is Claude-compatible ({model})")

    for persona, (source_file, expected_model) in PERSONAS.items():
        source = PLUGIN / "agents" / source_file
        wrapper = PLUGIN / "skills" / persona / "SKILL.md"
        agent_policy = PLUGIN / "skills" / persona / "agents" / "openai.yaml"
        eval_file = PLUGIN / "skills" / persona / "evals" / "eval.ps1"
        bad_fixture = PLUGIN / "skills" / persona / "evals" / "fixtures" / "bad-wrapper" / "SKILL.md"

        require(source.is_file(), f"{persona} canonical persona source exists")
        require(wrapper.is_file(), f"{persona} Codex persona wrapper exists")
        require(agent_policy.is_file(), f"{persona} Codex agent policy exists")
        require(eval_file.is_file(), f"{persona} wrapper eval exists")
        require(bad_fixture.is_file(), f"{persona} wrapper has a bad fixture")

        wrapper_text = wrapper.read_text(encoding="utf-8")
        policy_text = agent_policy.read_text(encoding="utf-8")
        require(f"../../agents/{source_file}" in wrapper_text, f"{persona} wrapper references canonical source")
        require("single source of truth" in wrapper_text, f"{persona} wrapper documents source-of-truth rule")
        require("allow_implicit_invocation: true" in policy_text, f"{persona} Codex policy allows implicit invocation")

        model_match = re.search(r"(?m)^model:\s*([A-Za-z0-9_.-]+)\s*$", wrapper_text)
        require(model_match is not None and model_match.group(1) == expected_model, f"{persona} wrapper model matches canonical tier")

        bad_text = bad_fixture.read_text(encoding="utf-8")
        require(f"../../agents/{source_file}" not in bad_text, f"{persona} bad fixture calibrates missing-source failure")

    compat = PLUGIN / "runtime-compatibility.md"
    require(compat.is_file(), "runtime compatibility guide exists")
    compat_text = compat.read_text(encoding="utf-8")
    require("model_reasoning_effort" in compat_text, "compatibility guide documents Codex reasoning effort")
    require("gpt-5.5" in compat_text, "compatibility guide documents GPT-5.5 mapping")
    require(".codex-plugin/marketplace.json" in compat_text, "compatibility guide documents Codex marketplace manifest")
    require(".claude-plugin/marketplace.json" in compat_text, "compatibility guide documents Claude marketplace manifest")

    print("DUAL RUNTIME CHECK PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
