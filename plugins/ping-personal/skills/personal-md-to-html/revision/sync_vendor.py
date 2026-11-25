#!/usr/bin/env python3
"""Copy the shared revision runtime into personal-htsw/walk/revision/ (byte-identical).

Usage:
  python sync_vendor.py

Run it after any edit to revision.js, revision.css or revision.py in this folder.
The VendorTests in tests/test_revision.py fail when the two copies differ.
"""
import shutil
import sys
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent
VENDOR_DIR = SOURCE_DIR.parents[1] / "personal-htsw" / "walk" / "revision"
FILE_NAMES = ("revision.js", "revision.css", "revision.py")


def main():
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    for file_name in FILE_NAMES:
        source_file = SOURCE_DIR / file_name
        if not source_file.exists():
            print("SYNC FAIL: missing " + str(source_file))
            return 1
        shutil.copyfile(source_file, VENDOR_DIR / file_name)
    print("SYNC OK: copied %d files to %s" % (len(FILE_NAMES), VENDOR_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
