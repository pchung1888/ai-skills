import argparse
import sys
from pathlib import Path


def resolve(slug, area_override, docs_root):
    if area_override:
        return area_override
    docs = Path(docs_root)
    # Check slug as-is first
    if (docs / slug).is_dir():
        return slug
    # Longest left-anchored hyphen-prefix match
    parts = slug.split("-")
    for i in range(len(parts) - 1, 0, -1):
        prefix = "-".join(parts[:i])
        if (docs / prefix).is_dir():
            return prefix
    # Fallback: use slug (will be created)
    return slug


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--slug", required=True)
    p.add_argument("--area", dest="area_override")
    p.add_argument("--docs-root", dest="docs_root", default="docs")
    args = p.parse_args()
    print(resolve(args.slug, args.area_override, args.docs_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
