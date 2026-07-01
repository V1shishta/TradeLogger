#!/usr/bin/env python3
"""Entry point for Trade Journal Pro.

Usage:
    python run.py                 # start the server on http://127.0.0.1:8000
    python run.py --port 9000     # custom port
    python run.py --seed          # load demo data into a fresh demo account
    python run.py --seed --reset  # wipe the DB first, then seed

The app is 100% standard library — no pip install required.
"""
import argparse

from backend import server
from backend import seed as seed_mod


def main():
    parser = argparse.ArgumentParser(description="Trade Journal Pro")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--seed", action="store_true", help="Seed a demo account and exit")
    parser.add_argument("--reset", action="store_true", help="Wipe the database (use with --seed)")
    args = parser.parse_args()

    if args.seed:
        seed_mod.run(reset=args.reset)
        return
    server.serve(args.host, args.port)


if __name__ == "__main__":
    main()
