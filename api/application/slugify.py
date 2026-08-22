import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_FALLBACK_SLUG = "untitled"


def slugify(text: str) -> str:
    """Derives a URL/slug-safe identifier from a display name (e.g. a category's name). Falls
    back to a fixed placeholder for the edge case of a name with no alphanumeric characters at all
    (e.g. "!!!") — the resulting slug still has to be non-empty to satisfy each table's NOT NULL
    slug column, and a caller can always rename to fix a collision the same way as any other
    duplicate slug."""
    slug = _NON_ALNUM.sub("-", text.strip().lower()).strip("-")
    return slug or _FALLBACK_SLUG
