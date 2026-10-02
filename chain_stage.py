#!/usr/bin/env python3
"""Settlement commands for the integrations API and the hub ledger."""

from __future__ import annotations

import json
import os
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


def return_for_refund(data: dict) -> tuple[dict, int] | None:
    """Return a sale when a refund names the fulfillment it closes."""
    if not isinstance(data, dict) or not data.get("fulfillment_id"):
        return None
    fulfillment_id = data.get("fulfillment_id")
    return_id = data.get("return_id") or f"return:{fulfillment_id}"
    try:
        artifact = {
            "return_id": _text(return_id, "return_id"),
            "fulfillment_id": _text(fulfillment_id, "fulfillment_id"),
        }
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    if not os.environ.get("SKINTWIN_CHAIN_LEDGER"):
        return {"ok": True, "artifact": artifact}, 200
    locator = _locator()
    if locator is None:
        return {"ok": False, "error": "supply-chain hub is not present"}, 400
    error = locator.commit_commands([{"command": "return_sale", "args": artifact}])
    if error:
        return {"ok": False, "error": error}, 400
    return {"ok": True, "artifact": artifact}, 200


def paystack_settlement(transaction: dict) -> dict | None:
    """A verified Paystack charge settles when its metadata names a fulfillment.

    Paystack's amount is already in minor units.
    """
    if not isinstance(transaction, dict):
        return None
    data = transaction.get("data") if isinstance(transaction.get("data"), dict) else transaction
    if not isinstance(data, dict):
        return None
    metadata = data.get("metadata") if data.get("metadata") is not None else {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except json.JSONDecodeError:
            metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    fulfillment_id = metadata.get("fulfillment_id") or data.get("fulfillment_id")
    if not isinstance(fulfillment_id, str) or not fulfillment_id.strip():
        return None
    reference = data.get("reference") or data.get("id") or fulfillment_id
    settlement_id = metadata.get("settlement_id") or f"pay-{reference}"
    if not isinstance(settlement_id, str) or not settlement_id.strip():
        return None
    amount = data.get("amount")
    if isinstance(amount, str) and amount.strip():
        try:
            amount = int(amount.strip()) if amount.strip().isdigit() else float(amount.strip())
        except ValueError:
            return None
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    cents = int(amount) if isinstance(amount, int) else int(round(float(amount)))
    if cents < 1:
        return None
    currency = data.get("currency") or metadata.get("currency") or "NGN"
    return {
        "fulfillment_id": fulfillment_id.strip(),
        "settlement_id": settlement_id.strip(),
        "amount_cents": cents,
        "currency": currency,
    }


def record_paystack_settlement(transaction: dict) -> tuple[dict, int] | None:
    payment = paystack_settlement(transaction)
    if payment is None:
        return None
    return settlement_for_payment(payment)


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
    if not os.environ.get("SKINTWIN_CHAIN_LEDGER"):
        return result
    locator = _locator()
    if locator is None:
        return {"ok": False, "error": "supply-chain hub is not present"}, 400
    error = locator.commit_command(request)
    if error:
        return {"ok": False, "error": error}, 400
    return result


def formula_id_from_shopify(product: dict) -> str | None:
    if not isinstance(product, dict):
        return None
    direct = product.get("formulaId") or product.get("formula_id")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    tags = product.get("tags")
    if isinstance(tags, str):
        tags = tags.split(",")
    if not isinstance(tags, list):
        return None
    for tag in tags:
        value = str(tag).strip()
        marker = "formula:"
        if value.lower().startswith(marker):
            formula = value[len(marker) :].strip()
            if formula:
                return formula
    return None


def shopify_catalog_commands(product: dict) -> list[dict]:
    formula_id = formula_id_from_shopify(product)
    if formula_id is None:
        return []
    name = _text(product.get("title") or product.get("name"), "name")
    variants = product.get("variants") if isinstance(product.get("variants"), list) else []
    sku = ""
    if variants and isinstance(variants[0], dict):
        sku = variants[0].get("sku") or ""
    sku = _text(sku or product.get("sku") or name, "sku")
    return [
        {
            "command": "catalog_sku",
            "args": {"sku_id": sku, "formula_id": formula_id, "name": name},
        }
    ]


def draft_order_commands(draft: dict) -> list[dict]:
    """A completed B2B draft is an outlet sale. Open and invoiced drafts are not."""
    if not isinstance(draft, dict):
        raise StageRejection("draft order is required")
    status = str(draft.get("status") or "").strip().lower()
    if status != "completed":
        return []
    order_number = draft.get("order_id") or draft.get("name") or draft.get("id")
    return shopify_fulfillment_commands(
        {
            "order_number": order_number,
            "line_items": draft.get("line_items") or [],
        }
    )


def shopify_fulfillment_commands(order: dict) -> list[dict]:
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    order_number = order.get("order_number") or order.get("name") or order.get("id")
    order_id = _text(str(order_number) if order_number is not None else "", "order number")
    items = order.get("line_items")
    if items is None:
        items = []
    if not isinstance(items, list):
        raise StageRejection("line_items must be a list")
    commands = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise StageRejection("each line item must be an object")
        sku = item.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            continue
        location, milligrams, kind, practitioner = _shopify_line(item)
        if location is None and milligrams is None and kind is None:
            continue
        if not isinstance(location, str) or not location.strip() or milligrams is None:
            raise StageRejection(f"sku {sku} requires location and milligrams")
        args = {
            "fulfillment_id": f"{order_id}:{index}:{sku.strip()}",
            "sku_id": sku.strip(),
            "location": location.strip(),
            "milligrams": _milligrams(milligrams),
            "kind": kind or "retail",
            "practitioner_id": practitioner,
        }
        if args["kind"] == "treatment" and not practitioner:
            raise StageRejection("practitioner_id is required")
        commands.append({"command": "fulfill", "args": args})
    return commands


def shopify_return_commands(order: dict) -> list[dict]:
    """A cancelled order returns the sale its lines would draw."""
    return _sale_returns(shopify_fulfillment_commands(order))


def _sale_returns(fulfillments: list[dict]) -> list[dict]:
    returns = []
    for command in fulfillments:
        fulfillment_id = command["args"]["fulfillment_id"]
        returns.append(
            {
                "command": "return_sale",
                "args": {
                    "return_id": f"return:{fulfillment_id}",
                    "fulfillment_id": fulfillment_id,
                },
            }
        )
    return returns


def shopify_settlement_commands(order: dict) -> list[dict]:
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    currency = order.get("currency") or "USD"
    explicit = order.get("fulfillment_id")
    if isinstance(explicit, str) and explicit.strip():
        order_number = order.get("order_number") or order.get("id") or explicit
        return [
            {
                "command": "settle",
                "args": {
                    "settlement_id": _text(
                        str(order.get("settlement_id") or f"pay-{order_number}"),
                        "settlement_id",
                    ),
                    "fulfillment_id": explicit.strip(),
                    "amount_cents": _price_cents(order.get("total_price") or order.get("amount")),
                    "currency": currency,
                },
            }
        ]
    commands = []
    order_number = order.get("order_number") or order.get("name") or order.get("id")
    order_id = str(order_number) if order_number is not None else ""
    for index, item in enumerate(order.get("line_items") or []):
        if not isinstance(item, dict):
            continue
        sku = item.get("sku")
        if not isinstance(sku, str) or not sku.strip():
            continue
        location, milligrams, _kind, _practitioner = _shopify_line(item)
        if location is None and milligrams is None:
            continue
        quantity = item.get("quantity") or 1
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
            raise StageRejection("quantity must be a positive integer")
        commands.append(
            {
                "command": "settle",
                "args": {
                    "settlement_id": f"pay-{order_id}:{index}:{sku.strip()}",
                    "fulfillment_id": f"{order_id}:{index}:{sku.strip()}",
                    "amount_cents": _price_cents(item.get("price")) * quantity,
                    "currency": currency,
                },
            }
        )
    return commands


def opencart_catalog_commands(product: dict) -> list[dict]:
    if not isinstance(product, dict):
        return []
    return shopify_catalog_commands(
        {
            "title": product.get("name") or product.get("title"),
            "sku": product.get("sku") or product.get("model"),
            "tags": product.get("tags") if product.get("tags") is not None else product.get("tag"),
            "formula_id": product.get("formula_id") or product.get("formulaId"),
            "variants": product.get("variants"),
        }
    )


_OPENCART_SHIPPED = frozenset({"shipped", "complete", "completed", "delivered", "fulfilled"})
_OPENCART_PAID = frozenset({"paid", "complete", "completed", "processed"})
_OPENCART_RETURNED = frozenset({"refunded", "cancelled", "canceled", "voided", "reversed"})


def opencart_fulfillment_commands(order: dict) -> list[dict]:
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    if _opencart_returned(order):
        return []
    status = _opencart_status(order)
    if order.get("fulfilled") is not True and status not in _OPENCART_SHIPPED:
        return []
    items = []
    for item in order.get("products") or order.get("line_items") or []:
        if not isinstance(item, dict):
            raise StageRejection("each product must be an object")
        items.append(
            {
                "sku": item.get("sku") or item.get("model"),
                "location": item.get("location"),
                "milligrams": item.get("milligrams"),
                "properties": item.get("properties"),
                "kind": item.get("kind"),
                "practitioner_id": item.get("practitioner_id"),
            }
        )
    return shopify_fulfillment_commands(
        {
            "order_number": order.get("order_id") or order.get("order_number") or order.get("id"),
            "line_items": items,
        }
    )


def opencart_settlement_commands(order: dict) -> list[dict]:
    """A paid OpenCart order settles the fulfillment its lines already name."""
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    if _opencart_returned(order):
        return []
    status = _opencart_status(order)
    if order.get("paid") is not True and status not in _OPENCART_PAID:
        return []
    items = []
    for item in order.get("products") or order.get("line_items") or []:
        if not isinstance(item, dict):
            raise StageRejection("each product must be an object")
        price = item.get("price")
        quantity = item.get("quantity") or 1
        if price is None and item.get("total") is not None:
            price = item.get("total")
            quantity = 1
        if price is None:
            continue
        items.append(
            {
                "sku": item.get("sku") or item.get("model"),
                "location": item.get("location"),
                "milligrams": item.get("milligrams"),
                "properties": item.get("properties"),
                "price": price,
                "quantity": _quantity(quantity) if price is not None else 1,
            }
        )
    return shopify_settlement_commands(
        {
            "order_number": order.get("order_id") or order.get("order_number") or order.get("id"),
            "currency": order.get("currency_code") or order.get("currency") or "USD",
            "total_price": order.get("total"),
            "fulfillment_id": order.get("fulfillment_id"),
            "settlement_id": order.get("settlement_id"),
            "line_items": items,
        }
    )


def opencart_return_commands(order: dict) -> list[dict]:
    """A refunded or cancelled order returns the sale its lines name."""
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    if not _opencart_returned(order):
        return []
    named = {
        key: value
        for key, value in order.items()
        if key not in {"status", "new_status", "order_status", "returned", "fulfilled", "paid"}
    }
    named["status"] = "shipped"
    return _sale_returns(opencart_fulfillment_commands(named))


def _opencart_status(order: dict) -> str:
    return str(order.get("status") or order.get("new_status") or order.get("order_status") or "").strip().lower()


def _opencart_returned(order: dict) -> bool:
    return order.get("returned") is True or _opencart_status(order) in _OPENCART_RETURNED


def wix_delivery_commands(booking: dict) -> list[dict]:
    if not isinstance(booking, dict):
        raise StageRejection("booking is required")
    booking = booking.get("booking") if isinstance(booking.get("booking"), dict) else booking
    booking_id = _text(str(booking.get("id") or ""), "booking id")
    services = booking.get("services") or []
    if isinstance(services, dict):
        services = [services]
    if not isinstance(services, list):
        raise StageRejection("services must be a list")
    commands = []
    for index, service in enumerate(services):
        if not isinstance(service, dict):
            raise StageRejection("each service must be an object")
        delivery = service.get("delivery")
        if not isinstance(delivery, dict):
            continue
        source = _text(delivery.get("source"), "source")
        destination = _text(delivery.get("destination"), "destination")
        if source == destination:
            raise StageRejection("transfer source and destination must differ")
        commands.append(
            {
                "command": "transfer",
                "args": {
                    "transfer_id": f"{booking_id}:{index}",
                    "sku_id": _text(delivery.get("sku_id"), "sku_id"),
                    "batch_id": _text(delivery.get("batch_id"), "batch_id"),
                    "source": source,
                    "destination": destination,
                    "milligrams": _milligrams(delivery.get("milligrams")),
                },
            }
        )
    return commands


def record_opencart_catalog(product: dict) -> dict | None:
    try:
        commands = opencart_catalog_commands(product)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_many(commands)


def record_opencart_fulfillments(order: dict) -> dict | None:
    try:
        commands = (
            opencart_fulfillment_commands(order)
            + opencart_settlement_commands(order)
            + opencart_return_commands(order)
        )
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_idempotent(commands)


def record_wix_deliveries(booking: dict) -> dict | None:
    try:
        commands = wix_delivery_commands(booking)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_many(commands)


def record_shopify_catalog(product: dict) -> dict | None:
    try:
        commands = shopify_catalog_commands(product)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_many(commands)


def record_shopify_fulfillments(order: dict) -> dict | None:
    try:
        commands = shopify_fulfillment_commands(order)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_fulfillments(commands)


def record_shopify_returns(order: dict) -> dict | None:
    try:
        commands = shopify_return_commands(order)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_idempotent(commands)


def record_draft_order(draft: dict) -> dict | None:
    try:
        commands = draft_order_commands(draft)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_fulfillments(commands)


def record_shopify_settlement(order: dict) -> dict | None:
    try:
        commands = shopify_settlement_commands(order)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_many(commands)


def _shopify_line(item: dict) -> tuple[object, object, str | None, str | None]:
    location = item.get("location")
    milligrams = item.get("milligrams")
    kind = None
    practitioner = item.get("practitioner_id")
    properties = item.get("properties") or []
    if isinstance(properties, list):
        for prop in properties:
            if not isinstance(prop, dict):
                continue
            name = str(prop.get("name") or "").lower()
            value = prop.get("value")
            if name == "location" and not location:
                location = value
            elif name == "milligrams" and milligrams is None:
                milligrams = value
            elif name == "kind" and isinstance(value, str):
                kind = value.strip()
            elif name == "practitioner_id" and not practitioner:
                practitioner = value
    return location, milligrams, kind, practitioner if isinstance(practitioner, str) else None


def _milligrams(value: object) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StageRejection("milligrams must be a positive integer")
    return value


def _price_cents(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise StageRejection("amount_cents is required")
    try:
        cents = int(round(float(value) * 100))
    except (TypeError, ValueError) as exc:
        raise StageRejection("amount_cents is required") from exc
    if cents < 1:
        raise StageRejection("amount_cents must be a positive integer")
    return cents


def _commit_fulfillments(commands: list[dict]) -> dict | None:
    """Append new fulfillments. The same sale arriving again is not a second draw."""
    return _commit_idempotent(commands)


def _commit_idempotent(commands: list[dict]) -> dict | None:
    """Append commands that are not already on the ledger with the same args."""
    if not commands:
        return None
    fresh = _unrecorded(commands)
    if fresh is None:
        return {"ok": False, "error": "id already exists"}
    if not fresh:
        return {"ok": True, "count": 0}
    return _commit_many(fresh)


def _command_identity(command: dict) -> tuple[str, str] | None:
    args = command.get("args") or {}
    name = command.get("command")
    if name == "fulfill":
        return ("fulfill", str(args.get("fulfillment_id")))
    if name == "settle":
        return ("settle", str(args.get("settlement_id")))
    if name == "return_sale":
        return ("return_sale", str(args.get("return_id")))
    return None


def _unrecorded(commands: list[dict]) -> list[dict] | None:
    raw = os.environ.get("SKINTWIN_CHAIN_LEDGER")
    if not raw:
        return commands
    path = Path(raw)
    if not path.is_file():
        return commands
    found: dict[tuple[str, str], dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        identity = _command_identity(record)
        if identity is None:
            continue
        found[identity] = record.get("args") or {}
    fresh: list[dict] = []
    for command in commands:
        identity = _command_identity(command)
        if identity is None:
            fresh.append(command)
            continue
        prior = found.get(identity)
        if prior is None:
            fresh.append(command)
            continue
        if prior != command["args"]:
            return None
    return fresh


def _quantity(value: object) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StageRejection("quantity must be a positive integer")
    return value


def _commit_many(commands: list[dict]) -> dict | None:
    if not commands:
        return None
    if not os.environ.get("SKINTWIN_CHAIN_LEDGER"):
        use_shared_ledger()
    locator = _locator()
    if locator is None:
        return {"ok": False, "error": "supply-chain hub is not present"}
    error = locator.commit_commands(commands)
    if error:
        return {"ok": False, "error": error}
    return {"ok": True, "count": len(commands)}


def use_shared_ledger() -> None:
    locator = _locator()
    if locator is not None:
        locator.bind_ledger()


_LOCATOR = None


def _locator():
    global _LOCATOR
    if _LOCATOR is False:
        return None
    if _LOCATOR is not None:
        return _LOCATOR
    import importlib.util

    script = _locate_script()
    if script is None:
        _LOCATOR = False
        return None
    spec = importlib.util.spec_from_file_location("skintwin_chain_locate", script)
    if spec is None or spec.loader is None:
        _LOCATOR = False
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _LOCATOR = module
    return module


def _recorded_hub(directory: Path, file_name: str) -> Path | None:
    directory = directory.resolve()
    registry_path = directory / "domain" / "org-ecosystem.json"
    script = directory / "domain" / file_name
    if not registry_path.is_file() or not (directory / "domain" / "supply-chain.json").is_file():
        return None
    if not script.is_file():
        return None
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    hub = data.get("hub") if isinstance(data, dict) else None
    name = hub.get("name") if isinstance(hub, dict) else None
    if name != directory.name:
        return None
    return script


def _locate_script() -> Path | None:
    override = os.environ.get("SKINTWIN_HUB_ROOT")
    if override:
        found = _recorded_hub(Path(override), "locate.py")
        if found is not None:
            return found
    start = Path(__file__).resolve()
    for parent in [start, *start.parents]:
        if not (parent / ".git").exists():
            continue
        try:
            children = list(parent.parent.iterdir())
        except OSError:
            return None
        for child in children:
            found = _recorded_hub(child, "locate.py")
            if found is not None:
                return found
        return None
    return None


def main() -> None:
    body, status = respond(json.load(sys.stdin))
    json.dump(body, sys.stdout)
    if status != 200:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
