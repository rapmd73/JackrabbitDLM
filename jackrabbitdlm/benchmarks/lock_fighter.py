#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LockFighter - Stress Test for Jackrabbit DLM

Aggressive stress tester that hammers the DLM with lock/contention scenarios.
Designed to test stability under high concurrency -- NOT a security audit.

Usage:
    python3 lock_fighter.py [count] [chaos] [aggressive] [locks]
    
    count       Number of successful iterations (default: 1000)
    chaos       Randomly toggle between aggressive/patient modes
    aggressive  No retries, single-pass lock checks
    locks       Skip memory operations, test locks only

See also:
    - https://en.wikipedia.org/wiki/Stress_testing
    - https://en.wikipedia.org/wiki/Race_condition
    - https://en.wikipedia.org/wiki/Contention_(telecommunications)
"""

import sys
import os
import time
import json
import random

from jackrabbitdlm import Locker

PORT = 37373


def run_fighter(count=1000, chaos=False, aggressive=False, test_memory=True):
    """
    Run a single stress-test fighter process.
    
    Returns:
        dict with stats: pid, elapsed, failures, successes, reads, writes, contention, killed
    """
    ws = len(str(count))

    c = 0     # Memory counter
    f = 0     # Failed locks
    s = 0     # Successful locks
    r = 0     # Reads
    w = 0     # Writes
    k = 0     # Connections killed (payload too large)

    fw1 = Locker("LockerTest", Timeout=10, Retry=0, Port=PORT)
    memory = Locker('LockFighter', ID='LockFighterMemory', Port=PORT)

    if not fw1.IsDLM():
        print("JackrabbitDLM not found/running")
        sys.exit(1)

    # Auth credentials for large payload tests
    name = 'LockFighter'
    identity = ("PGQL3NNKy8Un5gikm2HqmJA_GHbnG8EX_146O30J28itRAC5VAa7CTOsNHLPysgB9"
                "M4BfdHN-xN8Gro7im2MoYGPkYlni6_qIIDsivXbzEHcELamOOl5CWFArQn_BUejj7"
                "Bps7eMQrDL9ozad2qvtazZuVlWAHQ8Ow5Y9WXjDm9zgvkt7eYa4BNhJ82SAgYL1S"
                "lUty8hV6jIYSB8_qZhYtWcKaGoAtRaJnFBXN_9n2ZBcZ8wt1Q-ZIcdVVUCi7bix9C"
                "p0owcsZj2gUaP_JrAWDZxVXz_ZbHuZkYo9aQqhnSbWwrXcwVaZHM6sNWfMg5bOpik"
                "2RSWQRsIsW3L9G7zzsVwOzrxkwWAPlo1ifu47LXA2PXFEmDLpbGHIwUyilLELjXRz"
                "o4Y5LxjtTJgMzsk2nBTw-49tDkgF-iMUQ-eBaOZ9b0ZgygJpH_c9p1Rh3aSWQ5DeL"
                "uWIseIUTgBB_WpaMPlhnLpqvG9X0I0RnimTy73_ySzZAhbCC6ltm1MY6D6sHuywM8"
                "mEU7FEw3S1kjVse7EkubdeLcfkkv1zuUPgnytbIWYrK-yhkKGF-9KB4sup9ls7o0d"
                "mdKySjWdS7OfV2SEiljPg82fgAr5Dy9QVXWzUUiSTReqMLQFC3w1z7HXyaILFkSRD"
                "E7HvZsukDhrXxO83G4H_5Botp2iVHHgrCM6X2jMpm4zTbxGxSin-seWt7cRid3j2f"
                "ouns9xh3IIb72vAlDA8iUDIdUdnfQPsveUHuLw8f7oBy87fqLCqgAjBZcsnfjiMT0"
                "oMEtrxMhlvyXnXdwjTBH2to9-WFe1psapsjz3fOXlGqFU8LGs-U3BknCQ6lZpJ90m8"
                "pzMWzzEgpGDHykPKomhQXVxPFaOZFI5nw1UF4IPuGvmVsfWQQR-upDWbRHgptHOJuR"
                "c7h4EFhFDIkTRrRtMIX3B1DEoSuun8B2vJfdSrjLJ_6E20c1pzGniQjvEZL_vr_eCu"
                "_sf2GSWZ_qlcAty7KBa-u0edyyqx3NCNp6IlqKYgqmeL9Otg_a51TuEdUo06ToqPd"
                "iVaBhBvNYMltNCVqPt95lHscdqYLhy8b0xD1XezkzIKH9wIrmrslOqIFe-RgchYGu"
                "Ko82v3Axx25CFCLG6bS3zILTtBTIRPgEnURqMfJNzgo2LvvcHjqoqLDr_uQsj7FCE"
                "zegEh_Z02OmxbibCG2jXT9ycFXMIhu3QciYKgoSZffo_OsZRHFnnSCFD96X_8AFXOz"
                "qDej5TrL_x6ysxRljAfrLl_s5cMyOEtIbniC_b0HD8pFppCGJvCRfBeXHakkfqF8k4"
                "vuT_QBWGTOw3SJJ01uaug0nghh_6xljcSZzBK2OXns33hK2XLK7Euu0VFWK-ueyYUV"
                "mGu_89tlFWT9cl5QNxYbPOAWRPd6gzc9Tq3aHZn6vWvg1c9He8L1DVFESVSFakQFHf"
                "TrOT43RCsiTTQ4zmDeXhsI3UY0MbOMKOO9SehwKBDTwT-v3OOuprHFhmF99ypJSW5H"
                "ui8-T2yOMv1sQTkY1flLD1wZyqcAw6y1iDm-MBXBIWPpVrOj4PhO5-_1LnqLWUX-Fv"
                "tSri1HPaZjy65ehQepamUS4AOZqGJvgMN_oAVHskguszq1Vlz2d9FsrjAdOxg6BLfI"
                "9x7PMQcbaFFVgl8XCQpe3pSE9eErWxIyIPk4wuGDHEVdk-xpiywpKaLC7MoX--Hmym"
                "FsrVWatfULyi5lwlY2Z9Mqxqp2Xwg9HL3RxpJah_XeKhsTaEta6YeBJYnKA4JpiMpn"
                "mzeLNk8amiCYSBSOUUM3DwTk7ndz-p5sn6zpNbUovyrE2G-rBrgUxpbJm_SR6d_rCV"
                "iq5JB3D_YR1MdJrkzu-VeBPfkz_JDpYTR7joDG5YOMSRCiB-bDqez86vi0MN3p7H86"
                "bvmKDaHrajsYRfxhMh77xhHNIh5hVVDRCXt9FTrXQ6A0S3vyRPBP9PT7jCCXzhQpoL"
                "wJuy-ERwuqwc6t9IM7-n2DRMu4M-mV9PK")

    wv = random.random()
    start_time = time.time()

    while c < count:
        try:
            retry_mode = random.random() > 0.5 if chaos else not aggressive

            if retry_mode:
                rl = fw1.Lock(expire=10)
            else:
                rl = fw1.IsLocked(expire=10)

            if rl == 'locked':
                try:
                    # Read
                    s_data = memory.Get()
                    r += 1

                    if 'DataStore' in s_data:
                        c = int(s_data['DataStore'])
                        if c < count and random.random() > round(wv, 2):
                            c += 1
                            memory.Put(data=str(c), expire=10)
                            w += 1
                    else:
                        memory.Put(data=str(c), expire=10)
                        w += 1

                    # Random junk payloads (if testing memory)
                    test_mem = random.random() > 0.5 if chaos else test_memory
                    if test_mem:
                        if random.random() > 0.5:
                            junker = Locker(
                                f'Junker:{fw1.GetID()}',
                                name=name, identity=identity, Port=PORT
                            )
                        else:
                            junker = Locker(f'Junker:{fw1.GetID()}', Port=PORT)

                        data = str(os.urandom(random.randint(8, 768) * 1024))
                        res = junker.Put(data=data, expire=random.randint(3, 60))
                        if junker.Error:
                            k += 1

                        if random.random() > 0.75:
                            junker.Erase()

                    s += 1
                except Exception:
                    f += 1
                    if retry_mode:
                        time.sleep(0.1)
                fw1.Unlock()
            else:
                f += 1
                if retry_mode:
                    time.sleep(0.1)

        except Exception:
            f += 1
            if not aggressive:
                time.sleep(0.1)

        if not aggressive:
            time.sleep(0.1)

    elapsed = time.time() - start_time
    cr = round((f / (s + f)) * 100, 2) if f > 0 else 0

    flag = 'C' if chaos else ('T' if not aggressive else 'F')
    print(f"{flag} {os.getpid():8} {elapsed:.8f} {f:{ws}} {s:{ws}} {r:{ws}} {w:{ws}} {cr:.2f} {k:{ws}} {c}")

    return {
        'pid': os.getpid(), 'elapsed': elapsed,
        'failures': f, 'successes': s, 'reads': r, 'writes': w,
        'contention': cr, 'killed': k
    }


if __name__ == '__main__':
    count = 1000
    chaos = 'chaos' in sys.argv
    aggressive = 'aggressive' in sys.argv
    test_memory = 'locks' not in sys.argv

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        count = int(sys.argv[1])

    run_fighter(count, chaos, aggressive, test_memory)
