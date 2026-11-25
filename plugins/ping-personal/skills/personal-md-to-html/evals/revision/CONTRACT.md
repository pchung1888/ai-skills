# Gate harness build commands

`buildPage(shape)` in `lib/harness.mjs` writes each page into `os.tmpdir()/rev-gates-<pid>/` with these commands
(S = `plugins/ping-personal/skills`, E = `S/personal-md-to-html/evals/revision`):

| Shape | Command |
|---|---|
| old-plain, old-script, placement | `python S/personal-md-to-html/revision/revision.py inject E/fixtures/<shape>.html --out <tmp>/<shape>.html` |
| interactive | `python S/personal-md-to-html/md-to-html.py E/fixtures/interactive.md --out <tmp>/interactive.html` |
| walk | `python S/personal-htsw/walk/walk-build.py E/fixtures/walk.json --out <tmp>/walk.html` |

Run with `node E/run-gates.mjs [--steps a,b] [--list] [--require a,b] [--selftest]`.
Playwright is found through NODE_PATH, then `REV_PW_DIR`, then `D:/playground/gstack/gstack/node_modules`.
