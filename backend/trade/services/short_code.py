"""Reversible short code encoding for listing IDs.

Encodes integer IDs to short alphanumeric strings using XOR obfuscation + base36.
Not cryptographically secure — just hides sequential IDs from casual observation.
"""

_XOR_KEY = 0x4D7A3E
_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'


def encode(listing_id: int) -> str:
    """Encode a listing ID to a short alphanumeric code."""
    n = listing_id ^ _XOR_KEY
    if n == 0:
        return _ALPHABET[0]
    chars = []
    while n > 0:
        chars.append(_ALPHABET[n % 36])
        n //= 36
    return ''.join(reversed(chars))


def decode(code: str) -> int | None:
    """Decode a short code back to a listing ID. Returns None on invalid input."""
    try:
        n = int(code, 36)
    except ValueError:
        return None
    return n ^ _XOR_KEY
