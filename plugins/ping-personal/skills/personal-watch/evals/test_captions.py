"""Offline self-check for scripts/captions.py (no network). Run: python evals/test_captions.py
Prints CAPTIONS TEST PASS."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import captions  # noqa: E402


def main():
    rolling = captions.to_text(open(os.path.join(HERE, "fixtures", "rolling-auto.vtt"), encoding="utf-8").read())
    assert rolling.startswith("[0:00] Hi friends, it occurred to me"), rolling[:80]
    # YouTube auto-captions repeat each line in the next cue; the text must hold each line once.
    assert rolling.count("Hi friends, it occurred to me") == 1, rolling[:300]
    assert rolling.count("that I have") == 1
    assert "<c>" not in rolling and "-->" not in rolling and "align:start" not in rolling

    manual = captions.to_text(open(os.path.join(HERE, "fixtures", "manual.vtt"), encoding="utf-8").read())
    assert manual.startswith("[0:00] Manual captions do not repeat."), manual
    assert "\n[0:31] Thirty seconds later a new mark." in manual, manual  # a mark after 30 s, tags stripped

    assert captions.video_id("https://www.youtube.com/watch?v=M6mYodf0dJM&t=42s") == "M6mYodf0dJM"
    assert captions.video_id("https://youtu.be/F3lL98Pj90o") == "F3lL98Pj90o"
    assert captions.video_id("BsJGo1wFTvQ") == "BsJGo1wFTvQ"
    assert all(ord(ch) < 128 for ch in rolling + manual)
    print("CAPTIONS TEST PASS")


if __name__ == "__main__":
    main()
