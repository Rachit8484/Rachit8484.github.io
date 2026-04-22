"""Rebuild all UPSC PYQ JSON artefacts from source.

Outputs
-------
Prelims (from the upstream CSV):
  prelims-gs1-2015-2024.json      — consolidated
  by-year/<year>.json             — one file per year
  by-topic/<slug>.json            — one file per subject

Mains (from PDFs OCR'd in raw-pdfs/ + existing upstream JSON for 2013-2021):
  mains-pyqs.json                 — consolidated Mains questions
  mains-by-paper/<slug>.json      — one file per paper (GS-I/II/III/IV/Essay)
  mains-by-year/<year>.json       — one file per Mains year

The Mains pipeline:
  1. OCR cached PDFs in raw-pdfs/.ocr-cache/ (run ocr_mains_pdfs.py if empty).
  2. Parse cached text with mains_parser.
  3. Merge with the existing upstream dataset for 2013–2021 (from
     amanbh2/UPSC-Star), preserving those entries verbatim.
  4. Apply keyword-based classifier to add subject/topic tags.
  5. Assign stable ids (m-0001, m-0002, …) after sorting newest-first.

Run: ``python build.py`` (uses system python or venv; OCR/PDF deps only needed
when raw-pdfs exist but cache is empty).
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

from mains_classify import classify
from mains_parser import parse_file as parse_ocr_file


# ───────────────────── config ─────────────────────

ROOT = Path(__file__).resolve().parent

# Prelims
CSV_URL = "https://raw.githubusercontent.com/rachit8484/upsc/main/public/upscpyqs.csv"
YEARS = range(2015, 2025)
PAPER_FILTER = "GS1"
PRELIMS_CONSOLIDATED = ROOT / "prelims-gs1-2015-2024.json"
PRELIMS_BY_YEAR = ROOT / "by-year"
PRELIMS_BY_TOPIC = ROOT / "by-topic"

# Mains
OCR_CACHE = ROOT / "raw-pdfs" / ".ocr-cache"
MAINS_UPSTREAM_URL = (
    "https://raw.githubusercontent.com/amanbh2/UPSC-Star/master/UPSC%20Star%20Data.json"
)
MAINS_CONSOLIDATED = ROOT / "mains-pyqs.json"
MAINS_BY_PAPER = ROOT / "mains-by-paper"
MAINS_BY_YEAR = ROOT / "mains-by-year"

PAPER_TITLES: dict[str, str] = {
    "GS-I":   "General Studies I — History, Society & Geography",
    "GS-II":  "General Studies II — Polity, Governance & IR",
    "GS-III": "General Studies III — Economy, Env, S&T & Security",
    "GS-IV":  "General Studies IV — Ethics & Integrity",
    "Essay":  "Essay",
}


# ───────────────────── shared helpers ─────────────────────


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "upsc-pyq-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ───────────────────── Prelims pipeline ─────────────────────


def reshape_prelims(rows: list[dict]) -> list[dict]:
    by_year: dict[int, int] = defaultdict(int)
    out: list[dict] = []
    for r in rows:
        if (r.get("Paper") or "").strip().upper() != PAPER_FILTER:
            continue
        try:
            year = int((r.get("Year") or "").strip())
        except ValueError:
            continue
        if year not in YEARS:
            continue
        by_year[year] += 1
        out.append({
            "id": f"{year}-{by_year[year]:03d}",
            "year": year,
            "paper": "GS1",
            "question": (r.get("Question") or "").strip(),
            "options": {
                "A": (r.get("Option A") or "").strip(),
                "B": (r.get("Option B") or "").strip(),
                "C": (r.get("Option C") or "").strip(),
                "D": (r.get("Option D") or "").strip(),
            },
            "correct_answer": (r.get("Correct Answer") or "").strip() or None,
            "explanation": (r.get("Explanation") or "").strip() or None,
            "subject": (r.get("Subject") or "").strip() or None,
            "topic": (r.get("Topic") or "").strip() or None,
            "passage": (r.get("Passage") or "").strip() or None,
            "image_url": (r.get("Image Url") or "").strip() or None,
        })
    return out


def build_prelims() -> None:
    print(f"[prelims] fetching {CSV_URL}", file=sys.stderr)
    try:
        csv_text = fetch_text(CSV_URL)
    except Exception as e:
        print(f"[prelims] upstream fetch failed ({e}); leaving existing JSON untouched",
              file=sys.stderr)
        return
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    print(f"[prelims] upstream rows: {len(rows)}", file=sys.stderr)

    questions = reshape_prelims(rows)
    print(f"[prelims] filtered {PAPER_FILTER} {min(YEARS)}-{max(YEARS)}: {len(questions)}",
          file=sys.stderr)

    write_json(PRELIMS_CONSOLIDATED, questions)

    for path in PRELIMS_BY_YEAR.glob("*.json"):
        path.unlink()
    for path in PRELIMS_BY_TOPIC.glob("*.json"):
        path.unlink()

    per_year: dict[int, list[dict]] = defaultdict(list)
    per_subject: dict[str, list[dict]] = defaultdict(list)
    for q in questions:
        per_year[q["year"]].append(q)
        per_subject[q["subject"] or "uncategorized"].append(q)

    for year in sorted(per_year):
        write_json(PRELIMS_BY_YEAR / f"{year}.json", per_year[year])
    for subject, qs in per_subject.items():
        write_json(PRELIMS_BY_TOPIC / f"{slugify(subject)}.json", qs)

    print("[prelims] per-year counts:", file=sys.stderr)
    for year, n in sorted(Counter(q["year"] for q in questions).items()):
        print(f"  {year}: {n}", file=sys.stderr)


# ───────────────────── Mains pipeline ─────────────────────


def load_upstream_mains() -> list[dict]:
    """Fetch the amanbh2/UPSC-Star dataset and normalize to our schema."""
    print(f"[mains] fetching upstream {MAINS_UPSTREAM_URL}", file=sys.stderr)
    src = json.loads(fetch_text(MAINS_UPSTREAM_URL))

    paper_map = {"GSI": "GS-I", "GSII": "GS-II", "GSIII": "GS-III", "GSIV": "GS-IV"}
    out: list[dict] = []
    for key, rows in src.items():
        paper = paper_map.get(key, key)
        for r in rows:
            q = (r.get("Question") or "").strip()
            if not q:
                continue
            try:
                year = int(r.get("Year")) if r.get("Year") else None
            except (TypeError, ValueError):
                year = None
            out.append({
                "paper": paper,
                "paperTitle": PAPER_TITLES.get(paper, paper),
                "year": year,
                "question": q,
                "words": r.get("WordLimit"),
                "marks": r.get("Marks"),
                "source": "upstream",
            })
    return out


def load_parsed_pdf_mains() -> list[dict]:
    """Read every OCR cache file and hand it to the parser."""
    if not OCR_CACHE.exists():
        print(f"[mains] no OCR cache at {OCR_CACHE}; skipping PDF parse",
              file=sys.stderr)
        return []
    out: list[dict] = []
    for ocr_path in sorted(OCR_CACHE.glob("*.txt")):
        parsed = parse_ocr_file(ocr_path)
        for q in parsed:
            out.append({
                "paper": q.paper,
                "paperTitle": PAPER_TITLES.get(q.paper, q.paper),
                "year": q.year,
                "question": q.question,
                "words": q.words,
                "marks": q.marks,
                "section": q.section,
                "sub": q.sub,
                "q_num": q.q_num,
                "source": "pdf",
            })
    return out


def dedupe_mains(items: list[dict]) -> list[dict]:
    """Deduplicate on (paper, year, normalized first 120 chars of question)."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for q in items:
        key = (
            q["paper"],
            q["year"],
            re.sub(r"\W+", "", (q["question"] or "").lower())[:120],
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def classify_mains(items: list[dict]) -> None:
    """Add subject/topic keys in place."""
    for q in items:
        c = classify(q["question"], q["paper"])
        q["subject"] = c.subject
        q["topic"] = c.topic


def assign_ids(items: list[dict]) -> None:
    """Sort newest-year first, paper ascending, then stamp m-0001 ids."""
    paper_order = {"GS-I": 0, "GS-II": 1, "GS-III": 2, "GS-IV": 3, "Essay": 4}
    items.sort(key=lambda x: (
        -(x.get("year") or 0),
        paper_order.get(x.get("paper"), 99),
        x.get("q_num") or 99,
        x.get("section") or "",
        x.get("sub") or "",
    ))
    for i, q in enumerate(items, 1):
        q["id"] = f"m-{i:04d}"


def build_mains() -> None:
    upstream = load_upstream_mains()
    parsed = load_parsed_pdf_mains()
    print(f"[mains] upstream: {len(upstream)}  parsed-from-pdf: {len(parsed)}",
          file=sys.stderr)

    combined = dedupe_mains(upstream + parsed)
    print(f"[mains] after dedupe: {len(combined)}", file=sys.stderr)

    classify_mains(combined)
    assign_ids(combined)

    # Clean up internal-only keys before persisting.
    public_keys = ("id", "paper", "paperTitle", "year", "question",
                   "words", "marks", "subject", "topic",
                   "section", "sub", "q_num", "source")
    final = [{k: q.get(k) for k in public_keys} for q in combined]

    write_json(MAINS_CONSOLIDATED, final)

    # Per-paper + per-year splits.
    for path in MAINS_BY_PAPER.glob("*.json"):
        path.unlink()
    for path in MAINS_BY_YEAR.glob("*.json"):
        path.unlink()

    per_paper: dict[str, list[dict]] = defaultdict(list)
    per_year: dict[int, list[dict]] = defaultdict(list)
    for q in final:
        per_paper[q["paper"]].append(q)
        if q["year"] is not None:
            per_year[q["year"]].append(q)
    for paper, qs in per_paper.items():
        write_json(MAINS_BY_PAPER / f"{slugify(paper)}.json", qs)
    for year in sorted(per_year):
        write_json(MAINS_BY_YEAR / f"{year}.json", per_year[year])

    print("[mains] per-paper counts:", file=sys.stderr)
    for p, n in Counter(q["paper"] for q in final).most_common():
        print(f"  {p}: {n}", file=sys.stderr)
    print("[mains] per-year counts:", file=sys.stderr)
    for y, n in sorted(Counter(q["year"] for q in final).items(),
                       key=lambda x: (x[0] is None, x[0])):
        print(f"  {y}: {n}", file=sys.stderr)
    print("[mains] per-subject counts:", file=sys.stderr)
    for s, n in Counter(q["subject"] for q in final).most_common():
        print(f"  {s}: {n}", file=sys.stderr)


# ───────────────────── entry ─────────────────────


def main() -> int:
    build_prelims()
    build_mains()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
