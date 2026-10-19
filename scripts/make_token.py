#!/usr/bin/env python3
"""Print a JWT for testing.   JWT_SECRET=... python scripts/make_token.py alice --plan pro"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway.auth import create_token


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sub", help="user id to put in the token")
    parser.add_argument("--plan", choices=["free", "pro"], default="free")
    parser.add_argument("--ttl", type=int, default=3600, help="seconds until expiry")
    args = parser.parse_args()
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        sys.exit("Set JWT_SECRET to the same value the gateway uses")
    print(create_token(args.sub, args.plan, secret, args.ttl))


if __name__ == "__main__":
    main()
