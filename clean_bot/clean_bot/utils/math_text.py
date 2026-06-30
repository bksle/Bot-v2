"""Plain-text helpers (no discord imports)."""

from __future__ import annotations

import unicodedata

# Mathematical Sans-Serif Bold Italic — Unicode Mathematical Alphanumeric Symbols
_MATH_SANS_BOLD_ITALIC_CAP_A = 0x1D63C
_MATH_SANS_BOLD_ITALIC_SM_A = 0x1D656

_ARABIC_CODEPOINT_RANGES: tuple[tuple[int, int], ...] = (
    (0x0600, 0x06FF),  # Arabic
    (0x0750, 0x077F),  # Arabic Supplement
    (0x08A0, 0x08FF),  # Arabic Extended-A
    (0xFB50, 0xFDFF),  # Arabic Presentation Forms-A
    (0xFE70, 0xFEFF),  # Arabic Presentation Forms-B
)


def _codepoint_in_ranges(cp: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _is_arabic_script_char(ch: str) -> bool:
    return _codepoint_in_ranges(ord(ch), _ARABIC_CODEPOINT_RANGES)


def _preserve_as_number(ch: str) -> bool:
    """ASCII digits and any Unicode decimal digit class (e.g. Arabic-Indic ٠–٩)."""
    if ch in "0123456789":
        return True
    return unicodedata.category(ch) == "Nd"


def to_mathematical_sans_serif_bold_italic(text: str) -> str:
    """
    Convert ASCII Latin letters (A–Z, a–z) to Mathematical Sans-Serif Bold Italic.

    Arabic script codepoints and decimal digits (ASCII or Arabic-Indic, etc.) are
    left unchanged; other characters pass through unchanged.
    """
    parts: list[str] = []
    for ch in text:
        if _is_arabic_script_char(ch) or _preserve_as_number(ch):
            parts.append(ch)
        elif "A" <= ch <= "Z":
            parts.append(chr(_MATH_SANS_BOLD_ITALIC_CAP_A + (ord(ch) - ord("A"))))
        elif "a" <= ch <= "z":
            parts.append(chr(_MATH_SANS_BOLD_ITALIC_SM_A + (ord(ch) - ord("a"))))
        else:
            parts.append(ch)
    return "".join(parts)
