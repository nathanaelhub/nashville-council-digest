"""Check a summary against the official text it summarizes.

A summary passes only if every checkable fact in it appears in the source:
dollar amounts (compared as numbers, so "$6 million" matches "$6,000,000"),
other numbers and percentages, council districts, legislation file numbers,
and capitalized names (people, places, organizations). What this cannot
check is meaning: "approves" vs "rejects" with the same nouns. That is what
the eval's judge is for, and the eval measures both. The first word of a
sentence is not checked as a name (it is usually a capitalized verb), so a
one-word name opening a sentence goes unchecked.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

SCALE = {"thousand": 1e3, "million": 1e6, "billion": 1e9}
MONEY = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)(?:\s*(thousand|million|billion)\b)?", re.I)
NUMBER = re.compile(r"(?<![\w$.,])(\d[\d,]*(?:\.\d+)?)(%| percent)?(?![\w])", re.I)
FILE_NO = re.compile(r"\b(?:BL|RS|SBL|SRS|R|O)\d{4}-\d{1,5}\b")
DISTRICT = re.compile(r"\bDistricts?\s+(\d{1,2})((?:\s*(?:,|and|&)\s*\d{1,2})*)", re.I)
SENTENCE_START = re.compile(r"(?:^|[.!?:;]\s+|\n)\W*$")
NAME = re.compile(r"\b[A-Z][a-zA-Z'’.-]+(?:\s+(?:of|the|and|for|de|&)?\s*[A-Z][a-zA-Z'’.-]+)*")

# Capitalized words that are fine without appearing in the source.
COMMON = {
    "the", "a", "an", "this", "it", "its", "council", "metro", "metropolitan", "nashville", "davidson",
    "county", "city", "government", "resolution", "ordinance", "bill", "amendment", "substitute",
    "tennessee", "state", "district", "districts", "mayor", "item", "items", "if", "under", "for",
    "in", "on", "with", "after", "about", "and", "to", "of", "by", "from", "these", "that",
    "would", "will", "also", "approves", "allows", "lets", "gives", "sets", "accepts", "adds",
    "changes", "creates", "names", "renames", "appoints", "asks", "requests", "recognizes",
    "honors", "authorizes", "approving", "accepting", "people", "residents", "members", "january",
    "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
}


@dataclass
class Problem:
    kind: str     # money / number / district / file / name
    value: str
    def __str__(self) -> str:
        return f"{self.kind} {self.value!r} not found in the source"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s)


def amount(num: str, scale: str | None) -> float:
    return float(num.replace(",", "")) * SCALE.get((scale or "").lower(), 1)


def amounts(text: str) -> set[float]:
    return {round(amount(n, s), 2) for n, s in MONEY.findall(text)}


def numbers(text: str) -> set[float]:
    out = set()
    for n, _pct in NUMBER.findall(text):
        try:
            out.add(round(float(n.replace(",", "")), 4))
        except ValueError:
            pass
    return out


def district_numbers(text: str) -> set[int]:
    out = set()
    for first, rest in DISTRICT.findall(text):
        out.add(int(first))
        out.update(int(n) for n in re.findall(r"\d{1,2}", rest))
    return out


def check(summary: str, source: str) -> list[Problem]:
    s, src = norm(summary), norm(source)
    low = src.lower()
    problems: list[Problem] = []

    src_money = amounts(src)
    src_numbers = numbers(src) | src_money
    for n, scale in MONEY.findall(s):
        if round(amount(n, scale), 2) not in src_money:
            problems.append(Problem("money", f"${n}{' ' + scale if scale else ''}"))
    rest = MONEY.sub(" ", s)
    rest = FILE_NO.sub(" ", rest)
    rest = DISTRICT.sub(" ", rest)  # districts are checked on their own below
    for n, _pct in NUMBER.findall(rest):
        if round(float(n.replace(",", "")), 4) not in src_numbers:
            problems.append(Problem("number", n))
    src_districts = district_numbers(src)
    for d in sorted(district_numbers(s)):
        if d not in src_districts:
            problems.append(Problem("district", str(d)))
    for f in FILE_NO.findall(s):
        if f not in src:
            problems.append(Problem("file", f))
    for m in NAME.finditer(s):
        name = m.group()
        words = re.findall(r"[A-Za-z][A-Za-z'.-]*", name)
        if SENTENCE_START.search(s[:m.start()]):
            words = words[1:]  # "Pays for ..." is a verb, not a name
        words = [w for w in words if w.lower() not in COMMON]
        missing = [w for w in words if w.lower().strip(".") not in low]
        if missing:
            problems.append(Problem("name", name.rstrip(".")))
    return problems
