import hashlib
from dataclasses import dataclass

# Based on DllTranslation/Models/ParatranzEntry.cs
@dataclass
class ParatranzEntry:
    """Represents a single entry for translation."""
    key: str
    original: str
    translation: str
    stage: int
    context: str

def generate_hash(text: str) -> str:
    """Generates a SHA256 hash for the given text."""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()