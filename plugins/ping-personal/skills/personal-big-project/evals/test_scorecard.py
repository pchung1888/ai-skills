"""Self-check for scripts/scorecard.py and references/scorecard.json: bands, per-10-hour rates, coverage,
"incomplete" without an owner score, the SAFETY flag from hard breaches only, one consuming metric per
owner-message class, the calibration against the owner's best run, the trend, and the export scrub.
Run: python evals/test_scorecard.py   Prints SCORECARD TEST PASS."""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import scorecard  # noqa: E402

CARD = scorecard.load_card()


def run(run_id, hours, owner_score=None, **values):
    metrics = [{"id": k, "value": v, "unit": "", "label": "EXTRACTED", "source": "test"} for k, v in values.items()]
    if owner_score is not None:
        metrics.append({"id": "ownerScore", "value": owner_score, "unit": "1-5", "label": "EXTRACTED", "source": "test"})
    return {"schemaVersion": 1, "runId": run_id, "runDate": "2026-10-" + run_id[-2:], "goalKind": "test run",
            "skillVersion": "0.43.0", "scorecardVersion": 1, "unattendedHours": hours, "backfilled": False,
            "metrics": metrics, "complaintsBySkill": {}}


# Numeric facts of two real runs (backfill shape: judgment metrics left out = UNKNOWN).
PROJ808 = run("proj808-18", 37, owner_score=5, verdict="deferred", tasksFinished=0.98, reworkShare=0.18, verifierShare=0.0,
            capOverrun="PASS", protectedPush="PASS", baselineChanged="PASS")
MR174 = run("mr174-29", 1.3, owner_score=2, verdict="stopped", reworkShare=0.26, verifierShare=0.2,
            capOverrun="PASS", protectedPush="PASS", baselineChanged="PASS", externalState="FAIL")
PROJ759 = run("proj759-27", 1.5, owner_score=4, verdict="all", tasksFinished=0.94, reworkShare=0.04, verifierShare=0.36,
            capOverrun="PASS", baselineChanged="PASS")


def main():
    # One consuming metric per owner-message class (judge row 10), and every metric id is unique.
    ids = [m["id"] for d in CARD["dimensions"] for m in d["metrics"]]
    assert len(ids) == len(set(ids)), ids
    assert all(v in ids for v in CARD["classMetric"].values()), CARD["classMetric"]
    assert sum(d["weight"] for d in CARD["dimensions"]) == 100

    # Bands: atLeast, atMost, between, map, direct; a value outside every band grades 0.
    g = scorecard.grade_metric
    assert g({"grade": "atLeast", "bands": [[0.9, 5], [0.5, 1]]}, 0.95, None, CARD) == 5
    assert g({"grade": "atLeast", "bands": [[0.9, 5], [0.5, 1]]}, 0.2, None, CARD) == 0
    assert g({"grade": "atMost", "bands": [[2, 5], [4, 4]]}, 3, None, CARD) == 4
    assert g({"grade": "between", "bands": [[0.8, 1.25, 5], [0.5, 2.0, 1]]}, 1.9, None, CARD) == 1
    assert g({"grade": "map", "map": {"yes": 5, "no": 0}}, "n/a", None, CARD) is None  # not chosen is unknown
    assert g({"grade": "direct"}, 4, None, CARD) == 4
    # Per-10-hour rates: 3 complaints in 37 h is 0.8 per 10 h (grade 5); under minHours the rate is unknown.
    per = {"grade": "atMost", "per10h": True, "bands": [[1, 5], [2, 4]]}
    assert g(per, 3, 37, CARD) == 5 and g(per, 3, 0.6, CARD) is None and g(per, 3, None, CARD) is None
    assert g(per, None, 37, CARD) is None  # an unknown value never grades 0

    # Coverage and "incomplete": no owner score -> never ranked; the coverage is printed, never hidden.
    r = scorecard.grade_run(run("x-01", 5, verdict="all", tasksFinished=1.0), CARD)
    assert r["status"] == "incomplete" and r["coverage"] < 100, r
    full = scorecard.grade_run(PROJ808, CARD)
    assert full["status"] == "complete" and full["dimensions"]["completion"] is None, full  # 0.4 of 1.0 known: unknown

    # SAFETY: a hard breach flags the run; a soft check fail (report-plain) is not a safety item at all.
    assert scorecard.grade_run(MR174, CARD)["safety"] == "SAFETY", scorecard.grade_run(MR174, CARD)
    assert scorecard.grade_run(PROJ759, CARD)["safety"] in ("PASS", "UNKNOWN")
    assert "reportPlain" not in CARD["safety"]

    # Calibration (owner order O6): the owner's best run grades at the top of the known runs.
    scores = {x["runId"]: scorecard.grade_run(x, CARD)["score"] for x in (PROJ808, MR174, PROJ759)}
    assert scores["proj808-18"] >= max(scores.values()) - 5, scores
    assert scores["mr174-29"] < scores["proj759-27"], scores  # the owner scored them 2 and 4

    # Gap for improve mode: weight x (5 - grade), largest first.
    gaps = scorecard.gaps(scorecard.grade_run(MR174, CARD), CARD)
    assert gaps[0][0] == "outcome" and gaps == sorted(gaps, key=lambda x: -x[1]), gaps

    tmp = tempfile.mkdtemp()
    try:
        # Export: only allowed keys and short tokens leave the repo; a quote or a scrub pattern refuses the copy.
        src = os.path.join(tmp, "metrics.json")
        json.dump(MR174, open(src, "w"))
        out = os.path.join(tmp, "retros")
        assert scorecard.export(src, out, "2026-10-29-mr174", []) == os.path.join(out, "2026-10-29-mr174.metrics.json")
        bad = dict(MR174, metrics=MR174["metrics"] + [{"id": "quote", "value": "the client said x", "unit": "", "label": "EXTRACTED", "source": "t"}])
        json.dump(bad, open(src, "w"))
        assert "not allowed" in scorecard.export_problem(bad, []), scorecard.export_problem(bad, [])
        leaky = dict(MR174, goalKind="answer review comments for PROJ-759")
        assert "scrub" in scorecard.export_problem(leaky, [r"PROJ-\d+"]), scorecard.export_problem(leaky, [r"PROJ-\d+"])
        assert scorecard.export_problem(dict(MR174, extra={"a": 1}), []) != ""

        # Trend: one row per run, oldest first, with coverage and the safety flag.
        many = os.path.join(tmp, "many")
        os.makedirs(many)
        for x in (PROJ759, PROJ808, MR174):
            json.dump(x, open(os.path.join(many, x["runId"] + ".metrics.json"), "w"))
        text = scorecard.trend(many, CARD)
        rows = [l for l in text.splitlines() if l.startswith("| 2026")]
        assert [l.split("|")[2].strip() for l in rows] == ["proj808-18", "proj759-27", "mr174-29"], rows
        assert "SAFETY" in rows[2] and "%" in rows[0], rows
        print("SCORECARD TEST PASS")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
