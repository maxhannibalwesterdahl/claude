"""Regelbaseret læser til danske ingredienslinjer.

    "1½ dl piskefløde, måske lidt mindre"
    -> quantity=1.5, unit="dl", item="piskefløde", note="måske lidt mindre"

`item` er det, man køber: forberedelse ("finthakket", "skyllede") og størrelse
("store", "lille") fjernes, mens ord der gør varen til et andet produkt
("hakket oksekød", "frossen spinat", "røget paprika") beholdes.
"""

import re

from .model import ParsedIngredient

# Alias -> kanonisk enhed. None betyder styk (samme som ingen enhed).
UNITS: dict[str, str | None] = {
    "g": "g", "gr": "g", "gram": "g",
    "kg": "kg", "kilo": "kg",
    "ml": "ml", "cl": "cl", "dl": "dl",
    "l": "l", "liter": "l",
    "tsk": "tsk", "teskefuld": "tsk", "teske": "tsk",
    "spsk": "spsk", "spiseskefuld": "spsk", "spiseske": "spsk",
    "knsp": "knsp", "knivspids": "knsp", "knivspidser": "knsp",
    "nip": "nip", "drys": "drys", "dryp": "dryp", "stænk": "stænk",
    "fed": "fed",
    "dåse": "dåse", "dåser": "dåse", "ds": "dåse",
    "pakke": "pakke", "pakker": "pakke", "pk": "pakke",
    "pose": "pose", "poser": "pose",
    "glas": "glas",
    "bundt": "bundt", "bundter": "bundt",
    "håndfuld": "håndfuld", "håndfulde": "håndfuld",
    "skive": "skive", "skiver": "skive",
    "stængel": "stængel", "stængler": "stængel", "stilk": "stængel", "stilke": "stængel",
    "ark": "ark",
    "bakke": "bakke", "bakker": "bakke",
    "potte": "potte", "potter": "potte",
    "cm": "cm", "centimeter": "cm",
    "terning": "terning", "terninger": "terning",
    "plade": "plade", "plader": "plade",
    "blad": "blad", "blade": "blad",
    "kvist": "kvist", "kviste": "kvist",
    "stk": None, "styk": None,
}

# Forberedelse, tilstand og størrelse. Fjernes foran varen.
PREP_WORDS = {
    "hakket", "hakkede", "finthakket", "finthakkede", "grofthakket", "grofthakkede",
    "revet", "revne", "reven", "groftrevet", "groftrevne", "fintrevet", "fintrevne",
    "presset", "pressede", "friskpresset", "friskpressede",
    "skyllet", "skyllede", "skrællet", "skrællede", "renset", "rensede",
    "plukket", "plukkede", "drænet", "drænede", "smeltet", "smeltede",
    "blødt", "blød", "bløde", "knust", "knuste", "udstenet", "udstenede",
    "optøet", "optøede", "stuetempereret", "stuetempererede",
    "afskallet", "afskallede", "halveret", "halverede", "klippet", "klippede",
    "skrubbet", "skrubbede", "uskrællet", "uskrællede",
    "kogende",
    "koldt", "kold", "kolde", "lunkent", "lunken", "varmt", "varm",
    "lille", "små", "stor", "stort", "store", "mellem", "mellemstor", "mellemstore",
    "moden", "modent", "modne", "valgfri", "valgfrit", "god", "godt", "gode",
}

# Forberedelsesord, der er en del af produktets navn foran disse varer.
# "hakket oksekød" og "revet ost" købes sådan, "hakket persille" gør ikke.
PRODUCT_PREFIXES = {
    "hakket": {"oksekød", "svinekød", "kalvekød", "kyllingekød", "kylling", "lammekød",
               "grisekød", "grise-", "okse-", "kalkun", "kalkunkød"},
    "hakkede": {"tomater", "mandler", "hasselnødder"},
    "revet": {"ost", "cheddar", "mozzarella", "parmesan", "emmentaler",
              "cheddarost", "mozzarellaost", "pizzaost"},
    "knuste": {"tomater"},
}

FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125}
_FRAC_CHARS = "".join(FRACTIONS)

# Et tal: "2", "1,5", "1.5", "1½", "½", "1/2", "1 1/2".
_NUMBER = rf"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:[.,]\d+)?[{_FRAC_CHARS}]?|[{_FRAC_CHARS}])"
_QUANTITY_RE = re.compile(rf"^\s*(?P<a>{_NUMBER})(?:\s*[-–]\s*(?P<b>{_NUMBER}))?\s*")

