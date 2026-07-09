import re

# Matches a leading meta-preamble line only when it both starts with a typical
# interjection/announcement word AND contains a trigger word ("here's", "here
# is", "script"), so ordinary narration ("Welcome to the show!") is never
# caught just because it happens to start with a capitalized word.
_PREAMBLE = re.compile(
    r'^\s*(?=[^\n:]*?\b(?:here\'s|here is|script)\b)'
    r'(?:sure|okay|alright|certainly|absolutely|here\'s|here is)[^\n:]*:\s*',
    re.IGNORECASE,
)
_HEADING = re.compile(r'^#{1,6}\s*', re.MULTILINE)
# Bracketed/parenthesized labels ("[Narrator]:", "(Host)") with an optional
# trailing colon, or a bare capitalized label followed by a colon ("HOST:").
_SPEAKER_LABEL = re.compile(
    r'^\s*(?:\[[^\]]+\]|\([^)]+\))\s*:?\s*|^\s*[A-Z][A-Za-z0-9 ]{0,20}:\s*',
    re.MULTILINE,
)
_MARKDOWN_EMPHASIS = re.compile(r'(\*\*|\*|__|_|`)')
_EXTRA_BLANK_LINES = re.compile(r'\n{3,}')


def sanitize_script(text: str) -> str:
    """
    Strip markdown emphasis, headings, speaker labels, and conversational
    preambles that LLMs sometimes emit despite instructions not to — TTS
    engines read this literally (e.g. "asterisk asterisk" or "Host colon").

    Markdown emphasis is stripped before speaker-label detection so labels
    wrapped in emphasis (e.g. "**Host:**") are still recognized as labels
    rather than leaking through as plain text.
    """
    cleaned = text.strip()
    cleaned = _PREAMBLE.sub('', cleaned, count=1).strip()
    cleaned = _MARKDOWN_EMPHASIS.sub('', cleaned)
    cleaned = _HEADING.sub('', cleaned)
    cleaned = _SPEAKER_LABEL.sub('', cleaned)
    cleaned = _EXTRA_BLANK_LINES.sub('\n\n', cleaned)
    return cleaned.strip()


def validate_script(text: str, min_words: int = 30, max_words: int = 3000) -> str | None:
    """Return an error message if the script fails basic sanity checks, else None."""
    word_count = len(text.split())
    if word_count < min_words:
        return f"Script too short ({word_count} words) — likely a generation failure."
    if word_count > max_words:
        return f"Script too long ({word_count} words) — exceeds safe TTS/duration bounds."
    return None
