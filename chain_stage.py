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
    if not isinstance(data, dict):
        return None
    fulfillment_id = _named(data, "fulfillment_id", "fulfillmentId")
    if not fulfillment_id:
        return None
    return_id = _named(data, "return_id", "returnId") or f"return:{fulfillment_id}"
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
    fulfillment_id = _named(metadata, "fulfillment_id", "fulfillmentId") or _named(
        data, "fulfillment_id", "fulfillmentId"
    )
    if not fulfillment_id:
        return None
    reference = _order_label(data, "reference", "id") or fulfillment_id
    settlement_id = (
        _named(metadata, "settlement_id", "settlementId")
        or _named(data, "settlement_id", "settlementId")
        or f"pay-{reference}"
    )
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
    currency = _currency_text(data.get("currency")) or _currency_text(metadata.get("currency")) or "NGN"
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
    if not isinstance(data, dict):
        return None
    fulfillment_id = _named(data, "fulfillment_id", "fulfillmentId")
    if not fulfillment_id:
        return None
    try:
        cents = _cents(data)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    settlement_id = _named(data, "settlement_id", "settlementId") or f"pay-{fulfillment_id}"
    return respond(
        {
            "command": "settle",
            "args": {
                "settlement_id": settlement_id,
                "fulfillment_id": fulfillment_id,
                "amount_cents": cents,
                "currency": _currency_text(data.get("currency")) or "USD",
            },
        }
    )


def _cents(data: dict) -> int:
    """A whole cent string is already minor units. A numeric amount is major units."""
    amount_cents = _whole_count(data.get("amount_cents"))
    if isinstance(amount_cents, int) and not isinstance(amount_cents, bool):
        return amount_cents
    amount = data.get("amount")
    if isinstance(amount, str):
        text = amount.strip()
        try:
            amount = float(text) if text else None
        except ValueError:
            amount = None
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise StageRejection("amount_cents is required")
    cents = int(round(float(amount) * 100))
    if cents < 1:
        raise StageRejection("amount_cents must be a positive integer")
    return cents


def respond(body: dict) -> tuple[dict, int]:
    commands = body.get("commands")
    if isinstance(commands, list):
        return _respond_many(commands)
    if body.get("command") != "settle":
        return {"ok": False, "error": f"unknown command {body.get('command')}"}, 400
    try:
        artifact = settle(body.get("args") or {})
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    return _commit({"command": "settle", "args": artifact}, ({"ok": True, "artifact": artifact}, 200))


def _respond_many(commands: list) -> tuple[dict, int]:
    """Several settlements of one invoice are one ledger write."""
    accepted = []
    try:
        for command in commands:
            if not isinstance(command, dict) or command.get("command") != "settle":
                name = command.get("command") if isinstance(command, dict) else command
                return {"ok": False, "error": f"unknown command {name}"}, 400
            artifact = settle(command.get("args") or {})
            accepted.append({"command": "settle", "args": artifact})
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}, 400
    if not accepted or os.environ.get("SKINTWIN_CHAIN_SKIP_DISPATCH") == "1":
        return {"ok": True, "artifact": accepted, "count": len(accepted)}, 200
    if not os.environ.get("SKINTWIN_CHAIN_LEDGER"):
        return {"ok": True, "artifact": accepted, "count": len(accepted)}, 200
    locator = _locator()
    if locator is None:
        return {"ok": False, "error": "supply-chain hub is not present"}, 400
    error = locator.commit_commands(accepted)
    if error:
        return {"ok": False, "error": error}, 400
    return {"ok": True, "artifact": accepted, "count": len(accepted)}, 200


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StageRejection(f"{label} is required")
    return value.strip()


def _whole_count(value: object) -> object:
    """A digit string is that integer. Anything else is left as written."""
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return value


def _positive(value: object, label: str) -> int:
    value = _whole_count(value)
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
    direct = _named(product, "formulaId", "formula_id")
    if direct:
        return direct
    metafields = product.get("metafields")
    if isinstance(metafields, list):
        for field in metafields:
            if not isinstance(field, dict):
                continue
            if field.get("key") not in ("formula_id", "formulaId"):
                continue
            value = field.get("value")
            if isinstance(value, str) and value.strip():
                return value.strip()
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