_PAREN_RE = re.compile(r"\(([^)]*)\)")
_LEADING_OPTIONAL_RE = re.compile(r"^(?:evt\.?|eventuelt|lidt)\s+", re.IGNORECASE)

# Adskillere mellem vare og note, i prioriteret rækkefølge. Kommaet må ikke være
# et decimalkomma ("2,2 kg").
_NOTE_SEPARATORS = [
    re.compile(r",(?!\d)"),
    re.compile(r"\s+[-–]\s+"),
    re.compile(r"\s\+\s"),
    re.compile(r"\s+(?:på\s+)?ca\.\s"),
    re.compile(r"\s+eller\s+"),
    re.compile(r"\s+fra\s+"),
    re.compile(r"\s+til\s+(?:at\s|stegning|pynt|servering|pensling|drys)"),
]

# Forberedelse efter varen uden komma: "cherrytomater i halve",
# "forårsløg i 3 cm skrå stykker".
_TRAILING_CUT_RE = re.compile(
    r"\s+i\s+(?:\S+\s+){0,3}?"
    r"(?:tern|terninger|skiver|både|halve|kvarte|strimler|stykker|buketter|stave|ringe|flager)\b.*$"
)


def _to_float(text: str) -> float:
    text = text.strip()
    if " " in text:  # "1 1/2"
        whole, frac = text.split(None, 1)
        return float(whole) + _to_float(frac)
    if "/" in text:
        num, den = text.split("/", 1)
        return float(num) / float(den)
    if text[-1] in FRACTIONS:
        head = text[:-1]
        return (float(head) if head else 0.0) + FRACTIONS[text[-1]]
    return float(text.replace(",", "."))


def _split_note(text: str) -> tuple[str, str | None]:
    """Adskil vare og note: parenteser, kendte adskillere og skæring efter varen."""
    notes: list[str] = []

    def keep_paren(m: re.Match[str]) -> str:
        notes.append(m.group(1).strip())
        return " "

    text = _PAREN_RE.sub(keep_paren, text)
    for sep in _NOTE_SEPARATORS:
        parts = sep.split(text, maxsplit=1)
        # "2 små, finthakkede fed hvidløg": står der kun størrelse/forberedelse
        # før kommaet, er det ikke en note. Spring kommaet over.
        while len(parts) == 2 and _only_prep(parts[0]):
            head, tail = parts
            rest = sep.split(tail, maxsplit=1)
            parts = [head + " " + rest[0]] + rest[1:]
        if len(parts) == 1:
            text = parts[0]
        elif parts[0].strip():
            text = parts[0]
            notes.append(parts[1].strip())
    m = _TRAILING_CUT_RE.search(text)
    if m and text[: m.start()].strip():
        notes.append(m.group(0).strip())
        text = text[: m.start()]
    note = ", ".join(n for n in notes if n) or None
    return text, note


def _only_prep(text: str) -> bool:
    words = _clean(text).split()
    # Enheden står stadig foran her ("g små, faste kartofler").
    return bool(words) and all(w in PREP_WORDS or w in UNITS for w in words)


def _is_product_prefix(word: str, following: list[str]) -> bool:
    heads = PRODUCT_PREFIXES.get(word)
    return bool(heads and following and following[0] in heads)


def _strip_prep(words: list[str]) -> list[str]:
    """Fjern forberedelses- og størrelsesord i starten, men behold produktnavne."""
    while len(words) > 1 and words[0] in PREP_WORDS and not _is_product_prefix(words[0], words[1:]):
        words = words[1:]
    return words


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip(" .;:-").lower()


class DanishRuleParser:
    def parse(self, line: str) -> ParsedIngredient:
        raw = line
        text = re.sub(r"\s+", " ", line).strip()
        text = _LEADING_OPTIONAL_RE.sub("", text)

        quantity = quantity_max = None
        m = _QUANTITY_RE.match(text)
        if m:
            quantity = _to_float(m.group("a"))
            if m.group("b"):
                quantity_max = _to_float(m.group("b"))
            text = text[m.end():]

        item_text, note = _split_note(text)
        words = _strip_prep(_clean(item_text).split())

        unit = None
        if len(words) > 1 and words[0].rstrip(".") in UNITS:
            unit = UNITS[words[0].rstrip(".")]
            words = words[1:]
            if len(words) > 1 and words[0] == "af":  # "kviste af persille"
                words = words[1:]
            words = _strip_prep(words)

        item = _LEADING_OPTIONAL_RE.sub("", " ".join(words))
        return ParsedIngredient(
            raw=raw,
            quantity=quantity,
            unit=unit,
            item=item,
            note=note,
            quantity_max=quantity_max,
        )
