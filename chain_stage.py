#!/usr/bin/env python3
"""Settlement commands for the integrations API and the hub ledger."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


class StageRejection(ValueError):
    pass


def settle(args: dict) -> dict:
    currency = _text(args.get("currency"), "currency").upper()
    if len(currency) != 3 or not currency.isalpha():
        raise StageRejection("currency must be a 3-letter code")
    return {
        "settlement_id": _text(args.get("settlement_id"), "settlement_id"),
        "fulfillment_id": _text(args.get("fulfillment_id"), "fulfillment_id"),
        "amount_cents": _positive(args.get("amount_cents"), "amount_cents"),
        "currency": currency,
    }


def settlement_for_payment(data: dict) -> tuple[dict, int] | None:
    """Settle a payment that names a fulfillment before the processor runs."""
    if not isinstance(data, dict) or not data.get("fulfillment_id"):
        return None
    try:
        cents = _cents(data)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    return respond(
        {
            "command": "settle",
            "args": {
                "settlement_id": data.get("settlement_id") or "",
                "fulfillment_id": data.get("fulfillment_id") or "",
                "amount_cents": cents,
                "currency": data.get("currency") or "USD",
            },
        }
    )


def _cents(data: dict) -> int:
    amount_cents = data.get("amount_cents")
    if isinstance(amount_cents, int) and not isinstance(amount_cents, bool):
        return amount_cents
    amount = data.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise StageRejection("amount_cents is required")
    cents = int(round(float(amount) * 100))
    if cents < 1:
        raise StageRejection("amount_cents must be a positive integer")
    return cents


def respond(body: dict) -> tuple[dict, int]:
    if body.get("command") != "settle":
        return {"ok": False, "error": f"unknown command {body.get('command')}"}, 400
    try:
        artifact = settle(body.get("args") or {})
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    return _commit(body, ({"ok": True, "artifact": artifact}, 200))


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StageRejection(f"{label} is required")
    return value.strip()


def _positive(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StageRejection(f"{label} must be a positive integer")
    return value


def _commit(request: dict, result: tuple[dict, int]) -> tuple[dict, int]:
    if result[1] != 200 or os.environ.get("SKINTWIN_CHAIN_SKIP_DISPATCH") == "1":
        return result
    ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
    if not ledger:
        return result
    hub = _hub_root()
    if hub is None:
        return {"ok": False, "error": "supply-chain hub is not present"}, 400
    completed = subprocess.run(
        [sys.executable, "-m", "domain.ledger"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        cwd=hub,
        check=False,
    )
    if completed.returncode != 0:
        try:
            message = json.loads(completed.stdout or "{}").get("error")
        except json.JSONDecodeError:
            message = None
        return {"ok": False, "error": message or completed.stderr or "ledger rejected the command"}, 400
    return result


def use_shared_ledger() -> None:
    hub = _hub_root()
    if hub is None:
        return
    os.environ.setdefault("SKINTWIN_HUB_ROOT", str(hub))
    os.environ.setdefault("SKINTWIN_CHAIN_LEDGER", str(hub / "var" / "supply-chain.jsonl"))


def _hub_root() -> Path | None:
    override = os.environ.get("SKINTWIN_HUB_ROOT")
    candidates = [Path(override)] if override else []
    candidates.extend(
        [
            Path("/agent/repos/skintwin-ecosystem-design"),
            Path("/workspace/repos/skintwin-ecosystem-design"),
        ]
    )
    for candidate in candidates:
        if (candidate / "domain" / "ledger.py").is_file():
            return candidate
    return None


def main() -> None:
    body, status = respond(json.load(sys.stdin))
    json.dump(body, sys.stdout)
    if status != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
