import re

TAIWAN_PLATE_PATTERNS = [
    re.compile(r"^[A-Z]{2,4}-\d{3,4}$"),
    re.compile(r"^\d{4}-[A-Z]{2}$"),
]


def normalize_plate(text: str) -> str:
    text = text.upper().strip()
    text = re.sub(r"[^\w]", "", text)

    m = re.match(r"^([A-Z]{2,4})(\d{3,4})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    m = re.match(r"^(\d{4})([A-Z]{2})$", text)
    if m:
        return f"{m.group(1)}-{m.group(2)}"

    return text


def is_valid_taiwan_plate(text: str) -> bool:
    normalized = normalize_plate(text)
    return any(p.match(normalized) for p in TAIWAN_PLATE_PATTERNS)