def _named(record: object, *keys: str) -> str:
    """The first non-blank string wins. A blank value falls through to the next key."""
    if not isinstance(record, dict):
        return ""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _currency_text(value: object) -> str:
    """A blank currency is absent. A present code is kept as written."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return ""


def _order_label(record: object, *keys: str) -> str:
    """A present order number wins. A blank one falls through to the next name."""
    if not isinstance(record, dict):
        return ""
    for key in keys:
        value = record.get(key)
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value:
            return str(value).strip()
    return ""


def _named_sku(record: object) -> str:
    return _named(record, "sku", "sku_id", "skuId")


def _catalog_skus(product: dict, name: str) -> list[str]:
    """Each variant that names a sku is its own catalog entry. A blank sku is not one."""
    variants = product.get("variants") if isinstance(product.get("variants"), list) else []
    skus: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        sku = _named_sku(variant)
        if not sku or sku in seen:
            continue
        seen.add(sku)
        skus.append(sku)
    if skus:
        return skus
    return [_text(_named_sku(product) or name, "sku")]


def _catalog_name(product: dict) -> str:
    """A present title wins. A blank title falls through to the product name."""
    return _text(_named(product, "title", "name"), "name")


def shopify_catalog_commands(product: dict) -> list[dict]:
    if not isinstance(product, dict):
        return []
    formula_id = formula_id_from_shopify(product)
    if formula_id is not None:
        name = _catalog_name(product)
        return [
            {
                "command": "catalog_sku",
                "args": {"sku_id": sku, "formula_id": formula_id, "name": name},
            }
            for sku in _catalog_skus(product, name)
        ]
    named: list[tuple[str, str]] = []
    seen: set[str] = set()
    variants = product.get("variants") if isinstance(product.get("variants"), list) else []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        sku = _named_sku(variant)
        if not sku or sku in seen:
            continue
        variant_formula = formula_id_from_shopify(variant)
        if variant_formula is None:
            continue
        seen.add(sku)
        named.append((sku, variant_formula))
    if not named:
        return []
    name = _catalog_name(product)
    return [
        {
            "command": "catalog_sku",
            "args": {"sku_id": sku, "formula_id": variant_formula, "name": name},
        }
        for sku, variant_formula in named
    ]


def draft_order_commands(draft: dict) -> list[dict]:
    """A completed B2B draft is an outlet sale. Open and invoiced drafts are not."""
    if not isinstance(draft, dict):
        raise StageRejection("draft order is required")
    status = str(draft.get("status") or "").strip().lower()
    if status != "completed":
        return []
    order_number = _order_label(draft, "order_id", "name", "id")
    return shopify_fulfillment_commands(
        {
            "order_number": order_number,
            "line_items": draft.get("line_items") or [],
            "note_attributes": draft.get("note_attributes") or [],
        }
    )


def shopify_fulfillment_commands(order: dict) -> list[dict]:
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    order_id = _text(_order_label(order, "order_number", "name", "id"), "order number")
    items = order.get("line_items")
    if items is None:
        items = []
    if not isinstance(items, list):
        raise StageRejection("line_items must be a list")
    commands = []
    defaults = _order_line_defaults(order)
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise StageRejection("each line item must be an object")
        sku = _named_sku(item)
        if not sku:
            continue
        location, milligrams, kind, practitioner = _shopify_line(item, defaults)
        if location is None and milligrams is None and kind is None:
            continue
        if not isinstance(location, str) or not location.strip() or milligrams is None:
            raise StageRejection(f"sku {sku} requires location and milligrams")
        args = {
            "fulfillment_id": f"{order_id}:{index}:{sku}",
            "sku_id": sku,
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


_SHOPIFY_RETURNED = frozenset({"refunded", "voided"})


def _shopify_returned(order: dict) -> bool:
    if order.get("cancelled_at") or order.get("cancel_reason"):
        return True
    status = str(order.get("financial_status") or "").strip().lower()
    return status in _SHOPIFY_RETURNED


def shopify_refunded_line_commands(order: dict) -> list[dict]:
    """A fully refunded line of a shipped order returns that sale.

    A refund quantity below the line quantity stays off the ledger.
    """
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    items = order.get("line_items") or []
    if not isinstance(items, list):
        raise StageRejection("line_items must be a list")
    indexes: dict[object, int] = {}
    for index, item in enumerate(items):
        if isinstance(item, dict) and item.get("id") is not None:
            indexes[item.get("id")] = index
    refunds = order.get("refunds") or []
    if not isinstance(refunds, list):
        raise StageRejection("refunds must be a list")
    order_id = _text(_order_label(order, "order_number", "name", "id"), "order number")
    returns = []
    seen: set[str] = set()
    for refund in refunds:
        if not isinstance(refund, dict):
            raise StageRejection("each refund must be an object")
        lines = refund.get("refund_line_items") or []
        if not isinstance(lines, list):
            raise StageRejection("refund_line_items must be a list")
        for refund_line in lines:
            if not isinstance(refund_line, dict):
                raise StageRejection("each refund line must be an object")
            line = refund_line.get("line_item")
            line_id = refund_line.get("line_item_id")
            if not isinstance(line, dict):
                line = next(
                    (item for item in items if isinstance(item, dict) and item.get("id") == line_id),
                    None,
                )
            if not isinstance(line, dict):
                continue
            index = indexes.get(line.get("id", line_id))
            if index is None:
                continue
            refunded = refund_line.get("quantity")
            sold = line.get("quantity") or 1
            try:
                refunded_qty = _quantity(refunded)
                sold_qty = _quantity(sold)
            except StageRejection:
                continue
            if refunded_qty != sold_qty:
                continue
            sku = _named_sku(line)
            if not sku:
                continue
            location, milligrams, _kind, _practitioner = _shopify_line(line, _order_line_defaults(order))
            if location is None and milligrams is None:
                continue
            if not isinstance(location, str) or not location.strip() or milligrams is None:
                raise StageRejection(f"sku {sku} requires location and milligrams")
            fulfillment_id = f"{order_id}:{index}:{sku}"
            if fulfillment_id in seen:
                continue
            seen.add(fulfillment_id)
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


def shopify_order_update_commands(order: dict) -> list[dict]:
    """An order update records a sale only once Shopify says it shipped, paid, or came back.

    An open update and a partial fulfillment stay off the ledger.
    A refund quantity below the line quantity stays off the return.
    A paid order that is not fulfilled does not settle, because the sale is not on the ledger yet.
    """
    if not isinstance(order, dict):
        raise StageRejection("order is required")
    fulfillment_status = str(order.get("fulfillment_status") or "").strip().lower()
    if _shopify_returned(order) or fulfillment_status == "restocked":
        return shopify_return_commands(order)
    if fulfillment_status != "fulfilled":
        return []
    commands = shopify_fulfillment_commands(order)
    financial = str(order.get("financial_status") or "").strip().lower()
    if financial == "paid":
        commands.extend(shopify_settlement_commands(order))
    elif financial == "partially_refunded":
        commands.extend(shopify_refunded_line_commands(order))
    return commands


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
    currency = _currency_text(order.get("currency")) or "USD"
    explicit = _named(order, "fulfillment_id", "fulfillmentId")
    if explicit:
        order_number = _order_label(order, "order_number", "id") or explicit
        return [
            {
                "command": "settle",
                "args": {
                    "settlement_id": _text(
                        _named(order, "settlement_id", "settlementId") or f"pay-{order_number}",
                        "settlement_id",
                    ),
                    "fulfillment_id": explicit,
                    "amount_cents": _price_cents(_first_amount(order.get("total_price"), order.get("amount"))),
                    "currency": currency,
                },
            }
        ]
    commands = []
    order_id = _order_label(order, "order_number", "name", "id")
    defaults = _order_line_defaults(order)
    for index, item in enumerate(order.get("line_items") or []):
        if not isinstance(item, dict):
            continue
        sku = _named_sku(item)
        if not sku:
            continue
        location, milligrams, _kind, _practitioner = _shopify_line(item, defaults)
        if location is None and milligrams is None:
            continue
        quantity = _quantity_or_one(item.get("quantity"))
        commands.append(
            {
                "command": "settle",
                "args": {
                    "settlement_id": f"pay-{order_id}:{index}:{sku}",
                    "fulfillment_id": f"{order_id}:{index}:{sku}",
                    "amount_cents": _price_cents(item.get("price")) * quantity,
                    "currency": currency,
                },
            }
        )
    return commands


def opencart_catalog_commands(product: dict) -> list[dict]:
    if not isinstance(product, dict):
        return []
    mapped = {
        "title": _named(product, "name", "title"),
        "sku": _named_sku(product) or _named(product, "model"),
        "tags": product.get("tags") if product.get("tags") is not None else product.get("tag"),
        "formula_id": _named(product, "formula_id", "formulaId"),
        "variants": product.get("variants"),
    }
    if "metafields" in product:
        mapped["metafields"] = product.get("metafields")
    return shopify_catalog_commands(mapped)


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
        items.append(_opencart_identity(item))
    return shopify_fulfillment_commands(
        {
            "order_number": _order_label(order, "order_id", "order_number", "id"),
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
        quantity = item.get("quantity")
        if _missing_amount(price) and not _missing_amount(item.get("total")):
            price = item.get("total")
            quantity = 1
        if _missing_amount(price):
            continue
        line = _opencart_identity(item)
        line["price"] = price
        line["quantity"] = _quantity_or_one(quantity)
        items.append(line)
    return shopify_settlement_commands(
        {
            "order_number": _order_label(order, "order_id", "order_number", "id"),
            "currency": (
                _currency_text(order.get("currency_code"))
                or _currency_text(order.get("currency"))
                or "USD"
            ),
            "total_price": order.get("total"),
            "fulfillment_id": _named(order, "fulfillment_id", "fulfillmentId"),
            "settlement_id": _named(order, "settlement_id", "settlementId"),
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


# OpenCart connector payment map, labeled with the status names that map already uses.
_OPENCART_STATUS_IDS = {
    1: "pending",
    2: "pending",
    3: "shipped",
    5: "complete",
    7: "canceled",
    11: "refunded",
}


def _opencart_status(order: dict) -> str:
    named = str(order.get("status") or order.get("new_status") or order.get("order_status") or "").strip().lower()
    if named:
        return named
    for key in ("new_status_id", "order_status_id"):
        if order.get(key) is None:
            continue
        label = _OPENCART_STATUS_IDS.get(_opencart_status_code(order.get(key)))
        if label:
            return label
    return ""


def _opencart_status_code(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _opencart_returned(order: dict) -> bool:
    return order.get("returned") is True or _opencart_status(order) in _OPENCART_RETURNED


def _opencart_identity(item: dict) -> dict:
    """A line field names the sale. Product options do when the line does not."""
    properties = item.get("properties")
    if properties is None:
        options = item.get("option")
        if not isinstance(options, list):
            options = item.get("options")
        properties = options if isinstance(options, list) else None
    return {
        "sku": _named_sku(item) or _named(item, "model"),
        "location": item.get("location"),
        "milligrams": item.get("milligrams"),
        "properties": properties,
        "kind": item.get("kind"),
        "practitioner_id": _named(item, "practitionerId", "practitioner_id") or None,
    }


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
                    "sku_id": _text(_named(delivery, "sku_id", "skuId", "sku"), "sku_id"),
                    "batch_id": _text(_named(delivery, "batch_id", "batchId"), "batch_id"),
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
    return _commit_idempotent(commands)


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
    return _commit_idempotent(commands)


def record_shopify_catalog(product: dict) -> dict | None:
    try:
        commands = shopify_catalog_commands(product)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_idempotent(commands)


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


def record_shopify_order_update(order: dict) -> dict | None:
    try:
        commands = shopify_order_update_commands(order)
    except StageRejection as exc:
        return {"ok": False, "error": str(exc)}
    return _commit_idempotent(commands)


def record_synced_sale(platform: str, payload: dict) -> dict | None:
    """A platform sync records the same sale the webhook would record.

    An order that does not name a shipped sale, delivery, or return stays off the ledger.
    """
    if not isinstance(payload, dict):
        return None
    name = str(platform or "").strip().lower()
    if name == "shopify":
        return record_shopify_order_update(payload)
    if name == "opencart":
        return record_opencart_fulfillments(payload)
    if name == "wix":
        return record_wix_deliveries(payload)
    return None


def record_synced_catalog(platform: str, payload: dict) -> dict | None:
    """A platform product sync records the same catalog the webhook would record.

    A product that does not name a formula stays off the ledger.
    """
    if not isinstance(payload, dict):
        return None
    name = str(platform or "").strip().lower()
    if name == "shopify":
        return record_shopify_catalog(payload)
    if name == "opencart":
        return record_opencart_catalog(payload)
    return None


_LINE_ATTRIBUTES = {
    "location": "location",
    "milligrams": "milligrams",
    "kind": "kind",
    "practitioner_id": "practitioner_id",
    "practitionerid": "practitioner_id",
}


def _attribute_values(entries: object) -> dict:
    """Line properties and note attributes name a sale.

    REST payloads use name. GraphQL custom attributes use key.
    A present name wins, so a gift name does not fall through to a location key.
    practitionerId is the same practitioner as practitioner_id.
    """
    found: dict[str, object] = {}
    if not isinstance(entries, list):
        return found
    for prop in entries:
        if not isinstance(prop, dict):
            continue
        name = str(prop.get("name") or prop.get("key") or "").strip().lower()
        canonical = _LINE_ATTRIBUTES.get(name)
        if canonical is None or canonical in found:
            continue
        found[canonical] = prop.get("value")
    return found


def _order_line_defaults(order: dict) -> dict:
    """Order note attributes name the same line fields a property can name."""
    return _attribute_values(order.get("note_attributes"))


def _text_or_same(value: object) -> object:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return value


def _missing_amount(value: object) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _shopify_line(item: dict, defaults: dict | None = None) -> tuple[object, object, str | None, str | None]:
    defaults = defaults or {}
    location = _text_or_same(item.get("location"))
    milligrams = None if _missing_amount(item.get("milligrams")) else item.get("milligrams")
    kind = item.get("kind")
    kind = kind.strip() if isinstance(kind, str) else None
    if not kind:
        kind = None
    practitioner = _named(item, "practitionerId", "practitioner_id")
    for name, value in _attribute_values(item.get("properties")).items():
        if name == "location" and location is None:
            location = _text_or_same(value)
        elif name == "milligrams" and milligrams is None and not _missing_amount(value):
            milligrams = value
        elif name == "kind" and kind is None and isinstance(value, str):
            kind = value.strip() or None
        elif name == "practitioner_id" and not practitioner:
            practitioner = value.strip() if isinstance(value, str) else value
    if location is None:
        location = _text_or_same(defaults.get("location"))
    if milligrams is None and not _missing_amount(defaults.get("milligrams")):
        milligrams = defaults.get("milligrams")
    if kind is None and isinstance(defaults.get("kind"), str):
        kind = defaults["kind"].strip()
    if not practitioner and defaults.get("practitioner_id"):
        practitioner = defaults["practitioner_id"]
    if not isinstance(practitioner, str):
        return location, milligrams, kind, None
    return location, milligrams, kind, practitioner.strip() or None


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
    if name == "catalog_sku":
        return ("catalog_sku", str(args.get("sku_id")))
    if name == "transfer":
        return ("transfer", str(args.get("transfer_id")))
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


def _first_amount(*values: object) -> object:
    """A present amount wins. A blank one falls through to the next amount."""
    for value in values:
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
            continue
        if value:
            return value
    return None


def _quantity_or_one(value: object) -> int:
    """A missing or blank quantity is one. A present count is kept."""
    if isinstance(value, str):
        if not value.strip():
            value = 1
    elif not value:
        value = 1
    return _quantity(value)


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
