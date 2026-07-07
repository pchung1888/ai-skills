---
title: Code with path demo
---
# Code with path

The `path=` info-string attribute emits a small-caps monospace file-path eyebrow
above each code block. Quoting is required for paths that contain spaces.

```python path=~/.claude/skills/personal-md-to-html/themes/arc/components/eyebrow.py
def render(source_text: str) -> str:
    content = " ".join(source_text.strip().split())
    return f'<p class="eyebrow">{content}</p>'
```

```js path="C:/Program Files (x86)/foo/bar.js"
const cols = Object.keys(rows[0]);
return Object.fromEntries(cols.map(c => [c, inferOne(rows, c)]));
```
