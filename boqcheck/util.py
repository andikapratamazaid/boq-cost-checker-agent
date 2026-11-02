"""Number, unit and text normalisation helpers (Indonesian construction documents)."""
from __future__ import annotations

import math
import re


def parse_number(x, locale: str = "auto"):
    """Parse a spreadsheet cell into a float, or None.

    locale 'auto' (default): Indonesian-style ('.' thousands, ',' decimal), except that a plain number with a
    decimal point is kept as-is when that is unambiguous (12.5, 1234.5, 0.125). A lone '1.234' (one dot, exactly three
    digits after it, at most three digits before it) is read as 1234, because that is how Indonesian sheets write it.
    locale 'en': ',' is thousands and '.' is the decimal point.
    """
    if x is None:
        return None
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and math.isnan(x)) else float(x)
    s = str(x).strip()
    if s == "" or s.lower() in ("nan", "none", "-", "n/a"):
        return None
    s = re.sub(r"(?i)\brp\.?", "", s).replace(" ", "").replace("\u00a0", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if s.startswith("-"):
        neg, s = True, s[1:]
    if not s:
        return None
    if locale in ("auto", "plain", "en") and re.fullmatch(r"\d+(\.\d+)?", s):
        head, _, tail = s.partition(".")
        thousands = locale == "auto" and len(tail) == 3 and head != "0" and len(head) <= 3
        v = float(head + tail) if thousands else float(s)
    elif locale == "en":
        v = float(s.replace(",", ""))
    else:  # Indonesian style
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
        elif "," in s:
            s = s.replace(".", "").replace(",", ".")
        elif s.count(".") > 1:
            s = s.replace(".", "")
        elif "." in s:
            head, tail = s.split(".")
            s = head + tail if len(tail) == 3 else s
        try:
            v = float(s)
        except ValueError:
            return None
    return -v if neg else v


_UNIT_MAP = {
    "m": "m", "m1": "m", "m'": "m", "mtr": "m", "meter": "m", "lm": "m", "mlari": "m",
    "m2": "m2", "m3": "m3", "kg": "kg", "ton": "ton", "buah": "bh", "bh": "bh", "unit": "unit", "ls": "ls",
    "lumpsum": "ls", "lump": "ls", "titik": "titik", "oh": "oh", "zak": "zak", "lembar": "lbr", "lbr": "lbr",
    "set": "set", "stel": "stel", "batang": "btg", "btg": "btg", "liter": "l", "ltr": "l",
}


def norm_unit(u) -> str:
    s = str(u or "").strip().lower().replace(" ", "").replace(".", "").replace("²", "2").replace("³", "3")
    return _UNIT_MAP.get(s, s)


def units_compatible(a, b) -> bool:
    return norm_unit(a) == norm_unit(b)


_STOP = {"dan", "dengan", "untuk", "yang", "per", "ke", "di", "pada", "serta", "dgn", "utk", "cm"}
_SYN = {
    "pek": "pekerjaan", "pekj": "pekerjaan", "pengerjaan": "pekerjaan",
    "pas": "pasang", "psg": "pasang", "pasangan": "pasang", "pemasangan": "pasang", "memasang": "pasang",
    "bata": "bata", "batubata": "bata", "batumerah": "bata",
    "pelesteran": "plester", "plesteran": "plester", "plester": "plester",
    "pengecatan": "cat", "pelapisan": "cat", "cat": "cat",
    "begisting": "bekisting", "bekesting": "bekisting", "bekisting": "bekisting",
    "penulangan": "pembesian", "pembesian": "pembesian",
    "penggalian": "galian", "galian": "galian",
    "pengurugan": "urug", "urugan": "urug", "urug": "urug",
    "plafond": "plafon", "plafon": "plafon", "tbl": "tebal", "dlm": "dalam",
    "kudakuda": "kudakuda",
}


def norm_text(s) -> list[str]:
    """Tokenise a work-item description so that spelling variants compare equal."""
    t = str(s or "").lower().replace("½", " setengah ")
    t = t.replace("kuda-kuda", "kudakuda").replace("kuda kuda", "kudakuda")
    t = re.sub(r"\bbatu\s+merah\b|\bbata\s+merah\b|\bbatu\s+bata\b", " bata ", t)
    t = re.sub(r"\bk\s*-?\s*(\d{2,3})\b", r" k\1 ", t)                         # K-225 / K 225 -> k225
    t = re.sub(r"(\d+)\s*[x×]\s*(\d+)", r" \1x\2 ", t)                          # 40 x 40 -> 40x40
    t = re.sub(r"\b1\s*(?:pc|sm|pc\.)?\s*:\s*(\d+)(?:\s*(?:pp|ps|psr|pasir))?", r" mix\1 ", t)  # 1 Pc : 4 Pp -> mix4
    t = re.sub(r"\b1\s*/\s*2\b", " setengah ", t)
    t = re.sub(r"(\d),(\d)", r"\1.\2", t)
    t = re.sub(r"[^a-z0-9.\s]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    toks = []
    for w in t.split():
        w = _SYN.get(w, w)
        if w in _STOP or not w:
            continue
        toks.append(w)
    return toks


def has_digit(tok: str) -> bool:
    return any(c.isdigit() for c in tok)
