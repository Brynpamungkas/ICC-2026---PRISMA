"""Text normalization shared by S1 and the catalog (K-12, conservative option: no stemming, no fuzzy matching).

Must stay identical to scripts/catalog_lib.normalize_term (a unit test checks this)."""
import re
import unicodedata


def normalize_term(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).casefold()
    t = re.sub(r"[^\w\s%]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokenize(text: str) -> list[str]:
    n = normalize_term(text)
    return n.split(" ") if n else []
