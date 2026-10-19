"""Copy the fixtures to DEST and turn good-run/repo into a real git repo with a local bare remote, so
check_run.py's git checks have something to read. Usage: python materialize.py DEST   (DEST must not exist).

Layout created under DEST: the fixture files, good-run/repo/.git (branch topic/123-fixes, one commit past
the base commit), and remote.git (a bare repo used as "origin"). good-run/repo/autopilot/inputs.json gets
baseCommit, remote, remoteTagsAtStart and remoteHeadsAtStart filled from that remote.
"""
import json
import os
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BRANCH = "topic/123-fixes"


def git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    done = subprocess.run(["git", "-c", "user.name=fixture", "-c", "user.email=fixture@example.com",
                           "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
                          cwd=cwd, capture_output=True, text=True, env=env)
    assert done.returncode == 0, f"git {' '.join(args)}: {done.stderr}"
    return done.stdout.strip()


def refs(repo, kind):
    return [" ".join(line.split()) for line in git(repo, "ls-remote", f"--{kind}", "origin").splitlines()]


def remove_tree(path):
    """rmtree that also removes git's read-only object files (Windows refuses to delete them)."""
    def unlock(func, name, *_):
        os.chmod(name, stat.S_IWRITE)
        func(name)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=unlock)
    else:
        shutil.rmtree(path, onerror=unlock)


def materialize(dest):
    shutil.copytree(HERE, dest, ignore=shutil.ignore_patterns("__pycache__", "materialize.py"))
    repo = os.path.join(dest, "good-run", "repo")
    remote = os.path.join(dest, "remote.git")
    git(dest, "init", "--bare", "-b", "main", remote)
    git(repo, "init", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "tag", "v1.0")
    git(repo, "remote", "add", "origin", "../../remote.git")  # relative: a copy of DEST has its own remote
    git(repo, "push", "origin", "main", "v1.0")
    start_tags, start_heads = refs(repo, "tags"), refs(repo, "heads")
    git(repo, "checkout", "-b", BRANCH)
    with open(os.path.join(repo, "work.txt"), "w", newline="\n") as f:
        f.write("the run's change\n")
    git(repo, "add", "work.txt")
    git(repo, "commit", "-m", "the run's work")
    git(repo, "push", "origin", BRANCH)
    path = os.path.join(repo, "autopilot", "inputs.json")
    with open(path, encoding="utf-8") as f:
        inputs = json.load(f)
    inputs.update(baseCommit=base, remote="origin", remoteTagsAtStart=start_tags, remoteHeadsAtStart=start_heads)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(inputs, f, indent=1)
    return dest


if __name__ == "__main__":
    print(materialize(sys.argv[1]))
