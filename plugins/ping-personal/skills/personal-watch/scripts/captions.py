"""Fetch a video's captions with yt-dlp and turn them into readable text with [mm:ss] marks.
Captions only: no video or audio is downloaded and nothing is uploaded anywhere.

  python captions.py <url-or-youtube-id> [...] --out <empty folder> [--lang en]

Prints one line per video:
  OK <id> <words> words -> <text file>   (first line of the text file is the title)
  NO-CAPTIONS <id>                       (the video has no captions in that language)
  RATE-LIMITED <id>                      (YouTube refused; retry later, one video at a time)
  FAILED <id>: <yt-dlp's last error line>
Exit 0 when every video is OK, else 1. Needs yt-dlp on PATH (winget install yt-dlp.yt-dlp);
this script never installs anything.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys

MARK_EVERY_S = 30  # one [mm:ss] mark per half minute is enough to cite a quote and still read smoothly
SLEEP_BETWEEN_S = 20  # yt-dlp pause between caption requests; YouTube answers 429 to fast bursts
CUE_TIME = re.compile(r"^(\d+):(\d\d):(\d\d)\.\d+\s+-->")


def to_text(vtt):
    """Readable text from WebVTT. YouTube auto-captions repeat the previous line in each cue, so a
    line is kept only when it differs from the last kept line."""
    out, last_line, last_mark, start = [], None, None, 0
    for raw in vtt.splitlines():
        m = CUE_TIME.match(raw)
        if m:
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        line = re.sub(r"<[^>]+>", "", raw).strip()
        if not line or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or line == last_line:
            continue
        if last_mark is None or start - last_mark >= MARK_EVERY_S:
            out.append("\n[%d:%02d] " % (start // 60, start % 60))
            last_mark = start
        out.append(line + " ")
        last_line = line
    return "".join(out).strip() + "\n"


def video_id(arg):
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", arg)
    return m.group(1) if m else arg


def fetch(arg, out_dir, lang):
    vid = video_id(arg)
    cmd = ["yt-dlp", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", lang,
           "--sub-format", "vtt", "--sleep-subtitles", str(SLEEP_BETWEEN_S), "--no-playlist",
           "--print", "before_dl:%(title)s", "--no-simulate", "-o", os.path.join(out_dir, "%(id)s.%(ext)s"), arg]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    log = proc.stdout + proc.stderr
    vtts = sorted(glob.glob(os.path.join(out_dir, vid + "*.vtt")))
    if not vtts:
        if "429" in log or "Too Many Requests" in log:
            return "RATE-LIMITED %s" % vid
        if "no subtitles" in log.lower() or "There are no" in log:
            return "NO-CAPTIONS %s" % vid
        errors = [l for l in log.splitlines() if "ERROR" in l]
        return "FAILED %s: %s" % (vid, errors[-1] if errors else "no caption file written")
    title = proc.stdout.strip().splitlines()[0] if proc.stdout.strip() else vid
    with open(vtts[0], encoding="utf-8", errors="replace") as f:
        text = to_text(f.read())
    path = os.path.join(out_dir, vid + ".txt")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(title + "\n\n" + text)
    return "OK %s %d words -> %s" % (vid, len(text.split()), path)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("videos", nargs="+", help="YouTube URLs or 11-character ids. Example: https://www.youtube.com/watch?v=M6mYodf0dJM")
    ap.add_argument("--out", required=True, help="a new, empty folder for this run (downloads are untrusted data). Example: <scratchpad>/watch-run-1")
    ap.add_argument("--lang", default="en", help="caption language code. Example: en")
    a = ap.parse_args()
    if not shutil.which("yt-dlp"):
        print("FAILED setup: yt-dlp is not on PATH. Ask the owner to install it: winget install yt-dlp.yt-dlp")
        return 1
    os.makedirs(a.out, exist_ok=True)
    results = [fetch(v, a.out, a.lang) for v in a.videos]  # one at a time: parallel requests trigger 429
    print("\n".join(results))
    return 0 if all(r.startswith("OK") for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
