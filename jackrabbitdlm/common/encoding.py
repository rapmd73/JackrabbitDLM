#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared encoding/decoding functions for Jackrabbit DLM.

This module provides the default table-based encoding that converts each byte
into two printable characters. The encoding is NOT encryption -- it is simple
obfuscation to prevent casual inspection of network traffic.

Users can replace these with custom encoder/decoder functions (AES, zlib, etc.)
by passing them to the Locker constructor.

See also:
    - https://en.wikipedia.org/wiki/Obfuscation_(software)
    - https://en.wikipedia.org/wiki/Character_encoding
"""

import json
import random

# Encoding alphabet -- different order = different output.
# Reasonable obfuscation for short-lived locks (seconds to minutes).
ALPHABET = '1aA2bB3cC4dD5eE6fF7gG8hH9iI0jJ!kK@lL#mM$nN%oO^pP&qQ*rR(sS)tT/uU?vV=wW+xX;yY:zZ'
BASELEN = len(ALPHABET)

# Pre-calculated for O(1) lookups -- doubles throughput vs on-the-fly computation.
ENCODE_TABLE = [ALPHABET[b // BASELEN] + ALPHABET[b % BASELEN] for b in range(256)]
DECODE_TABLE = {ALPHABET[b // BASELEN] + ALPHABET[b % BASELEN]: b for b in range(256)}


def dlmEncode(data_bytes):
    """
    Encode bytes/str/dict into a two-char-per-byte printable string.
    
    Args:
        data_bytes: bytes, str, or dict (dicts are JSON-serialized first)
    
    Returns:
        Encoded string, or empty bytes on failure.
    """
    try:
        if isinstance(data_bytes, dict):
            data_bytes = json.dumps(data_bytes)
        if isinstance(data_bytes, str):
            data_bytes = data_bytes.encode('utf-8')
        return "".join(ENCODE_TABLE[b] for b in data_bytes)
    except Exception:
        return b""


def dlmDecode(encoded_str):
    """
    Decode a two-char-per-byte string back to raw bytes.
    
    Args:
        encoded_str: The encoded string to decode
    
    Returns:
        Decoded bytes, or empty bytes on failure.
    """
    try:
        if not encoded_str:
            return b""
        return bytes(DECODE_TABLE[encoded_str[i:i + 2]] for i in range(0, len(encoded_str), 2))
    except Exception:
        return b""


def ShuffleJSON(payload):
    """
    Randomize JSON key order for network transport obfuscation.
    
    This is NOT security -- it is zero-effort obfuscation at the transport
    layer. The cost is ~0.0007s for ~100 keys. The goal is to force full
    parsing instead of positional analysis by an observer.
    
    See also:
        - https://en.wikipedia.org/wiki/Obfuscation_(software)
    
    Args:
        payload: dict or JSON string
    
    Returns:
        dict with randomized key order
    """
    def _random_json(obj):
        if isinstance(obj, dict):
            items = list(obj.items())
            random.shuffle(items)
            return {k: _random_json(v) for k, v in items}
        elif isinstance(obj, list):
            return [_random_json(item) for item in obj]
        return obj

    if isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = payload

    return _random_json(data)
