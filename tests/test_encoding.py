#!/usr/bin/env python3
"""Basic encoding round-trip tests."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from jackrabbitdlm.common.encoding import dlmEncode, dlmDecode, ShuffleJSON


def test_encode_decode_roundtrip():
    """Test that encoding then decoding returns original data."""
    test_cases = [
        b"hello world",
        b'{"key": "value", "num": 42}',
        b"",
        bytes(range(256)),
    ]
    for original in test_cases:
        encoded = dlmEncode(original)
        decoded = dlmDecode(encoded)
        assert decoded == original, f"Roundtrip failed for {original[:50]}"
    print("PASS: encode/decode roundtrip")


def test_shuffle_json():
    """Test that ShuffleJSON preserves data while randomizing order."""
    data = {"z": 1, "a": 2, "m": {"nested": True, "deep": [1, 2, 3]}}
    shuffled = ShuffleJSON(data)
    assert shuffled["z"] == 1
    assert shuffled["a"] == 2
    assert shuffled["m"]["nested"] is True
    assert shuffled["m"]["deep"] == [1, 2, 3]
    print("PASS: ShuffleJSON")


if __name__ == '__main__':
    test_encode_decode_roundtrip()
    test_shuffle_json()
    print("All tests passed!")
