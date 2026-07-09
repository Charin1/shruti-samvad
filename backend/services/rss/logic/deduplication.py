import hashlib
import re
from typing import Optional
from Levenshtein import ratio

def normalize_url(url: str) -> str:
    """Normalize URL by removing fragments and query parameters."""
    # Simple normalization: remove trailing slash and fragments
    url = url.split('#')[0]
    # Remove tracking parameters
    url = re.sub(r'utm_[a-z]+=[^&]+&?', '', url)
    url = url.rstrip('?').rstrip('&')
    return url.lower().strip()

def calculate_content_hash(text: Optional[str]) -> str:
    """Calculate SHA256 of cleaned text (first 2000 chars) for deduplication."""
    if not text:
        return ""
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Use first 2000 chars to avoid small variations at the end
    relevant_content = text[:2000].encode('utf-8')
    return hashlib.sha256(relevant_content).hexdigest()

def is_title_similar(title1: str, title2: str, threshold: float = 0.85) -> bool:
    """Check if two titles are similar using Levenshtein distance."""
    # Pre-processing
    t1 = re.sub(r'\W+', ' ', title1).lower().strip()
    t2 = re.sub(r'\W+', ' ', title2).lower().strip()
    
    return ratio(t1, t2) >= threshold
