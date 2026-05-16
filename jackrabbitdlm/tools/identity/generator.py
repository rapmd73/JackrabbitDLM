#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Identity Generator for Jackrabbit DLM

Creates authentication configuration files with cryptographically random
identity strings. Required for authenticated (long-TTL, large-payload) operations.

Usage:
    python3 -m jackrabbitdlm.tools.identity <name>
    
    Creates: {BASE_DIR}/Config/{name}.cfg

See also:
    - https://en.wikipedia.org/wiki/Cryptographically_secure_pseudorandom_number_generator
    - https://en.wikipedia.org/wiki/Authentication
"""

import sys
import os
import json
import time
import random
import secrets

BASE_DIR = os.environ.get("JACKRABBIT_BASE", "/home/JackrabbitDLM")
CONFIG_DIR = os.path.join(BASE_DIR, "Config")


def generate_identity(name):
    """
    Generate a new identity file for the given name.
    
    Args:
        name: Identity name (used as filename)
    
    Returns:
        True if created, False if already exists or error.
    """
    path = os.path.join(CONFIG_DIR, f"{name}.cfg")
    
    if os.path.exists(path):
        print(f"Identity '{name}' already exists. Aborting.")
        return False

    os.makedirs(CONFIG_DIR, exist_ok=True)
    
    random.seed(time.time())
    length = random.randrange(1023, 2048)
    identity = secrets.token_urlsafe(length)

    with open(path, 'w') as f:
        f.write(json.dumps({"Identity": identity}) + '\n')

    print(f"Identity '{name}' written to {path}")
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 -m jackrabbitdlm.tools.identity <name>")
        sys.exit(1)

    if not generate_identity(sys.argv[1]):
        sys.exit(1)


if __name__ == '__main__':
    main()
