#!/usr/bin/env python3
"""Settlement acceptance for external payment connectors."""

from __future__ import annotations

import json
import sys


def settle(args: dict) -> dict:
    currency = _text(args.get("currency"), "currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ValueError("currency must be a 3-letter code")
    return {
        "settlement_id": _text(args.get("settlement_id"), "settlement_id"),
        "fulfillment_id": _text(args.get("fulfillment_id"), "fulfillment_id"),
        "amount_cents": _positive(args.get("amount_cents"), "amount_cents"),
        "currency": currency,
    }


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()


def _positive(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def main() -> None:
    request = json.load(sys.stdin)
    if request.get("command") != "settle":
        _fail(f"unknown command {request.get('command')}")
    try:
        artifact = settle(request.get("args") or {})
    except ValueError as exc:
        _fail(str(exc))
    json.dump({"ok": True, "artifact": artifact}, sys.stdout)


def _fail(message: str) -> None:
    json.dump({"ok": False, "error": message}, sys.stdout)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
