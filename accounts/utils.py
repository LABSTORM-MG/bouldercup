import re
from datetime import datetime
from html import escape
from html.parser import HTMLParser

from django.utils.text import slugify

from .models import Participant


_VOID_TAGS = frozenset({"br", "hr"})

_ALLOWED_ATTRS: dict[str, frozenset] = {
    "p":          frozenset({"style", "class"}),
    "h1":         frozenset({"style", "class"}),
    "h2":         frozenset({"style", "class"}),
    "h3":         frozenset({"style", "class"}),
    "h4":         frozenset({"style", "class"}),
    "blockquote": frozenset({"style", "class"}),
    "strong":     frozenset(),
    "em":         frozenset(),
    "u":          frozenset(),
    "s":          frozenset(),
    "sub":        frozenset(),
    "sup":        frozenset(),
    "br":         frozenset(),
    "hr":         frozenset(),
    "a":          frozenset({"href", "rel", "target"}),
    "ul":         frozenset({"style", "class", "start", "reversed", "type"}),
    "ol":         frozenset({"style", "class", "start", "reversed", "type"}),
    "li":         frozenset({"style", "class"}),
    "figure":     frozenset({"class"}),
    "table":      frozenset({"class"}),
    "tbody":      frozenset(),
    "thead":      frozenset(),
    "tr":         frozenset(),
    "td":         frozenset({"colspan", "rowspan", "style"}),
    "th":         frozenset({"colspan", "rowspan", "style"}),
    "span":       frozenset({"class", "style"}),
}

_TEXT_ALIGN_RE = re.compile(
    r"text-align\s*:\s*(left|center|right|justify)\s*;?", re.IGNORECASE
)
_SAFE_HREF_RE = re.compile(r"^(https?://|mailto:|/)", re.IGNORECASE)


def _filter_style(value: str) -> str | None:
    m = _TEXT_ALIGN_RE.search(value)
    return f"text-align: {m.group(1).lower()};" if m else None


def _filter_href(value: str) -> str | None:
    v = value.strip()
    return v if _SAFE_HREF_RE.match(v) else None


class _HtmlSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag not in _ALLOWED_ATTRS:
            return
        allowed = _ALLOWED_ATTRS[tag]
        parts = [tag]
        for name, value in attrs:
            if name not in allowed:
                continue
            if value is None:
                parts.append(name)
                continue
            if name == "style":
                value = _filter_style(value)
                if value is None:
                    continue
            elif name == "href":
                value = _filter_href(value)
                if value is None:
                    continue
            parts.append(f'{name}="{escape(value, quote=True)}"')
        self._out.append(f'<{" ".join(parts)}>')

    def handle_endtag(self, tag):
        if tag in _ALLOWED_ATTRS and tag not in _VOID_TAGS:
            self._out.append(f"</{tag}>")

    def handle_data(self, data):
        self._out.append(escape(data, quote=False))


def sanitize_html(html: str) -> str:
    """Strip disallowed tags/attributes from CKEditor5 HTML, preserving text content."""
    if not html:
        return html
    parser = _HtmlSanitizer()
    parser.feed(html)
    return "".join(parser._out)


def parse_date(value: str):
    """
    Parse date string in multiple formats.
    
    Supports: DD-MM-YYYY, DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD
    
    Returns:
        date object or None if parsing fails
    """
    formats = ("%d-%m-%Y", "%d.%m.%Y", "%d/%m/%Y", "%Y-%m-%d")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_gender(value: str) -> str | None:
    """
    Normalize gender string to model choice values.
    
    Accepts variations like 'm', 'male', 'w', 'weiblich', etc.
    
    Returns:
        'male', 'female', 'mixed' or None if unknown
    """
    mapping = {
        "m": "male",
        "male": "male",
        "w": "female",
        "f": "female",
        "female": "female",
        "weiblich": "female",
        "männlich": "male",
        "divers": "mixed",
        "mixed": "mixed",
        "other": "mixed",
    }
    return mapping.get(value.lower() if value else "")


def unique_username(base: str) -> str:
    """
    Generate unique username from base string.
    
    Appends numbers if username already exists.
    
    Args:
        base: Base string for username
        
    Returns:
        Unique username
    """
    cleaned = slugify(base) or "teilnehmer"
    candidate = cleaned
    counter = 1
    while Participant.objects.filter(username=candidate).exists():
        counter += 1
        candidate = f"{cleaned}{counter}"
    return candidate


def pick_value(row: dict, *keys: str) -> str:
    """
    Pick first non-empty value from dict by trying multiple keys.

    Useful for CSV parsing where column names might vary.

    Args:
        row: Dictionary to search in
        *keys: Keys to try in order

    Returns:
        First non-empty value found, or empty string
    """
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def hash_password(raw_password: str) -> str:
    """
    Hash a password using Django's make_password.

    Args:
        raw_password: The plaintext password to hash

    Returns:
        The hashed password string (e.g., pbkdf2_sha256$...)
    """
    from django.contrib.auth.hashers import make_password
    return make_password(raw_password)


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        raw_password: The plaintext password to verify
        hashed_password: The hashed password to check against

    Returns:
        True if the password matches, False otherwise
    """
    from django.contrib.auth.hashers import check_password
    return check_password(raw_password, hashed_password)
