"""OCR-to-structured-question parser for UPSC Mains PDFs.

UPSC Mains PDFs are image-only scans with bilingual (Hindi + English)
content. We OCR each page with Tesseract (English-only), which renders
Devanagari as garbled ASCII. This module extracts clean English questions +
metadata by:

1. Finding question-marker boundaries (``1.``, ``Q1.``, ``Q.1``) as the
   coarse structure of the paper.
2. Within each block, keeping only the lines that look like real English
   prose. The Hindi garble fails the filter and is discarded.
3. Recovering marks / word limit from an explicit ``(Answer in N words) M``
   anchor if present, else falling back to paper conventions
   (Q1–Q10 = 150w/10m, Q11–Q20 = 250w/15m).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


# ───────────────────────── English-prose filter ─────────────────────────

# Words that appear in almost every real English UPSC question. We require
# at least one of these to accept a line as English. This is extremely
# robust against OCR'd Devanagari, which never happens to coincide with
# these tokens in well-formed English context.
_STOPWORDS = {
    # Articles / prepositions
    "the", "of", "and", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "by", "for", "with", "to", "from", "into", "upon",
    "about", "against", "between", "among", "through", "during", "before",
    "after", "above", "below", "over", "under", "again", "further",
    # Pronouns / determiners
    "this", "that", "these", "those", "such", "all", "any", "both", "each",
    "few", "more", "most", "other", "some", "no", "not", "only", "own",
    "same", "so", "than", "too", "very", "its", "their", "our", "your",
    # Question words
    "how", "why", "what", "which", "who", "whom", "whose", "when", "where",
    "whether", "do", "does", "did", "has", "have", "had",
    # UPSC-isms
    "discuss", "explain", "analyse", "analyze", "examine", "comment",
    "evaluate", "describe", "elucidate", "elaborate", "illustrate",
    "identify", "critically", "briefly", "highlight", "assess", "compare",
    "contrast", "bring", "out", "suggest", "recent", "role", "india",
    "indian", "policy", "government", "justify", "enumerate", "delineate",
    "substantiate", "investigate", "establish", "enunciate",
}

# Characters allowed in clean English text (letters, digits, punctuation).
_ALLOWED_CHARS = re.compile(r"[A-Za-z0-9 ,.;:'\"?!()\-\[\]/&%]")
_WORD_RE = re.compile(r"[A-Za-z]+")


def is_english_prose(line: str) -> bool:
    """Strict English filter tuned against OCR'd Devanagari noise.

    A line qualifies only if all of these hold:
    * Has ≥ 3 alphabetic tokens.
    * Average token length ≥ 3.8 (Hindi OCR bursts average ~3–3.5).
    * Contains ≥ 2 DISTINCT stopwords, counting only tokens of length ≥ 2
      (so "a" alone can't anchor a line).
    * At most 35% of tokens of length ≤ 2.
    """
    s = line.strip()
    if len(s) < 6:
        return False
    tokens = _WORD_RE.findall(s)
    if len(tokens) < 3:
        return False
    avg = sum(len(t) for t in tokens) / len(tokens)
    if avg < 3.8:
        return False
    long_tokens = [t.lower() for t in tokens if len(t) >= 2]
    distinct_stops = {t for t in long_tokens if t in _STOPWORDS}
    if len(distinct_stops) < 2:
        return False
    short = sum(1 for t in tokens if len(t) <= 2)
    if short / len(tokens) > 0.35:
        return False
    return True


# ───────────────────────── line-level cleanup ─────────────────────────

_RUNNING_FOOTER_RE = re.compile(r"^[A-Z]{2,}-G-[A-Z]{2,}(?:/\d+)?\s*\d*\s*$")
_PAGE_MARK_RE = re.compile(r"^\s*\d{1,3}\s*\[?\s*(P\.?T\.?O\.?|Pe\s*T\.?O\.?)?\]?\s*$", re.IGNORECASE)
_PAGE_BREAK_RE = re.compile(r"^==== PAGE BREAK ====\s*$")

_INSTRUCTION_RE = re.compile(
    r"(Question\s+Paper\s+Specific\s+Instructions|"
    r"Please\s+read\s+each\s+of\s+the\s+following|"
    r"There\s+are\s+(?:TWENTY|TWELVE|EIGHT|TWO)\s+questions|"
    r"All\s+questions\s+are\s+compulsory|"
    r"The\s+number\s+of\s+marks\s+carried\s+by\s+a\s+question|"
    r"Answers?\s+must\s+be\s+written\s+in\s+the\s+medium|"
    r"Admission\s+Certificate|QCA\s*Booklet|Question[-\s]cum[-\s]Answer|"
    r"No\s+marks\s+will\s+be\s+given|Word\s+limit(?:\s+in)?|"
    r"Any\s+page\s+or\s+portion|printed\s+both\s+in\s+HINDI|"
    r"Keep\s+the\s+word\s+limit|must\s+be\s+stated\s+clearly|"
    r"struck\s+off|Answers?\s+to\s+(?:Question[s]?\s+[Nn]os?\.|the\s+question)|"
    r"Time\s+Allowed|Maximum\s+Marks|DETACHABLE|"
    r"Civil\s+Services\s+\(Main\)|GENERAL\s+STUDIES\s+\(?Paper|"
    r"^\s*QUESTION\s+PAPER|^\s*ESSAY\s*$|^\s*Paper\s*[IV]+\s*$|"
    r"^\s*Write\s+two\s+essays,\s+choosing\s+one\s+topic|"
    r"in\s+about\s+1000\s*[-–—]\s*1200\s+words)",
    re.IGNORECASE,
)


def strip_structural_noise(raw: str) -> str:
    out: list[str] = []
    for ln in raw.splitlines():
        stripped = ln.strip()
        if not stripped:
            out.append("")
            continue
        if _PAGE_BREAK_RE.match(stripped):
            out.append("")
            continue
        if _RUNNING_FOOTER_RE.match(stripped) or _PAGE_MARK_RE.match(stripped):
            continue
        if _INSTRUCTION_RE.search(stripped):
            continue
        out.append(ln)
    return "\n".join(out)


# ───────────────────────── data class ─────────────────────────


@dataclass
class Question:
    paper: str
    year: int
    question: str
    words: int | None
    marks: int | None
    section: str | None = None
    sub: str | None = None
    q_num: int | None = None


# ───────────────────────── GS-I/II/III parser ─────────────────────────


# Matches question markers including OCR-damaged variants. Tesseract often
# misreads digits as similar-looking letters (1↔i/l/I/L, 0↔o/O, 5↔s/S).
# We accept:
#   * "Q" prefix followed by any combination of digits + look-alikes
#     ("Q1.", "Qi.", "Qll.", "Qi3s.", "Qs.")
#   * bare number (1-2 digits) without prefix ("1.", "12,")
Q_MARKER_RE = re.compile(
    r"^\s*(?:Q\.?\s*[0-9iIlLsSoO]{1,3}|\d{1,2})\s*[\.,]\s+",
    re.IGNORECASE | re.MULTILINE,
)

# Matches "(Answer in 150 words) 10" or "(Answer in 250 words). 15"
ANSWER_ANCHOR_RE = re.compile(
    r"\(\s*Answer\s+in\s+(\d{2,3})\s+word[s]?\s*\)\s*\.?\s*(\d{1,3})?",
    re.IGNORECASE,
)

# Trailing marks on an English line without the (Answer...) anchor.
TRAILING_MARKS_RE = re.compile(r"(?:[:.,\s]|^)(10|15|20|25|125)\s*\.?\s*$")


def _extract_english(block: str) -> str:
    """Return the concatenated English lines of a block, in source order."""
    keep = [L.strip() for L in block.splitlines() if is_english_prose(L)]
    # Drop any residual "(Answer in N words) M" text — we already captured it.
    text = " ".join(keep)
    text = ANSWER_ANCHOR_RE.sub("", text)
    # Also strip an explicit leading "N." that might have survived.
    text = re.sub(r"^\s*(?:Q\.?\s*)?\d{1,2}\.\s*", "", text)
    # Collapse spaces and strip wrap-around punctuation.
    text = " ".join(text.split()).strip(" .:,-")
    return text


def parse_gs_standard(raw_text: str, year: int, paper: str) -> list[Question]:
    """Parse GS-I/II/III. Expect 20 questions per paper; Q1–Q10 are 150w/10m,
    Q11–Q20 are 250w/15m."""
    text = strip_structural_noise(raw_text)

    markers = list(Q_MARKER_RE.finditer(text))
    # Skip any leading marker whose trailing English text is too short —
    # this is typically a stray "2." in the preamble.
    # Assume first real Q1 marker is the one that starts the FIRST block with
    # English content ≥ 30 chars.
    starts: list[int] = []
    for m in markers:
        # peek at the first 400 chars of potential block
        block = text[m.end(): m.end() + 600]
        english = _extract_english(block)
        if len(english) >= 30:
            starts.append(m.start())
    if len(starts) < 5:
        return []

    # Build block ranges.
    blocks: list[str] = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(text)
        blocks.append(text[s:e])

    # Trim to 20 questions.
    blocks = blocks[:20]

    questions: list[Question] = []
    for i, blk in enumerate(blocks, 1):
        am = ANSWER_ANCHOR_RE.search(blk)
        words: int | None = None
        marks: int | None = None
        if am:
            words = int(am.group(1))
            if am.group(2):
                marks = int(am.group(2))

        english = _extract_english(blk)
        # If there's a trailing marks number on the last English line, peel
        # it off (and use it for marks if we don't have one yet).
        # The english string is already joined so the tail-marks pattern
        # applies to the whole string.
        tm = TRAILING_MARKS_RE.search(english)
        if tm and marks is None:
            marks = int(tm.group(1))
        if tm:
            english = english[: tm.start()].rstrip(" .:,")

        if not english or len(english) < 20:
            continue

        if words is None:
            words = 150 if i <= 10 else 250
        if marks is None:
            marks = 10 if i <= 10 else 15

        questions.append(Question(
            paper=paper, year=year, question=english,
            words=words, marks=marks, q_num=i,
        ))
    return questions


# ───────────────────────── GS-IV parser ─────────────────────────


GS4_Q_RE = re.compile(r"^\s*Q\.?\s*(\d{1,2})\.?\s*", re.MULTILINE | re.IGNORECASE)


def parse_gs_iv(raw_text: str, year: int) -> list[Question]:
    """GS-IV. Splits by (Answer in N words) anchors, then tags section and
    parent-Q number from context. Sub-letters (a)/(b) are also captured."""
    text = strip_structural_noise(raw_text)
    anchors = list(ANSWER_ANCHOR_RE.finditer(text))
    if not anchors:
        return []

    questions: list[Question] = []
    prev_end = 0
    current_section: str | None = None
    current_parent: int | None = None
    for m in anchors:
        chunk = text[prev_end:m.start()]
        # Track section (A/B) advances.
        for sec_m in re.finditer(r"\bSECTION\s+([AB])\b", chunk, re.IGNORECASE):
            current_section = sec_m.group(1).upper()
        # Track latest parent Q number.
        for qm in GS4_Q_RE.finditer(chunk):
            try:
                current_parent = int(qm.group(1))
            except ValueError:
                pass
        # Latest "(a)"/"(b)" sub-letter.
        subs = list(re.finditer(r"\(([a-h])\)", chunk, re.IGNORECASE))
        sub = f"({subs[-1].group(1).lower()})" if subs else None

        english = _extract_english(chunk)
        if not english or len(english) < 20:
            prev_end = m.end()
            continue
        words = int(m.group(1))
        marks_raw = m.group(2)
        marks = int(marks_raw) if marks_raw else (10 if words == 150 else 20)
        questions.append(Question(
            paper="GS-IV", year=year, question=english,
            words=words, marks=marks,
            section=current_section, sub=sub, q_num=current_parent,
        ))
        prev_end = m.end()
    return questions


# ───────────────────────── Essay parser ─────────────────────────


def parse_essay(raw_text: str, year: int) -> list[Question]:
    """Essay: 8 topics, 4 per section. Each topic is a single concise English
    sentence. We scan all lines, keep those that pass strict English filter,
    have 15 ≤ len < 250, and are preceded by a numeric marker."""
    text = strip_structural_noise(raw_text)
    out: list[Question] = []
    section: str | None = None

    lines = text.splitlines()
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        sec_m = re.fullmatch(r"SECTION\s+([AB])", stripped, re.IGNORECASE)
        if sec_m:
            section = sec_m.group(1).upper()
            i += 1
            continue
        num_m = re.match(r"^\s*(\d+)\s*[\.,]\s*(.*)$", lines[i])
        if num_m:
            first = num_m.group(2).strip(" .,-|")
            # The numbered line usually has the Hindi topic; the English
            # translation is on the next (or next-plus-one) line. Search the
            # following few lines for the English version.
            candidate = first if is_english_prose(first) else ""
            for j in range(1, 4):
                if i + j >= len(lines):
                    break
                nxt = lines[i + j].strip(" .,-|")
                if not nxt:
                    continue
                if re.match(r"^\s*\d+\s*[\.,]\s+", nxt):
                    break
                if re.fullmatch(r"SECTION\s+[AB]", nxt, re.IGNORECASE):
                    break
                if is_english_prose(nxt):
                    # If candidate is already English, merge (wrapped line).
                    candidate = (candidate + " " + nxt).strip() if candidate else nxt
                    # Peek ahead: wrap one more line if it looks like
                    # continuation English.
                    if i + j + 1 < len(lines):
                        peek = lines[i + j + 1].strip(" .,-|")
                        if peek and is_english_prose(peek) and \
                           not re.match(r"^\s*\d+\s*[\.,]\s+", peek):
                            candidate = (candidate + " " + peek).strip()
                    break
            candidate = candidate.strip(" .,-|")
            if candidate and 15 <= len(candidate) < 280 and \
               not re.search(r"\d+\s*[x×]\s*\d", candidate):
                out.append(Question(
                    paper="Essay", year=year, question=candidate,
                    words=1100, marks=125, section=section,
                ))
        i += 1

    # Dedupe on lowercase (OCR sometimes double-reads a topic).
    seen: set[str] = set()
    dedup: list[Question] = []
    for q in out:
        k = q.question.lower()
        if k in seen:
            continue
        seen.add(k)
        dedup.append(q)
    return dedup[:8]  # hard cap at 8 topics


# ───────────────────────── dispatcher ─────────────────────────


def parse_file(ocr_path: Path) -> list[Question]:
    m = re.match(r"(\d{4})-(GS-I{1,3}V?|Essay)", ocr_path.stem)
    if not m:
        return []
    year = int(m.group(1))
    paper = m.group(2)
    raw = ocr_path.read_text()
    if paper in {"GS-I", "GS-II", "GS-III"}:
        return parse_gs_standard(raw, year=year, paper=paper)
    if paper == "GS-IV":
        return parse_gs_iv(raw, year=year)
    if paper == "Essay":
        return parse_essay(raw, year=year)
    return []
