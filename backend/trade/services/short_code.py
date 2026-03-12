"""Reversible short code encoding for listing IDs.

Encodes UUID IDs to short alphanumeric strings using XOR obfuscation + base36.
Not cryptographically secure — just hides sequential IDs from casual observation.
"""

from uuid import UUID

_XOR_KEY = 0x4D7A3E
_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyz'


def encode(listing_id) -> str:
    """Encode a listing ID (UUID) to a short alphanumeric code."""
    if isinstance(listing_id, UUID):
        n = listing_id.int ^ _XOR_KEY
    else:
        n = int(listing_id) ^ _XOR_KEY
    if n == 0:
        return _ALPHABET[0]
    chars = []
    while n > 0:
        chars.append(_ALPHABET[n % 36])
        n //= 36
    return ''.join(reversed(chars))


def decode(code: str) -> UUID | None:
    """Decode a short code back to a listing UUID. Returns None on invalid input."""
    try:
        n = int(code, 36)
    except ValueError:
        return None
    raw = n ^ _XOR_KEY
    try:
        return UUID(int=raw)
    except (ValueError, OverflowError):
        return None
