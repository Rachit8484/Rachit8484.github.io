# UPSC CSE Prelims GS Paper 1 — PYQ Practice (2015–2024)

Live: **[therachitagarwal.com/upsc](https://therachitagarwal.com/upsc/)**

A single-file, zero-dependency web app for practicing **1,053 UPSC Civil
Services Prelims General Studies Paper 1** questions from the last 10 exam
years (2015–2024), plus a structured JSON dataset you can reuse.

## What's here

```
upsc-pyq/
├── index.html                     # The viewer / quiz app
├── prelims-gs1-2015-2024.json     # Consolidated (all 1,053 questions)
├── by-year/
│   ├── 2015.json  ...  2024.json  # Split by year
├── by-topic/
│   ├── indian-polity-and-governance.json
│   ├── indian-economy.json
│   ├── ... (12 topic files)
└── build.py                       # Reshape script (re-run to rebuild)
```

## Features

### Browse & Practice
- Cascading filters: **Year → Topic → Subtopic**. Pick "Indian Geography" as
  the topic and the subtopic menu narrows to the 8 subtopics actually present
  in that subject (e.g. *Indian Map*, *Drainage System of India*).
- **Click an option** (A / B / C / D) to lock in an answer. The correct option
  is highlighted green, your wrong pick red, and the explanation expands
  inline.
- Full-text **search** across question text, options, and explanations, with
  highlighted matches.
- Live counts and per-year breakdown chips.
- Pagination, 25 questions per page.

### Custom Quiz
- Pick any combination of **years**, one **topic**, one **subtopic**, and a
  question count. Shortcut buttons for *all years*, *last 3 years*, etc.
- One-question-at-a-time runner with progress bar, back/forward navigation,
  and submit-at-end grading.
- Results page with overall score, attempted count, and a full per-question
  **review** showing your answer, the correct answer, and explanation.
- **Retake** the same quiz, or build a new one.

### Shareable quizzes
- Every quiz has a permanent URL hash containing the exact question IDs:
  `therachitagarwal.com/upsc/#quiz=2022-012,2023-045,2024-007,…`
- **Copy shareable link** on both the builder and the results screen.
- Anyone who opens the link gets the same questions in the same order — useful
  for study groups or setting a quiz for a friend.

Works in any modern browser. Dark/light mode follows system preference. No
build step, no npm install.

## Running locally

Because the page fetches `prelims-gs1-2015-2024.json`, browsers block
`file://` loads — you must serve over HTTP:

```bash
cd upsc-pyq
python3 -m http.server 8000
# then open http://localhost:8000/ in your browser
```

Any static server works (Node `npx serve`, nginx, GitHub Pages, etc.).

## Schema

Every question is a JSON object with this shape:

```json
{
  "id": "2024-001",
  "year": 2024,
  "paper": "GS1",
  "question": "How many Delimitation Commissions have been constituted by the Government of India till December 2023?",
  "options": {
    "A": "One",
    "B": "Two",
    "C": "Three",
    "D": "Four"
  },
  "correct_answer": "D",
  "explanation": "Delimitation Commissions have been constituted 4 times in India ...",
  "subject": "Indian Polity and Governance",
  "topic": "Constitutional and Non-constitutional Bodies",
  "passage": null,
  "image_url": null
}
```

In the web app, `subject` is presented as **Topic** and `topic` as
**Subtopic**, matching the way candidates usually talk about syllabus
coverage (e.g. *Indian Geography → Indian Map*).

## Coverage

| Year | Questions |
| ---- | --------- |
| 2015 | 102       |
| 2016 | 109       |
| 2017 | 111       |
| 2018 | 108       |
| 2019 | 108       |
| 2020 | 110       |
| 2021 | 98        |
| 2022 | 106       |
| 2023 | 100       |
| 2024 | 101       |

Counts above the expected 100 reflect minor duplicates / multi-set captures in
the source; de-duplicate downstream if strict 100/year is needed.

### Topic distribution

| Topic                                          | Questions |
| ---------------------------------------------- | --------- |
| Indian Economy                                 | 210       |
| Environment & Ecology and Disaster Management  | 157       |
| Current Affairs and Miscellaneous              | 146       |
| Indian Polity and Governance                   | 139       |
| Science & Tech and Basic Science               | 102       |
| Modern India                                   | 68        |
| Indian Geography                               | 53        |
| World Geography                                | 49        |
| Ancient India                                  | 38        |
| Art & Culture                                  | 33        |
| International Relations                        | 33        |
| Medieval India                                 | 25        |

## Source

The raw questions originate from the official UPSC Civil Services
(Preliminary) Examination papers published by the Union Public Service
Commission at [upsc.gov.in](https://upsc.gov.in/examinations/previous-question-papers).
This folder reshapes a curated upstream CSV of those questions (with topic
tags, answers, and explanations) into a normalized JSON schema — see
`LICENSE-upstream.txt` for the upstream MIT notice.

This folder:
1. Filters the upstream CSV to GS Paper 1 only (excludes CSAT / Paper 2).
2. Scopes to the last 10 exam years (2015–2024).
3. Reshapes the flat CSV into a normalized JSON schema with an explicit ID
   (`<year>-<seq>`) per question and a nested `options` object.
4. Splits into year-wise and topic-wise files for convenient access.

## Rebuilding

```bash
python3 build.py
```

`build.py` re-downloads the upstream CSV and rebuilds every JSON file from
scratch. No third-party dependencies required (stdlib only).

## Caveats

- **Topic tags are editorial.** UPSC papers themselves do not carry topic
  labels; the tags come from the upstream curator. Expect occasional
  classification disagreements.
- **Image-based questions** (maps, diagrams) have `image_url` populated only
  where the upstream source had an image; many are empty.
- **Passages** (shared stems for question groups) are preserved in the
  `passage` field when present.
- For the authoritative questions, always cross-reference the official UPSC
  PDFs linked above.

## 2025 Paper

The 2025 Prelims paper (held 25 May 2025) is available on
[upsc.gov.in](https://upsc.gov.in/sites/default/files/QP-CSP-25-GENERAL-STUDIES-PAPER-I-26052025.pdf)
but is not yet in this dataset because the upstream source only covers up to
2024. Re-run `build.py` after the upstream adds 2025 to pick it up.
