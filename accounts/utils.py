from datetime import datetime

from django.utils.text import slugify

from .models import Participant


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
