---
name: personal-rea
model: inherit
description: Reverse engineer something from a plain-English request using REA (Reverse Engineer Anything). The user says what they want to know about an app, file, website or capture; this skill picks the REA tool, runs it, and explains the findings with evidence, so the user never has to learn REA's 200+ tools. TRIGGER on /personal-rea, "use rea", "reverse engineer", "reverse this", "decompile", "how does <app> do X", "what is inside this exe / dll / apk / asar". Not for code whose source is already in hand (read the source instead).
---

# /personal-rea - reverse engineer in plain English

The user describes the question in English. This skill turns it into REA calls and
answers in English. REA (`rea-agents` on npm, github.com/morluto/rea) is an MCP
server whose tools appear as `mcp__rea__*`; its own skill
`reverse-engineer-anything` holds the full tool-routing table.

## Step 1 - Pin down three things

1. **Target**: an absolute path (exe, dll, asar, apk, folder, har, sqlite...) or a URL.
2. **Question**: what the user wants to know ("how does search work", "what API does it call").
3. **Authorization**: the user's own software, open source, or a licence that allows analysis.

Ask ONE short question only for what is missing. If the target is a client's,
vendor's or commercial binary, ask whether analysis is allowed before any call.
Never help bypass licensing, DRM or activation; say so and stop.

## Step 2 - Route through REA's own skill

Load the `reverse-engineer-anything` skill (installed by `rea setup`) and follow
its "Route the target first" table. Do not copy that table here; it changes with
each REA release.

- Static analysis first. It reads files and never runs the target.
- Runtime capture (launching or attaching to the app, browser actions) runs the
  target with the user's permissions: ask before doing it.
- If `mcp__rea__*` tools are missing in this session, use the CLI fallback below,
  then tell the user to restart Claude Code so the MCP tools load.

## Step 3 - When a needed engine is missing

Do not install anything silently. Tell the user in one line which optional engine the
question needs (table below), what it costs to add, and offer to do it. Keep
answering whatever the installed pieces can answer.

## Step 4 - Report

Use the user's answer -> mechanism -> TL;DR shape:

- **Answer**: 1-2 sentences in plain English, then the how-it-works story.
- **Evidence table**: claim | where REA found it (function, module, address, file) | label.
  Label every claim `EXTRACTED` (REA returned it), `INFERRED` (your reading of it,
  with a one-sentence basis) or `UNKNOWN`.
- **Limits**: what REA said it could not see. Decompiled code is an approximation;
  server-side code never shipped to this machine is invisible.
- **Next question**: one suggested follow-up the user can say in English.

## Example Windows install

| Item | Value |
|---|---|
| Node for REA | portable Node 24 at `%USERPROFILE%\.rea-node\node-v24.22.0-win-x64` (global Node 22.13 is too old and is left alone) |
| CLI | `& "$env:USERPROFILE\.rea-node\node-v24.22.0-win-x64\rea.cmd" <command>` |
| Health check | `rea doctor --client claude_code` |
| MCP registration | user scope in `~/.claude.json`, server name `rea` |

CLI fallback example: `rea analyze-javascript-application D:/path/to/app --json`.
`rea --help` lists the 150+ commands; `rea <command> --help` shows one.

## Works now vs optional

| Target | Works now? | Optional piece to add |
|---|---|---|
| Electron / JavaScript apps, ASAR | yes | - |
| .NET assemblies (static) | yes | - |
| Go / Rust embedded metadata, WASM, SQLite, EVM, HAR/SAZ captures | yes | - |
| Websites | yes, if a Chrome-family browser is installed | - |
| Native EXE / DLL (C, C++, VB6 COM) | no | Ghidra 12.1.x + JDK 21+, set `GHIDRA_INSTALL_DIR` and `JAVA_HOME` (Windows support is experimental) |
| Native, commercial engine | no | IDA Pro + its MCP, set `REA_IDA_MCP_CONFIG` |
| Android APK code | no | Java + jadx-headless-mcp 0.7.1 JAR, set `REA_JADX_MCP_JAR` |
| Runtime instrumentation | partial | frida install script was skipped; reinstall with `npm install -g --allow-scripts=frida rea-agents@<version>` using the portable Node |
| Packet captures (pcap) | no | Wireshark `tshark` + `capinfos` |
| Firmware extraction | no | Binwalk / Unblob (Linux only) |
| Hopper | never | macOS only |
| Codex | not registered | `rea setup --client codex --dry-run`, then apply; back up `~/.codex/config.toml` first |

## Update or remove

- Update: with the portable Node first on PATH, `npm install -g rea-agents@<new version>`,
  then `rea setup --client claude_code --dry-run`, review, apply with `--yes`.
- Remove: `rea uninstall` (add `--purge-data` to drop `~/.rea`), then delete `%USERPROFILE%\.rea-node`.
- Only install from npm `rea-agents`, github.com/morluto/rea or rea.tools. Fake "REA.exe"
  downloads have circulated as malware.
