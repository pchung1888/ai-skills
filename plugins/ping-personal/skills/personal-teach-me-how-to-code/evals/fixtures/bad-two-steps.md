**Step 8a passed.**

- Check 1: right. The title bar holds the buttons, and `canMaintain` hides Copy To Next Year.

---

**Step 8b: the page reads the URL and loads the data (lines 41-57)**

**Lines 42-50: read the URL.** These lines work like `Request.QueryString` at the top of an ASP page.

```tsx
const [params, setParams] = useSearchParams();
const year = params.get('year') ?? String(thisYear);
const pageNo = Math.max(1, Number(params.get('page') ?? 1) || 1);
```

- `params.get('year')` reads `?year=2025` from the URL.
- `??` means "if it is missing, use this". So a URL with no year shows this year.
- Line 47 turns `?page=abc` into page 1. It has the same job as your `IsNumeric` check before `CInt`.

**Why the URL holds the filter:** F5, the Back button and a pasted link all show the same grid.

**Lines 51-52: the boxes keep their own copy.**

```tsx
const [yearBox, setYearBox] = useState(year);
```

- `useState` is page memory. It keeps a value between redraws.
- If you type `2027`, only `yearBox` changes. The grid still shows 2025 until you click **Filter**.

**React pattern here:** two values, typed (the box) and applied (the URL).

```
You type 2027        -> yearBox = "2027"        (grid unchanged)
You click Filter     -> setParams -> URL ?year=2027
Page redraws         -> year = "2027" -> qs changes
useFetch sees new qs -> GET /api/app?year=2027 -> grid shows 2027
```

---

**Step 9a: types and helpers (lines 1-67)**

The detail page starts with its types.

---

**Tell me:**

- You type `2030` and do not click Filter. Which year does the grid show?
- You press F5 on `?year=2025`. Which year shows, and which line reads it?
