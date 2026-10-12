"""Address normalization for matching typed addresses against the City of
Toronto Address Points index — stdlib only, so the index build script and
the runtime lookup share it and their keys can never drift.

normalize() reduces an address to one canonical form: casefolded, no
punctuation, street type and direction contracted ("Street" -> "st",
"West" -> "w"), unit info dropped (so every unit collapses to its building),
and trailing city / province / postal code removed:

    normalize("Unit 5, 100 Queen Street West, Toronto, ON M5H 2N2")
    -> "100 queen st w"

The street type and direction are only rewritten in their usual position at
the end of the street name, so "St Clair Ave W" and "Avenue Rd" keep their
leading "st" / "avenue". No fuzzy matching: typos are not corrected.
"""
import re
from typing import NamedTuple

# Every spelling maps to one canonical (short) form, applied to both the
# index and the query, so it doesn't matter which form the city data uses.
_STREET_TYPES = {
    "avenue": "ave", "ave": "ave", "av": "ave",
    "boulevard": "blvd", "blvd": "blvd", "boul": "blvd",
    "circle": "cir", "cir": "cir", "circ": "cir",
    "circuit": "crct", "crct": "crct",
    "court": "crt", "crt": "crt", "ct": "crt",
    "crescent": "cres", "cres": "cres", "cr": "cres",
    "drive": "dr", "dr": "dr",
    "gardens": "gdns", "gdns": "gdns",
    "grove": "grv", "grv": "grv",
    "heights": "hts", "hts": "hts",
    "highway": "hwy", "hwy": "hwy",
    "lane": "ln", "ln": "ln",
    "parkway": "pkwy", "pkwy": "pkwy",
    "place": "pl", "pl": "pl",
    "road": "rd", "rd": "rd",
    "square": "sq", "sq": "sq",
    "street": "st", "st": "st",
    "terrace": "ter", "terr": "ter", "ter": "ter",
    "trail": "trl", "trl": "trl",
}

_DIRECTIONS = {
    "east": "e", "e": "e",
    "west": "w", "w": "w",
    "north": "n", "n": "n",
    "south": "s", "s": "s",
}

# Words that introduce a unit, followed by the unit's own token ("unit 5",
# "apt 12b"). "#305" is handled separately since it carries no space.
_UNIT_WORDS = {"unit", "apt", "apartment", "suite", "ste", "ph", "penthouse"}

# Trailing locality words dropped whether or not a comma precedes them.
_TRAILING_PLACE = {"toronto", "on", "ont", "ontario", "canada"}
# Former municipalities: only dropped as a whole comma-separated segment,
# since "York" or "East York" can also be part of a street name.
_LOCALITIES = {"toronto", "etobicoke", "north york", "scarborough", "east york", "york", "old toronto"}

_POSTAL = re.compile(r"\b[a-z]\d[a-z]\s?\d[a-z]\d\b")
_HASH_UNIT = re.compile(r"#\s*\w+")
# "12-100 Queen St W": the part before the dash is a unit number.
_UNIT_DASH = re.compile(r"^\s*\w+\s*-\s*(\d+\w?)\b")
_NUMBER = re.compile(r"^(\d+)([a-z]?)$")


class ParsedAddress(NamedTuple):
    number: int | None
    suffix: str  # "a" for "12A"; "" when none
    street: str  # normalized street name, e.g. "queen st w"


def _clean(text: str) -> str:
    text = text.casefold()
    text = _HASH_UNIT.sub(" ", text)
    text = _UNIT_DASH.sub(r"\1", text)
    text = text.replace("'", "")  # "St. John's" -> "st johns"
    return re.sub(r"[^\w,]+", " ", text)


def _strip_segments(text: str) -> str:
    """Drop comma-separated segments that are a locality, province, postal
    code, or a bare unit ("Unit 5, 100 Queen St W")."""
    kept = []
    for seg in text.split(","):
        seg = " ".join(seg.split())
        if not seg or seg in _LOCALITIES or seg in _TRAILING_PLACE or _POSTAL.fullmatch(seg):
            continue
        words = seg.split()
        if words[0] in _UNIT_WORDS and len(words) <= 2:
            continue
        kept.append(seg)
    return " ".join(kept)


def _drop_units(words: list[str]) -> list[str]:
    out, skip = [], False
    for w in words:
        if skip:
            skip = False
        elif w in _UNIT_WORDS:
            skip = True  # drop the marker and the unit token after it
        else:
            out.append(w)
    return out


def _canonical_street(words: list[str]) -> list[str]:
    """Contract the trailing direction and street type in place."""
    words = list(words)
    end = len(words)
    if end >= 2 and words[-1] in _DIRECTIONS:
        words[-1] = _DIRECTIONS[words[-1]]
        end -= 1
    if end >= 2 and words[end - 1] in _STREET_TYPES:
        words[end - 1] = _STREET_TYPES[words[end - 1]]
    return ["st" if w == "saint" else w for w in words]


def _words(text: str) -> list[str]:
    text = _POSTAL.sub(" ", _strip_segments(_clean(text)))
    words = _drop_units(text.split())
    while words and words[-1] in _TRAILING_PLACE:
        words.pop()
    return words


def parse_query(text: str) -> ParsedAddress:
    """Split an address into (number, suffix, normalized street).

    number is None when the text doesn't start with a house number, e.g. a
    bare street name typed into the autocomplete box.
    """
    words = _words(text)
    number, suffix = None, ""
    if words:
        m = _NUMBER.match(words[0])
        if m:
            number, suffix = int(m.group(1)), m.group(2)
            words = words[1:]
    return ParsedAddress(number, suffix, " ".join(_canonical_street(words)))


def normalize(text: str) -> str:
    """Canonical form of an address, e.g. "100 queen st w" or "12a main st"."""
    p = parse_query(text)
    head = f"{p.number}{p.suffix}" if p.number is not None else ""
    return " ".join(part for part in (head, p.street) if part)
