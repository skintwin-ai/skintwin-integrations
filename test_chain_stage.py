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
    opencart_return_commands,
    opencart_settlement_commands,
    paystack_settlement,
    record_opencart_catalog,
    record_opencart_fulfillments,
    record_draft_order,
    record_paystack_settlement,
    record_shopify_catalog,
    record_shopify_fulfillments,
    record_shopify_returns,
    record_shopify_settlement,
    return_for_refund,
    record_wix_deliveries,
    respond,
    settlement_for_payment,
    shopify_catalog_commands,
    shopify_fulfillment_commands,
    record_shopify_order_update,
    shopify_order_update_commands,
    shopify_return_commands,
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
        sized = shopify_catalog_commands(
            {
                "title": "Gentle cleanser",
                "tags": "formula:cleanser",
                "variants": [
                    {"sku": "sku-cleanser-30"},
                    {"sku": " "},
                    {"sku": "sku-cleanser-30"},
                    {"sku": "sku-cleanser-50"},
                ],
            }
        )
        self.assertEqual([command["args"]["sku_id"] for command in sized], ["sku-cleanser-30", "sku-cleanser-50"])
        self.assertEqual(
            shopify_catalog_commands(
                {"title": "Gentle cleanser", "tags": "formula:cleanser", "variants": [{"sku": " "}]}
            )[0]["args"]["sku_id"],
            "Gentle cleanser",
        )
        self.assertEqual(
            shopify_catalog_commands(
                {"title": "Cleanser", "tags": "retail", "variants": [{"sku": "sku-a"}, {"sku": "sku-b"}]}
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                unnamed = record_shopify_catalog(
                    {"title": "Cleanser", "tags": "retail", "variants": [{"sku": "sku-a"}, {"sku": "sku-b"}]}
                )
                self.assertIsNone(unnamed)
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
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "cleanser",
                                        "name": "Gentle cleanser",
                                        "lines": [["glycerin", 8000]],
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
                recorded = record_shopify_catalog(
                    {
                        "title": "Gentle cleanser",
                        "tags": "formula:cleanser",
                        "variants": [{"sku": "sku-cleanser-30"}, {"sku": "sku-cleanser-50"}],
                    }
                )
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertEqual(text.count("sku-cleanser-30"), 1)
                self.assertEqual(text.count("sku-cleanser-50"), 1)
                again = record_shopify_catalog(
                    {
                        "title": "Gentle cleanser",
                        "tags": "formula:cleanser",
                        "variants": [{"sku": "sku-cleanser-30"}, {"sku": "sku-cleanser-50"}],
                    }
                )
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
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

    def test_a_repeated_formula_tag_catalogs_the_sku_once(self) -> None:
        plain = {"title": "Cleanser", "tags": "retail", "variants": [{"sku": "sku-cleanser"}]}
        self.assertIsNone(record_shopify_catalog(plain))
        self.assertIsNone(record_opencart_catalog({"name": "Cleanser", "sku": "sku-cleanser"}))
        product = {
            "title": "Gentle cleanser",
            "tags": "formula:cleanser",
            "variants": [{"sku": "sku-cleanser"}],
        }
        opencart = {"name": "Gentle cleanser", "sku": "sku-cleanser", "tag": "formula:cleanser"}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing = record_shopify_catalog(product)
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
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "cleanser",
                                        "name": "Gentle cleanser",
                                        "lines": [["glycerin", 8000]],
                                    },
                                },
                            ]
                        }
                    ),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                first = record_shopify_catalog(product)
                self.assertTrue(first["ok"])
                self.assertEqual(first["count"], 1)
                recorded = ledger.read_text(encoding="utf-8")
                self.assertEqual(recorded.count("sku-cleanser"), 1)
                again = record_shopify_catalog(product)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
                shopify = self._webhook_module("shopify")
                updated = shopify.ShopifyWebhookHandler("secret").on_product_updated(product)
                self.assertEqual(updated["recorded"]["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
                renamed = record_shopify_catalog({**product, "title": "Renamed cleanser"})
                self.assertFalse(renamed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
                repeated = record_opencart_catalog(opencart)
                self.assertTrue(repeated["ok"])
                self.assertEqual(repeated["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

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

    def test_order_note_attributes_name_the_sale_when_the_line_does_not(self) -> None:
        line = {"sku": "sku-serum-c", "price": "185.00", "quantity": 1}
        notes = [
            {"name": "location", "value": "cape-town"},
            {"name": "milligrams", "value": "2000"},
            {"name": "gift", "value": "thanks"},
        ]
        open_order = {"order_number": 9, "currency": "ZAR", "line_items": [line], "note_attributes": notes}
        self.assertEqual(shopify_order_update_commands(open_order), [])
        fulfilled = {**open_order, "fulfillment_status": "fulfilled"}
        drawn = shopify_order_update_commands(fulfilled)
        self.assertEqual(drawn[0]["args"]["location"], "cape-town")
        self.assertEqual(drawn[0]["args"]["milligrams"], 2000)
        paid = shopify_order_update_commands({**fulfilled, "financial_status": "paid"})
        self.assertEqual([command["command"] for command in paid], ["fulfill", "settle"])
        owned = {
            **fulfilled,
            "line_items": [
                {
                    **line,
                    "properties": [
                        {"name": "location", "value": "johannesburg"},
                        {"name": "milligrams", "value": "1500"},
                    ],
                }
            ],
        }
        self.assertEqual(shopify_order_update_commands(owned)[0]["args"]["location"], "johannesburg")
        self.assertEqual(shopify_order_update_commands(owned)[0]["args"]["milligrams"], 1500)
        self.assertEqual(
            shopify_order_update_commands(
                {**fulfilled, "note_attributes": [{"name": "gift", "value": "thanks"}]}
            ),
            [],
        )
        self.assertEqual(
            draft_order_commands(
                {"id": 3, "status": "open", "line_items": [line], "note_attributes": notes}
            ),
            [],
        )
        completed = draft_order_commands(
            {"id": 3, "status": "completed", "line_items": [line], "note_attributes": notes}
        )
        self.assertEqual(completed[0]["args"]["location"], "cape-town")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                pending = record_shopify_order_update(open_order)
                self.assertIsNone(pending)
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
                recorded = record_shopify_order_update({**fulfilled, "financial_status": "paid"})
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("9:0:sku-serum-c", text)
                again = record_shopify_order_update({**fulfilled, "financial_status": "paid"})
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
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

    def test_shopify_order_update_records_a_fulfilled_paid_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "price": "185.00",
            "quantity": 1,
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        open_order = {"order_number": 9, "currency": "ZAR", "line_items": [line]}
        self.assertEqual(shopify_order_update_commands(open_order), [])
        self.assertEqual(
            shopify_order_update_commands({**open_order, "financial_status": "paid"}),
            [],
        )
        self.assertEqual(
            shopify_order_update_commands({**open_order, "fulfillment_status": "partial"}),
            [],
        )
        fulfilled = {**open_order, "fulfillment_status": "fulfilled"}
        drawn = shopify_order_update_commands(fulfilled)
        self.assertEqual([command["command"] for command in drawn], ["fulfill"])
        paid = {**fulfilled, "financial_status": "paid"}
        both = shopify_order_update_commands(paid)
        self.assertEqual([command["command"] for command in both], ["fulfill", "settle"])
        self.assertEqual(both[1]["args"]["settlement_id"], "pay-9:0:sku-serum-c")
        self.assertEqual(both[1]["args"]["amount_cents"], 18500)
        self.assertEqual(both[1]["args"]["currency"], "ZAR")
        partial = {**paid, "financial_status": "partially_refunded"}
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(partial)],
            ["fulfill"],
        )
        named_line = {**line, "id": 100}
        named_partial = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [named_line],
            "refunds": [
                {
                    "refund_line_items": [
                        {"line_item_id": 100, "quantity": 1, "line_item": named_line},
                    ]
                }
            ],
        }
        named_commands = shopify_order_update_commands(named_partial)
        self.assertEqual([command["command"] for command in named_commands], ["fulfill", "return_sale"])
        self.assertEqual(named_commands[1]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        self.assertEqual(
            shopify_order_update_commands(
                {
                    **open_order,
                    "financial_status": "partially_refunded",
                    "line_items": [named_line],
                    "refunds": named_partial["refunds"],
                }
            ),
            [],
        )
        short = {
            **named_partial,
            "refunds": [
                {"refund_line_items": [{"line_item_id": 100, "quantity": 1, "line_item": {**named_line, "quantity": 2}}]}
            ],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(short)],
            ["fulfill"],
        )
        refunded = shopify_order_update_commands({**paid, "financial_status": "refunded"})
        self.assertEqual([command["command"] for command in refunded], ["return_sale"])
        self.assertEqual(refunded[0]["args"]["return_id"], "return:9:0:sku-serum-c")
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands({**paid, "cancelled_at": "2026-10-02T00:00:00Z"})],
            ["return_sale"],
        )
        self.assertIsNone(record_shopify_order_update(open_order))
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing = record_shopify_order_update(paid)
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 5000]],
                                    },
                                },
                                {
                                    "command": "catalog_sku",
                                    "args": {
                                        "sku_id": "sku-serum-c",
                                        "formula_id": "serum-c",
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
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                recorded = record_shopify_order_update(paid)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-9:0:sku-serum-c", text)
                again = record_shopify_order_update(paid)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                changed_line = {
                    **line,
                    "properties": [
                        {"name": "location", "value": "cape-town"},
                        {"name": "milligrams", "value": "4000"},
                    ],
                }
                changed = record_shopify_order_update({**paid, "line_items": [changed_line]})
                self.assertFalse(changed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                returned = record_shopify_order_update({**paid, "financial_status": "refunded"})
                self.assertTrue(returned["ok"])
                self.assertEqual(returned["count"], 1)
                self.assertIn("return:9:0:sku-serum-c", ledger.read_text(encoding="utf-8"))
                repeat = record_shopify_order_update({**paid, "financial_status": "refunded"})
                self.assertTrue(repeat["ok"])
                self.assertEqual(repeat["count"], 0)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

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
        self.assertEqual(
            opencart_settlement_commands(
                {
                    "order_id": 4,
                    "status": "shipped",
                    "currency_code": "ZAR",
                    "products": [
                        {"model": "sku-serum-c", "location": "cape-town", "milligrams": 2000, "price": "185.00"}
                    ],
                }
            ),
            [],
        )
        paid = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "ZAR",
                "products": [
                    {
                        "model": "sku-serum-c",
                        "location": "cape-town",
                        "milligrams": 2000,
                        "price": "185.00",
                        "quantity": "1",
                    }
                ],
            }
        )
        self.assertEqual(paid[0]["command"], "settle")
        self.assertEqual(paid[0]["args"]["settlement_id"], "pay-4:0:sku-serum-c")
        self.assertEqual(paid[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
        self.assertEqual(paid[0]["args"]["amount_cents"], 18500)
        self.assertEqual(paid[0]["args"]["currency"], "ZAR")
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

    def test_a_wix_booking_records_a_named_delivery_once(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        booking = {"id": "book-1", "services": [{"name": "Facial"}, {"delivery": delivery}]}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                wix = self._webhook_module("wix")
                plain = wix.WixWebhookHandler("secret").on_booking_created(
                    {"id": "book-plain", "services": [{"name": "Facial"}]}
                )
                self.assertIsNone(plain["recorded"])
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
                            ]
                        }
                    ),
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = wix.WixWebhookHandler("secret").on_booking_created(booking)
                self.assertTrue(created["recorded"]["ok"])
                self.assertEqual(created["recorded"]["count"], 1)
                recorded = ledger.read_text(encoding="utf-8")
                self.assertEqual(recorded.count("book-1:1"), 1)
                updated = wix.WixWebhookHandler("secret").on_booking_updated(booking)
                self.assertEqual(updated["recorded"]["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
                changed = {
                    **booking,
                    "services": [{"name": "Facial"}, {"delivery": {**delivery, "milligrams": 1000}}],
                }
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").on_booking_updated(changed)
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_paid_opencart_order_settles_a_shipped_sale_once(self) -> None:
        product = {
            "model": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "price": "185.00",
            "quantity": "1",
        }
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing = record_opencart_fulfillments(
                    {"order_id": 4, "status": "complete", "currency_code": "ZAR", "products": [product]}
                )
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
                shipped = record_opencart_fulfillments(
                    {"order_id": 4, "status": "shipped", "currency_code": "ZAR", "products": [product]}
                )
                self.assertTrue(shipped["ok"])
                self.assertEqual(shipped["count"], 1)
                shipped_text = ledger.read_text(encoding="utf-8")
                self.assertIn("4:0:sku-serum-c", shipped_text)
                self.assertNotIn("pay-4:0:sku-serum-c", shipped_text)
                paid = record_opencart_fulfillments(
                    {"order_id": 4, "status": "paid", "currency_code": "ZAR", "products": [product]}
                )
                self.assertTrue(paid["ok"])
                self.assertEqual(paid["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-4:0:sku-serum-c", text)
                again = record_opencart_fulfillments(
                    {"order_id": 4, "status": "completed", "currency_code": "ZAR", "products": [product]}
                )
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                changed = record_opencart_fulfillments(
                    {
                        "order_id": 4,
                        "status": "paid",
                        "currency_code": "ZAR",
                        "products": [{**product, "price": "90.00"}],
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

    def test_an_opencart_status_id_records_the_named_sale(self) -> None:
        product = {
            "model": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "price": "185.00",
            "quantity": "1",
        }
        named = {"order_id": 4, "status": "complete", "currency_code": "ZAR", "products": [product]}
        by_id = {"order_id": 4, "order_status_id": 5, "currency_code": "ZAR", "products": [product]}
        self.assertEqual(opencart_fulfillment_commands(by_id), opencart_fulfillment_commands(named))
        self.assertEqual(opencart_settlement_commands(by_id), opencart_settlement_commands(named))
        shipped = {"order_id": 4, "new_status_id": "3", "currency_code": "ZAR", "products": [product]}
        self.assertEqual(
            opencart_fulfillment_commands(shipped),
            opencart_fulfillment_commands({**named, "status": "shipped"}),
        )
        self.assertEqual(opencart_settlement_commands(shipped), [])
        self.assertEqual(opencart_return_commands(shipped), [])
        returned = {"order_id": 4, "new_status_id": 11, "products": [product]}
        self.assertEqual(
            opencart_return_commands(returned),
            opencart_return_commands({**named, "status": "refunded"}),
        )
        self.assertEqual(
            opencart_fulfillment_commands({"order_id": 4, "new_status_id": 1, "products": [product]}),
            [],
        )
        self.assertEqual(
            opencart_fulfillment_commands(
                {"order_id": 4, "status": "pending", "order_status_id": 5, "products": [product]}
            ),
            [],
        )
        self.assertEqual(
            opencart_fulfillment_commands({"order_id": 4, "order_status_id": 15, "products": [product]}),
            [],
        )
        self.assertEqual(
            opencart_fulfillment_commands(
                {"order_id": 4, "order_status_id": 5, "products": [{"model": "sku-serum-c", "price": "185.00"}]}
            ),
            [],
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                pending = record_opencart_fulfillments(
                    {"order_id": 4, "new_status_id": 2, "products": [product]}
                )
                self.assertIsNone(pending)
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
                recorded = record_opencart_fulfillments(by_id)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("4:0:sku-serum-c", text)
                self.assertIn("pay-4:0:sku-serum-c", text)
                again = record_opencart_fulfillments(
                    {"order_id": 4, "new_status_id": 5, "currency_code": "ZAR", "products": [product]}
                )
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
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

    def test_a_cancelled_storefront_sale_returns_stock_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        product = {
            "model": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "price": "185.00",
            "quantity": "1",
        }
        shopify_order = {"order_number": 9, "line_items": [line]}
        commands = shopify_return_commands(shopify_order)
        self.assertEqual(
            commands,
            [
                {
                    "command": "return_sale",
                    "args": {
                        "return_id": "return:9:0:sku-serum-c",
                        "fulfillment_id": "9:0:sku-serum-c",
                    },
                }
            ],
        )
        self.assertEqual(
            opencart_return_commands({"order_id": 4, "status": "pending", "products": [product]}),
            [],
        )
        self.assertEqual(
            opencart_return_commands({"order_id": 4, "status": "shipped", "products": [product]}),
            [],
        )
        refunded_order = {
            "order_id": 4,
            "status": "refunded",
            "currency_code": "ZAR",
            "products": [product],
        }
        self.assertEqual(opencart_fulfillment_commands(refunded_order), [])
        self.assertEqual(opencart_settlement_commands(refunded_order), [])
        self.assertEqual(
            opencart_return_commands(refunded_order)[0]["args"]["fulfillment_id"],
            "4:0:sku-serum-c",
        )
        self.assertEqual(
            len(opencart_return_commands({"order_id": 4, "status": "canceled", "products": [product]})),
            1,
        )
        self.assertEqual(
            len(
                opencart_return_commands(
                    {"order_id": 4, "returned": True, "status": "pending", "products": [product]}
                )
            ),
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing = record_shopify_returns(shopify_order)
                self.assertFalse(missing["ok"])
                self.assertFalse(ledger.exists())
                refund_missing = record_opencart_fulfillments(refunded_order)
                self.assertFalse(refund_missing["ok"])
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
                                        "milligrams": 8000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "cleanser",
                                        "name": "Gentle cleanser",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
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
                                        "milligrams": 8000,
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
                fulfilled = record_shopify_fulfillments(shopify_order)
                self.assertTrue(fulfilled["ok"])
                self.assertEqual(fulfilled["count"], 1)
                returned = record_shopify_returns(shopify_order)
                self.assertTrue(returned["ok"])
                self.assertEqual(returned["count"], 1)
                self.assertIn("return:9:0:sku-serum-c", ledger.read_text(encoding="utf-8"))
                again = record_shopify_returns(shopify_order)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                shipped = record_opencart_fulfillments(
                    {"order_id": 4, "status": "shipped", "currency_code": "ZAR", "products": [product]}
                )
                self.assertTrue(shipped["ok"])
                self.assertEqual(shipped["count"], 1)
                self.assertNotIn("return:4:", ledger.read_text(encoding="utf-8"))
                refunded = record_opencart_fulfillments(refunded_order)
                self.assertTrue(refunded["ok"])
                self.assertEqual(refunded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("return:4:0:sku-serum-c", text)
                self.assertNotIn("pay-4:", text)
                cancelled = record_opencart_fulfillments(
                    {"order_id": 4, "status": "cancelled", "products": [product]}
                )
                self.assertTrue(cancelled["ok"])
                self.assertEqual(cancelled["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                pending = record_opencart_fulfillments(
                    {"order_id": 8, "status": "pending", "products": [product]}
                )
                self.assertIsNone(pending)
                lines = [json.loads(row) for row in text.splitlines() if row.strip()]
                for record in lines:
                    if record["command"] == "return_sale" and record["args"]["return_id"] == "return:9:0:sku-serum-c":
                        record["args"]["fulfillment_id"] = "9:0:other"
                mutated = "".join(json.dumps(record) + "\n" for record in lines)
                ledger.write_text(mutated, encoding="utf-8")
                changed = record_shopify_returns(shopify_order)
                self.assertFalse(changed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), mutated)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_pos_refund_returns_the_named_sale_once(self) -> None:
        self.assertIsNone(return_for_refund({"amount": 10}))
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            body, status = return_for_refund(
                {"fulfillment_id": "order-retail", "return_id": "return:tx-1:order-retail"}
            )
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
        self.assertEqual(status, 200)
        self.assertEqual(body["artifact"]["return_id"], "return:tx-1:order-retail")
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing_body, missing_status = return_for_refund(
                    {"fulfillment_id": "order-retail", "return_id": "return:tx-1:order-retail"}
                )
                self.assertEqual(missing_status, 400)
                self.assertFalse(missing_body["ok"])
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "order-retail",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
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
                body, status = return_for_refund(
                    {"fulfillment_id": "order-retail", "return_id": "return:tx-1:order-retail"}
                )
                self.assertEqual(status, 200)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("return:tx-1:order-retail", text)
                again_body, again_status = return_for_refund(
                    {"fulfillment_id": "order-retail", "return_id": "return:tx-1:order-retail"}
                )
                self.assertEqual(again_status, 400)
                self.assertFalse(again_body["ok"])
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

    def test_a_verified_paystack_charge_settles_the_named_sale_once(self) -> None:
        plain = {"status": True, "data": {"amount": 18500, "currency": "NGN", "reference": "salon-1"}}
        self.assertIsNone(paystack_settlement(plain))
        self.assertIsNone(record_paystack_settlement(plain))
        verified = {
            "status": True,
            "data": {
                "amount": "18500",
                "currency": "ngn",
                "reference": "salon-1",
                "metadata": json.dumps(
                    {"fulfillment_id": "order-retail", "client_id": "1", "settlement_id": "pay-salon-1"}
                ),
            },
        }
        self.assertEqual(
            paystack_settlement(verified),
            {
                "fulfillment_id": "order-retail",
                "settlement_id": "pay-salon-1",
                "amount_cents": 18500,
                "currency": "ngn",
            },
        )
        with tempfile.TemporaryDirectory() as tmp:
            ledger = Path(tmp) / "supply-chain.jsonl"
            previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
            previous_hub = os.environ.get("SKINTWIN_HUB_ROOT")
            script = _locate_script()
            self.assertIsNotNone(script)
            hub = script.parents[1]
            os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
            os.environ["SKINTWIN_HUB_ROOT"] = str(hub)
            try:
                missing_body, missing_status = record_paystack_settlement(verified)
                self.assertEqual(missing_status, 400)
                self.assertFalse(missing_body["ok"])
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "order-retail",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
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
                body, status = record_paystack_settlement(verified)
                self.assertEqual(status, 200)
                self.assertEqual(body["artifact"]["amount_cents"], 18500)
                self.assertEqual(body["artifact"]["currency"], "NGN")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-salon-1", text)
                again_body, again_status = record_paystack_settlement(verified)
                self.assertEqual(again_status, 400)
                self.assertFalse(again_body["ok"])
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

    def _webhook_module(self, platform: str):
        import importlib
        import types

        root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"

        def ensure(name: str, path: Path):
            current = sys.modules.get(name)
            if current is not None and getattr(current, "__path__", None):
                return current
            module = types.ModuleType(name)
            module.__path__ = [str(path)]
            module.__package__ = name
            sys.modules[name] = module
            return module

        ensure("integrations", root)
        ensure("integrations.common", root / "common")
        ensure(f"integrations.{platform}", root / platform)
        return importlib.import_module(f"integrations.{platform}.webhooks")

    def test_a_created_order_records_only_when_it_already_names_a_sale(self) -> None:
        shopify = self._webhook_module("shopify")
        opencart = self._webhook_module("opencart")
        directory = Path(tempfile.mkdtemp())
        ledger = directory / "supply-chain.jsonl"
        previous_ledger = os.environ.get("SKINTWIN_CHAIN_LEDGER")
        os.environ["SKINTWIN_CHAIN_LEDGER"] = str(ledger)
        line = {
            "sku": "sku-serum-c",
            "quantity": 1,
            "location": "cape-town",
            "milligrams": 2000,
            "price": "185.00",
        }
        try:
            created = shopify.ShopifyWebhookHandler("secret").on_order_created(
                {"id": 11, "order_number": 11, "line_items": [line]}
            )
            self.assertIsNone(created["recorded"])
            self.assertFalse(ledger.exists())
            with self.assertRaises(shopify.WebhookError):
                shopify.ShopifyWebhookHandler("secret").on_order_created(
                    {
                        "id": 11,
                        "order_number": 11,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "paid",
                        "line_items": [line],
                    }
                )
            self.assertFalse(ledger.exists())
            pending = opencart.OpenCartWebhookHandler("secret").on_order_created(
                {"order_id": 8, "status": "pending", "products": [line]}
            )
            self.assertIsNone(pending["recorded"])
            self.assertFalse(ledger.exists())
            with self.assertRaises(opencart.WebhookError):
                opencart.OpenCartWebhookHandler("secret").on_order_created(
                    {"order_id": 8, "status": "complete", "currency_code": "ZAR", "products": [line]}
                )
            self.assertFalse(ledger.exists())
        finally:
            if previous_ledger is None:
                os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
            else:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger


if __name__ == "__main__":
    unittest.main()
