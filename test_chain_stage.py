import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from chain_stage import (
    _locate_script,
    draft_order_commands,
    opencart_catalog_commands,
    opencart_fulfillment_commands,
    record_draft_order,
    record_shopify_fulfillments,
    record_shopify_settlement,
    record_wix_deliveries,
    respond,
    settlement_for_payment,
    shopify_catalog_commands,
    shopify_fulfillment_commands,
    shopify_settlement_commands,
    wix_delivery_commands,
)


class SettlementRouteTests(unittest.TestCase):
    def test_accepts_a_zar_settlement(self) -> None:
        body, status = respond(
            {
                "command": "settle",
                "args": {
                    "settlement_id": "pay-1",
                    "fulfillment_id": "order-retail",
                    "amount_cents": 18500,
                    "currency": "zar",
                },
            }
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["artifact"]["currency"], "ZAR")

    def test_payment_without_a_fulfillment_is_not_a_settlement(self) -> None:
        self.assertIsNone(settlement_for_payment({"amount": 10, "currency": "USD"}))

    def test_confirmed_payment_names_the_fulfillment_it_closes(self) -> None:
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            body, status = settlement_for_payment(
                {
                    "settlement_id": "pay-confirm",
                    "fulfillment_id": "order-retail",
                    "amount": 45.5,
                    "currency": "ZAR",
                }
            )
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertEqual(status, 200)
        self.assertEqual(body["artifact"]["settlement_id"], "pay-confirm")
        self.assertEqual(body["artifact"]["amount_cents"], 4550)

    def test_payment_amount_is_recorded_in_cents(self) -> None:
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            body, status = settlement_for_payment(
                {
                    "settlement_id": "pay-1",
                    "fulfillment_id": "order-retail",
                    "amount": 185.0,
                    "currency": "zar",
                }
            )
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertEqual(status, 200)
        self.assertEqual(body["artifact"]["amount_cents"], 18500)
        self.assertEqual(body["artifact"]["currency"], "ZAR")

    def test_payment_against_an_empty_ledger_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            try:
                body, status = settlement_for_payment(
                    {
                        "settlement_id": "pay-1",
                        "fulfillment_id": "missing-order",
                        "amount_cents": 100,
                        "currency": "ZAR",
                    }
                )
            finally:
                if previous is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])
        self.assertFalse(ledger.exists())
        self.assertIn("fulfillment", json.dumps(body))

    def test_shopify_formula_tag_is_a_catalog_sku(self) -> None:
        commands = shopify_catalog_commands(
            {
                "title": "Vitamin C serum",
                "tags": "retail, Formula:serum-c",
                "variants": [{"sku": "sku-serum-c"}],
            }
        )
        self.assertEqual(commands[0]["args"]["formula_id"], "serum-c")
        self.assertEqual(commands[0]["args"]["sku_id"], "sku-serum-c")
        self.assertEqual(shopify_catalog_commands({"title": "Cleanser", "tags": "retail"}), [])

    def test_shopify_fulfillment_uses_line_properties(self) -> None:
        commands = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {"sku": "sku-ignore", "quantity": 1},
                    {
                        "sku": "sku-serum-c",
                        "properties": [
                            {"name": "location", "value": "cape-town"},
                            {"name": "milligrams", "value": "5000"},
                        ],
                    },
                ],
            }
        )
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["args"]["fulfillment_id"], "9:1:sku-serum-c")
        self.assertEqual(commands[0]["args"]["milligrams"], 5000)
        self.assertEqual(commands[0]["args"]["kind"], "retail")

    def test_incomplete_shopify_line_does_not_fulfill_the_earlier_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            try:
                result = record_shopify_fulfillments(
                    {
                        "order_number": 9,
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "properties": [
                                    {"name": "location", "value": "cape-town"},
                                    {"name": "milligrams", "value": "5000"},
                                ],
                            },
                            {
                                "sku": "sku-cleanser",
                                "properties": [{"name": "location", "value": "cape-town"}],
                            },
                        ],
                    }
                )
            finally:
                if previous is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertFalse(result["ok"])
        self.assertFalse(ledger.exists())

    def test_completed_b2b_draft_is_one_outlet_sale(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        self.assertEqual(draft_order_commands({"status": "open", "id": 3, "line_items": [line]}), [])
        self.assertEqual(
            draft_order_commands({"status": "invoice_sent", "id": 3, "line_items": [line]}),
            [],
        )
        commands = draft_order_commands(
            {"status": "Completed", "id": 3, "order_id": 9, "name": "#D3", "line_items": [line]}
        )
        self.assertEqual(commands[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        self.assertEqual(commands[0]["args"]["milligrams"], 2000)
        self.assertEqual(commands[0]["args"]["location"], "cape-town")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            draft = {"status": "completed", "id": 3, "order_id": 9, "line_items": [line]}
            try:
                missing = record_draft_order(draft)
                self.assertFalse(missing["ok"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {"ingredient_id": "glycerin", "inci": "Glycerin", "cas": "56-81-5"},
                                },
                                {
                                    "command": "qualify_supplier",
                                    "args": {
                                        "qualification_id": "qual-glycerin",
                                        "supplier_name": "Inland Humectants",
                                        "ingredient_id": "glycerin",
                                    },
                                },
                                {
                                    "command": "receive_lot",
                                    "args": {
                                        "lot_id": "lot-glycerin",
                                        "ingredient_id": "glycerin",
                                        "qualification_id": "qual-glycerin",
                                        "milligrams": 5000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "cleanser",
                                        "name": "Gentle cleanser",
                                        "lines": [["glycerin", 5000]],
                                    },
                                },
                                {
                                    "command": "catalog_sku",
                                    "args": {
                                        "sku_id": "sku-serum-c",
                                        "formula_id": "cleanser",
                                        "name": "Vitamin C serum",
                                    },
                                },
                                {
                                    "command": "manufacture",
                                    "args": {
                                        "batch_id": "batch-1",
                                        "sku_id": "sku-serum-c",
                                        "units": 1,
                                        "allocations": [["glycerin", "lot-glycerin", 5000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "to-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 5000,
                                    },
                                },
                            ]
                        }
                    ),
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                recorded = record_draft_order(draft)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("9:0:sku-serum-c", text)
                again = record_shopify_fulfillments(
                    {"order_number": 9, "line_items": [line]}
                )
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                changed = record_draft_order(
                    {
                        "status": "completed",
                        "id": 3,
                        "order_id": 9,
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "properties": [
                                    {"name": "location", "value": "cape-town"},
                                    {"name": "milligrams", "value": "4000"},
                                ],
                            }
                        ],
                    }
                )
                self.assertFalse(changed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_paid_shopify_order_settles_the_named_fulfillment(self) -> None:
        commands = shopify_settlement_commands(
            {
                "order_number": 9,
                "currency": "ZAR",
                "total_price": "185.00",
                "fulfillment_id": "9:0:sku-serum-c",
            }
        )
        self.assertEqual(commands[0]["args"]["amount_cents"], 18500)
        self.assertEqual(commands[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        self.assertIsNone(record_shopify_settlement({"order_number": 9, "line_items": []}))

    def test_opencart_and_wix_events_use_the_same_ledger_commands(self) -> None:
        catalog = opencart_catalog_commands(
            {"name": "Vitamin C serum", "model": "sku-serum-c", "tag": "formula:serum-c"}
        )
        self.assertEqual(catalog[0]["args"]["formula_id"], "serum-c")
        self.assertEqual(catalog[0]["args"]["sku_id"], "sku-serum-c")
        self.assertEqual(
            opencart_fulfillment_commands(
                {
                    "order_id": 4,
                    "status": "pending",
                    "products": [{"model": "sku-serum-c", "location": "cape-town", "milligrams": 5000}],
                }
            ),
            [],
        )
        fulfilled = opencart_fulfillment_commands(
            {
                "order_id": 4,
                "status": "Shipped",
                "products": [{"model": "sku-serum-c", "location": "cape-town", "milligrams": 5000}],
            }
        )
        self.assertEqual(fulfilled[0]["command"], "fulfill")
        self.assertEqual(fulfilled[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
        deliveries = wix_delivery_commands(
            {
                "id": "book-1",
                "services": [
                    {"name": "Facial"},
                    {
                        "delivery": {
                            "sku_id": "sku-serum-c",
                            "batch_id": "batch-1",
                            "source": "plant",
                            "destination": "cape-town",
                            "milligrams": 2000,
                        }
                    },
                ],
            }
        )
        self.assertEqual(len(deliveries), 1)
        self.assertEqual(deliveries[0]["args"]["transfer_id"], "book-1:1")
        self.assertIsNone(record_wix_deliveries({"id": "book-1", "services": [{"name": "Facial"}]}))

    def test_wix_delivery_against_an_empty_ledger_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            try:
                result = record_wix_deliveries(
                    {
                        "id": "book-1",
                        "services": [
                            {
                                "delivery": {
                                    "sku_id": "sku-serum-c",
                                    "batch_id": "batch-1",
                                    "source": "plant",
                                    "destination": "cape-town",
                                    "milligrams": 2000,
                                }
                            }
                        ],
                    }
                )
            finally:
                if previous is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertFalse(result["ok"])
        self.assertFalse(ledger.exists())

    def test_rejects_a_bad_currency(self) -> None:
        body, status = respond(
            {
                "command": "settle",
                "args": {
                    "settlement_id": "pay-1",
                    "fulfillment_id": "order-retail",
                    "amount_cents": 100,
                    "currency": "US",
                },
            }
        )
        self.assertEqual(status, 400)
        self.assertFalse(body["ok"])


if __name__ == "__main__":
    unittest.main()
