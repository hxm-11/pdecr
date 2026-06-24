"""
Clean parsed document text for PD-ECR ingestion.

Rules (in order):
1. Strip non-printable / replacement characters (obvious garbled text)
2. Remove repeated header/footer lines (appear > 2 times or on > 60 % of pages)
3. Merge abnormal line breaks (Chinese text split mid-sentence)
4. Collapse blank lines (max 1 consecutive)
5. Preserve heading hierarchy (# / ## / ###)
6. Preserve table rows (| ... |)
7. Never rewrite business facts (numbers, dates, names, measurements)
"""

from __future__ import annotations

import re
from collections import Counter


# ── Character-level cleaning ──

_RE_REPLACEMENT_CHAR = re.compile(r"�")          # Unicode replacement char
_RE_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # non-printable (keep \t \n)
_RE_GARBLED_BLOCK = re.compile(r"[^一-鿿　-〿＀-￯a-zA-Z0-9\s.,;:!?()\[\]{}/%°@#&*+=_\-|'\"<>]{4,}")

# ── Header / footer detection ──

_RE_PAGE_NUMBER = re.compile(r"^\s*\d{1,4}\s*$")     # standalone page number
_RE_SEPARATOR_LINE = re.compile(r"^[-=_*]{10,}$")     # ---- or ====
_RE_SHORT_REPEAT = re.compile(r"^.{1,30}$")            # potential header/footer (short lines)

# ── Chinese mid-sentence break merging ──

_RE_CHINESE = re.compile(r"[一-鿿　-〿＀-￯]")

# ── Heading / table markers ──

_RE_HEADING = re.compile(r"^#{1,6}\s")
_RE_TABLE_ROW = re.compile(r"^\|.+\|$")
_RE_TABLE_SEP = re.compile(r"^\|[\s\-:]+\|$")


def clean_text(text: str, *, dedup_headers: bool = True) -> str:
    """Clean parsed document text.

    Args:
        text: Raw parsed text (MinerU / Docling / OCR output).
        dedup_headers: If True, detect and remove repeated header/footer lines.

    Returns:
        Cleaned text.
    """
    if not text:
        return ""

    # ── Step 1: Character-level sanitisation ──
    text = _RE_REPLACEMENT_CHAR.sub(" ", text)
    text = _RE_CONTROL_CHARS.sub(" ", text)

    lines = text.splitlines()

    # ── Step 2: Detect and remove repeated header/footer lines ──
    if dedup_headers and len(lines) > 5:
        lines = _remove_repeated_headers_footers(lines)

    # ── Step 3: Merge abnormal line breaks (Chinese mid-sentence) ──
    merged: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        # Don't merge headings, table rows, or explicitly empty lines
        if (
            not line
            or _RE_HEADING.match(line)
            or _RE_TABLE_ROW.match(line.strip())
            or _RE_TABLE_SEP.match(line.strip())
        ):
            merged.append(line)
            i += 1
            continue

        # Try to merge with next line if current line looks incomplete
        # (ends with Chinese char or doesn't end with sentence-ending punctuation)
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if (
                next_line
                and not _RE_HEADING.match(next_line)
                and not _RE_TABLE_ROW.match(next_line)
                and not _RE_TABLE_SEP.match(next_line)
                and _should_merge(line, next_line)
            ):
                merged.append(line.rstrip() + next_line)
                i += 2
                continue

        merged.append(line)
        i += 1

    # ── Step 4: Collapse blank lines (max 1 consecutive) ──
    result: list[str] = []
    prev_empty = False
    for line in merged:
        is_empty = not line.strip()
        if is_empty:
            if not prev_empty:
                result.append("")
            prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    # ── Step 5: Strip leading/trailing blank lines ──
    while result and not result[0].strip():
        result.pop(0)
    while result and not result[-1].strip():
        result.pop()

    return "\n".join(result)


def _should_merge(current: str, next_line: str) -> bool:
    """Decide whether *current* and *next_line* should be merged into one."""
    current_stripped = current.rstrip()
    next_stripped = next_line.strip()

    if not current_stripped or not next_stripped:
        return False

    # Case 1: Current line ends with a Chinese character → likely mid-sentence break
    if _RE_CHINESE.search(current_stripped[-1]):
        return True

    # Case 2: Current line ends mid-word (lowercase letter or hyphen)
    if current_stripped[-1].islower() or current_stripped[-1] == "-":
        # Next line starts with lowercase — continuation of same word/sentence
        if next_stripped[0].islower():
            return True

    # Case 3: Current line does NOT end with sentence-ending punctuation
    # and next line starts lowercase or Chinese (continuation)
    if current_stripped[-1] not in ".!?。！？…)" and current_stripped[-1] != '"':
        if _RE_CHINESE.search(next_stripped[0]) or next_stripped[0].islower():
            # Only merge if current is reasonably long (not a standalone label)
            if len(current_stripped) > 15:
                return True

    return False


def _remove_repeated_headers_footers(lines: list[str]) -> list[str]:
    """Detect and blank out lines that appear as page headers/footers.

    Strategy:
    - Lines shorter than 60 chars that appear more than twice OR on > 60 % of pages
    - Standalone numbers (page numbers)
    - Separator rows (------)
    - Lines that are exactly the same on nearly every "page"
    """
    if len(lines) < 10:
        return list(lines)

    stripped = [line.strip() for line in lines]
    counter = Counter(line for line in stripped if line and len(line) < 60)

    total_lines = len(stripped)
    threshold = max(3, total_lines * 0.4)  # appear on > 40% of lines

    noisy: set[str] = set()
    for line, count in counter.items():
        if count >= threshold:
            noisy.add(line)
        # Very frequent short lines (appear > 10 times) are almost certainly noise
        if count > 10 and len(line) < 20:
            noisy.add(line)

    # Also detect separator rows and page numbers
    cleaned: list[str] = []
    for line in lines:
        s = line.strip()
        if s in noisy:
            cleaned.append("")  # blank out, don't remove (preserves paragraph spacing)
        elif _RE_PAGE_NUMBER.match(s):
            cleaned.append("")
        elif _RE_SEPARATOR_LINE.match(s):
            cleaned.append("")
        else:
            cleaned.append(line)

    return cleaned


def clean_for_embedding(text: str) -> str:
    """Extra cleaning specifically before embedding into vector DB.

    This is stricter than clean_text — it also:
    - Removes checkbox markers [ ] [x]
    - Normalises multiple spaces
    - Trims whitespace more aggressively
    But still preserves business facts.
    """
    text = clean_text(text)

    # Remove checkbox markers scattered by OCR
    text = re.sub(r"\[ \]\s*", "", text)
    text = re.sub(r"\[x\]\s*", "", text)
    text = re.sub(r"\[X\]\s*", "", text)

    # Normalise whitespace (but preserve line breaks)
    text = re.sub(r"[ \t]+", " ", text)

    return text
