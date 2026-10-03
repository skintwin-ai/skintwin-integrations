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
    record_wix_cancellation,
    record_wix_deliveries,
    respond,
    settlement_for_payment,
    shopify_catalog_commands,
    shopify_fulfillment_commands,
    record_shopify_fulfilled_order,
    record_shopify_order_update,
    record_shopify_paid_order,
    record_synced_catalog,
    record_synced_sale,
    shopify_order_update_commands,
    shopify_return_commands,
    shopify_settlement_commands,
    wix_delivery_commands,
    wix_return_commands,
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

    def test_a_formula_metafield_catalogs_the_sku_once(self) -> None:
        product = {
            "title": "Gentle cleanser",
            "tags": "retail",
            "variants": [{"sku": "sku-cleanser"}],
            "metafields": [
                {"key": "gift", "value": "thanks"},
                {"key": "formula_id", "value": " cleanser "},
            ],
        }
        commands = shopify_catalog_commands(product)
        self.assertEqual(commands[0]["args"]["formula_id"], "cleanser")
        self.assertEqual(commands[0]["args"]["sku_id"], "sku-cleanser")
        named = {**product, "formula_id": "serum-c"}
        self.assertEqual(shopify_catalog_commands(named)[0]["args"]["formula_id"], "serum-c")
        tagged = {
            **product,
            "tags": "formula:other",
            "metafields": [{"key": "formulaId", "value": "cleanser"}],
        }
        self.assertEqual(shopify_catalog_commands(tagged)[0]["args"]["formula_id"], "cleanser")
        blank = {
            "title": "Cleanser",
            "tags": "retail",
            "variants": [{"sku": "sku-cleanser"}],
            "metafields": [{"key": "formula_id", "value": " "}, {"key": "gift", "value": "cleanser"}],
        }
        self.assertEqual(shopify_catalog_commands(blank), [])
        self.assertEqual(opencart_catalog_commands({**product, "name": "Gentle cleanser"}), commands)
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
                unnamed = record_shopify_catalog(blank)
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
                recorded = record_shopify_catalog(product)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertEqual(text.count("sku-cleanser"), 1)
                again = record_shopify_catalog(product)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                opencart = record_opencart_catalog({**product, "name": "Gentle cleanser"})
                self.assertTrue(opencart["ok"])
                self.assertEqual(opencart["count"], 0)
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

    def test_a_blank_formula_id_records_the_named_formula_once(self) -> None:
        preferred = shopify_catalog_commands(
            {
                "title": "Vitamin C serum",
                "formulaId": "serum-c",
                "formula_id": "cleanser",
                "variants": [{"sku": "sku-serum"}],
            }
        )
        self.assertEqual(preferred[0]["args"]["formula_id"], "serum-c")
        fallen = shopify_catalog_commands(
            {
                "title": "Gentle cleanser",
                "formulaId": "  ",
                "formula_id": " cleanser ",
                "variants": [{"sku": "sku-cleanser"}],
            }
        )
        self.assertEqual(fallen[0]["args"]["formula_id"], "cleanser")
        variant = shopify_catalog_commands(
            {
                "title": "Shelf",
                "tags": "retail",
                "variants": [{"sku": "sku-variant", "formulaId": "  ", "formula_id": "cleanser"}],
            }
        )
        self.assertEqual(variant[0]["args"]["sku_id"], "sku-variant")
        self.assertEqual(variant[0]["args"]["formula_id"], "cleanser")
        unnamed = {"title": "Shelf", "formulaId": "  ", "tags": "retail", "variants": [{"sku": "sku-plain"}]}
        self.assertEqual(shopify_catalog_commands(unnamed), [])
        opencart = opencart_catalog_commands(
            {"name": "Gentle cleanser", "formula_id": "  ", "formulaId": "cleanser", "sku": "sku-cleanser"}
        )
        self.assertEqual(opencart[0]["args"]["formula_id"], "cleanser")
        product = {
            "title": "Gentle cleanser",
            "formulaId": "  ",
            "formula_id": "cleanser",
            "variants": [{"sku": "sku-cleanser"}],
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
                skipped = record_shopify_catalog(unnamed)
                self.assertIsNone(skipped)
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
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 2000]],
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
                recorded = record_shopify_catalog(product)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("sku-cleanser", text)
                self.assertNotIn("sku-plain", text)
                again = record_shopify_catalog(product)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                renamed = record_shopify_catalog({**product, "formulaId": "serum-c"})
                self.assertFalse(renamed["ok"])
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

    def test_a_blank_product_name_records_the_named_title_once(self) -> None:
        preferred = shopify_catalog_commands(
            {
                "title": "Vitamin C serum",
                "name": "Other",
                "formula_id": "serum-c",
                "variants": [{"sku": "sku-serum"}],
            }
        )
        self.assertEqual(preferred[0]["args"]["name"], "Vitamin C serum")
        fallen = shopify_catalog_commands(
            {
                "title": "  ",
                "name": " Gentle cleanser ",
                "formula_id": "cleanser",
                "variants": [{"sku": " "}],
            }
        )
        self.assertEqual(fallen[0]["args"]["name"], "Gentle cleanser")
        self.assertEqual(fallen[0]["args"]["sku_id"], "Gentle cleanser")
        owned = opencart_catalog_commands(
            {
                "name": "Gentle cleanser",
                "title": "Other",
                "formulaId": "cleanser",
                "sku": "sku-cleanser",
            }
        )
        self.assertEqual(owned[0]["args"]["name"], "Gentle cleanser")
        opencart = opencart_catalog_commands(
            {
                "name": "  ",
                "title": " Gentle cleanser ",
                "formula_id": "cleanser",
                "model": "sku-cleanser",
            }
        )
        self.assertEqual(opencart[0]["args"]["name"], "Gentle cleanser")
        self.assertEqual(opencart[0]["args"]["sku_id"], "sku-cleanser")
        product = {
            "title": "  ",
            "name": "Gentle cleanser",
            "formula_id": "cleanser",
            "variants": [{"sku": "sku-cleanser"}],
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
                missing = record_shopify_catalog(
                    {"title": "  ", "name": "  ", "formula_id": "cleanser", "sku": "sku-missing"}
                )
                self.assertFalse(missing["ok"])
                plain = record_shopify_catalog({"title": "  ", "name": "Shelf", "tags": "retail", "sku": "sku-shelf"})
                self.assertIsNone(plain)
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
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 2000]],
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
                recorded = record_shopify_catalog(product)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("Gentle cleanser", text)
                self.assertIn("sku-cleanser", text)
                again = record_shopify_catalog(product)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                changed = record_shopify_catalog({**product, "formula_id": "serum-c"})
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

    def test_a_variant_formula_metafield_catalogs_that_sku_once(self) -> None:
        owned = shopify_catalog_commands(
            {
                "title": "Vitamin C serum",
                "formula_id": "serum-c",
                "variants": [
                    {
                        "sku": "sku-serum-c",
                        "metafields": [{"key": "formula_id", "value": "cleanser"}],
                    }
                ],
            }
        )
        self.assertEqual(owned[0]["args"]["formula_id"], "serum-c")
        product = {
            "title": "Shelf",
            "tags": "retail",
            "variants": [
                {
                    "sku": "sku-cleanser",
                    "metafields": [
                        {"key": "gift", "value": "thanks"},
                        {"key": "formula_id", "value": " cleanser "},
                    ],
                },
                {"sku": "sku-plain"},
                {"sku": " ", "metafields": [{"key": "formula_id", "value": "cleanser"}]},
                {
                    "sku": "sku-serum",
                    "formula_id": "serum-c",
                    "metafields": [{"key": "formula_id", "value": "other"}],
                },
                {"sku": "sku-cleanser", "metafields": [{"key": "formula_id", "value": "other"}]},
            ],
        }
        commands = shopify_catalog_commands(product)
        self.assertEqual(
            [(command["args"]["sku_id"], command["args"]["formula_id"]) for command in commands],
            [("sku-cleanser", "cleanser"), ("sku-serum", "serum-c")],
        )
        self.assertEqual(shopify_catalog_commands({"title": "Shelf", "tags": "retail", "variants": [{"sku": "sku-plain"}]}), [])
        self.assertEqual(
            opencart_catalog_commands({**product, "name": "Shelf"}),
            commands,
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
                    {"title": "Shelf", "tags": "retail", "variants": [{"sku": "sku-plain"}]}
                )
                self.assertIsNone(unnamed)
                self.assertFalse(ledger.exists())
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
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 2000]],
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
                recorded = record_shopify_catalog(product)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertEqual(text.count("sku-cleanser"), 1)
                self.assertEqual(text.count("sku-serum"), 1)
                self.assertNotIn("sku-plain", text)
                again = record_shopify_catalog(product)
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

    def test_a_blank_line_location_records_the_named_location_once(self) -> None:
        preferred = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "location": "cape-town",
                        "milligrams": 2000,
                        "properties": [
                            {"name": "location", "value": "johannesburg"},
                            {"name": "milligrams", "value": "9000"},
                        ],
                    }
                ],
            }
        )
        self.assertEqual(preferred[0]["args"]["location"], "cape-town")
        self.assertEqual(preferred[0]["args"]["milligrams"], 2000)
        fallen = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "location": "  ",
                        "milligrams": "  ",
                        "properties": [
                            {"name": "location", "value": " cape-town "},
                            {"name": "milligrams", "value": "2000"},
                        ],
                    }
                ],
                "note_attributes": [
                    {"name": "location", "value": "johannesburg"},
                    {"name": "milligrams", "value": "9000"},
                ],
            }
        )
        self.assertEqual(fallen[0]["args"]["location"], "cape-town")
        self.assertEqual(fallen[0]["args"]["milligrams"], 2000)
        noted = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [{"sku": "sku-serum-c", "location": "  ", "milligrams": ""}],
                "note_attributes": [
                    {"name": "location", "value": "cape-town"},
                    {"name": "milligrams", "value": "2000"},
                ],
            }
        )
        self.assertEqual(noted[0]["args"]["location"], "cape-town")
        self.assertEqual(noted[0]["args"]["milligrams"], 2000)
        self.assertEqual(
            shopify_fulfillment_commands(
                {"order_number": 9, "line_items": [{"sku": "sku-serum-c", "location": "  "}]}
            ),
            [],
        )
        order = {
            "order_number": 9,
            "line_items": [
                {
                    "sku": "sku-serum-c",
                    "location": "  ",
                    "properties": [
                        {"name": "location", "value": "cape-town"},
                        {"name": "milligrams", "value": "2000"},
                    ],
                }
            ],
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
                skipped = record_shopify_fulfillments(
                    {"order_number": 9, "line_items": [{"sku": "sku-serum-c", "location": "  "}]}
                )
                self.assertIsNone(skipped)
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
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                recorded_sale = record_shopify_fulfillments(order)
                self.assertTrue(recorded_sale["ok"])
                self.assertEqual(recorded_sale["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"location": "cape-town"', text)
                again = record_shopify_fulfillments(order)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                changed = record_shopify_fulfillments(
                    {
                        "order_number": 9,
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "location": "johannesburg",
                                "milligrams": 2000,
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

    def test_a_property_key_names_the_sale_once(self) -> None:
        keyed = {
            "order_number": 9,
            "line_items": [
                {
                    "sku": "sku-serum-c",
                    "properties": [
                        {"key": "location", "value": "cape-town"},
                        {"key": "milligrams", "value": "5000"},
                        {"key": "gift", "value": "thanks"},
                    ],
                }
            ],
        }
        commands = shopify_fulfillment_commands(keyed)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        self.assertEqual(commands[0]["args"]["location"], "cape-town")
        self.assertEqual(commands[0]["args"]["milligrams"], 5000)
        named = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "properties": [
                            {"name": "location", "key": "gift", "value": "johannesburg"},
                            {"name": "milligrams", "key": "location", "value": "2000"},
                        ],
                    }
                ],
            }
        )
        self.assertEqual(named[0]["args"]["location"], "johannesburg")
        self.assertEqual(named[0]["args"]["milligrams"], 2000)
        gift = {
            "order_number": 9,
            "line_items": [
                {"sku": "sku-serum-c", "properties": [{"key": "gift", "value": "thanks"}]}
            ],
        }
        self.assertEqual(shopify_fulfillment_commands(gift), [])
        self.assertEqual(
            shopify_fulfillment_commands(
                {
                    "order_number": 9,
                    "line_items": [
                        {
                            "sku": "sku-serum-c",
                            "properties": [
                                {"name": "gift", "key": "location", "value": "cape-town"}
                            ],
                        }
                    ],
                }
            ),
            [],
        )
        notes = [
            {"key": "location", "value": "cape-town"},
            {"key": "milligrams", "value": "2000"},
            {"key": "gift", "value": "thanks"},
        ]
        drawn = shopify_order_update_commands(
            {
                "order_number": 9,
                "line_items": [{"sku": "sku-serum-c"}],
                "note_attributes": notes,
                "fulfillment_status": "fulfilled",
            }
        )
        self.assertEqual(drawn[0]["args"]["location"], "cape-town")
        self.assertEqual(drawn[0]["args"]["milligrams"], 2000)
        optioned = opencart_fulfillment_commands(
            {
                "order_id": 4,
                "status": "shipped",
                "products": [
                    {
                        "model": "sku-serum-c",
                        "option": [
                            {"key": "location", "value": "cape-town"},
                            {"key": "milligrams", "value": "2000"},
                            {"key": "size", "value": "30ml"},
                        ],
                    }
                ],
            }
        )
        self.assertEqual(optioned[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
        self.assertEqual(optioned[0]["args"]["milligrams"], 2000)
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
                unnamed = record_shopify_fulfillments(gift)
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
                recorded = record_shopify_fulfillments(keyed)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                again = record_shopify_fulfillments(keyed)
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

    def test_a_line_named_by_sku_id_records_that_sale_once(self) -> None:
        preferred = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {"title": "Gift"},
                    {
                        "sku": "sku-serum-c",
                        "sku_id": "sku-other",
                        "location": "cape-town",
                        "milligrams": 2000,
                    },
                    {
                        "sku": "  ",
                        "sku_id": " sku-cleanser ",
                        "location": "cape-town",
                        "milligrams": 1000,
                    },
                ],
            }
        )
        self.assertEqual(
            [command["args"]["sku_id"] for command in preferred],
            ["sku-serum-c", "sku-cleanser"],
        )
        self.assertEqual(preferred[1]["args"]["fulfillment_id"], "9:2:sku-cleanser")
        catalog = shopify_catalog_commands(
            {
                "title": "Vitamin C serum",
                "tags": "formula:serum-c",
                "variants": [
                    {"sku": "  ", "sku_id": "sku-serum-c"},
                    {"skuId": "sku-serum-30"},
                ],
            }
        )
        self.assertEqual(
            [command["args"]["sku_id"] for command in catalog],
            ["sku-serum-c", "sku-serum-30"],
        )
        shipped = opencart_fulfillment_commands(
            {
                "order_id": 4,
                "status": "shipped",
                "products": [
                    {
                        "model": "sku-model",
                        "sku_id": "sku-serum-c",
                        "location": "cape-town",
                        "milligrams": 2000,
                    }
                ],
            }
        )
        self.assertEqual(shipped[0]["args"]["sku_id"], "sku-serum-c")
        deliveries = wix_delivery_commands(
            {
                "id": "book-1",
                "services": [
                    {
                        "delivery": {
                            "sku_id": "  ",
                            "skuId": "sku-serum-c",
                            "batch_id": "  ",
                            "batchId": "batch-1",
                            "source": "plant",
                            "destination": "cape-town",
                            "milligrams": 2000,
                        }
                    }
                ],
            }
        )
        self.assertEqual(deliveries[0]["args"]["sku_id"], "sku-serum-c")
        self.assertEqual(deliveries[0]["args"]["batch_id"], "batch-1")
        unnamed = {"order_number": 9, "line_items": [{"title": "Gift", "location": "cape-town", "milligrams": 2000}]}
        named = {
            "order_number": 9,
            "line_items": [
                {"title": "Gift"},
                {"sku_id": "sku-serum-c", "location": "cape-town", "milligrams": 2000},
            ],
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
                skipped = record_shopify_fulfillments(unnamed)
                self.assertIsNone(skipped)
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
                recorded = record_shopify_fulfillments(named)
                self.assertTrue(recorded["ok"], recorded)
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:1:sku-serum-c"', text)
                again = record_shopify_fulfillments(named)
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

    def test_a_treatment_named_by_practitioner_id_records_that_sale_once(self) -> None:
        preferred = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "location": "cape-town",
                        "milligrams": 2000,
                        "kind": "treatment",
                        "practitionerId": "aya",
                        "practitioner_id": "other",
                    },
                    {
                        "sku_id": "sku-cleanser",
                        "location": "cape-town",
                        "milligrams": 1000,
                        "kind": "treatment",
                        "practitionerId": "  ",
                        "practitioner_id": " aya ",
                    },
                ],
            }
        )
        self.assertEqual(preferred[0]["args"]["practitioner_id"], "aya")
        self.assertEqual(preferred[0]["args"]["kind"], "treatment")
        self.assertEqual(preferred[1]["args"]["practitioner_id"], "aya")
        self.assertEqual(preferred[1]["args"]["sku_id"], "sku-cleanser")
        noted = shopify_fulfillment_commands(
            {
                "order_number": 9,
                "line_items": [{"sku": "sku-serum-c", "kind": "treatment"}],
                "note_attributes": [
                    {"name": "practitionerId", "key": "gift", "value": "aya"},
                    {"name": "location", "value": "cape-town"},
                    {"name": "milligrams", "value": "2000"},
                ],
            }
        )
        self.assertEqual(noted[0]["args"]["practitioner_id"], "aya")
        optioned = opencart_fulfillment_commands(
            {
                "order_id": 4,
                "status": "shipped",
                "products": [
                    {
                        "sku": "sku-serum-c",
                        "kind": "treatment",
                        "option": [
                            {"name": "practitionerId", "value": "aya"},
                            {"name": "location", "value": "cape-town"},
                            {"name": "milligrams", "value": "2000"},
                        ],
                    }
                ],
            }
        )
        self.assertEqual(optioned[0]["args"]["practitioner_id"], "aya")
        missing = {
            "order_number": 9,
            "line_items": [
                {
                    "sku": "sku-serum-c",
                    "location": "cape-town",
                    "milligrams": 2000,
                    "kind": "treatment",
                }
            ],
        }
        with self.assertRaises(Exception):
            shopify_fulfillment_commands(missing)
        named = {
            "order_number": 9,
            "line_items": [
                {
                    "sku": "sku-serum-c",
                    "location": "cape-town",
                    "milligrams": 2000,
                    "kind": "treatment",
                    "practitionerId": "aya",
                }
            ],
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
                rejected = record_shopify_fulfillments(missing)
                self.assertFalse(rejected["ok"])
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
                                    "command": "certify_practitioner",
                                    "args": {
                                        "certificate_id": "cert-aya",
                                        "practitioner_id": "aya",
                                        "course": "Facial protocol",
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
                recorded = record_shopify_fulfillments(named)
                self.assertTrue(recorded["ok"], recorded)
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"practitioner_id": "aya"', text)
                self.assertIn('"kind": "treatment"', text)
                again = record_shopify_fulfillments(named)
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

    def test_a_paid_fulfilled_order_draws_and_settles_that_sale(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "price": "185.00",
            "quantity": 1,
            "location": "cape-town",
            "milligrams": 2000,
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
                waiting = record_shopify_paid_order(
                    {"order_number": 9, "financial_status": "paid", "currency": "ZAR", "line_items": [line]}
                )
                self.assertIsNone(waiting)
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
                drawn = record_shopify_fulfilled_order(
                    {"order_number": 9, "currency": "ZAR", "line_items": [line]}
                )
                self.assertEqual(drawn, {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertNotIn('"command": "settle"', text)
                paid = record_shopify_paid_order(
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "currency": "ZAR",
                        "line_items": [line],
                    }
                )
                self.assertEqual(paid, {"ok": True, "count": 1})
                settled = ledger.read_text(encoding="utf-8")
                self.assertIn('"settlement_id": "pay-9:0:sku-serum-c"', settled)
                self.assertIn('"amount_cents": 18500', settled)
                both = record_shopify_fulfilled_order(
                    {
                        "order_number": 10,
                        "financial_status": "paid",
                        "currency": "ZAR",
                        "line_items": [line],
                    }
                )
                self.assertEqual(both, {"ok": True, "count": 2})
                combined = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "10:0:sku-serum-c"', combined)
                self.assertIn('"settlement_id": "pay-10:0:sku-serum-c"', combined)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

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
        stripped = {
            **named_partial,
            "line_items": [{**named_line, "id": "100"}],
            "refunds": [
                {
                    "refund_line_items": [
                        {
                            "line_item_id": 100,
                            "quantity": 1,
                            "line_item": {"id": 100, "quantity": 1},
                        }
                    ]
                }
            ],
        }
        stripped_commands = shopify_order_update_commands(stripped)
        self.assertEqual([command["command"] for command in stripped_commands], ["fulfill", "return_sale"])
        self.assertEqual(stripped_commands[1]["args"]["fulfillment_id"], "9:0:sku-serum-c")
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
        omitted_quantity = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [{**named_line, "quantity": 2}],
            "refunds": [
                {
                    "refund_line_items": [
                        {
                            "line_item_id": 100,
                            "quantity": 2,
                            "line_item": {"id": 100, "sku": "sku-serum-c"},
                        }
                    ]
                }
            ],
        }
        omitted_commands = shopify_order_update_commands(omitted_quantity)
        self.assertEqual([command["command"] for command in omitted_commands], ["fulfill", "return_sale"])
        self.assertEqual(omitted_commands[1]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        partial_omitted = {
            **omitted_quantity,
            "refunds": [
                {
                    "refund_line_items": [
                        {
                            "line_item_id": 100,
                            "quantity": 1,
                            "line_item": {"id": 100, "sku": "sku-serum-c"},
                        }
                    ]
                }
            ],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(partial_omitted)],
            ["fulfill"],
        )
        omitted_id = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [named_line],
            "refunds": [
                {
                    "refund_line_items": [
                        {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                    ]
                }
            ],
        }
        omitted_id_commands = shopify_order_update_commands(omitted_id)
        self.assertEqual([command["command"] for command in omitted_id_commands], ["fulfill", "return_sale"])
        self.assertEqual(omitted_id_commands[1]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        sole = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [named_line],
            "refunds": [{"refund_line_items": [{"quantity": 1}]}],
        }
        sole_commands = shopify_order_update_commands(sole)
        self.assertEqual([command["command"] for command in sole_commands], ["fulfill", "return_sale"])
        self.assertEqual(sole_commands[1]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        sole_short = {
            **sole,
            "line_items": [{**named_line, "quantity": 2}],
            "refunds": [{"refund_line_items": [{"quantity": 1}]}],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(sole_short)],
            ["fulfill"],
        )
        two_skus = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [named_line, {**line, "sku": "sku-other", "id": 101}],
            "refunds": [{"refund_line_items": [{"quantity": 1}]}],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(two_skus)],
            ["fulfill", "fulfill"],
        )
        missed_id = {
            **sole,
            "refunds": [{"refund_line_items": [{"line_item_id": 404, "quantity": 1}]}],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(missed_id)],
            ["fulfill"],
        )
        ambiguous = {
            **paid,
            "financial_status": "partially_refunded",
            "line_items": [named_line, {**named_line, "id": 101}],
            "refunds": [
                {
                    "refund_line_items": [
                        {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                    ]
                }
            ],
        }
        self.assertEqual(
            [command["command"] for command in shopify_order_update_commands(ambiguous)],
            ["fulfill", "fulfill"],
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
                sole_order = {
                    "order_number": 21,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [line],
                    "refunds": [{"refund_line_items": [{"quantity": 1}]}],
                }
                sole_recorded = record_shopify_order_update(sole_order)
                self.assertTrue(sole_recorded["ok"], sole_recorded)
                self.assertEqual(sole_recorded["count"], 2)
                sole_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "21:0:sku-serum-c"', sole_text)
                self.assertIn('"return_id": "return:21:0:sku-serum-c"', sole_text)
                self.assertIn('"transfer_id": "to-cape-town"', sole_text)
                self.assertNotIn("return:to-cape-town", sole_text)
                sole_again = record_shopify_order_update(sole_order)
                self.assertTrue(sole_again["ok"])
                self.assertEqual(sole_again["count"], 0)
                self.assertEqual(ledger.read_text(encoding="utf-8"), sole_text)
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

    def test_a_cancelled_wix_booking_sends_the_named_delivery_back_once(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        booking = {"id": "book-1", "services": [{"name": "Facial"}, {"delivery": delivery}]}
        returned = wix_return_commands(booking)
        self.assertEqual(returned[0]["args"]["transfer_id"], "return:book-1:1")
        self.assertEqual(returned[0]["args"]["source"], "cape-town")
        self.assertEqual(returned[0]["args"]["destination"], "plant")
        self.assertEqual(returned[0]["args"]["milligrams"], 2000)
        self.assertEqual(wix_return_commands({"id": "book-1", "services": [{"name": "Facial"}]}), [])
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
                plain = wix.WixWebhookHandler("secret").on_booking_cancelled(
                    {"id": "book-plain", "services": [{"name": "Facial"}]}
                )
                self.assertIsNone(plain["recorded"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").on_booking_cancelled(booking)
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
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = wix.WixWebhookHandler("secret").on_booking_created(booking)
                self.assertEqual(created["recorded"], {"ok": True, "count": 1})
                cancelled = wix.WixWebhookHandler("secret").on_booking_cancelled(booking)
                self.assertEqual(cancelled["recorded"], {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-1:1"', text)
                again = wix.WixWebhookHandler("secret").on_booking_cancelled(booking)
                self.assertEqual(again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                changed = {
                    **booking,
                    "services": [{"name": "Facial"}, {"delivery": {**delivery, "milligrams": 1000}}],
                }
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").on_booking_cancelled(changed)
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

    def test_a_cancelled_wix_booking_returns_the_delivery_it_already_recorded(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        booking = {"id": "book-omit", "services": [{"name": "Facial"}, {"delivery": delivery}]}
        omitted = {"id": "book-omit", "services": [{"name": "Facial"}]}
        self.assertEqual(wix_return_commands(omitted), [])
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
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
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
                wix = self._webhook_module("wix")
                created = wix.WixWebhookHandler("secret").on_booking_created(booking)
                self.assertEqual(created["recorded"], {"ok": True, "count": 1})
                commands = wix_return_commands(omitted)
                self.assertEqual(commands[0]["args"]["transfer_id"], "return:book-omit:1")
                self.assertEqual(commands[0]["args"]["source"], "cape-town")
                self.assertEqual(commands[0]["args"]["destination"], "plant")
                self.assertEqual(commands[0]["args"]["milligrams"], 2000)
                cancelled = wix.WixWebhookHandler("secret").on_booking_cancelled(omitted)
                self.assertEqual(cancelled["recorded"], {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-omit:1"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                again = wix.WixWebhookHandler("secret").on_booking_cancelled(omitted)
                self.assertEqual(again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                split = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-split:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-split:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                            ]
                        }
                    ),
                    text=True,
                    capture_output=True,
                    env=os.environ.copy(),
                )
                self.assertEqual(split.returncode, 0, split.stderr or split.stdout)
                split_text = ledger.read_text(encoding="utf-8")
                mismatched = {
                    "id": "book-split",
                    "status": "cancelled",
                    "services": [{"name": "Facial"}, {"delivery": {**delivery, "milligrams": 1000}}],
                }
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").on_booking_cancelled(mismatched)
                self.assertEqual(ledger.read_text(encoding="utf-8"), split_text)
                both = {
                    "id": "book-split",
                    "status": "cancelled",
                    "services": [{"name": "Facial"}, {"delivery": delivery}],
                }
                cancelled_both = wix.WixWebhookHandler("secret").on_booking_cancelled(both)
                self.assertEqual(cancelled_both["recorded"], {"ok": True, "count": 2})
                returned_both = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-split:0"', returned_both)
                self.assertIn('"transfer_id": "return:book-split:1"', returned_both)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', returned_both)
                again_both = wix.WixWebhookHandler("secret").on_booking_cancelled(both)
                self.assertEqual(again_both["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), returned_both)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_cancelled_order_returns_the_sale_it_already_recorded(self) -> None:
        thin = {"id": 9, "order_number": 9, "cancelled_at": "2026-10-02T00:00:00Z"}
        opencart_cancel = {"order_id": 4, "new_status_id": 7}
        shopify_partial = {
            "id": 21,
            "order_number": 21,
            "cancelled_at": "2026-10-02T00:00:00Z",
            "line_items": [
                {"title": "Consultation"},
                {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 1000},
            ],
        }
        opencart_partial = {
            "order_id": 22,
            "new_status_id": 7,
            "products": [
                {"name": "Consultation"},
                {"model": "sku-serum-c", "location": "cape-town", "milligrams": 1000},
            ],
        }
        self.assertEqual(shopify_return_commands(thin), [])
        self.assertEqual(opencart_return_commands(opencart_cancel), [])
        self.assertEqual(
            [command["args"]["fulfillment_id"] for command in shopify_return_commands(shopify_partial)],
            ["21:1:sku-serum-c"],
        )
        self.assertEqual(
            [command["args"]["fulfillment_id"] for command in opencart_return_commands(opencart_partial)],
            ["22:1:sku-serum-c"],
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "4:0:sku-serum-c",
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
                shopify = self._webhook_module("shopify")
                commands = shopify_return_commands(thin)
                self.assertEqual(commands[0]["args"]["return_id"], "return:9:0:sku-serum-c")
                self.assertEqual(commands[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
                cancelled = shopify.ShopifyWebhookHandler("secret").on_order_cancelled(thin)
                self.assertEqual(cancelled["recorded"], {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:to-cape-town"', text)
                again = shopify.ShopifyWebhookHandler("secret").on_order_cancelled(thin)
                self.assertEqual(again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                absent = shopify.ShopifyWebhookHandler("secret").on_order_cancelled(
                    {"id": 19, "order_number": 19, "cancelled_at": "2026-10-02T00:00:00Z"}
                )
                self.assertIsNone(absent["recorded"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                opencart = self._webhook_module("opencart")
                returned = opencart_return_commands(opencart_cancel)
                self.assertEqual(returned[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
                changed = opencart.OpenCartWebhookHandler("secret").on_order_status_changed(opencart_cancel)
                self.assertEqual(changed["recorded"], {"ok": True, "count": 1})
                recorded = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:4:0:sku-serum-c"', recorded)
                repeated = opencart.OpenCartWebhookHandler("secret").on_order_status_changed(opencart_cancel)
                self.assertEqual(repeated["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), recorded)
                split = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "21:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "21:1:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "22:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "22:1:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
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
                self.assertEqual(split.returncode, 0, split.stderr or split.stdout)
                named = shopify_return_commands(shopify_partial)
                self.assertEqual(
                    [command["args"]["fulfillment_id"] for command in named],
                    ["21:1:sku-serum-c", "21:0:sku-serum-c"],
                )
                self.assertEqual(
                    [command["args"]["return_id"] for command in named],
                    ["return:21:1:sku-serum-c", "return:21:0:sku-serum-c"],
                )
                cancelled_split = shopify.ShopifyWebhookHandler("secret").on_order_cancelled(shopify_partial)
                self.assertEqual(cancelled_split["recorded"], {"ok": True, "count": 2})
                split_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:21:0:sku-serum-c"', split_text)
                self.assertIn('"return_id": "return:21:1:sku-serum-c"', split_text)
                self.assertEqual(split_text.count('"return_id": "return:4:0:sku-serum-c"'), 1)
                self.assertNotIn('"return_id": "return:22:0:sku-serum-c"', split_text)
                self.assertNotIn('"return_id": "return:to-cape-town"', split_text)
                cancelled_again = shopify.ShopifyWebhookHandler("secret").on_order_cancelled(shopify_partial)
                self.assertEqual(cancelled_again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), split_text)
                opencart_named = opencart_return_commands(opencart_partial)
                self.assertEqual(
                    [command["args"]["fulfillment_id"] for command in opencart_named],
                    ["22:1:sku-serum-c", "22:0:sku-serum-c"],
                )
                changed_split = opencart.OpenCartWebhookHandler("secret").on_order_status_changed(opencart_partial)
                self.assertEqual(changed_split["recorded"], {"ok": True, "count": 2})
                opencart_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:22:0:sku-serum-c"', opencart_text)
                self.assertIn('"return_id": "return:22:1:sku-serum-c"', opencart_text)
                self.assertEqual(opencart_text.count('"return_id": "return:21:0:sku-serum-c"'), 1)
                self.assertNotIn('"return_id": "return:to-cape-town"', opencart_text)
                opencart_again = opencart.OpenCartWebhookHandler("secret").on_order_status_changed(opencart_partial)
                self.assertEqual(opencart_again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), opencart_text)
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

    def test_opencart_options_name_the_sale_when_the_line_does_not(self) -> None:
        options = [
            {"name": "location", "value": "cape-town"},
            {"name": "milligrams", "value": "2000"},
            {"name": "size", "value": "30ml"},
        ]
        product = {"model": "sku-serum-c", "price": "185.00", "quantity": 1, "option": options}
        shipped = {"order_id": 4, "status": "shipped", "currency_code": "ZAR", "products": [product]}
        drawn = opencart_fulfillment_commands(shipped)
        self.assertEqual(drawn[0]["args"]["location"], "cape-town")
        self.assertEqual(drawn[0]["args"]["milligrams"], 2000)
        self.assertEqual(drawn[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
        owned = {**shipped, "products": [{**product, "location": "johannesburg", "milligrams": 1500}]}
        self.assertEqual(opencart_fulfillment_commands(owned)[0]["args"]["location"], "johannesburg")
        self.assertEqual(opencart_fulfillment_commands(owned)[0]["args"]["milligrams"], 1500)
        preferred = {
            **shipped,
            "products": [
                {
                    **product,
                    "properties": [
                        {"name": "location", "value": "durban"},
                        {"name": "milligrams", "value": "1000"},
                    ],
                }
            ],
        }
        self.assertEqual(opencart_fulfillment_commands(preferred)[0]["args"]["location"], "durban")
        self.assertEqual(opencart_fulfillment_commands(preferred)[0]["args"]["milligrams"], 1000)
        plural = {
            **shipped,
            "products": [{"model": "sku-serum-c", "price": "185.00", "quantity": 1, "options": options}],
        }
        self.assertEqual(opencart_fulfillment_commands(plural), drawn)
        sized = {
            "order_id": 4,
            "status": "shipped",
            "products": [{"model": "sku-serum-c", "option": [{"name": "size", "value": "30ml"}]}],
        }
        self.assertEqual(opencart_fulfillment_commands(sized), [])
        self.assertEqual(opencart_fulfillment_commands({**shipped, "status": "pending"}), [])
        complete = {**shipped, "status": "complete"}
        self.assertEqual(
            [command["command"] for command in opencart_fulfillment_commands(complete) + opencart_settlement_commands(complete)],
            ["fulfill", "settle"],
        )
        returned = opencart_return_commands({**shipped, "status": "refunded"})
        self.assertEqual(returned[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
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
                unnamed = record_opencart_fulfillments(sized)
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
                recorded = record_opencart_fulfillments(complete)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertEqual(text.count("pay-4:0:sku-serum-c"), 1)
                self.assertIn('"fulfillment_id": "4:0:sku-serum-c"', text)
                again = record_opencart_fulfillments(complete)
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
        self.assertIsNone(return_for_refund({"settlement_id": "pay-snake"}))
        self.assertIsNone(return_for_refund({"payment_intent_id": "pi_pos"}))
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "order-named",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "settle",
                                    "args": {
                                        "settlement_id": "pay-snake",
                                        "fulfillment_id": "order-named",
                                        "amount_cents": 2000,
                                        "currency": "USD",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "order-intent",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "settle",
                                    "args": {
                                        "settlement_id": "pay-pi_pos",
                                        "fulfillment_id": "order-intent",
                                        "amount_cents": 1000,
                                        "currency": "USD",
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
                missed_body, missed_status = return_for_refund(
                    {
                        "fulfillment_id": "missing-order",
                        "settlement_id": "pay-snake",
                        "payment_intent_id": "pi_pos",
                    }
                )
                self.assertEqual(missed_status, 400)
                self.assertFalse(missed_body["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                self.assertIsNone(
                    return_for_refund({"settlement_id": "pay-absent", "payment_intent_id": "pi_pos"})
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                named_body, named_status = return_for_refund(
                    {"settlement_id": "pay-snake", "return_key": "tx-named", "payment_intent_id": "pi_pos"}
                )
                self.assertEqual(named_status, 200)
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn("return:tx-named:order-named", named_text)
                self.assertNotIn("return:to-cape-town", named_text)
                named_again, named_again_status = return_for_refund(
                    {"settlement_id": "pay-snake", "return_key": "tx-named"}
                )
                self.assertEqual(named_again_status, 400)
                self.assertEqual(ledger.read_text(encoding="utf-8"), named_text)
                intent_body, intent_status = return_for_refund(
                    {"payment_intent_id": "pi_pos", "return_key": "tx-intent"}
                )
                self.assertEqual(intent_status, 200)
                intent_text = ledger.read_text(encoding="utf-8")
                self.assertIn("return:tx-intent:order-intent", intent_text)
                self.assertNotIn("return:to-cape-town", intent_text)
                intent_again, intent_again_status = return_for_refund(
                    {"payment_intent_id": "pi_pos", "return_key": "tx-intent"}
                )
                self.assertEqual(intent_again_status, 400)
                self.assertEqual(ledger.read_text(encoding="utf-8"), intent_text)
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

    def test_a_payment_named_by_a_blank_fulfillment_id_records_fulfillment_id_once(self) -> None:
        self.assertIsNone(
            settlement_for_payment(
                {"fulfillment_id": "  ", "fulfillmentId": "  ", "amount": 10, "currency": "USD"}
            )
        )
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            preferred, preferred_status = settlement_for_payment(
                {
                    "fulfillment_id": "order-retail",
                    "fulfillmentId": "other",
                    "settlement_id": "pay-snake",
                    "settlementId": "pay-camel",
                    "amount": 45.5,
                    "currency": "ZAR",
                }
            )
            self.assertEqual(preferred_status, 200, preferred)
            self.assertEqual(preferred["artifact"]["fulfillment_id"], "order-retail")
            self.assertEqual(preferred["artifact"]["settlement_id"], "pay-snake")
            fallen, fallen_status = settlement_for_payment(
                {
                    "fulfillment_id": "  ",
                    "fulfillmentId": " order-retail ",
                    "settlement_id": "  ",
                    "settlementId": " pay-camel ",
                    "amount_cents": 18500,
                    "currency": "zar",
                }
            )
            self.assertEqual(fallen_status, 200, fallen)
            self.assertEqual(fallen["artifact"]["fulfillment_id"], "order-retail")
            self.assertEqual(fallen["artifact"]["settlement_id"], "pay-camel")
            returned = return_for_refund(
                {
                    "fulfillment_id": "order-retail",
                    "fulfillmentId": "other",
                    "return_id": "return:tx-1:order-retail",
                    "returnId": "return:other",
                }
            )
            self.assertEqual(returned[1], 200)
            self.assertEqual(returned[0]["artifact"]["fulfillment_id"], "order-retail")
            self.assertEqual(returned[0]["artifact"]["return_id"], "return:tx-1:order-retail")
            fallen_return = return_for_refund(
                {"fulfillment_id": "  ", "fulfillmentId": "order-retail", "returnId": " return:camel "}
            )
            self.assertEqual(fallen_return[1], 200)
            self.assertEqual(fallen_return[0]["artifact"]["fulfillment_id"], "order-retail")
            self.assertEqual(fallen_return[0]["artifact"]["return_id"], "return:camel")
            self.assertIsNone(return_for_refund({"fulfillment_id": "  ", "returnId": "return:camel"}))
            charge = {
                "data": {
                    "amount": 18500,
                    "currency": "NGN",
                    "reference": "salon-camel",
                    "metadata": {
                        "fulfillment_id": "  ",
                        "fulfillmentId": "order-retail",
                        "settlement_id": "  ",
                        "settlementId": "pay-camel",
                    },
                }
            }
            self.assertEqual(paystack_settlement(charge)["fulfillment_id"], "order-retail")
            self.assertEqual(paystack_settlement(charge)["settlement_id"], "pay-camel")
            self.assertIsNone(
                paystack_settlement({"data": {"amount": 18500, "metadata": {"fulfillment_id": "  "}}})
            )
            explicit = shopify_settlement_commands(
                {
                    "order_number": 9,
                    "currency": "ZAR",
                    "total_price": "185.00",
                    "fulfillment_id": "  ",
                    "fulfillmentId": "9:0:sku-serum-c",
                    "settlementId": "pay-camel",
                }
            )
            self.assertEqual(explicit[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
            self.assertEqual(explicit[0]["args"]["settlement_id"], "pay-camel")
            owned = shopify_settlement_commands(
                {
                    "order_number": 9,
                    "total_price": "185.00",
                    "fulfillment_id": "9:0:sku-serum-c",
                    "fulfillmentId": "other",
                }
            )
            self.assertEqual(owned[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
            opencart = opencart_settlement_commands(
                {
                    "order_id": 4,
                    "paid": True,
                    "currency_code": "ZAR",
                    "total": "185.00",
                    "fulfillment_id": "  ",
                    "fulfillmentId": "4:0:sku-serum-c",
                    "settlementId": "pay-camel",
                }
            )
            self.assertEqual(opencart[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
            self.assertEqual(opencart[0]["args"]["settlement_id"], "pay-camel")
            self.assertEqual(
                opencart_settlement_commands({"order_id": 4, "paid": True, "fulfillment_id": "  "}),
                [],
            )
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
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
                unnamed = settlement_for_payment(
                    {"fulfillmentId": "  ", "settlementId": "pay-camel", "amount_cents": 100}
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
                settled, settled_status = settlement_for_payment(
                    {
                        "fulfillment_id": "  ",
                        "fulfillmentId": "order-retail",
                        "settlementId": "pay-camel",
                        "amount_cents": 18500,
                        "currency": "ZAR",
                    }
                )
                self.assertEqual(settled_status, 200, settled)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-camel", text)
                again, again_status = settlement_for_payment(
                    {
                        "fulfillmentId": "order-retail",
                        "settlement_id": "pay-camel",
                        "amount_cents": 18500,
                        "currency": "ZAR",
                    }
                )
                self.assertEqual(again_status, 400)
                self.assertFalse(again["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                returned_body, returned_status = return_for_refund(
                    {"fulfillmentId": "order-retail", "return_id": "  ", "returnId": "return:camel"}
                )
                self.assertEqual(returned_status, 200, returned_body)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("return:camel", text)
                returned_again, returned_again_status = return_for_refund(
                    {"fulfillment_id": "order-retail", "returnId": "return:camel"}
                )
                self.assertEqual(returned_again_status, 400)
                self.assertFalse(returned_again["ok"])
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

    def test_an_incoming_webhook_records_the_named_sale_once(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
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
                wix = self._webhook_module("wix")
                opencart = self._webhook_module("opencart")
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
                                        "milligrams": 4000,
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
                seeded_text = ledger.read_text(encoding="utf-8")
                plain = wix.WixWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {
                            "eventType": "booking/created",
                            "data": {"id": "book-plain", "services": [{"name": "Facial"}]},
                        }
                    ).encode()
                )
                self.assertEqual(plain["status"], "processed")
                self.assertIsNone(plain["result"]["recorded"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").process_webhook(
                        json.dumps(
                            {
                                "eventType": "booking/created",
                                "data": {
                                    "id": "book-hook",
                                    "services": [{"delivery": {**delivery, "milligrams": "lots"}}],
                                },
                            }
                        ).encode()
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                created = wix.WixWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {
                            "eventType": "booking/created",
                            "data": {"id": "book-hook", "services": [{"delivery": delivery}]},
                        }
                    ).encode()
                )
                self.assertEqual(created["result"]["recorded"]["count"], 1)
                self.assertIn("book-hook:0", ledger.read_text(encoding="utf-8"))
                again = wix.WixWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {
                            "eventType": "booking/created",
                            "data": {"id": "book-hook", "services": [{"delivery": delivery}]},
                        }
                    ).encode()
                )
                self.assertEqual(again["result"]["recorded"]["count"], 0)
                booked = ledger.read_text(encoding="utf-8")
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").process_webhook(
                        json.dumps(
                            {
                                "eventType": "booking/updated",
                                "data": {
                                    "id": "book-hook",
                                    "services": [{"delivery": {**delivery, "destination": "johannesburg"}}],
                                },
                            }
                        ).encode()
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                catalog = opencart.OpenCartWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {
                            "event": "product/created",
                            "data": {"name": "Cleanser", "sku": "sku-plain"},
                        }
                    ).encode()
                )
                self.assertIsNone(catalog["result"]["recorded"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                pending = opencart.OpenCartWebhookHandler("secret").process_webhook(
                    json.dumps({"order_id": 21, "status": "pending", "products": [product]}).encode(),
                    event_type="order/created",
                )
                self.assertIsNone(pending["result"]["recorded"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                with self.assertRaises(opencart.WebhookError):
                    opencart.OpenCartWebhookHandler("secret").process_webhook(
                        json.dumps(
                            {
                                "order_id": 21,
                                "status": "shipped",
                                "products": [{**product, "milligrams": "lots"}],
                            }
                        ).encode(),
                        event_type="order/created",
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                shipped = opencart.OpenCartWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {"order_id": 21, "status": "shipped", "products": [product]}
                    ).encode(),
                    event_type="order/created",
                )
                self.assertEqual(shipped["result"]["recorded"]["count"], 1)
                self.assertIn("21:0:sku-serum-c", ledger.read_text(encoding="utf-8"))
                repeated = opencart.OpenCartWebhookHandler("secret").process_webhook(
                    json.dumps(
                        {"order_id": 21, "status": "shipped", "products": [product]}
                    ).encode(),
                    event_type="order/created",
                )
                self.assertEqual(repeated["result"]["recorded"]["count"], 0)
                sold = ledger.read_text(encoding="utf-8")
                with self.assertRaises(opencart.WebhookError):
                    opencart.OpenCartWebhookHandler("secret").process_webhook(
                        json.dumps(
                            {
                                "order_id": 21,
                                "status": "shipped",
                                "products": [{**product, "location": "johannesburg"}],
                            }
                        ).encode(),
                        event_type="order/created",
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), sold)
                self.assertIn('"location": "cape-town"', sold)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_blank_order_number_records_the_named_order_once(self) -> None:
        line = {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 2000}
        preferred = shopify_fulfillment_commands(
            {"order_number": 9, "name": "#1002", "line_items": [line]}
        )
        self.assertEqual(preferred[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        named = shopify_fulfillment_commands(
            {"order_number": "  ", "name": " #1001 ", "line_items": [line]}
        )
        self.assertEqual(named[0]["args"]["fulfillment_id"], "#1001:0:sku-serum-c")
        numbered = shopify_fulfillment_commands(
            {"order_number": "  ", "name": "  ", "id": 15, "line_items": [line]}
        )
        self.assertEqual(numbered[0]["args"]["fulfillment_id"], "15:0:sku-serum-c")
        with self.assertRaises(Exception):
            shopify_fulfillment_commands(
                {"order_number": "  ", "name": "  ", "id": "  ", "line_items": [line]}
            )
        self.assertEqual(
            shopify_fulfillment_commands(
                {"order_number": "  ", "name": "#1001", "line_items": [{"sku": "sku-serum-c"}]}
            ),
            [],
        )
        drafted = draft_order_commands(
            {"status": "completed", "order_id": "  ", "name": "#1001", "line_items": [line]}
        )
        self.assertEqual(drafted[0]["args"]["fulfillment_id"], "#1001:0:sku-serum-c")
        shipped = opencart_fulfillment_commands(
            {"order_id": "  ", "order_number": 44, "status": "shipped", "products": [line]}
        )
        self.assertEqual(shipped[0]["args"]["fulfillment_id"], "44:0:sku-serum-c")
        settled = shopify_settlement_commands(
            {
                "order_number": "  ",
                "id": 77,
                "fulfillment_id": "sale-1",
                "total_price": "10.00",
                "currency": "USD",
            }
        )
        self.assertEqual(settled[0]["args"]["settlement_id"], "pay-77")
        self.assertEqual(settled[0]["args"]["fulfillment_id"], "sale-1")
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
                unnamed = record_shopify_fulfillments(
                    {"order_number": "  ", "name": "  ", "line_items": [line]}
                )
                self.assertFalse(unnamed["ok"])
                self.assertFalse(ledger.exists())
                skipped = record_shopify_fulfillments(
                    {"order_number": "  ", "name": "#1001", "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertIsNone(skipped)
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
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                order = {"order_number": "  ", "name": "#1001", "line_items": [line]}
                recorded_sale = record_shopify_fulfillments(order)
                self.assertTrue(recorded_sale["ok"])
                self.assertEqual(recorded_sale["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("#1001:0:sku-serum-c", text)
                again = record_shopify_fulfillments(order)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                changed = record_shopify_fulfillments(
                    {
                        "order_number": "  ",
                        "name": "#1001",
                        "line_items": [{**line, "location": "johannesburg"}],
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

    def test_a_blank_paystack_reference_records_the_charge_id_once(self) -> None:
        preferred = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "currency": "NGN",
                    "reference": "salon-1",
                    "id": 99,
                    "metadata": {"fulfillment_id": "order-retail"},
                }
            }
        )
        self.assertEqual(preferred["settlement_id"], "pay-salon-1")
        fallen = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "currency": "NGN",
                    "reference": "  ",
                    "id": 99,
                    "metadata": {"fulfillment_id": "order-retail"},
                }
            }
        )
        self.assertEqual(fallen["settlement_id"], "pay-99")
        self.assertEqual(fallen["fulfillment_id"], "order-retail")
        labeled = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "reference": "  ",
                    "id": "  ",
                    "metadata": {"fulfillment_id": "order-retail"},
                }
            }
        )
        self.assertEqual(labeled["settlement_id"], "pay-order-retail")
        self.assertIsNone(
            paystack_settlement({"data": {"amount": 18500, "reference": "  ", "id": 99}})
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
                unnamed = record_paystack_settlement(
                    {"data": {"amount": 18500, "reference": "  ", "id": 99, "currency": "NGN"}}
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
                charge = {
                    "data": {
                        "amount": 18500,
                        "currency": "NGN",
                        "reference": "  ",
                        "id": 99,
                        "metadata": {"fulfillment_id": "order-retail"},
                    }
                }
                body, status = record_paystack_settlement(charge)
                self.assertEqual(status, 200)
                self.assertEqual(body["artifact"]["settlement_id"], "pay-99")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-99", text)
                again_body, again_status = record_paystack_settlement(charge)
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

    def test_a_blank_currency_records_the_named_sale_once(self) -> None:
        preferred = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "currency": "ZAR",
                    "reference": "salon-1",
                    "metadata": {"fulfillment_id": "order-retail", "currency": "NGN"},
                }
            }
        )
        self.assertEqual(preferred["currency"], "ZAR")
        fallen = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "currency": "  ",
                    "reference": "salon-1",
                    "metadata": {"fulfillment_id": "order-retail", "currency": " zar "},
                }
            }
        )
        self.assertEqual(fallen["currency"], "zar")
        self.assertEqual(fallen["fulfillment_id"], "order-retail")
        defaulted = paystack_settlement(
            {
                "data": {
                    "amount": 18500,
                    "currency": "  ",
                    "reference": "salon-1",
                    "metadata": {"fulfillment_id": "order-retail", "currency": "  "},
                }
            }
        )
        self.assertEqual(defaulted["currency"], "NGN")
        self.assertIsNone(
            paystack_settlement({"data": {"amount": 18500, "currency": "  ", "reference": "salon-1"}})
        )
        paid = shopify_settlement_commands(
            {
                "order_number": 9,
                "currency": "ZAR",
                "fulfillment_id": "sale-1",
                "total_price": "10.00",
            }
        )
        self.assertEqual(paid[0]["args"]["currency"], "ZAR")
        blank_shop = shopify_settlement_commands(
            {
                "order_number": 9,
                "currency": "  ",
                "fulfillment_id": "sale-1",
                "total_price": "10.00",
            }
        )
        self.assertEqual(blank_shop[0]["args"]["currency"], "USD")
        self.assertEqual(blank_shop[0]["args"]["fulfillment_id"], "sale-1")
        self.assertEqual(
            shopify_settlement_commands(
                {
                    "order_number": 9,
                    "currency": "  ",
                    "line_items": [{"sku": "sku-serum-c", "price": "10.00"}],
                }
            ),
            [],
        )
        labeled = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "ZAR",
                "currency": "USD",
                "fulfillment_id": "sale-1",
                "total": "10.00",
            }
        )
        self.assertEqual(labeled[0]["args"]["currency"], "ZAR")
        coded = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "  ",
                "currency": " zar ",
                "fulfillment_id": "sale-1",
                "total": "10.00",
            }
        )
        self.assertEqual(coded[0]["args"]["currency"], "zar")
        self.assertEqual(coded[0]["args"]["fulfillment_id"], "sale-1")
        opencart_default = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "  ",
                "currency": "  ",
                "fulfillment_id": "sale-1",
                "total": "10.00",
            }
        )
        self.assertEqual(opencart_default[0]["args"]["currency"], "USD")
        self.assertEqual(
            opencart_settlement_commands(
                {"order_id": 4, "status": "pending", "currency_code": "  ", "currency": "ZAR"}
            ),
            [],
        )
        held = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            blank_payment, blank_status = settlement_for_payment(
                {
                    "fulfillment_id": "order-retail",
                    "settlement_id": "pay-blank",
                    "amount_cents": 100,
                    "currency": "  ",
                }
            )
            self.assertEqual(blank_status, 200)
            self.assertEqual(blank_payment["artifact"]["currency"], "USD")
            kept, kept_status = settlement_for_payment(
                {
                    "fulfillment_id": "order-retail",
                    "settlement_id": "pay-kept",
                    "amount_cents": 100,
                    "currency": " zar ",
                }
            )
            self.assertEqual(kept_status, 200)
            self.assertEqual(kept["artifact"]["currency"], "ZAR")
        finally:
            if held is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = held
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
                unnamed = record_paystack_settlement(
                    {"data": {"amount": 18500, "currency": "  ", "reference": "salon-1"}}
                )
                self.assertIsNone(unnamed)
                self.assertFalse(ledger.exists())
                rejected, rejected_status = settlement_for_payment(
                    {
                        "fulfillment_id": "order-retail",
                        "settlement_id": "pay-bad",
                        "amount_cents": 100,
                        "currency": "US",
                    }
                )
                self.assertEqual(rejected_status, 400)
                self.assertFalse(rejected["ok"])
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
                charge = {
                    "data": {
                        "amount": 18500,
                        "currency": "  ",
                        "reference": "salon-1",
                        "metadata": {"fulfillment_id": "order-retail", "currency": "ZAR"},
                    }
                }
                body, status = record_paystack_settlement(charge)
                self.assertEqual(status, 200, body)
                self.assertEqual(body["artifact"]["currency"], "ZAR")
                self.assertEqual(body["artifact"]["fulfillment_id"], "order-retail")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-salon-1", text)
                again_body, again_status = record_paystack_settlement(charge)
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


    def test_a_blank_price_records_the_named_sale_once(self) -> None:
        preferred = shopify_settlement_commands(
            {
                "order_number": 9,
                "currency": "USD",
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "price": "10.00",
                        "quantity": 2,
                        "location": "cape-town",
                        "milligrams": 2000,
                    }
                ],
            }
        )
        self.assertEqual(preferred[0]["args"]["amount_cents"], 2000)
        self.assertEqual(preferred[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        counted = shopify_settlement_commands(
            {
                "order_number": 9,
                "currency": "USD",
                "line_items": [
                    {
                        "sku": "sku-serum-c",
                        "price": "10.00",
                        "quantity": "  ",
                        "location": "cape-town",
                        "milligrams": 2000,
                    }
                ],
            }
        )
        self.assertEqual(counted[0]["args"]["amount_cents"], 1000)
        self.assertEqual(counted[0]["args"]["fulfillment_id"], "9:0:sku-serum-c")
        self.assertEqual(
            shopify_settlement_commands(
                {
                    "order_number": 9,
                    "currency": "USD",
                    "line_items": [{"sku": "sku-serum-c", "price": "10.00", "quantity": "  "}],
                }
            ),
            [],
        )
        kept = shopify_settlement_commands(
            {
                "order_number": 9,
                "fulfillment_id": "sale-1",
                "total_price": "12.00",
                "amount": "10.00",
                "currency": "USD",
            }
        )
        self.assertEqual(kept[0]["args"]["amount_cents"], 1200)
        fallen = shopify_settlement_commands(
            {
                "order_number": 9,
                "fulfillment_id": "sale-1",
                "total_price": "  ",
                "amount": "10.00",
                "currency": "USD",
            }
        )
        self.assertEqual(fallen[0]["args"]["amount_cents"], 1000)
        self.assertEqual(fallen[0]["args"]["fulfillment_id"], "sale-1")
        with self.assertRaises(Exception):
            shopify_settlement_commands(
                {
                    "order_number": 9,
                    "fulfillment_id": "sale-1",
                    "total_price": "  ",
                    "amount": "  ",
                    "currency": "USD",
                }
            )
        priced = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "USD",
                "products": [
                    {
                        "sku": "sku-serum-c",
                        "price": "10.00",
                        "quantity": 2,
                        "location": "cape-town",
                        "milligrams": 2000,
                    }
                ],
            }
        )
        self.assertEqual(priced[0]["args"]["amount_cents"], 2000)
        totaled = opencart_settlement_commands(
            {
                "order_id": 4,
                "status": "paid",
                "currency_code": "USD",
                "products": [
                    {
                        "sku": "sku-serum-c",
                        "price": "  ",
                        "total": "10.00",
                        "quantity": 3,
                        "location": "cape-town",
                        "milligrams": 2000,
                    }
                ],
            }
        )
        self.assertEqual(totaled[0]["args"]["amount_cents"], 1000)
        self.assertEqual(totaled[0]["args"]["fulfillment_id"], "4:0:sku-serum-c")
        self.assertEqual(
            opencart_settlement_commands(
                {
                    "order_id": 4,
                    "status": "paid",
                    "products": [
                        {
                            "sku": "sku-serum-c",
                            "price": "  ",
                            "total": "  ",
                            "location": "cape-town",
                            "milligrams": 2000,
                        }
                    ],
                }
            ),
            [],
        )
        self.assertEqual(
            opencart_settlement_commands(
                {"order_id": 4, "status": "pending", "currency_code": "USD", "total": "10.00"}
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
                unnamed = record_shopify_settlement(
                    {"order_number": 9, "currency": "USD", "line_items": [{"sku": "sku-serum-c", "price": "10.00"}]}
                )
                self.assertIsNone(unnamed)
                self.assertFalse(ledger.exists())
                rejected = record_shopify_settlement(
                    {
                        "order_number": 9,
                        "fulfillment_id": "order-retail",
                        "total_price": "  ",
                        "amount": "  ",
                        "currency": "USD",
                    }
                )
                self.assertFalse(rejected["ok"])
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
                order = {
                    "order_number": 9,
                    "fulfillment_id": "order-retail",
                    "total_price": "  ",
                    "amount": "10.00",
                    "currency": "USD",
                    "settlement_id": "pay-blank-price",
                }
                recorded = record_shopify_settlement(order)
                self.assertEqual(recorded, {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn("pay-blank-price", text)
                again = record_shopify_settlement(order)
                self.assertEqual(again["ok"], False)
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

    def test_a_settlement_command_named_by_a_cent_string_records_that_sale_once(self) -> None:
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            named, named_status = respond(
                {
                    "command": "settle",
                    "args": {
                        "settlement_id": "pay-text",
                        "fulfillment_id": "order-text",
                        "amount_cents": " 18500 ",
                        "currency": "usd",
                    },
                }
            )
            self.assertEqual(named_status, 200, named)
            self.assertEqual(named["artifact"]["amount_cents"], 18500)
            self.assertEqual(named["artifact"]["currency"], "USD")
            rejected, rejected_status = respond(
                {
                    "command": "settle",
                    "args": {
                        "settlement_id": "pay-word",
                        "fulfillment_id": "order-text",
                        "amount_cents": "lots",
                        "currency": "USD",
                    },
                }
            )
            self.assertEqual(rejected_status, 400)
            self.assertFalse(rejected["ok"])
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
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
                                        "fulfillment_id": "order-text",
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
                seeded_text = ledger.read_text(encoding="utf-8")
                missing, missing_status = respond(
                    {
                        "command": "settle",
                        "args": {
                            "settlement_id": "pay-missing",
                            "fulfillment_id": "order-text",
                            "currency": "USD",
                        },
                    }
                )
                self.assertEqual(missing_status, 400)
                self.assertFalse(missing["ok"])
                word, word_status = respond(
                    {
                        "command": "settle",
                        "args": {
                            "settlement_id": "pay-word",
                            "fulfillment_id": "order-text",
                            "amount_cents": "lots",
                            "currency": "USD",
                        },
                    }
                )
                self.assertEqual(word_status, 400)
                self.assertFalse(word["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                paid, paid_status = respond(
                    {
                        "command": "settle",
                        "args": {
                            "settlement_id": "pay-text",
                            "fulfillment_id": "order-text",
                            "amount_cents": " 18500 ",
                            "currency": "usd",
                        },
                    }
                )
                self.assertEqual(paid_status, 200, paid)
                self.assertEqual(paid["artifact"]["amount_cents"], 18500)
                recorded = ledger.read_text(encoding="utf-8")
                self.assertIn('"amount_cents": 18500', recorded)
                self.assertNotIn('"amount_cents": "', recorded)
                self.assertIn("pay-text", recorded)
                again, again_status = respond(
                    {
                        "command": "settle",
                        "args": {
                            "settlement_id": "pay-text",
                            "fulfillment_id": "order-text",
                            "amount_cents": "18500",
                            "currency": "USD",
                        },
                    }
                )
                self.assertEqual(again_status, 400)
                self.assertFalse(again["ok"])
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

    def test_a_payment_named_by_a_cent_string_settles_that_sale_once(self) -> None:
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            self.assertIsNone(settlement_for_payment({"amount_cents": " 18500 ", "currency": "USD"}))
            named, named_status = settlement_for_payment(
                {
                    "settlement_id": "pay-text",
                    "fulfillment_id": "order-text",
                    "amount_cents": " 18500 ",
                    "currency": "usd",
                }
            )
            self.assertEqual(named_status, 200, named)
            self.assertEqual(named["artifact"]["amount_cents"], 18500)
            self.assertEqual(named["artifact"]["currency"], "USD")
            major, major_status = settlement_for_payment(
                {
                    "settlement_id": "pay-major",
                    "fulfillment_id": "order-text",
                    "amount": " 185.00 ",
                    "currency": "USD",
                }
            )
            self.assertEqual(major_status, 200, major)
            self.assertEqual(major["artifact"]["amount_cents"], 18500)
            fallen, fallen_status = settlement_for_payment(
                {
                    "settlement_id": "pay-fall",
                    "fulfillment_id": "order-text",
                    "amount_cents": "lots",
                    "amount": "10.00",
                    "currency": "USD",
                }
            )
            self.assertEqual(fallen_status, 200, fallen)
            self.assertEqual(fallen["artifact"]["amount_cents"], 1000)
            zero, zero_status = settlement_for_payment(
                {
                    "settlement_id": "pay-zero",
                    "fulfillment_id": "order-text",
                    "amount_cents": "0",
                    "amount": "10.00",
                    "currency": "USD",
                }
            )
            self.assertEqual(zero_status, 400)
            self.assertFalse(zero["ok"])
            rejected, rejected_status = settlement_for_payment(
                {
                    "settlement_id": "pay-word",
                    "fulfillment_id": "order-text",
                    "amount": "lots",
                    "currency": "USD",
                }
            )
            self.assertEqual(rejected_status, 400)
            self.assertFalse(rejected["ok"])
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
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
                                        "fulfillment_id": "order-text",
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
                seeded_text = ledger.read_text(encoding="utf-8")
                self.assertIsNone(
                    settlement_for_payment({"amount_cents": "18500", "settlement_id": "pay-unnamed"})
                )
                missing, missing_status = settlement_for_payment(
                    {
                        "settlement_id": "pay-missing",
                        "fulfillment_id": "order-text",
                        "currency": "USD",
                    }
                )
                self.assertEqual(missing_status, 400)
                self.assertFalse(missing["ok"])
                word, word_status = settlement_for_payment(
                    {
                        "settlement_id": "pay-word",
                        "fulfillment_id": "order-text",
                        "amount": "lots",
                        "currency": "USD",
                    }
                )
                self.assertEqual(word_status, 400)
                self.assertFalse(word["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                paid, paid_status = settlement_for_payment(
                    {
                        "settlement_id": "pay-text",
                        "fulfillment_id": "order-text",
                        "amount_cents": " 18500 ",
                        "currency": "usd",
                    }
                )
                self.assertEqual(paid_status, 200, paid)
                self.assertEqual(paid["artifact"]["amount_cents"], 18500)
                recorded = ledger.read_text(encoding="utf-8")
                self.assertIn('"amount_cents": 18500', recorded)
                self.assertNotIn('"amount_cents": "', recorded)
                self.assertIn("pay-text", recorded)
                again, again_status = settlement_for_payment(
                    {
                        "settlement_id": "pay-text",
                        "fulfillment_id": "order-text",
                        "amount_cents": "18500",
                        "currency": "USD",
                    }
                )
                self.assertEqual(again_status, 400)
                self.assertFalse(again["ok"])
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

    def test_a_payment_without_a_settlement_id_settles_that_sale_once(self) -> None:
        previous = os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
        try:
            self.assertIsNone(settlement_for_payment({"amount": "185.00", "currency": "USD"}))
            named, named_status = settlement_for_payment(
                {
                    "fulfillment_id": "order-text",
                    "amount": " 185.00 ",
                    "currency": "usd",
                }
            )
            self.assertEqual(named_status, 200, named)
            self.assertEqual(named["artifact"]["settlement_id"], "pay-order-text")
            self.assertEqual(named["artifact"]["amount_cents"], 18500)
            preferred, preferred_status = settlement_for_payment(
                {
                    "settlement_id": "pay-stated",
                    "fulfillment_id": "order-text",
                    "amount": "10.00",
                    "currency": "USD",
                }
            )
            self.assertEqual(preferred_status, 200, preferred)
            self.assertEqual(preferred["artifact"]["settlement_id"], "pay-stated")
            blank, blank_status = settlement_for_payment(
                {
                    "settlement_id": "  ",
                    "fulfillmentId": "order-text",
                    "amount_cents": "18500",
                    "currency": "USD",
                }
            )
            self.assertEqual(blank_status, 200, blank)
            self.assertEqual(blank["artifact"]["settlement_id"], "pay-order-text")
            rejected, rejected_status = settlement_for_payment(
                {
                    "fulfillment_id": "order-text",
                    "amount": "lots",
                    "currency": "USD",
                }
            )
            self.assertEqual(rejected_status, 400)
            self.assertFalse(rejected["ok"])
        finally:
            if previous is not None:
                os.environ["SKINTWIN_CHAIN_LEDGER"] = previous
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
                                        "fulfillment_id": "order-text",
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
                seeded_text = ledger.read_text(encoding="utf-8")
                word, word_status = settlement_for_payment(
                    {
                        "fulfillment_id": "order-text",
                        "amount": "lots",
                        "currency": "USD",
                    }
                )
                self.assertEqual(word_status, 400)
                self.assertFalse(word["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                paid, paid_status = settlement_for_payment(
                    {
                        "fulfillment_id": "order-text",
                        "amount": "185.00",
                        "currency": "usd",
                    }
                )
                self.assertEqual(paid_status, 200, paid)
                self.assertEqual(paid["artifact"]["settlement_id"], "pay-order-text")
                recorded = ledger.read_text(encoding="utf-8")
                self.assertIn('"amount_cents": 18500', recorded)
                self.assertIn("pay-order-text", recorded)
                again, again_status = settlement_for_payment(
                    {
                        "fulfillment_id": "order-text",
                        "amount": "185.00",
                        "currency": "USD",
                    }
                )
                self.assertEqual(again_status, 400)
                self.assertFalse(again["ok"])
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

    def test_a_platform_sync_records_the_named_sale_once(self) -> None:
        self.assertIsNone(record_synced_sale("shopify", "nope"))
        self.assertIsNone(record_synced_sale("other", {"order_number": 9}))
        sale = {
            "order_number": 9,
            "fulfillment_status": "fulfilled",
            "line_items": [
                {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 2000}
            ],
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

            class _Sync:
                def __init__(self, rows):
                    self.rows = rows
                    self.mapped = []

                def sync_appointments(self, since=None):
                    return self.rows

                def map_order_to_unified(self, raw):
                    self.mapped.append(raw["order_number"])
                    return {"order_number": raw["order_number"]}

            try:
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationGateway = importlib.import_module("integrations.gateway").IntegrationGateway
                self.assertIsNone(
                    record_synced_sale(
                        "shopify",
                        {"order_number": 9, "line_items": [{"sku": "sku-serum-c"}]},
                    )
                )
                self.assertIsNone(record_synced_sale("wix", {"id": "book-1"}))
                self.assertIsNone(
                    record_synced_sale(
                        "opencart",
                        {"order_id": 9, "products": [{"sku": "sku-serum-c"}]},
                    )
                )
                rejected = record_synced_sale(
                    "shopify",
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "location": "cape-town",
                                "milligrams": "lots",
                            }
                        ],
                    },
                )
                self.assertFalse(rejected["ok"])
                self.assertFalse(ledger.exists())
                gateway = IntegrationGateway()
                skipped = _Sync(
                    [
                        {"order_number": 8, "line_items": [{"sku": "sku-serum-c"}]},
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "cape-town",
                                    "milligrams": "lots",
                                }
                            ],
                        },
                    ]
                )
                gateway.register_connector("shopify", skipped)
                synced = gateway.sync_appointments(["shopify"])
                self.assertEqual(skipped.mapped, [8])
                self.assertEqual(len(synced["shopify"]), 1)
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                recorded = record_synced_sale("shopify", sale)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"location": "cape-town"', text)
                self.assertIn('"milligrams": 2000', text)
                again = record_synced_sale("shopify", sale)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                changed = record_synced_sale(
                    "shopify",
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "location": "johannesburg",
                                "milligrams": 2000,
                            }
                        ],
                    },
                )
                self.assertFalse(changed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                repeat = _Sync([sale])
                gateway.register_connector("shopify", repeat)
                repeated = gateway.sync_appointments(["shopify"])
                self.assertEqual(repeat.mapped, [9])
                self.assertEqual(len(repeated["shopify"]), 1)
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

    def test_a_platform_sync_records_the_named_catalog_once(self) -> None:
        self.assertIsNone(record_synced_catalog("shopify", "nope"))
        self.assertIsNone(record_synced_catalog("wix", {"title": "Cleanser", "tags": "formula:cleanser"}))
        product = {
            "title": "Gentle cleanser",
            "tags": "formula:cleanser",
            "variants": [{"sku": "sku-cleanser"}],
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

            class _Products:
                def __init__(self, rows):
                    self.rows = rows
                    self.mapped = []

                def get_products(self):
                    return self.rows

                def map_product_to_unified(self, raw):
                    self.mapped.append(raw.get("title") or "")
                    return {"title": raw.get("title")}

            try:
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationGateway = importlib.import_module("integrations.gateway").IntegrationGateway
                self.assertIsNone(
                    record_synced_catalog(
                        "shopify",
                        {"title": "Cleanser", "tags": "retail", "variants": [{"sku": "sku-a"}]},
                    )
                )
                self.assertIsNone(
                    record_synced_catalog(
                        "opencart",
                        {"name": "Cleanser", "sku": "sku-a", "tags": "retail"},
                    )
                )
                rejected = record_synced_catalog(
                    "shopify",
                    {"tags": "formula:cleanser", "variants": [{"sku": "sku-cleanser"}]},
                )
                self.assertFalse(rejected["ok"])
                self.assertFalse(ledger.exists())
                gateway = IntegrationGateway()
                skipped = _Products(
                    [
                        {"title": "Shelf", "tags": "retail", "variants": [{"sku": "sku-a"}]},
                        {"tags": "formula:cleanser", "variants": [{"sku": "sku-cleanser"}]},
                    ]
                )
                gateway.register_connector("shopify", skipped)
                synced = gateway.sync_products(["shopify"])
                self.assertEqual(skipped.mapped, ["Shelf"])
                self.assertEqual(len(synced["shopify"]), 1)
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
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
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                recorded = record_synced_catalog("shopify", product)
                self.assertTrue(recorded["ok"])
                self.assertEqual(recorded["count"], 1)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-cleanser"', text)
                self.assertIn('"formula_id": "cleanser"', text)
                again = record_synced_catalog("shopify", product)
                self.assertTrue(again["ok"])
                self.assertEqual(again["count"], 0)
                same = record_synced_catalog(
                    "opencart",
                    {"name": "Gentle cleanser", "sku": "sku-cleanser", "tags": "formula:cleanser"},
                )
                self.assertTrue(same["ok"])
                self.assertEqual(same["count"], 0)
                changed = record_synced_catalog("shopify", {**product, "formulaId": "serum-c"})
                self.assertFalse(changed["ok"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                repeat = _Products([product])
                gateway.register_connector("shopify", repeat)
                repeated = gateway.sync_products(["shopify"])
                self.assertEqual(repeat.mapped, ["Gentle cleanser"])
                self.assertEqual(len(repeated["shopify"]), 1)
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


    def test_a_created_draft_records_the_named_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        draft = {"status": "completed", "id": 3, "order_id": 9, "line_items": [line]}
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationGateway = importlib.import_module("integrations.gateway").IntegrationGateway
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Drafts(ShopifyB2BConnector):
                    def __init__(self):
                        self.created = []

                    def create_draft_order(self, data):
                        self.created.append(data.get("status"))
                        return {"id": data.get("id"), "status": data.get("status")}

                gateway = IntegrationGateway()
                connector = _Drafts()
                gateway.register_connector("shopify", connector)
                opened = gateway.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [line]}
                )
                self.assertEqual(opened["status"], "open")
                self.assertEqual(connector.created, ["open"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    gateway.create_draft_order(
                        {
                            "status": "completed",
                            "id": 3,
                            "order_id": 9,
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "properties": [
                                        {"name": "location", "value": "cape-town"},
                                        {"name": "milligrams", "value": "lots"},
                                    ],
                                }
                            ],
                        }
                    )
                self.assertEqual(connector.created, ["open"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = gateway.create_draft_order(draft)
                self.assertEqual(created["id"], 3)
                self.assertEqual(connector.created, ["open", "completed"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                again = gateway.create_draft_order(draft)
                self.assertEqual(again["status"], "completed")
                self.assertEqual(connector.created, ["open", "completed", "completed"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    gateway.create_draft_order(
                        {
                            "status": "completed",
                            "id": 3,
                            "order_id": 9,
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "johannesburg",
                                    "milligrams": 2000,
                                }
                            ],
                        }
                    )
                self.assertEqual(connector.created, ["open", "completed", "completed"])
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


    def test_a_created_shopify_product_records_the_named_catalog_once(self) -> None:
        product = {
            "title": "Gentle cleanser",
            "tags": "formula:cleanser",
            "variants": [{"sku": "sku-cleanser"}],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Catalog(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.ENDPOINTS = {
                            "products": "products.json",
                            "product": "products/{id}.json",
                        }

                    def _saved(self, data):
                        title = data["product"].get("title")
                        echoes = {
                            "Echo cleanser": {
                                "title": "Echo cleanser",
                                "tags": "formula:cleanser",
                                "variants": [{"sku": "sku-echo"}],
                            },
                            "Missing formula": {
                                "title": "Missing formula",
                                "tags": "formula:absent",
                                "variants": [{"sku": "sku-missing"}],
                            },
                            "Blank formula": {
                                "title": "Blank formula",
                                "tags": "formula:",
                                "variants": [{"sku": "sku-blank"}],
                            },
                            "Serum echo": {
                                "title": "Serum echo",
                                "tags": "formula:serum-c",
                                "variants": [{"sku": "sku-echo"}],
                            },
                        }
                        if title in echoes:
                            return {"product": echoes[title]}
                        return {"product": data["product"]}

                    def post(self, endpoint, data):
                        self.sent.append(("post", data["product"].get("title")))
                        return self._saved(data)

                    def put(self, endpoint, data):
                        self.sent.append(("put", data["product"].get("title")))
                        return self._saved(data)

                connector = _Catalog()
                shelf = connector.create_product(
                    {"title": "Shelf", "tags": "retail", "variants": [{"sku": "sku-a"}]}
                )
                self.assertEqual(shelf["title"], "Shelf")
                self.assertEqual(connector.sent, [("post", "Shelf")])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_product(
                        {"tags": "formula:cleanser", "variants": [{"sku": "sku-cleanser"}]}
                    )
                self.assertEqual(connector.sent, [("post", "Shelf")])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
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
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_product(product)
                self.assertEqual(created["title"], "Gentle cleanser")
                self.assertEqual(connector.sent, [("post", "Shelf"), ("post", "Gentle cleanser")])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-cleanser"', text)
                self.assertIn('"formula_id": "cleanser"', text)
                updated = connector.update_product(4, product)
                self.assertEqual(updated["title"], "Gentle cleanser")
                self.assertEqual(
                    connector.sent,
                    [("post", "Shelf"), ("post", "Gentle cleanser"), ("put", "Gentle cleanser")],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.update_product(4, {**product, "formulaId": "serum-c"})
                self.assertEqual(
                    connector.sent,
                    [("post", "Shelf"), ("post", "Gentle cleanser"), ("put", "Gentle cleanser")],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                echo = {"title": "Echo cleanser", "tags": "retail", "variants": [{"sku": "sku-echo"}]}
                echoed = connector.create_product(echo)
                self.assertEqual(echoed["tags"], "formula:cleanser")
                self.assertIn(("post", "Echo cleanser"), connector.sent)
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-echo"', echoed_text)
                self.assertIn('"formula_id": "cleanser"', echoed_text)
                self.assertNotIn("serum-c", echoed_text)
                again = connector.create_product(echo)
                self.assertEqual(again["tags"], "formula:cleanser")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_missing = list(connector.sent)
                with self.assertRaises(IntegrationError):
                    connector.update_product(
                        8,
                        {"title": "Missing formula", "tags": "retail", "variants": [{"sku": "sku-missing"}]},
                    )
                self.assertEqual(connector.sent, before_missing + [("put", "Missing formula")])
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("sku-missing", ledger.read_text(encoding="utf-8"))
                blanked = connector.update_product(
                    9,
                    {"title": "Blank formula", "tags": "retail", "variants": [{"sku": "sku-blank"}]},
                )
                self.assertEqual(blanked["tags"], "formula:")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("sku-blank", ledger.read_text(encoding="utf-8"))
                with self.assertRaises(IntegrationError):
                    connector.update_product(
                        10,
                        {"title": "Serum echo", "tags": "retail", "variants": [{"sku": "sku-echo"}]},
                    )
                self.assertIn(("put", "Serum echo"), connector.sent)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("serum-c", ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub


    def test_a_saved_shopify_product_catalogs_the_request_skus_when_it_omits_variants(self) -> None:
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Catalog(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.echoes = {}
                        self.ENDPOINTS = {
                            "products": "products.json",
                            "product": "products/{id}.json",
                        }

                    def _saved(self, data):
                        title = data["product"].get("title")
                        if title in self.echoes:
                            return {"product": self.echoes[title]}
                        return {"product": data["product"]}

                    def post(self, endpoint, data):
                        self.sent.append(("post", data["product"].get("title")))
                        return self._saved(data)

                    def put(self, endpoint, data):
                        self.sent.append(("put", data["product"].get("title")))
                        return self._saved(data)

                connector = _Catalog()
                with self.assertRaises(IntegrationError):
                    connector.create_product(
                        {"title": "Early", "tags": "formula:nope", "variants": [{"sku": "sku-early"}]}
                    )
                self.assertEqual(connector.sent, [])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
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
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 4000]],
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                seeded_text = ledger.read_text(encoding="utf-8")
                connector.echoes["Plain"] = {"title": "Plain", "tags": "retail"}
                plain = connector.create_product(
                    {"title": "Plain", "variants": [{"sku": "sku-plain"}, {"sku": "sku-plain-50"}]}
                )
                self.assertEqual(plain["tags"], "retail")
                self.assertNotIn("variants", plain)
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                self.assertNotIn("sku-plain", seeded_text)
                connector.echoes["Bare cleanser"] = {"title": "Bare cleanser", "tags": "formula:cleanser"}
                created = connector.create_product(
                    {
                        "title": "Bare cleanser",
                        "variants": [{"sku": "sku-bare"}, {"sku": " "}, {"sku": "sku-bare-50"}],
                    }
                )
                self.assertEqual(created["title"], "Bare cleanser")
                self.assertNotIn("variants", created)
                self.assertIn(("post", "Bare cleanser"), connector.sent)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-bare"', text)
                self.assertIn('"sku_id": "sku-bare-50"', text)
                self.assertIn('"formula_id": "cleanser"', text)
                self.assertNotIn('"sku_id": "Bare cleanser"', text)
                again = connector.create_product(
                    {"title": "Bare cleanser", "variants": [{"sku": "sku-bare"}, {"sku": "sku-bare-50"}]}
                )
                self.assertEqual(again["title"], "Bare cleanser")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.echoes["Kept"] = {
                    "title": "Kept",
                    "tags": "formula:cleanser",
                    "variants": [{"sku": "sku-kept"}],
                }
                kept = connector.create_product({"title": "Kept", "variants": [{"sku": "sku-request"}]})
                self.assertEqual(kept["variants"], [{"sku": "sku-kept"}])
                kept_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-kept"', kept_text)
                self.assertNotIn("sku-request", kept_text)
                connector.echoes["Shelf sku"] = {
                    "title": "Shelf sku",
                    "tags": "formula:cleanser",
                    "sku": "sku-shelf",
                }
                shelf = connector.create_product(
                    {"title": "Shelf sku", "variants": [{"sku": "sku-request-shelf"}]}
                )
                self.assertEqual(shelf.get("sku"), "sku-shelf")
                shelf_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-shelf"', shelf_text)
                self.assertNotIn("sku-request-shelf", shelf_text)
                connector.echoes["Title cleanser"] = {"title": "Title cleanser", "tags": "formula:cleanser"}
                titled = connector.create_product({"title": "Title cleanser"})
                self.assertEqual(titled["title"], "Title cleanser")
                titled_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "Title cleanser"', titled_text)
                connector.echoes["Product sku"] = {"title": "Product sku", "tags": "formula:cleanser"}
                product_sku = connector.create_product(
                    {"title": "Product sku", "sku": "sku-product", "tags": "retail"}
                )
                self.assertEqual(product_sku.get("tags"), "formula:cleanser")
                self.assertNotIn("sku", product_sku)
                product_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(product_text.count('"sku_id": "sku-product"'), 1)
                self.assertNotIn('"sku_id": "Product sku"', product_text)
                again_product = connector.create_product(
                    {"title": "Product sku", "sku": "sku-product", "tags": "retail"}
                )
                self.assertEqual(again_product.get("title"), "Product sku")
                self.assertEqual(ledger.read_text(encoding="utf-8"), product_text)
                connector.echoes["Formula sku"] = {"title": "Formula sku", "tags": "formula:cleanser"}
                formula_sku = connector.create_product(
                    {
                        "title": "Formula sku",
                        "sku": "sku-formula",
                        "tags": "formula:cleanser",
                    }
                )
                formula_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(formula_text.count('"sku_id": "sku-formula"'), 1)
                self.assertNotIn('"sku_id": "Formula sku"', formula_text)
                connector.echoes["Camel sku"] = {
                    "title": "Camel sku",
                    "tags": "formula:cleanser",
                    "variants": [{"sku": " "}],
                }
                camel = connector.create_product({"title": "Camel sku", "skuId": "sku-camel"})
                self.assertEqual(camel["variants"], [{"sku": " "}])
                camel_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-camel"', camel_text)
                self.assertNotIn('"sku_id": "Camel sku"', camel_text)
                connector.echoes["Retail product"] = {"title": "Retail product", "tags": "retail"}
                retail_product = connector.create_product(
                    {"title": "Retail product", "sku": "sku-retail-product"}
                )
                self.assertEqual(retail_product.get("tags"), "retail")
                self.assertNotIn("sku-retail-product", ledger.read_text(encoding="utf-8"))
                connector.echoes["Named cleanser"] = {"title": "Named cleanser", "tags": "formula:cleanser"}
                named = connector.create_product(
                    {
                        "title": "Named cleanser",
                        "tags": "formula:cleanser",
                        "variants": [{"sku": "sku-named"}],
                    }
                )
                self.assertNotIn("variants", named)
                named_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(named_text.count('"sku_id": "sku-named"'), 1)
                self.assertNotIn('"sku_id": "Named cleanser"', named_text)
                named_again = connector.create_product(
                    {
                        "title": "Named cleanser",
                        "tags": "formula:cleanser",
                        "variants": [{"sku": "sku-named"}],
                    }
                )
                self.assertEqual(named_again["title"], "Named cleanser")
                self.assertEqual(ledger.read_text(encoding="utf-8"), named_text)
                connector.echoes["Blank variants"] = {
                    "title": "Blank variants",
                    "tags": "formula:cleanser",
                    "variants": [{"sku": " "}],
                }
                blanked = connector.create_product(
                    {"title": "Blank variants", "variants": [{"sku": "sku-blank-row"}]}
                )
                self.assertEqual(blanked["variants"], [{"sku": " "}])
                blank_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-blank-row"', blank_text)
                self.assertNotIn('"sku_id": "Blank variants"', blank_text)
                connector.echoes["Retail echo"] = {"title": "Retail echo", "tags": "retail"}
                retail = connector.create_product(
                    {
                        "title": "Retail echo",
                        "tags": "formula:cleanser",
                        "variants": [{"sku": "sku-retail"}],
                    }
                )
                self.assertEqual(retail["tags"], "retail")
                retail_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(retail_text.count('"sku_id": "sku-retail"'), 1)
                self.assertNotIn('"sku_id": "Retail echo"', retail_text)
                connector.echoes["Update cleanser"] = {"title": "Update cleanser", "tags": "formula:cleanser"}
                updated = connector.update_product(
                    4, {"title": "Update cleanser", "variants": [{"sku": "sku-update"}]}
                )
                self.assertNotIn("variants", updated)
                self.assertIn(("put", "Update cleanser"), connector.sent)
                updated_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-update"', updated_text)
                self.assertNotIn('"sku_id": "Update cleanser"', updated_text)
                connector.echoes["Missing formula"] = {"title": "Missing formula", "tags": "formula:absent"}
                before_missing = list(connector.sent)
                with self.assertRaises(IntegrationError) as missing:
                    connector.create_product(
                        {"title": "Missing formula", "variants": [{"sku": "sku-missing"}]}
                    )
                self.assertIn("formula", str(missing.exception))
                self.assertEqual(connector.sent, before_missing + [("post", "Missing formula")])
                self.assertEqual(ledger.read_text(encoding="utf-8"), updated_text)
                self.assertNotIn("sku-missing", ledger.read_text(encoding="utf-8"))
                connector.echoes["Switch cleanser"] = {"title": "Switch cleanser", "tags": "formula:serum-c"}
                before_switch = list(connector.sent)
                with self.assertRaises(IntegrationError) as switched:
                    connector.update_product(
                        8, {"title": "Switch cleanser", "variants": [{"sku": "sku-bare"}]}
                    )
                self.assertIn("already exists", str(switched.exception))
                self.assertEqual(connector.sent, before_switch + [("put", "Switch cleanser")])
                self.assertEqual(ledger.read_text(encoding="utf-8"), updated_text)
                self.assertEqual(updated_text.count('"sku_id": "sku-bare"'), 1)
                connector.echoes["Variant formula"] = {
                    "title": "Variant formula",
                    "variants": [{"metafields": [{"key": "formula_id", "value": " cleanser "}]}],
                }
                variant = connector.create_product(
                    {"title": "Variant formula", "variants": [{"sku": "sku-variant-formula"}]}
                )
                self.assertNotIn("sku", variant["variants"][0])
                variant_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(variant_text.count('"sku_id": "sku-variant-formula"'), 1)
                self.assertNotIn('"sku_id": "Variant formula"', variant_text)
                variant_again = connector.create_product(
                    {"title": "Variant formula", "variants": [{"sku": "sku-variant-formula"}]}
                )
                self.assertEqual(variant_again["title"], "Variant formula")
                self.assertEqual(ledger.read_text(encoding="utf-8"), variant_text)
                connector.echoes["Kept variant"] = {
                    "title": "Kept variant",
                    "variants": [
                        {
                            "sku": "sku-kept-variant",
                            "metafields": [{"key": "formula_id", "value": "cleanser"}],
                        }
                    ],
                }
                kept_variant = connector.create_product(
                    {"title": "Kept variant", "variants": [{"sku": "sku-request-variant"}]}
                )
                self.assertEqual(kept_variant["variants"][0]["sku"], "sku-kept-variant")
                kept_variant_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-kept-variant"', kept_variant_text)
                self.assertNotIn("sku-request-variant", kept_variant_text)
                connector.echoes["Two formulas"] = {
                    "title": "Two formulas",
                    "variants": [
                        {"metafields": [{"key": "formula_id", "value": "cleanser"}]},
                        {"metafields": [{"key": "formula_id", "value": "serum-c"}]},
                    ],
                }
                connector.create_product(
                    {
                        "title": "Two formulas",
                        "variants": [{"sku": "sku-two-cleanser"}, {"sku": "sku-two-serum"}],
                    }
                )
                two_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(two_text.count('"sku_id": "sku-two-cleanser"'), 1)
                self.assertEqual(two_text.count('"sku_id": "sku-two-serum"'), 1)
                self.assertNotIn('"sku_id": "Two formulas"', two_text)
                connector.create_product(
                    {
                        "title": "Two formulas",
                        "variants": [{"sku": "sku-two-cleanser"}, {"sku": "sku-two-serum"}],
                    }
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), two_text)
                connector.echoes["Shifted"] = {
                    "title": "Shifted",
                    "variants": [
                        {"metafields": [{"key": "formula_id", "value": "cleanser"}]},
                        {
                            "sku": "sku-shift-kept",
                            "metafields": [{"key": "formula_id", "value": "serum-c"}],
                        },
                    ],
                }
                connector.create_product(
                    {"title": "Shifted", "variants": [{"sku": " "}, {"sku": "sku-shift-request"}]}
                )
                shifted_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"sku_id": "sku-shift-kept"', shifted_text)
                self.assertNotIn("sku-shift-request", shifted_text)
                self.assertNotIn('"sku_id": "Shifted"', shifted_text)
                connector.echoes["Only variant"] = {
                    "title": "Only variant",
                    "variants": [
                        {"sku": " ", "metafields": [{"key": "formula_id", "value": "cleanser"}]}
                    ],
                }
                connector.create_product({"title": "Only variant", "sku": "sku-only-variant"})
                only_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(only_text.count('"sku_id": "sku-only-variant"'), 1)
                self.assertNotIn('"sku_id": "Only variant"', only_text)
                connector.echoes["Split formula"] = {
                    "title": "Split formula",
                    "variants": [{"metafields": [{"key": "formula_id", "value": "serum-c"}]}],
                }
                connector.create_product(
                    {
                        "title": "Split formula",
                        "variants": [{"sku": "sku-split", "formula_id": "cleanser"}],
                    }
                )
                split_lines = [
                    json.loads(line)
                    for line in ledger.read_text(encoding="utf-8").splitlines()
                    if '"sku_id": "sku-split"' in line
                ]
                self.assertEqual(len(split_lines), 1)
                self.assertEqual(split_lines[0]["args"]["formula_id"], "cleanser")
                connector.echoes["Update variant"] = {
                    "title": "Update variant",
                    "variants": [{"metafields": [{"key": "formulaId", "value": "cleanser"}]}],
                }
                connector.update_product(
                    11, {"title": "Update variant", "variants": [{"sku": "sku-update-variant"}]}
                )
                self.assertIn(("put", "Update variant"), connector.sent)
                update_variant_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(update_variant_text.count('"sku_id": "sku-update-variant"'), 1)
                self.assertNotIn('"sku_id": "Update variant"', update_variant_text)
                connector.echoes["Plain variant"] = {
                    "title": "Plain variant",
                    "variants": [{"title": "50 ml"}],
                }
                connector.create_product(
                    {"title": "Plain variant", "variants": [{"sku": "sku-plain-variant"}]}
                )
                self.assertNotIn("sku-plain-variant", ledger.read_text(encoding="utf-8"))
                connector.echoes["Dropped formula"] = {"title": "Dropped formula", "variants": [{}]}
                connector.create_product(
                    {
                        "title": "Dropped formula",
                        "variants": [
                            {
                                "sku": "sku-dropped",
                                "metafields": [{"key": "formula_id", "value": "cleanser"}],
                            }
                        ],
                    }
                )
                self.assertEqual(ledger.read_text(encoding="utf-8").count('"sku_id": "sku-dropped"'), 1)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_created_shopify_order_records_the_named_sale_once(self) -> None:
        sale = {
            "order_number": 9,
            "fulfillment_status": "fulfilled",
            "line_items": [
                {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 2000}
            ],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Orders(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.ENDPOINTS = {
                            "orders": "orders.json",
                            "order": "orders/{id}.json",
                        }

                    def _saved(self, data):
                        order = data["order"]
                        number = order.get("order_number")
                        echoes = {
                            11: {
                                "order_number": 11,
                                "fulfillment_status": "fulfilled",
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                    }
                                ],
                            },
                            12: {
                                "order_number": 12,
                                "fulfillment_status": "fulfilled",
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": "lots",
                                    }
                                ],
                            },
                            13: {
                                "order_number": 13,
                                "line_items": [{"sku": "sku-serum-c"}],
                            },
                            14: {
                                "order_number": 11,
                                "fulfillment_status": "fulfilled",
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "location": "johannesburg",
                                        "milligrams": 2000,
                                    }
                                ],
                            },
                        }
                        if number in echoes:
                            return {"order": echoes[number]}
                        return {"order": order}

                    def post(self, endpoint, data):
                        order = data["order"]
                        self.sent.append(("post", order.get("order_number")))
                        return self._saved(data)

                    def put(self, endpoint, data):
                        order = data["order"]
                        self.sent.append(("put", order.get("order_number")))
                        return self._saved(data)

                connector = _Orders()
                opened = connector.create_order(
                    {"order_number": 8, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(opened["order_number"], 8)
                self.assertEqual(connector.sent, [("post", 8)])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_order(
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "cape-town",
                                    "milligrams": "lots",
                                }
                            ],
                        }
                    )
                self.assertEqual(connector.sent, [("post", 8)])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_order(sale)
                self.assertEqual(created["order_number"], 9)
                self.assertEqual(connector.sent, [("post", 8), ("post", 9)])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                updated = connector.update_order(9, sale)
                self.assertEqual(updated["order_number"], 9)
                self.assertEqual(connector.sent, [("post", 8), ("post", 9), ("put", 9)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.update_order(
                        9,
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "johannesburg",
                                    "milligrams": 2000,
                                }
                            ],
                        },
                    )
                self.assertEqual(connector.sent, [("post", 8), ("post", 9), ("put", 9)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                echo = {"order_number": 11, "line_items": [{"sku": "sku-serum-c"}]}
                echoed = connector.create_order(echo)
                self.assertEqual(echoed["fulfillment_status"], "fulfilled")
                self.assertIn(("post", 11), connector.sent)
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "11:0:sku-serum-c"', echoed_text)
                self.assertIn('"location": "cape-town"', echoed_text)
                self.assertNotIn("johannesburg", echoed_text)
                again = connector.create_order(echo)
                self.assertEqual(again["fulfillment_status"], "fulfilled")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_bad = list(connector.sent)
                with self.assertRaises(IntegrationError):
                    connector.update_order(12, {"order_number": 12, "line_items": [{"sku": "sku-serum-c"}]})
                self.assertEqual(connector.sent, before_bad + [("put", 12)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "12:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                opened = connector.update_order(13, {"order_number": 13, "line_items": [{"sku": "sku-serum-c"}]})
                self.assertIsNone(opened.get("fulfillment_status"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "13:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                with self.assertRaises(IntegrationError):
                    connector.update_order(11, {"order_number": 14, "line_items": [{"sku": "sku-serum-c"}]})
                self.assertIn(("put", 14), connector.sent)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub


    def test_a_saved_shopify_fulfillment_draws_the_request_lines_when_it_omits_them(self) -> None:
        line = {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 2000}
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Orders(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.echoes = {}
                        self.ENDPOINTS = {"orders": "orders.json", "order": "orders/{id}.json"}

                    def _saved(self, data):
                        number = data["order"].get("order_number")
                        if number in self.echoes:
                            return {"order": self.echoes[number]}
                        return {"order": data["order"]}

                    def post(self, endpoint, data):
                        self.sent.append(("post", data["order"].get("order_number")))
                        return self._saved(data)

                    def put(self, endpoint, data):
                        self.sent.append(("put", data["order"].get("order_number")))
                        return self._saved(data)

                connector = _Orders()
                with self.assertRaises(IntegrationError):
                    connector.create_order(
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "line_items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.sent, [])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 20000,
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
                                        "units": 4,
                                        "allocations": [["glycerin", "lot-glycerin", 20000]],
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
                                        "milligrams": 20000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                seeded_text = ledger.read_text(encoding="utf-8")
                connector.echoes[21] = {"order_number": 21, "fulfillment_status": "fulfilled"}
                created = connector.create_order({"order_number": 21, "line_items": [line]})
                self.assertEqual(created["fulfillment_status"], "fulfilled")
                self.assertNotIn("line_items", created)
                self.assertIn(("post", 21), connector.sent)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "21:0:sku-serum-c"', text)
                self.assertIn('"location": "cape-town"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertIn('"transfer_id": "to-cape-town"', text)
                again = connector.create_order({"order_number": 21, "line_items": [line]})
                self.assertEqual(again["order_number"], 21)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.echoes[22] = {
                    "order_number": 22,
                    "fulfillment_status": "fulfilled",
                    "line_items": [{**line, "location": "johannesburg", "milligrams": 1500}],
                }
                before_kept = ledger.read_text(encoding="utf-8")
                with self.assertRaises(IntegrationError):
                    connector.create_order({"order_number": 22, "line_items": [line]})
                self.assertIn(("post", 22), connector.sent)
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                self.assertNotIn('"fulfillment_id": "22:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.echoes[23] = {"order_number": 23}
                opened = connector.create_order({"order_number": 23, "line_items": [line]})
                self.assertEqual(opened["order_number"], 23)
                self.assertNotIn("line_items", opened)
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn('"fulfillment_id": "23:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.echoes[24] = {"cancelled_at": "2026-10-02T00:00:00Z"}
                cancelled = connector.create_order({"order_number": 24, "line_items": [line]})
                self.assertEqual(cancelled.get("cancelled_at"), "2026-10-02T00:00:00Z")
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn("return:24", ledger.read_text(encoding="utf-8"))
                connector.echoes[25] = {"order_number": 25, "fulfillment_status": "fulfilled"}
                updated = connector.update_order(25, {"order_number": 25, "line_items": [line]})
                self.assertNotIn("line_items", updated)
                self.assertIn(("put", 25), connector.sent)
                updated_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "25:0:sku-serum-c"', updated_text)
                connector.echoes[26] = {
                    "order_number": 26,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "paid",
                }
                paid = connector.create_order(
                    {"order_number": 26, "line_items": [{**line, "price": "20.00"}]}
                )
                self.assertEqual(paid.get("financial_status"), "paid")
                paid_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "26:0:sku-serum-c"', paid_text)
                self.assertIn('"settlement_id": "pay-26:0:sku-serum-c"', paid_text)
                self.assertIn('"amount_cents": 2000', paid_text)
                connector.echoes[27] = {
                    "order_number": 27,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "paid",
                }
                before_unpriced = list(connector.sent)
                with self.assertRaises(IntegrationError) as unpriced:
                    connector.create_order({"order_number": 27, "line_items": [line]})
                self.assertIn("amount", str(unpriced.exception))
                self.assertEqual(connector.sent, before_unpriced + [("post", 27)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), paid_text)
                self.assertNotIn('"fulfillment_id": "27:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.echoes[28] = {
                    "order_number": 28,
                    "fulfillment_status": "fulfilled",
                    "line_items": [{**line, "milligrams": "lots"}],
                }
                before_lots = list(connector.sent)
                with self.assertRaises(IntegrationError):
                    connector.create_order({"order_number": 28, "line_items": [line]})
                self.assertEqual(connector.sent, before_lots + [("post", 28)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), paid_text)
                self.assertNotIn('"fulfillment_id": "28:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.echoes[29] = {"order_number": 29, "fulfillment_status": "fulfilled"}
                noted = connector.create_order(
                    {
                        "order_number": 29,
                        "line_items": [{"sku": "sku-serum-c"}],
                        "note_attributes": [
                            {"name": "location", "value": "cape-town"},
                            {"name": "milligrams", "value": "2000"},
                        ],
                    }
                )
                self.assertEqual(noted["order_number"], 29)
                self.assertNotIn("note_attributes", noted)
                noted_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "29:0:sku-serum-c"', noted_text)
                self.assertIn('"milligrams": 2000', noted_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_partial_refund_returns_the_sale_when_the_refund_lines_are_omitted(self) -> None:
        line = {
            "id": 100,
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
        }
        full_refund = {
            "refund_line_items": [{"quantity": 1, "line_item": {"sku": "sku-serum-c"}}],
        }

        def request(number, **extra):
            payload = {
                "order_number": number,
                "financial_status": "partially_refunded",
                "line_items": [line],
                "refunds": [full_refund],
            }
            payload.update(extra)
            return payload

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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Orders(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.echoes = {}
                        self.ENDPOINTS = {"orders": "orders.json", "order": "orders/{id}.json"}

                    def _saved(self, data):
                        number = data["order"].get("order_number")
                        if number in self.echoes:
                            return {"order": self.echoes[number]}
                        return {"order": data["order"]}

                    def post(self, endpoint, data):
                        self.sent.append(("post", data["order"].get("order_number")))
                        return self._saved(data)

                    def put(self, endpoint, data):
                        self.sent.append(("put", data["order"].get("order_number")))
                        return self._saved(data)

                connector = _Orders()
                with self.assertRaises(IntegrationError):
                    connector.create_order(
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "financial_status": "partially_refunded",
                            "line_items": [{**line, "milligrams": "lots"}],
                            "refunds": [full_refund],
                        }
                    )
                self.assertEqual(connector.sent, [])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 14000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 14000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 14000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 14000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.echoes[9] = {
                    "order_number": 9,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [line],
                }
                created = connector.create_order(request(9))
                self.assertEqual(created["order_number"], 9)
                self.assertNotIn("refunds", created)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', text)
                again = connector.create_order(request(9))
                self.assertEqual(again["order_number"], 9)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.echoes[17] = {
                    "order_number": 17,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [line],
                    "refunds": [{"refund_line_items": [{"quantity": 1, "line_item": {}}]}],
                }
                named = connector.create_order(request(17))
                self.assertEqual(named["order_number"], 17)
                self.assertEqual(named["refunds"][0]["refund_line_items"][0]["line_item"], {})
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "17:0:sku-serum-c"', named_text)
                self.assertIn('"return_id": "return:17:0:sku-serum-c"', named_text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', named_text)
                connector.echoes[18] = {
                    "order_number": 18,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [{**line, "quantity": 2}],
                    "refunds": [{"refund_line_items": [{"quantity": 1}]}],
                }
                kept_quantity = connector.create_order(
                    request(
                        18,
                        line_items=[{**line, "quantity": 2}],
                        refunds=[
                            {
                                "refund_line_items": [
                                    {"quantity": 2, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    )
                )
                self.assertEqual(kept_quantity["order_number"], 18)
                kept_quantity_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "18:0:sku-serum-c"', kept_quantity_text)
                self.assertNotIn('"return_id": "return:18:0:sku-serum-c"', kept_quantity_text)
                connector.echoes[19] = {
                    "order_number": 19,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [line, {**line, "id": 101}],
                    "refunds": [{"refund_line_items": [{"quantity": 1}]}],
                }
                chosen = connector.create_order(
                    request(
                        19,
                        line_items=[line, {**line, "id": 101}],
                        refunds=[
                            {
                                "refund_line_items": [
                                    {
                                        "quantity": 1,
                                        "line_item_id": 101,
                                        "line_item": {"id": 101, "sku": "sku-serum-c"},
                                    }
                                ]
                            }
                        ],
                    )
                )
                self.assertEqual(chosen["order_number"], 19)
                chosen_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "19:0:sku-serum-c"', chosen_text)
                self.assertIn('"fulfillment_id": "19:1:sku-serum-c"', chosen_text)
                self.assertIn('"return_id": "return:19:1:sku-serum-c"', chosen_text)
                self.assertNotIn('"return_id": "return:19:0:sku-serum-c"', chosen_text)
                connector.echoes[10] = {
                    "order_number": 10,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [{**line, "quantity": 2}],
                }
                short = connector.create_order(
                    request(
                        10,
                        line_items=[{**line, "quantity": 2}],
                        refunds=[
                            {
                                "refund_line_items": [
                                    {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    )
                )
                self.assertEqual(short["order_number"], 10)
                short_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "10:0:sku-serum-c"', short_text)
                self.assertNotIn('"return_id": "return:10:0:sku-serum-c"', short_text)
                connector.echoes[11] = {
                    "order_number": 11,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [{**line, "quantity": 2}],
                    "refunds": [
                        {
                            "refund_line_items": [
                                {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                            ]
                        }
                    ],
                }
                kept = connector.create_order(request(11))
                self.assertEqual(kept["order_number"], 11)
                kept_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "11:0:sku-serum-c"', kept_text)
                self.assertNotIn('"return_id": "return:11:0:sku-serum-c"', kept_text)
                connector.echoes[12] = {
                    "order_number": 12,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [{**line, "id": 100, "milligrams": 1000}, {**line, "id": 101, "milligrams": 1000}],
                }
                ambiguous = connector.create_order(
                    request(
                        12,
                        line_items=[{**line, "milligrams": 1000}, {**line, "id": 101, "milligrams": 1000}],
                    )
                )
                self.assertEqual(ambiguous["order_number"], 12)
                ambiguous_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "12:0:sku-serum-c"', ambiguous_text)
                self.assertIn('"fulfillment_id": "12:1:sku-serum-c"', ambiguous_text)
                self.assertNotIn("return:12:", ambiguous_text)
                connector.echoes[15] = {
                    "order_number": 15,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                }
                updated = connector.update_order(15, request(15))
                self.assertEqual(updated["order_number"], 15)
                self.assertNotIn("line_items", updated)
                updated_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "15:0:sku-serum-c"', updated_text)
                self.assertIn('"return_id": "return:15:0:sku-serum-c"', updated_text)
                connector.echoes[16] = {
                    "order_number": 16,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "paid",
                    "line_items": [{**line, "price": "20.00"}],
                }
                paid = connector.create_order(request(16, financial_status="paid"))
                self.assertEqual(paid["financial_status"], "paid")
                paid_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "16:0:sku-serum-c"', paid_text)
                self.assertIn('"settlement_id": "pay-16:0:sku-serum-c"', paid_text)
                self.assertNotIn('"return_id": "return:16:0:sku-serum-c"', paid_text)
                before_open = ledger.read_text(encoding="utf-8")
                connector.echoes[14] = {"order_number": 14, "financial_status": "partially_refunded"}
                opened = connector.create_order(request(14))
                self.assertEqual(opened["order_number"], 14)
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_open)
                self.assertNotIn('"fulfillment_id": "14:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.echoes[9] = {
                    "order_number": 9,
                    "fulfillment_status": "fulfilled",
                    "financial_status": "partially_refunded",
                    "line_items": [{**line, "location": "johannesburg"}],
                }
                before_changed = list(connector.sent)
                with self.assertRaises(IntegrationError):
                    connector.update_order(9, request(9, line_items=[{**line, "location": "johannesburg"}]))
                self.assertEqual(connector.sent, before_changed + [("put", 9)])
                self.assertEqual(ledger.read_text(encoding="utf-8"), paid_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_shopify_line_that_omits_its_sku_draws_the_request_sku(self) -> None:
        def fulfillment_milligrams(text, fulfillment_id):
            for record in text.splitlines():
                if not record.strip():
                    continue
                body = json.loads(record)
                if body.get("command") != "fulfill":
                    continue
                if (body.get("args") or {}).get("fulfillment_id") == fulfillment_id:
                    return body["args"]["milligrams"]
            return None

        kept = {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 1500}
        dropped = {"location": "cape-town", "milligrams": 2000}
        requested_line = {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 2000}
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                shopify = importlib.import_module("integrations.shopify.connector")
                ShopifyB2BConnector = shopify.ShopifyB2BConnector

                class _Orders(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.echoes = {}
                        self.ENDPOINTS = {
                            "orders": "orders.json",
                            "order": "orders/{id}.json",
                            "draft_orders": "draft_orders.json",
                        }

                    def post(self, endpoint, data):
                        if "draft_order" in data:
                            number = data["draft_order"].get("order_id")
                            self.sent.append(("draft", number))
                            return {"draft_order": self.echoes.get(("draft", number), data["draft_order"])}
                        number = data["order"].get("order_number")
                        self.sent.append(("order", number))
                        return {"order": self.echoes.get(("order", number), data["order"])}

                    def put(self, endpoint, data):
                        number = data["order"].get("order_number")
                        self.sent.append(("put", number))
                        return {"order": self.echoes.get(("order", number), data["order"])}

                connector = _Orders()
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 20000,
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
                                        "units": 4,
                                        "allocations": [["glycerin", "lot-glycerin", 20000]],
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
                                        "milligrams": 20000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                seeded_text = ledger.read_text(encoding="utf-8")
                conflicted = {
                    "order_number": 30,
                    "fulfillment_status": "fulfilled",
                    "line_items": [
                        kept,
                        {"sku": "sku-other", "location": "cape-town"},
                    ],
                }
                stamped = shopify._saved_shopify_fulfilled_lines(
                    conflicted,
                    {"line_items": [requested_line, requested_line]},
                )
                self.assertIs(stamped, conflicted)
                titled = {
                    "order_number": 31,
                    "fulfillment_status": "fulfilled",
                    "line_items": [kept, {"title": "Vitamin C serum", "location": "cape-town", "milligrams": 2000}],
                }
                self.assertIs(
                    shopify._saved_shopify_fulfilled_lines(
                        titled,
                        {
                            "line_items": [
                                requested_line,
                                {"title": "Vitamin C serum", "location": "cape-town", "milligrams": 2000},
                            ]
                        },
                    ),
                    titled,
                )
                connector.echoes[("order", 32)] = {
                    "order_number": 32,
                    "fulfillment_status": "fulfilled",
                    "line_items": [kept, dropped],
                }
                created = connector.create_order(
                    {"order_number": 32, "line_items": [requested_line, requested_line]}
                )
                self.assertNotIn("sku", created["line_items"][1])
                self.assertEqual(created["line_items"][0]["milligrams"], 1500)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "32:0:sku-serum-c"', text)
                self.assertIn('"fulfillment_id": "32:1:sku-serum-c"', text)
                self.assertEqual(fulfillment_milligrams(text, "32:0:sku-serum-c"), 1500)
                self.assertEqual(fulfillment_milligrams(text, "32:1:sku-serum-c"), 2000)
                again = connector.create_order(
                    {"order_number": 32, "line_items": [requested_line, requested_line]}
                )
                self.assertEqual(again["order_number"], 32)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.echoes[("order", 33)] = {
                    "order_number": 33,
                    "fulfillment_status": "fulfilled",
                    "line_items": [{"sku": "sku-serum-c", "location": "cape-town"}],
                }
                quantity = connector.create_order(
                    {"order_number": 33, "line_items": [requested_line]}
                )
                self.assertNotIn("milligrams", quantity["line_items"][0])
                quantity_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(fulfillment_milligrams(quantity_text, "33:0:sku-serum-c"), 2000)
                before_word = ledger.read_text(encoding="utf-8")
                connector.echoes[("order", 34)] = {
                    "order_number": 34,
                    "fulfillment_status": "fulfilled",
                    "line_items": [{**requested_line, "milligrams": "lots"}],
                }
                with self.assertRaises(IntegrationError):
                    connector.create_order({"order_number": 34, "line_items": [requested_line]})
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_word)
                connector.echoes[("order", 35)] = {
                    "order_number": 35,
                    "fulfillment_status": "fulfilled",
                    "line_items": [dropped, dropped],
                }
                blank = connector.create_order(
                    {
                        "order_number": 35,
                        "line_items": [
                            {"location": "cape-town", "milligrams": 2000},
                            requested_line,
                        ],
                    }
                )
                self.assertNotIn("sku", blank["line_items"][0])
                blank_text = ledger.read_text(encoding="utf-8")
                self.assertNotIn('"fulfillment_id": "35:0:', blank_text)
                self.assertEqual(fulfillment_milligrams(blank_text, "35:1:sku-serum-c"), 2000)
                connector.echoes[("draft", 40)] = {
                    "status": "completed",
                    "order_id": 40,
                    "line_items": [kept, dropped],
                }
                drafted = connector.create_draft_order(
                    {
                        "status": "open",
                        "order_id": 40,
                        "line_items": [requested_line, requested_line],
                    }
                )
                self.assertNotIn("sku", drafted["line_items"][1])
                draft_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(fulfillment_milligrams(draft_text, "40:0:sku-serum-c"), 1500)
                self.assertEqual(fulfillment_milligrams(draft_text, "40:1:sku-serum-c"), 2000)
                self.assertIn('"transfer_id": "to-cape-town"', draft_text)
                self.assertEqual(seeded_text in draft_text, True)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_completed_draft_records_the_named_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        draft = {"status": "completed", "id": 3, "order_id": 9, "line_items": [line]}
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Complete(ShopifyB2BConnector):
                    def __init__(self):
                        self.completed = []
                        self.response = {}

                    def put(self, endpoint, data):
                        self.completed.append(endpoint)
                        return {"draft_order": self.response}

                connector = _Complete()
                connector.response = {"status": "open", "id": 3, "order_id": 9, "line_items": [line]}
                opened = connector.complete_draft_order(3)
                self.assertEqual(opened["status"], "open")
                self.assertEqual(len(connector.completed), 1)
                self.assertFalse(ledger.exists())
                connector.response = {
                    "status": "completed",
                    "id": 3,
                    "order_id": 9,
                    "line_items": [
                        {
                            "sku": "sku-serum-c",
                            "properties": [
                                {"name": "location", "value": "cape-town"},
                                {"name": "milligrams", "value": "lots"},
                            ],
                        }
                    ],
                }
                with self.assertRaises(IntegrationError):
                    connector.complete_draft_order(3)
                self.assertEqual(len(connector.completed), 2)
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.response = draft
                completed = connector.complete_draft_order(3)
                self.assertEqual(completed["order_id"], 9)
                self.assertEqual(len(connector.completed), 3)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                again = connector.complete_draft_order(3)
                self.assertEqual(again["status"], "completed")
                self.assertEqual(len(connector.completed), 4)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.response = {
                    "status": "completed",
                    "id": 3,
                    "order_id": 9,
                    "line_items": [
                        {
                            "sku": "sku-serum-c",
                            "location": "johannesburg",
                            "milligrams": 2000,
                        }
                    ],
                }
                with self.assertRaises(IntegrationError):
                    connector.complete_draft_order(3)
                self.assertEqual(len(connector.completed), 5)
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


    def test_a_posted_draft_records_the_named_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
        }
        draft = {"status": "completed", "id": 3, "order_id": 9, "line_items": [line]}
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []

                    def post(self, endpoint, data):
                        body = data["draft_order"]
                        self.posted.append(body.get("status"))
                        echoes = {
                            11: {
                                "status": "completed",
                                "id": 11,
                                "order_id": 11,
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "properties": [
                                            {"name": "location", "value": "cape-town"},
                                            {"name": "milligrams", "value": "2000"},
                                        ],
                                    }
                                ],
                            },
                            12: {
                                "status": "completed",
                                "id": 12,
                                "order_id": 12,
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "properties": [
                                            {"name": "location", "value": "cape-town"},
                                            {"name": "milligrams", "value": "lots"},
                                        ],
                                    }
                                ],
                            },
                            13: {
                                "status": "open",
                                "id": 13,
                                "order_id": 13,
                                "line_items": [{"sku": "sku-serum-c"}],
                            },
                            14: {
                                "status": "completed",
                                "id": 11,
                                "order_id": 11,
                                "line_items": [
                                    {
                                        "sku": "sku-serum-c",
                                        "location": "johannesburg",
                                        "milligrams": 2000,
                                    }
                                ],
                            },
                        }
                        if body.get("id") in echoes:
                            return {"draft_order": echoes[body.get("id")]}
                        return {"draft_order": body}

                connector = _Posted()
                opened = connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [line]}
                )
                self.assertEqual(opened["status"], "open")
                self.assertEqual(connector.posted, ["open"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {
                            "status": "completed",
                            "id": 3,
                            "order_id": 9,
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "properties": [
                                        {"name": "location", "value": "cape-town"},
                                        {"name": "milligrams", "value": "lots"},
                                    ],
                                }
                            ],
                        }
                    )
                self.assertEqual(connector.posted, ["open"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_draft_order(draft)
                self.assertEqual(created["order_id"], 9)
                self.assertEqual(connector.posted, ["open", "completed"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                again = connector.create_draft_order(draft)
                self.assertEqual(again["status"], "completed")
                self.assertEqual(connector.posted, ["open", "completed", "completed"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {
                            "status": "completed",
                            "id": 3,
                            "order_id": 9,
                            "line_items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "johannesburg",
                                    "milligrams": 2000,
                                }
                            ],
                        }
                    )
                self.assertEqual(connector.posted, ["open", "completed", "completed"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                echo = {"status": "open", "id": 11, "line_items": [{"sku": "sku-serum-c"}]}
                echoed = connector.create_draft_order(echo)
                self.assertEqual(echoed["status"], "completed")
                self.assertEqual(connector.posted, ["open", "completed", "completed", "open"])
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "11:0:sku-serum-c"', echoed_text)
                self.assertIn('"location": "cape-town"', echoed_text)
                self.assertNotIn("johannesburg", echoed_text)
                again_echo = connector.create_draft_order(echo)
                self.assertEqual(again_echo["status"], "completed")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_bad = list(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {"status": "open", "id": 12, "line_items": [{"sku": "sku-serum-c"}]}
                    )
                self.assertEqual(connector.posted, before_bad + ["open"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "12:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                still_open = connector.create_draft_order(
                    {"status": "open", "id": 13, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(still_open["status"], "open")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "13:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {"status": "open", "id": 14, "line_items": [{"sku": "sku-serum-c"}]}
                    )
                self.assertEqual(connector.posted[-1], "open")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_posted_wix_booking_records_the_named_delivery_once(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        booking = {
            "id": "book-1",
            "service_id": "srv-001",
            "services": [{"name": "Facial"}, {"delivery": delivery}],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []
                        self.updated = []

                    def _service_id(self, body):
                        return ((body.get("bookedEntity") or {}).get("slot") or {}).get("serviceId")

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        body = (data or {}).get("booking", {})
                        echoes = {
                            "echo-facial": {
                                "id": "book-echo",
                                "services": [{"delivery": delivery}],
                            },
                            "bad-facial": {
                                "id": "book-bad-saved",
                                "services": [{"delivery": {**delivery, "milligrams": "lots"}}],
                            },
                            "plain-facial": {
                                "id": "book-plain",
                                "services": [{"name": "Facial"}],
                            },
                            "moved-facial": {
                                "id": "book-echo",
                                "services": [
                                    {"delivery": {**delivery, "destination": "johannesburg"}}
                                ],
                            },
                        }
                        saved = echoes.get(self._service_id(body))
                        if saved is not None:
                            return {"booking": saved}
                        return {"booking": {**body, "id": body.get("id") or "wix-created"}}

                    def get(self, endpoint, params=None):
                        return {"booking": {"id": endpoint, "revision": "1"}}

                    def put(self, endpoint, data=None):
                        self.updated.append(endpoint)
                        body = (data or {}).get("booking", {})
                        if body.get("id") == "book-outlet":
                            return {"booking": {"id": "book-outlet", "services": [{"delivery": delivery}]}}
                        return {"booking": body}

                connector = _Posted()
                opened = connector.create_appointment(
                    {
                        "service_id": "srv-001",
                        "services": [{"name": "Facial"}],
                    }
                )
                self.assertEqual(opened.get("id"), "wix-created")
                self.assertEqual(connector.posted, ["/bookings/v2/bookings"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "id": "book-bad",
                            "services": [{"delivery": {**delivery, "milligrams": "lots"}}],
                        }
                    )
                self.assertEqual(connector.posted, ["/bookings/v2/bookings"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_appointment(booking)
                self.assertEqual(connector.posted, ["/bookings/v2/bookings", "/bookings/v2/bookings"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-1:1"', text)
                self.assertIn('"milligrams": 2000', text)
                again = connector.create_appointment(booking)
                self.assertEqual(
                    connector.posted,
                    ["/bookings/v2/bookings", "/bookings/v2/bookings", "/bookings/v2/bookings"],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            **booking,
                            "services": [
                                {"name": "Facial"},
                                {"delivery": {**delivery, "destination": "johannesburg"}},
                            ],
                        }
                    )
                self.assertEqual(
                    connector.posted,
                    ["/bookings/v2/bookings", "/bookings/v2/bookings", "/bookings/v2/bookings"],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                updated = connector.update_appointment(
                    "book-2",
                    {"services": [{"delivery": delivery}]},
                )
                self.assertEqual(updated.get("id"), "book-2")
                self.assertEqual(connector.updated, ["/bookings/v2/bookings/book-2"])
                moved = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-2:0"', moved)
                repeated = connector.update_appointment(
                    "book-2",
                    {"services": [{"delivery": delivery}]},
                )
                self.assertEqual(repeated.get("id"), "book-2")
                self.assertEqual(
                    connector.updated,
                    ["/bookings/v2/bookings/book-2", "/bookings/v2/bookings/book-2"],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment(
                        "book-2",
                        {"services": [{"delivery": {**delivery, "destination": "johannesburg"}}]},
                    )
                self.assertEqual(
                    connector.updated,
                    ["/bookings/v2/bookings/book-2", "/bookings/v2/bookings/book-2"],
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                echoed = connector.create_appointment(
                    {"service_id": "echo-facial", "services": [{"name": "Facial"}]}
                )
                self.assertEqual(echoed.get("id"), "book-echo")
                self.assertIn("/bookings/v2/bookings", connector.posted)
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-echo:0"', echoed_text)
                self.assertIn('"destination": "cape-town"', echoed_text)
                self.assertNotIn("johannesburg", echoed_text)
                again_echo = connector.create_appointment(
                    {"service_id": "echo-facial", "services": [{"name": "Facial"}]}
                )
                self.assertEqual(again_echo.get("id"), "book-echo")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_bad = list(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"service_id": "bad-facial", "services": [{"name": "Facial"}]}
                    )
                self.assertEqual(len(connector.posted), len(before_bad) + 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("book-bad-saved", ledger.read_text(encoding="utf-8"))
                plain = connector.create_appointment(
                    {"service_id": "plain-facial", "services": [{"name": "Facial"}]}
                )
                self.assertEqual(plain.get("id"), "book-plain")
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("book-plain", ledger.read_text(encoding="utf-8"))
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"service_id": "moved-facial", "services": [{"name": "Facial"}]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                outlet = connector.update_appointment(
                    "book-outlet",
                    {"services": [{"name": "Facial"}]},
                )
                self.assertEqual(outlet.get("id"), "book-outlet")
                self.assertIn("/bookings/v2/bookings/book-outlet", connector.updated)
                self.assertIn('"transfer_id": "book-outlet:0"', ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_an_appointment_item_records_the_named_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector
                OpenCartConnector = importlib.import_module(
                    "integrations.opencart.connector"
                ).OpenCartConnector

                class _Shopify(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = 0

                    def post(self, endpoint, data=None):
                        self.posted += 1
                        return {"order": (data or {}).get("order", {})}

                class _OpenCart(OpenCartConnector):
                    def __init__(self):
                        self.calls = []

                    def set_customer(self, first_name, last_name, email, telephone):
                        self.calls.append("customer")
                        return {}

                    def add_to_cart(self, product_id, quantity=1, options=None):
                        self.calls.append("cart")
                        return {}

                    def create_order(self):
                        self.calls.append("order")
                        return {"order_id": 32}

                shopify = _Shopify()
                opencart = _OpenCart()
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
                seeded_text = ledger.read_text(encoding="utf-8")
                plain = shopify.create_appointment(
                    {
                        "order_number": 31,
                        "fulfillment_status": "fulfilled",
                        "items": [{"name": "Signature Facial", "quantity": 1}],
                    }
                )
                self.assertEqual(plain.get("financial_status"), "pending")
                self.assertEqual(shopify.posted, 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                with self.assertRaises(IntegrationError):
                    shopify.create_appointment(
                        {
                            "order_number": 31,
                            "fulfillment_status": "fulfilled",
                            "items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(shopify.posted, 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                sold = shopify.create_appointment(
                    {
                        "order_number": 31,
                        "fulfillment_status": "fulfilled",
                        "items": [line],
                    }
                )
                self.assertEqual(sold.get("financial_status"), "pending")
                self.assertEqual(shopify.posted, 2)
                self.assertIn("31:0:sku-serum-c", ledger.read_text(encoding="utf-8"))
                shopify.create_appointment(
                    {
                        "order_number": 31,
                        "fulfillment_status": "fulfilled",
                        "items": [line],
                    }
                )
                booked = ledger.read_text(encoding="utf-8")
                self.assertEqual(booked.count("31:0:sku-serum-c"), 1)
                with self.assertRaises(IntegrationError):
                    shopify.create_appointment(
                        {
                            "order_number": 31,
                            "fulfillment_status": "fulfilled",
                            "items": [{**line, "location": "johannesburg"}],
                        }
                    )
                self.assertEqual(shopify.posted, 3)
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                pending = opencart.create_appointment(
                    {
                        "order_id": 32,
                        "client_email": "adaeze.obi@example.com",
                        "items": [line],
                    }
                )
                self.assertEqual(pending.get("order_id"), 32)
                self.assertEqual(opencart.calls, ["customer", "cart", "order"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                with self.assertRaises(IntegrationError):
                    opencart.create_appointment(
                        {
                            "order_id": 32,
                            "status": "shipped",
                            "items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(opencart.calls, ["customer", "cart", "order"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), booked)
                opencart.create_appointment(
                    {
                        "order_id": 32,
                        "status": "shipped",
                        "client_email": "adaeze.obi@example.com",
                        "items": [line],
                    }
                )
                self.assertIn("32:0:sku-serum-c", ledger.read_text(encoding="utf-8"))
                opencart.create_appointment(
                    {
                        "order_id": 32,
                        "status": "shipped",
                        "client_email": "adaeze.obi@example.com",
                        "items": [line],
                    }
                )
                sold_text = ledger.read_text(encoding="utf-8")
                self.assertEqual(sold_text.count("32:0:sku-serum-c"), 1)
                with self.assertRaises(IntegrationError):
                    opencart.create_appointment(
                        {
                            "order_id": 32,
                            "status": "shipped",
                            "items": [{**line, "location": "johannesburg"}],
                        }
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), sold_text)
                self.assertIn('"location": "cape-town"', sold_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_posted_appointment_records_the_named_sale_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "quantity": 1,
            "price": "25.00",
            "location": "cape-town",
            "milligrams": 2000,
        }
        order = {
            "order_number": 9,
            "fulfillment_status": "fulfilled",
            "financial_status": "paid",
            "currency": "ZAR",
            "line_items": [line],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.updated = []

                    def post(self, endpoint, data=None):
                        body = (data or {}).get("order", {})
                        self.posted.append(body.get("financial_status"))
                        return {"order": body}

                    def put(self, endpoint, data=None):
                        self.updated.append(endpoint)
                        return {"order": (data or {}).get("order", {})}

                connector = _Posted()
                opened = connector.create_appointment(
                    {
                        "client_email": "adaeze.obi@example.com",
                        "items": [{"name": "Signature Facial", "quantity": 1, "price": 250}],
                    }
                )
                self.assertEqual(opened.get("financial_status"), "pending")
                self.assertEqual(connector.posted, ["pending"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "line_items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.posted, ["pending"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_appointment(order)
                self.assertEqual(created.get("financial_status"), "pending")
                self.assertEqual(connector.posted, ["pending", "pending"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertIn('"amount_cents": 2500', text)
                self.assertIn('"currency": "ZAR"', text)
                again = connector.create_appointment(order)
                self.assertEqual(connector.posted, ["pending", "pending", "pending"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {**order, "line_items": [{**line, "location": "johannesburg"}]}
                    )
                self.assertEqual(connector.posted, ["pending", "pending", "pending"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                updated = connector.update_appointment(
                    "10",
                    {**order, "order_number": 10},
                )
                self.assertEqual(updated.get("financial_status"), "pending")
                self.assertEqual(connector.updated, ["orders/10.json"])
                moved = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "10:0:sku-serum-c"', moved)
                repeated = connector.update_appointment(
                    "10",
                    {**order, "order_number": 10},
                )
                self.assertEqual(connector.updated, ["orders/10.json", "orders/10.json"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment(
                        "10",
                        {
                            **order,
                            "order_number": 10,
                            "line_items": [{**line, "location": "johannesburg"}],
                        },
                    )
                self.assertEqual(connector.updated, ["orders/10.json", "orders/10.json"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_posted_opencart_appointment_records_the_named_sale_once(self) -> None:
        product = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "price": "185.00",
            "quantity": "1",
        }
        order = {
            "order_id": 9,
            "status": "complete",
            "currency_code": "ZAR",
            "client_email": "adaeze.obi@example.com",
            "products": [product],
            "items": [{"product_id": 9, "quantity": 1}],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                OpenCartConnector = importlib.import_module(
                    "integrations.opencart.connector"
                ).OpenCartConnector

                class _Posted(OpenCartConnector):
                    def __init__(self):
                        self.calls = []
                        self.product_id = None

                    def set_customer(self, first_name, last_name, email, telephone):
                        self.calls.append("customer")
                        return {}

                    def add_to_cart(self, product_id, quantity=1, options=None):
                        self.calls.append("cart")
                        self.product_id = product_id
                        return {}

                    def create_order(self):
                        self.calls.append("order")
                        echoes = {
                            11: {
                                "order_id": 12,
                                "status": "shipped",
                                "products": [product],
                            },
                            13: {
                                "order_id": 13,
                                "status": "shipped",
                                "products": [{**product, "milligrams": "lots"}],
                            },
                            14: {"order_id": 14},
                            15: {
                                "order_id": 12,
                                "status": "shipped",
                                "products": [{**product, "location": "johannesburg"}],
                            },
                        }
                        return echoes.get(self.product_id, {"order_id": 9})

                    def update_order_history(self, order_id, order_status_id, comment="", notify=False):
                        self.calls.append(("history", order_id, order_status_id))
                        if order_id == 16:
                            return {"order_id": 16, "status": "shipped", "products": [product]}
                        return {"order_id": order_id}

                connector = _Posted()
                opened = connector.create_appointment(
                    {
                        "client_email": "adaeze.obi@example.com",
                        "items": [{"product_id": 9, "quantity": 1}],
                    }
                )
                self.assertEqual(opened.get("order_id"), 9)
                self.assertEqual(connector.calls, ["customer", "cart", "order"])
                self.assertFalse(ledger.exists())
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "order_id": 9,
                            "status": "complete",
                            "products": [{**product, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.calls, ["customer", "cart", "order"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_appointment(order)
                self.assertEqual(created.get("order_id"), 9)
                self.assertEqual(
                    connector.calls,
                    ["customer", "cart", "order", "customer", "cart", "order"],
                )
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertIn('"amount_cents": 18500', text)
                self.assertIn('"currency": "ZAR"', text)
                again = connector.create_appointment(order)
                self.assertEqual(connector.calls.count("order"), 3)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {**order, "products": [{**product, "location": "johannesburg"}]}
                    )
                self.assertEqual(connector.calls.count("order"), 3)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                updated = connector.update_appointment(
                    "11",
                    {"status": "complete", "currency_code": "ZAR", "products": [product]},
                )
                self.assertEqual(updated.get("order_id"), 11)
                self.assertIn(("history", 11, 1), connector.calls)
                moved = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "11:0:sku-serum-c"', moved)
                repeated = connector.update_appointment(
                    "11",
                    {"status": "complete", "currency_code": "ZAR", "products": [product]},
                )
                self.assertEqual(repeated.get("order_id"), 11)
                self.assertEqual(connector.calls.count(("history", 11, 1)), 2)
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment(
                        "11",
                        {
                            "status": "complete",
                            "products": [{**product, "location": "johannesburg"}],
                        },
                    )
                self.assertEqual(connector.calls.count(("history", 11, 1)), 2)
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                echoed = connector.create_appointment(
                    {
                        "client_email": "echo@example.com",
                        "items": [{"product_id": 11, "quantity": 1}],
                    }
                )
                self.assertEqual(echoed.get("status"), "shipped")
                self.assertIn("order", connector.calls)
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "12:0:sku-serum-c"', echoed_text)
                self.assertIn('"location": "cape-town"', echoed_text)
                self.assertNotIn("johannesburg", echoed_text)
                again_echo = connector.create_appointment(
                    {
                        "client_email": "echo@example.com",
                        "items": [{"product_id": 11, "quantity": 1}],
                    }
                )
                self.assertEqual(again_echo.get("order_id"), 12)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_bad = connector.calls.count("order")
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"items": [{"product_id": 13, "quantity": 1}]}
                    )
                self.assertEqual(connector.calls.count("order"), before_bad + 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "13:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                plain = connector.create_appointment(
                    {"items": [{"product_id": 14, "quantity": 1}]}
                )
                self.assertEqual(plain.get("order_id"), 14)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn('"fulfillment_id": "14:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"items": [{"product_id": 15, "quantity": 1}]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                outlet = connector.update_appointment("16", {"status": "pending"})
                self.assertEqual(outlet.get("status"), "shipped")
                self.assertIn(("history", 16, 1), connector.calls)
                self.assertIn('"fulfillment_id": "16:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_opencart_shipment_draws_the_request_products_when_it_omits_them(self) -> None:
        line = {
            "sku": "sku-serum-c",
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                OpenCartConnector = importlib.import_module(
                    "integrations.opencart.connector"
                ).OpenCartConnector

                class _Posted(OpenCartConnector):
                    def __init__(self):
                        self.calls = []
                        self.responses = []
                        self.history = []

                    def set_customer(self, first_name, last_name, email, telephone):
                        self.calls.append("customer")
                        return {}

                    def add_to_cart(self, product_id, quantity=1, options=None):
                        self.calls.append("cart")
                        return {}

                    def create_order(self):
                        self.calls.append("order")
                        return self.responses.pop(0)

                    def update_order_history(self, order_id, order_status_id, comment="", notify=False):
                        self.calls.append(("history", order_id, order_status_id))
                        return self.history.pop(0)

                connector = _Posted()
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "order_id": 9,
                            "status": "complete",
                            "products": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.calls, [])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 20000,
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
                                        "units": 4,
                                        "allocations": [["glycerin", "lot-glycerin", 20000]],
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
                                        "milligrams": 20000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"order_id": 21, "status": "shipped"})
                created = connector.create_appointment(
                    {
                        "order_id": 21,
                        "status": "pending",
                        "products": [line],
                        "items": [{"product_id": 21, "quantity": 1}],
                    }
                )
                self.assertEqual(created.get("status"), "shipped")
                self.assertNotIn("products", created)
                self.assertIn("order", connector.calls)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "21:0:sku-serum-c"', text)
                self.assertIn('"location": "cape-town"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertNotIn('"settlement_id": "pay-21:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "to-cape-town"', text)
                connector.responses.append({"order_id": 21, "status": "shipped"})
                again = connector.create_appointment(
                    {"order_id": 21, "status": "pending", "products": [line]}
                )
                self.assertEqual(again.get("order_id"), 21)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {
                        "order_id": 22,
                        "status": "shipped",
                        "products": [{**line, "location": "johannesburg", "milligrams": 1500}],
                    }
                )
                before_kept = ledger.read_text(encoding="utf-8")
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"order_id": 22, "status": "pending", "products": [line]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                self.assertNotIn('"fulfillment_id": "22:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"order_id": 23})
                opened = connector.create_appointment(
                    {"order_id": 23, "status": "pending", "products": [line]}
                )
                self.assertEqual(opened.get("order_id"), 23)
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn('"fulfillment_id": "23:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"status": "canceled"})
                cancelled = connector.create_appointment(
                    {"order_id": 24, "status": "pending", "products": [line]}
                )
                self.assertEqual(cancelled.get("status"), "canceled")
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn("return:24", ledger.read_text(encoding="utf-8"))
                connector.responses.append({"status": "shipped"})
                before_blank = list(connector.calls)
                with self.assertRaises(IntegrationError) as blank:
                    connector.create_appointment(
                        {"order_id": 30, "status": "pending", "products": [line]}
                    )
                self.assertIn("order number", str(blank.exception))
                self.assertEqual(connector.calls, before_blank + ["customer", "order"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn('"fulfillment_id": "30:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.history.append({"order_status_id": 3})
                updated = connector.update_appointment(
                    "25",
                    {"status": "pending", "products": [line]},
                )
                self.assertEqual(updated.get("order_status_id"), 3)
                self.assertIn(("history", 25, 1), connector.calls)
                updated_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "25:0:sku-serum-c"', updated_text)
                connector.responses.append(
                    {"order_id": 26, "status": "complete", "currency_code": "ZAR"}
                )
                paid = connector.create_appointment(
                    {"order_id": 26, "status": "pending", "products": [line]}
                )
                self.assertEqual(paid.get("status"), "complete")
                paid_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "26:0:sku-serum-c"', paid_text)
                self.assertIn('"settlement_id": "pay-26:0:sku-serum-c"', paid_text)
                self.assertIn('"amount_cents": 18500', paid_text)
                self.assertIn('"currency": "ZAR"', paid_text)
                connector.responses.append(
                    {
                        "order_id": 28,
                        "status": "shipped",
                        "products": [{**line, "milligrams": "lots"}],
                    }
                )
                before_lots = list(connector.calls)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"order_id": 28, "status": "pending", "products": [line]}
                    )
                self.assertEqual(connector.calls, before_lots + ["customer", "order"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), paid_text)
                self.assertNotIn('"fulfillment_id": "28:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"order_id": 29, "status": "shipped"})
                noted = connector.create_appointment(
                    {
                        "order_id": 29,
                        "status": "pending",
                        "products": [
                            {
                                "sku": "sku-serum-c",
                                "option": [
                                    {"name": "location", "value": "cape-town"},
                                    {"name": "milligrams", "value": "2000"},
                                ],
                            }
                        ],
                    }
                )
                self.assertEqual(noted.get("order_id"), 29)
                self.assertNotIn("products", noted)
                noted_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "29:0:sku-serum-c"', noted_text)
                self.assertIn('"milligrams": 2000', noted_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_cancelled_order_records_the_named_return_once(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
        }
        cancelled = {
            "id": 9,
            "order_number": 9,
            "cancelled_at": "2026-10-02T00:00:00Z",
            "line_items": [line],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        body = self.responses.pop(0)
                        return {"order": body}

                connector = _Posted()
                connector.responses.append({"id": 1, "line_items": [{"title": "Signature Facial"}]})
                opened = connector.cancel_order(1)
                self.assertEqual(opened.get("id"), 1)
                self.assertEqual(connector.posted, ["orders/1/cancel.json"])
                self.assertFalse(ledger.exists())
                connector.responses.append(
                    {
                        "order_number": 9,
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.cancel_order(9)
                self.assertEqual(connector.posted, ["orders/1/cancel.json", "orders/9/cancel.json"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append(cancelled)
                returned = connector.cancel_order(9)
                self.assertEqual(returned.get("order_number"), 9)
                self.assertEqual(connector.posted.count("orders/9/cancel.json"), 2)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                connector.responses.append(cancelled)
                again = connector.cancel_order(9)
                self.assertEqual(again.get("order_number"), 9)
                self.assertEqual(connector.posted.count("orders/9/cancel.json"), 3)
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

    def test_a_confirmed_wix_booking_records_the_named_delivery_once(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        confirmed = {
            "id": "book-1",
            "services": [{"name": "Facial"}, {"delivery": delivery}],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        body = self.responses.pop(0)
                        return {"booking": body}

                connector = _Posted()
                connector.responses.append({"id": "book-facial", "services": [{"name": "Facial"}]})
                opened = connector.confirm_appointment("book-facial")
                self.assertEqual(opened.get("id"), "book-facial")
                self.assertEqual(connector.posted, ["/bookings/v2/bookings/book-facial/confirm"])
                self.assertFalse(ledger.exists())
                connector.responses.append(
                    {
                        "id": "book-bad",
                        "services": [{"delivery": {**delivery, "milligrams": "lots"}}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.confirm_appointment("book-bad")
                self.assertEqual(
                    connector.posted,
                    [
                        "/bookings/v2/bookings/book-facial/confirm",
                        "/bookings/v2/bookings/book-bad/confirm",
                    ],
                )
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append(confirmed)
                booked = connector.confirm_appointment("book-1")
                self.assertEqual(booked.get("id"), "book-1")
                self.assertIn("/bookings/v2/bookings/book-1/confirm", connector.posted)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-1:1"', text)
                self.assertIn('"milligrams": 2000', text)
                connector.responses.append(confirmed)
                again = connector.confirm_appointment("book-1")
                self.assertEqual(again.get("id"), "book-1")
                self.assertEqual(connector.posted.count("/bookings/v2/bookings/book-1/confirm"), 2)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {
                        **confirmed,
                        "services": [
                            {"name": "Facial"},
                            {"delivery": {**delivery, "destination": "johannesburg"}},
                        ],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.confirm_appointment("book-1")
                self.assertEqual(connector.posted.count("/bookings/v2/bookings/book-1/confirm"), 3)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append({"services": [{"delivery": delivery}]})
                moved = connector.confirm_appointment("book-2")
                self.assertEqual(moved.get("services"), [{"delivery": delivery}])
                self.assertEqual(connector.posted.count("/bookings/v2/bookings/book-2/confirm"), 1)
                transferred = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-2:0"', transferred)
                connector.responses.append({"services": [{"delivery": delivery}]})
                repeated = connector.confirm_appointment("book-2")
                self.assertEqual(repeated.get("services"), [{"delivery": delivery}])
                self.assertEqual(connector.posted.count("/bookings/v2/bookings/book-2/confirm"), 2)
                self.assertEqual(ledger.read_text(encoding="utf-8"), transferred)
                connector.responses.append(
                    {"services": [{"delivery": {**delivery, "destination": "johannesburg"}}]}
                )
                with self.assertRaises(IntegrationError):
                    connector.confirm_appointment("book-2")
                self.assertEqual(connector.posted.count("/bookings/v2/bookings/book-2/confirm"), 3)
                self.assertEqual(ledger.read_text(encoding="utf-8"), transferred)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_connector_cancel_returns_the_movement_it_already_recorded(self) -> None:
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector
                OpenCartConnector = importlib.import_module(
                    "integrations.opencart.connector"
                ).OpenCartConnector

                class _Shopify(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"order": {}}

                class _Wix(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"booking": {}}

                class _OpenCart(OpenCartConnector):
                    def __init__(self):
                        self.posted = []

                    def update_order_history(self, order_id, order_status_id, comment="", notify=False):
                        self.posted.append((order_id, order_status_id))
                        return {"order_id": order_id}

                shopify = _Shopify()
                wix = _Wix()
                opencart = _OpenCart()
                self.assertEqual(shopify.cancel_order(9), {})
                self.assertTrue(wix.cancel_appointment("book-1"))
                self.assertTrue(opencart.cancel_appointment("4"))
                self.assertEqual(shopify.posted, ["orders/9/cancel.json"])
                self.assertEqual(wix.posted, ["/bookings/v2/bookings/book-1/cancel"])
                self.assertEqual(opencart.posted, [(4, 7)])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 12000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 12000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 12000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-1:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "4:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-2:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "return:book-2:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "cape-town",
                                        "destination": "plant",
                                        "milligrams": 500,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "cover:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1500,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                self.assertTrue(wix.cancel_appointment("book-1"))
                self.assertEqual(shopify.cancel_order(9), {})
                self.assertTrue(opencart.cancel_appointment("4"))
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-1:1"', text)
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertIn('"return_id": "return:4:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn("return:xfer-cape-town", text)
                self.assertNotIn('"transfer_id": "return:cover:0"', text)
                self.assertTrue(wix.cancel_appointment("book-1"))
                self.assertEqual(shopify.cancel_order(9), {})
                self.assertTrue(opencart.cancel_appointment("4"))
                self.assertTrue(wix.cancel_appointment("book-19"))
                self.assertEqual(shopify.cancel_order(19), {})
                self.assertTrue(opencart.cancel_appointment("19"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                with self.assertRaises(IntegrationError):
                    wix.cancel_appointment("book-2")
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

    def test_a_deleted_draft_returns_the_sale_it_already_recorded(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector
                shopify = self._webhook_module("shopify")

                class _Complete(ShopifyB2BConnector):
                    def __init__(self):
                        self.response = {}

                    def put(self, endpoint, data):
                        return {"draft_order": self.response}

                draft_named = {
                    "id": 3,
                    "name": "#D3",
                    "order_id": 30,
                    "line_items": [
                        {"title": "Consultation"},
                        {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 1000},
                    ],
                }
                self.assertEqual(
                    [command["args"]["fulfillment_id"] for command in shopify_return_commands(draft_named)],
                    ["30:1:sku-serum-c"],
                )
                deleted = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted({"id": 3})
                self.assertEqual(deleted["draft_order_id"], 3)
                self.assertIsNone(deleted["recorded"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "milligrams": 6000,
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector = _Complete()
                connector.response = {"status": "completed", "line_items": [line]}
                completed = connector.complete_draft_order(3)
                self.assertEqual(completed["id"], 3)
                drawn = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "3:0:sku-serum-c"', drawn)
                self.assertNotIn('"return_id": "return:3:0:sku-serum-c"', drawn)
                returned = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted({"id": 3})
                self.assertEqual(returned["recorded"], {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:3:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertNotIn("return:to-cape-town", text)
                again = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted({"id": 3})
                self.assertEqual(again["recorded"], {"ok": True, "count": 0})
                other = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted({"id": 19})
                self.assertIsNone(other["recorded"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                split = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "30:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "30:1:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "4:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 1000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(split.returncode, 0, split.stderr or split.stdout)
                drafted = {
                    "id": 3,
                    "name": "#D3",
                    "order_id": 30,
                    "line_items": [
                        {"title": "Consultation"},
                        {"sku": "sku-serum-c", "location": "cape-town", "milligrams": 1000},
                    ],
                }
                named = shopify_return_commands(drafted)
                self.assertEqual(
                    [command["args"]["fulfillment_id"] for command in named],
                    ["30:1:sku-serum-c", "30:0:sku-serum-c"],
                )
                returned_draft = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted(drafted)
                self.assertEqual(returned_draft["recorded"], {"ok": True, "count": 2})
                draft_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:30:0:sku-serum-c"', draft_text)
                self.assertIn('"return_id": "return:30:1:sku-serum-c"', draft_text)
                self.assertNotIn('"return_id": "return:#D3:', draft_text)
                self.assertEqual(draft_text.count('"return_id": "return:3:0:sku-serum-c"'), 1)
                self.assertNotIn('"return_id": "return:9:0:sku-serum-c"', draft_text)
                self.assertNotIn('"return_id": "return:4:0:sku-serum-c"', draft_text)
                self.assertNotIn("return:to-cape-town", draft_text)
                drafted_again = shopify.ShopifyWebhookHandler("secret").on_draft_order_deleted(drafted)
                self.assertEqual(drafted_again["recorded"], {"ok": True, "count": 0})
                self.assertEqual(ledger.read_text(encoding="utf-8"), draft_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_partial_refund_returns_the_sale_it_already_recorded(self) -> None:
        line = {"id": 100, "sku": "sku-serum-c", "quantity": 1}
        refund = {
            "refund_line_items": [
                {"line_item_id": 100, "quantity": 1, "line_item": line},
            ]
        }
        order = {
            "order_number": 9,
            "fulfillment_status": "fulfilled",
            "financial_status": "partially_refunded",
            "line_items": [line],
            "refunds": [refund],
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
                self.assertEqual(shopify_order_update_commands(order), [])
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 12000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 12000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 12000]],
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
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "4:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "19:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                bad = {
                    **order,
                    "refunds": [
                        {
                            "refund_line_items": [
                                {
                                    "line_item_id": 100,
                                    "quantity": 1,
                                    "line_item": {**line, "milligrams": "lots"},
                                }
                            ]
                        }
                    ],
                }
                rejected = record_shopify_order_update(bad)
                self.assertFalse(rejected["ok"])
                drawn = ledger.read_text(encoding="utf-8")
                self.assertNotIn('"return_id": "return:9:0:sku-serum-c"', drawn)
                short = {
                    **order,
                    "order_number": 4,
                    "refunds": [
                        {
                            "refund_line_items": [
                                {
                                    "line_item_id": 100,
                                    "quantity": 1,
                                    "line_item": {**line, "quantity": 2},
                                }
                            ]
                        }
                    ],
                }
                self.assertIsNone(record_shopify_order_update(short))
                self.assertEqual(ledger.read_text(encoding="utf-8"), drawn)
                returned = record_shopify_order_update(order)
                self.assertEqual(returned, {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:4:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:19:0:sku-serum-c"', text)
                self.assertNotIn("return:to-cape-town", text)
                again = record_shopify_order_update(order)
                self.assertEqual(again, {"ok": True, "count": 0})
                other = {**order, "order_number": 8}
                self.assertIsNone(record_shopify_order_update(other))
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

    def test_a_canceled_wix_update_returns_the_delivery_it_already_recorded(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        booking = {"id": "book-update", "services": [{"name": "Facial"}, {"delivery": delivery}]}
        declined = {
            "id": "book-decline",
            "status": "DECLINED",
            "services": [{"name": "Facial"}, {"delivery": delivery}],
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
                wix = self._webhook_module("wix")
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
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                seeded_text = ledger.read_text(encoding="utf-8")
                with self.assertRaises(wix.WebhookError):
                    wix.WixWebhookHandler("secret").on_booking_updated(
                        {
                            "id": "book-early",
                            "status": "CANCELED",
                            "services": [{"name": "Facial"}, {"delivery": delivery}],
                        }
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), seeded_text)
                created = wix.WixWebhookHandler("secret").on_booking_created(booking)
                self.assertEqual(created["recorded"], {"ok": True, "count": 1})
                kept = wix.WixWebhookHandler("secret").on_booking_created(declined)
                self.assertEqual(kept["recorded"], {"ok": True, "count": 1})
                synced = wix.WixWebhookHandler("secret").on_booking_created(
                    {"id": "book-sync", "services": [{"name": "Facial"}, {"delivery": delivery}]}
                )
                self.assertEqual(synced["recorded"], {"ok": True, "count": 1})
                declined_update = wix.WixWebhookHandler("secret").on_booking_updated(
                    {"id": "book-decline", "status": "DECLINED", "services": [{"name": "Facial"}]}
                )
                self.assertIsNone(declined_update["recorded"])
                updated = wix.WixWebhookHandler("secret").on_booking_updated(
                    {"booking": {"id": "book-update", "status": "CANCELED", "services": [{"name": "Facial"}]}}
                )
                self.assertEqual(updated["recorded"], {"ok": True, "count": 1})
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-update:1"', text)
                self.assertNotIn('"transfer_id": "return:book-decline:1"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                again = wix.WixWebhookHandler("secret").on_booking_updated(
                    {"id": "book-update", "status": "cancelled"}
                )
                self.assertEqual(again["recorded"], {"ok": True, "count": 0})
                returned = record_synced_sale("wix", {"id": "book-sync", "status": "CANCELED"})
                self.assertEqual(returned, {"ok": True, "count": 1})
                final = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-sync:1"', final)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', final)
                absent = record_synced_sale("wix", {"id": "book-19", "status": "CANCELED"})
                self.assertIsNone(absent)
                self.assertEqual(ledger.read_text(encoding="utf-8"), final)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_canceled_wix_update_returns_the_delivery_when_the_payload_omits_it(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.updated = []

                    def get(self, endpoint, params=None):
                        return {"booking": {"id": endpoint, "revision": "1"}}

                    def put(self, endpoint, data=None):
                        self.updated.append(endpoint)
                        body = (data or {}).get("booking", {})
                        booking_id = body.get("id")
                        if booking_id == "book-sync":
                            return {"booking": {"id": "book-sync", "status": "CANCELED"}}
                        return {"booking": {"id": booking_id, "revision": "2"}}

                connector = _Posted()
                early = connector.update_appointment("book-1", {"status": "CANCELED"})
                self.assertEqual(early.get("id"), "book-1")
                self.assertEqual(connector.updated, ["/bookings/v2/bookings/book-1"])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 10000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 10000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 10000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-1:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-decline:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-sync:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-2:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "return:book-2:0",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "cape-town",
                                        "destination": "plant",
                                        "milligrams": 500,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                declined = connector.update_appointment("book-decline", {"status": "DECLINED"})
                self.assertEqual(declined.get("id"), "book-decline")
                held = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-decline:1"', held)
                self.assertNotIn('"transfer_id": "return:book-decline:1"', held)
                updated = connector.update_appointment("book-1", {"status": "CANCELED"})
                self.assertEqual(updated.get("id"), "book-1")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-1:1"', text)
                self.assertIn('"source": "cape-town"', text)
                self.assertIn('"destination": "plant"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                self.assertNotIn('"transfer_id": "return:book-decline:1"', text)
                again = connector.update_appointment("book-1", {"status": "cancelled"})
                self.assertEqual(again.get("id"), "book-1")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                absent = connector.update_appointment("book-19", {"status": "CANCELED"})
                self.assertEqual(absent.get("id"), "book-19")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                echoed = connector.update_appointment(
                    "book-sync",
                    {"services": [{"name": "Facial"}]},
                )
                self.assertEqual(echoed.get("status"), "CANCELED")
                echoed_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-sync:1"', echoed_text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', echoed_text)
                before_named = len(connector.updated)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment(
                        "book-1",
                        {
                            "status": "CANCELED",
                            "services": [
                                {"name": "Facial"},
                                {"delivery": {**delivery, "milligrams": 1000}},
                            ],
                        },
                    )
                self.assertEqual(len(connector.updated), before_named)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
                before_conflict = len(connector.updated)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment("book-2", {"status": "CANCELED"})
                self.assertEqual(len(connector.updated), before_conflict + 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), echoed_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_canceled_wix_create_returns_the_delivery_when_the_payload_omits_it(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        body = (data or {}).get("booking", {})
                        service_id = ((body.get("bookedEntity") or {}).get("slot") or {}).get("serviceId")
                        if service_id == "echo-facial":
                            return {
                                "booking": {
                                    "id": "book-echo",
                                    "services": [{"delivery": delivery}],
                                }
                            }
                        return {"booking": {"id": body.get("id") or "wix-created", "revision": "1"}}

                connector = _Posted()
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "id": "book-early",
                            "status": "CANCELED",
                            "services": [{"name": "Facial"}, {"delivery": delivery}],
                        }
                    )
                self.assertEqual(connector.posted, [])
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-omit:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-named:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_appointment(
                    {
                        "id": "book-omit",
                        "status": "CANCELED",
                        "service_id": "echo-facial",
                        "services": [{"name": "Facial"}],
                    }
                )
                self.assertEqual(created.get("id"), "book-echo")
                self.assertEqual(connector.posted, ["/bookings/v2/bookings"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-omit:1"', text)
                self.assertNotIn('"transfer_id": "book-echo:0"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                again = connector.create_appointment(
                    {"id": "book-omit", "status": "cancelled", "services": [{"name": "Facial"}]}
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                absent = connector.create_appointment(
                    {
                        "id": "book-19",
                        "status": "CANCELED",
                        "service_id": "echo-facial",
                        "services": [{"name": "Facial"}],
                    }
                )
                self.assertEqual(absent.get("id"), "book-echo")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                self.assertNotIn('"transfer_id": "book-echo:0"', ledger.read_text(encoding="utf-8"))
                named = connector.create_appointment(
                    {
                        "id": "book-named",
                        "status": "CANCELED",
                        "services": [{"name": "Facial"}, {"delivery": delivery}],
                    }
                )
                self.assertEqual(named.get("revision"), "1")
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-named:1"', named_text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', named_text)
                before_changed = len(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "id": "book-named",
                            "status": "CANCELED",
                            "services": [
                                {"name": "Facial"},
                                {"delivery": {**delivery, "milligrams": 1000}},
                            ],
                        }
                    )
                self.assertEqual(len(connector.posted), before_changed)
                self.assertEqual(ledger.read_text(encoding="utf-8"), named_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_canceled_wix_confirm_returns_the_delivery_when_the_booking_omits_it(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"booking": self.responses.pop(0)}

                connector = _Posted()
                connector.responses.append(
                    {
                        "id": "book-early",
                        "status": "CANCELED",
                        "services": [{"name": "Facial"}, {"delivery": delivery}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.confirm_appointment("book-early")
                self.assertEqual(connector.posted, ["/bookings/v2/bookings/book-early/confirm"])
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
                                        "milligrams": 12000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 12000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 12000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-omit:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-named:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "book-declined:1",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 2000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append(
                    {"id": "book-echo", "status": "CANCELED", "services": [{"name": "Facial"}]}
                )
                confirmed = connector.confirm_appointment("book-omit")
                self.assertEqual(confirmed.get("id"), "book-echo")
                self.assertIn("/bookings/v2/bookings/book-omit/confirm", connector.posted)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-omit:1"', text)
                self.assertNotIn('"transfer_id": "book-echo:0"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                connector.responses.append(
                    {"id": "book-omit", "status": "cancelled", "services": [{"name": "Facial"}]}
                )
                connector.confirm_appointment("book-omit")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {"id": "book-19", "status": "CANCELED", "services": [{"name": "Facial"}]}
                )
                absent = connector.confirm_appointment("book-19")
                self.assertEqual(absent.get("id"), "book-19")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {"id": "book-declined", "status": "DECLINED", "services": [{"name": "Facial"}]}
                )
                declined = connector.confirm_appointment("book-declined")
                self.assertEqual(declined.get("status"), "DECLINED")
                declined_text = ledger.read_text(encoding="utf-8")
                self.assertNotIn('"transfer_id": "return:book-declined:1"', declined_text)
                self.assertIn('"transfer_id": "book-declined:1"', declined_text)
                connector.responses.append(
                    {
                        "id": "book-named",
                        "status": "CANCELED",
                        "services": [{"name": "Facial"}, {"delivery": delivery}],
                    }
                )
                named = connector.confirm_appointment("book-named")
                self.assertEqual(named.get("id"), "book-named")
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "return:book-named:1"', named_text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', named_text)
                before_changed = len(connector.posted)
                connector.responses.append(
                    {
                        "id": "book-named",
                        "status": "CANCELED",
                        "services": [
                            {"name": "Facial"},
                            {"delivery": {**delivery, "milligrams": 1000}},
                        ],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.confirm_appointment("book-named")
                self.assertEqual(len(connector.posted), before_changed + 1)
                self.assertEqual(ledger.read_text(encoding="utf-8"), named_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_shopify_cancel_returns_the_sale_when_the_order_omits_its_id(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Orders(ShopifyB2BConnector):
                    def __init__(self):
                        self.sent = []
                        self.responses = []
                        self.ENDPOINTS = {"orders": "orders.json", "order": "orders/{id}.json"}

                    def post(self, endpoint, data=None):
                        self.sent.append(("post", endpoint))
                        return {"order": self.responses.pop(0)}

                    def put(self, endpoint, data=None):
                        self.sent.append(("put", endpoint))
                        return {"order": self.responses.pop(0)}

                connector = _Orders()
                connector.responses.append({"cancelled_at": "2026-10-02T00:00:00Z"})
                absent = connector.update_order(7, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(absent.get("cancelled_at"), "2026-10-02T00:00:00Z")
                self.assertEqual(connector.sent, [("put", "orders/7.json")])
                self.assertFalse(ledger.exists())
                connector.responses.append(
                    {
                        "cancelled_at": "2026-10-02T00:00:00Z",
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.update_order(9, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(connector.sent, [("put", "orders/7.json"), ("put", "orders/9.json")])
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
                                        "milligrams": 12000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 12000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 12000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 10000,
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "9:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "19:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "8:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "4:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"cancelled_at": "2026-10-02T00:00:00Z"})
                updated = connector.update_order(9, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(updated.get("cancelled_at"), "2026-10-02T00:00:00Z")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn('"return_id": "return:19:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', text)
                connector.responses.append({"cancel_reason": "customer"})
                connector.update_order(9, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append({"order_number": 19, "cancelled_at": "2026-10-02T00:00:00Z"})
                other = connector.update_order(9, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(other.get("order_number"), 19)
                named = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:19:0:sku-serum-c"', named)
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', named)
                connector.responses.append({"financial_status": "voided"})
                connector.create_order({"order_number": 8, "line_items": [{"title": "Signature Facial"}]})
                voided = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:8:0:sku-serum-c"', voided)
                connector.responses.append({"fulfillment_status": "restocked"})
                connector.update_order(4, {"line_items": [{"title": "Signature Facial"}]})
                restocked = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:4:0:sku-serum-c"', restocked)
                connector.responses.append({"line_items": [line]})
                opened = connector.update_order(5, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(opened.get("line_items"), [line])
                self.assertNotIn('"fulfillment_id": "5:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), restocked)
                before_changed = list(connector.sent)
                connector.responses.append(
                    {
                        "cancelled_at": "2026-10-02T00:00:00Z",
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.update_order(19, {"line_items": [{"title": "Signature Facial"}]})
                self.assertEqual(connector.sent, before_changed + [("put", "orders/19.json")])
                self.assertEqual(ledger.read_text(encoding="utf-8"), restocked)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_opencart_cancel_returns_the_sale_when_the_order_omits_its_id(self) -> None:
        product = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                OpenCartConnector = importlib.import_module(
                    "integrations.opencart.connector"
                ).OpenCartConnector

                class _Posted(OpenCartConnector):
                    def __init__(self):
                        self.calls = []
                        self.responses = []

                    def set_customer(self, first_name, last_name, email, telephone):
                        self.calls.append("customer")
                        return {}

                    def add_to_cart(self, product_id, quantity=1, options=None):
                        self.calls.append("cart")
                        return {}

                    def create_order(self):
                        self.calls.append("order")
                        return self.responses.pop(0)

                connector = _Posted()
                connector.responses.append({"status": "canceled"})
                absent = connector.create_appointment(
                    {"order_id": 7, "items": [{"product_id": 7, "quantity": 1}]}
                )
                self.assertEqual(absent.get("status"), "canceled")
                self.assertEqual(connector.calls, ["customer", "cart", "order"])
                self.assertFalse(ledger.exists())
                connector.responses.append(
                    {"status": "canceled", "products": [{**product, "milligrams": "lots"}]}
                )
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"order_id": 9, "items": [{"product_id": 9, "quantity": 1}]}
                    )
                self.assertEqual(connector.calls, ["customer", "cart", "order", "customer", "cart", "order"])
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
                                        "milligrams": 12000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 12000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 12000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 10000,
                                    },
                                },
                                *[
                                    {
                                        "command": "fulfill",
                                        "args": {
                                            "fulfillment_id": f"{order_id}:0:sku-serum-c",
                                            "sku_id": "sku-serum-c",
                                            "location": "cape-town",
                                            "milligrams": 2000,
                                            "kind": "retail",
                                        },
                                    }
                                    for order_id in (9, 19, 8, 4, 5)
                                ],
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"status": "canceled"})
                created = connector.create_appointment(
                    {"order_id": 9, "items": [{"product_id": 9, "quantity": 1}]}
                )
                self.assertEqual(created.get("status"), "canceled")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn('"return_id": "return:19:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', text)
                connector.responses.append({"status": "cancelled"})
                connector.create_appointment(
                    {"order_id": 9, "items": [{"product_id": 9, "quantity": 1}]}
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append({"order_id": 19, "status": "canceled"})
                named = connector.create_appointment(
                    {"order_id": 9, "items": [{"product_id": 9, "quantity": 1}]}
                )
                self.assertEqual(named.get("order_id"), 19)
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:19:0:sku-serum-c"', named_text)
                connector.responses.append({"status_id": 7})
                connector.create_appointment(
                    {"order_id": 8, "items": [{"product_id": 8, "quantity": 1}]}
                )
                status_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:8:0:sku-serum-c"', status_text)
                connector.responses.append({"status": "pending"})
                pending = connector.create_appointment(
                    {"order_id": 4, "items": [{"product_id": 4, "quantity": 1}]}
                )
                self.assertEqual(pending.get("status"), "pending")
                self.assertNotIn('"return_id": "return:4:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), status_text)
                connector.responses.append(
                    {
                        "status": "shipped",
                        "products": [{**product, "location": "johannesburg"}],
                    }
                )
                with self.assertRaises(IntegrationError) as shipped:
                    connector.create_appointment(
                        {"order_id": 5, "items": [{"product_id": 5, "quantity": 1}]}
                    )
                self.assertIn("order number", str(shipped.exception))
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), status_text)
                connector.responses.append({"status": "canceled"})
                connector.create_appointment({"items": [{"product_id": 5, "quantity": 1}]})
                self.assertNotIn('"return_id": "return:5:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), status_text)
                held = ledger.read_text(encoding="utf-8")
                connector.responses.append(
                    {"status": "canceled", "products": [{**product, "milligrams": "lots"}]}
                )
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"order_id": 5, "items": [{"product_id": 5, "quantity": 1}]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), held)
                self.assertNotIn('"return_id": "return:5:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_completed_draft_that_omits_its_id_records_the_request_sale(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "properties": [
                {"name": "location", "value": "cape-town"},
                {"name": "milligrams", "value": "2000"},
            ],
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []
                        self.ENDPOINTS = {"draft_orders": "draft_orders.json"}

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"draft_order": self.responses.pop(0)}

                connector = _Posted()
                connector.responses.append(
                    {
                        "status": "completed",
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "properties": [
                                    {"name": "location", "value": "cape-town"},
                                    {"name": "milligrams", "value": "lots"},
                                ],
                            }
                        ],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {"status": "open", "id": 3, "order_id": 9, "line_items": [{"sku": "sku-serum-c"}]}
                    )
                self.assertEqual(connector.posted, ["draft_orders.json"])
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
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
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"status": "completed", "line_items": [line]})
                created = connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(created.get("status"), "completed")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertNotIn('"fulfillment_id": "3:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                connector.responses.append({"status": "completed", "line_items": [line]})
                connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {"status": "completed", "id": 11, "order_id": 11, "line_items": [line]}
                )
                named = connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(named.get("order_id"), 11)
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "11:0:sku-serum-c"', named_text)
                connector.responses.append({"status": "completed", "line_items": [line]})
                connector.create_draft_order(
                    {"status": "open", "id": 4, "line_items": [{"sku": "sku-serum-c"}]}
                )
                four = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "4:0:sku-serum-c"', four)
                connector.responses.append({"status": "open", "line_items": [line]})
                opened = connector.create_draft_order(
                    {"status": "open", "id": 5, "order_id": 5, "line_items": [{"sku": "sku-serum-c"}]}
                )
                self.assertEqual(opened.get("status"), "open")
                self.assertNotIn('"fulfillment_id": "5:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), four)
                connector.responses.append({"status": "completed", "line_items": [line]})
                with self.assertRaises(IntegrationError) as missing:
                    connector.create_draft_order({"status": "open", "line_items": [{"sku": "sku-serum-c"}]})
                self.assertIn("order number", str(missing.exception))
                self.assertEqual(ledger.read_text(encoding="utf-8"), four)
                connector.responses.append(
                    {
                        "status": "completed",
                        "line_items": [
                            {
                                "sku": "sku-serum-c",
                                "location": "johannesburg",
                                "milligrams": 2000,
                            }
                        ],
                    }
                )
                with self.assertRaises(IntegrationError) as changed:
                    connector.create_draft_order(
                        {"status": "open", "id": 3, "order_id": 9, "line_items": [{"sku": "sku-serum-c"}]}
                    )
                self.assertIn("already exists", str(changed.exception))
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), four)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_completed_draft_that_omits_its_lines_records_the_request_sale(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []
                        self.ENDPOINTS = {"draft_orders": "draft_orders.json"}

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"draft_order": self.responses.pop(0)}

                connector = _Posted()
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {
                            "status": "completed",
                            "order_id": 9,
                            "line_items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.posted, [])
                self.assertFalse(ledger.exists())
                seeded = subprocess.run(
                    [sys.executable, "-m", "domain.ledger"],
                    cwd=hub,
                    input=json.dumps(
                        {
                            "commands": [
                                {
                                    "command": "specify_ingredient",
                                    "args": {
                                        "ingredient_id": "glycerin",
                                        "inci": "Glycerin",
                                        "cas": "56-81-5",
                                    },
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
                                        "milligrams": 20000,
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
                                        "units": 4,
                                        "allocations": [["glycerin", "lot-glycerin", 20000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 20000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"status": "completed"})
                created = connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [line]}
                )
                self.assertEqual(created.get("status"), "completed")
                self.assertNotIn("line_items", created)
                self.assertEqual(connector.posted, ["draft_orders.json"])
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertNotIn('"fulfillment_id": "3:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                connector.responses.append({"status": "completed"})
                again = connector.create_draft_order(
                    {"status": "open", "id": 3, "order_id": 9, "line_items": [line]}
                )
                self.assertEqual(again.get("status"), "completed")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {
                        "status": "completed",
                        "order_id": 22,
                        "line_items": [{**line, "location": "johannesburg", "milligrams": 1500}],
                    }
                )
                before_kept = ledger.read_text(encoding="utf-8")
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {"status": "open", "order_id": 22, "line_items": [line]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
                self.assertNotIn('"fulfillment_id": "22:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"status": "open", "order_id": 23})
                opened = connector.create_draft_order(
                    {"status": "open", "order_id": 23, "line_items": [line]}
                )
                self.assertEqual(opened.get("status"), "open")
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn('"fulfillment_id": "23:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"status": "completed"})
                before_blank = list(connector.posted)
                with self.assertRaises(IntegrationError) as blank:
                    connector.create_draft_order({"status": "open", "line_items": [line]})
                self.assertIn("order number", str(blank.exception))
                self.assertEqual(connector.posted, before_blank + ["draft_orders.json"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                connector.responses.append(
                    {
                        "status": "completed",
                        "order_id": 28,
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                before_lots = list(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.create_draft_order(
                        {"status": "open", "order_id": 28, "line_items": [line]}
                    )
                self.assertEqual(connector.posted, before_lots + ["draft_orders.json"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_kept)
                self.assertNotIn('"fulfillment_id": "28:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"status": "completed", "id": 29})
                noted = connector.create_draft_order(
                    {
                        "status": "open",
                        "line_items": [{"sku": "sku-serum-c"}],
                        "note_attributes": [
                            {"name": "location", "value": "cape-town"},
                            {"name": "milligrams", "value": "2000"},
                        ],
                    }
                )
                self.assertEqual(noted.get("id"), 29)
                self.assertNotIn("note_attributes", noted)
                noted_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "29:0:sku-serum-c"', noted_text)
                self.assertIn('"milligrams": 2000', noted_text)
                connector.responses.append(
                    {
                        "status": "completed",
                        "order_id": 31,
                        "line_items": [{**line, "milligrams": 1500}],
                    }
                )
                kept = connector.create_draft_order(
                    {"status": "open", "order_id": 31, "line_items": [line]}
                )
                self.assertEqual(kept["line_items"][0]["milligrams"], 1500)
                kept_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "31:0:sku-serum-c"', kept_text)
                self.assertIn('"milligrams": 1500', kept_text)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_shopify_appointment_cancel_returns_the_sale_when_the_saved_order_omits_its_id(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.responses = []
                        self.ENDPOINTS = {"orders": "orders.json", "order": "orders/{id}.json"}

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"order": self.responses.pop(0)}

                connector = _Posted()
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "order_number": 9,
                            "fulfillment_status": "fulfilled",
                            "items": [{**line, "milligrams": "lots"}],
                        }
                    )
                self.assertEqual(connector.posted, [])
                self.assertFalse(ledger.exists())
                connector.responses.append({"cancelled_at": "2026-10-02T00:00:00Z"})
                absent = connector.create_appointment(
                    {"order_number": 7, "items": [{"name": "Signature Facial", "quantity": 1}]}
                )
                self.assertEqual(absent.get("cancelled_at"), "2026-10-02T00:00:00Z")
                self.assertEqual(connector.posted, ["orders.json"])
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 8000,
                                    },
                                },
                                {
                                    "command": "fulfill",
                                    "args": {
                                        "fulfillment_id": "19:0:sku-serum-c",
                                        "sku_id": "sku-serum-c",
                                        "location": "cape-town",
                                        "milligrams": 2000,
                                        "kind": "retail",
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"cancelled_at": "2026-10-02T00:00:00Z"})
                created = connector.create_appointment(
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "items": [line],
                    }
                )
                self.assertEqual(created.get("cancelled_at"), "2026-10-02T00:00:00Z")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', text)
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', text)
                self.assertNotIn('"return_id": "return:19:0:sku-serum-c"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', text)
                connector.responses.append({"cancel_reason": "customer"})
                connector.create_appointment(
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "items": [line],
                    }
                )
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append({"order_number": 19, "cancelled_at": "2026-10-02T00:00:00Z"})
                named = connector.create_appointment(
                    {"order_number": 9, "items": [{"name": "Signature Facial", "quantity": 1}]}
                )
                self.assertEqual(named.get("order_number"), 19)
                named_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"return_id": "return:19:0:sku-serum-c"', named_text)
                self.assertIn('"return_id": "return:9:0:sku-serum-c"', named_text)
                connector.responses.append({"financial_status": "pending"})
                pending = connector.create_appointment(
                    {"order_number": 4, "items": [{"name": "Signature Facial", "quantity": 1}]}
                )
                self.assertEqual(pending.get("financial_status"), "pending")
                self.assertNotIn('"fulfillment_id": "4:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                self.assertEqual(ledger.read_text(encoding="utf-8"), named_text)
                held = ledger.read_text(encoding="utf-8")
                connector.responses.append(
                    {
                        "cancelled_at": "2026-10-02T00:00:00Z",
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {"order_number": 4, "items": [{"name": "Signature Facial", "quantity": 1}]}
                    )
                self.assertEqual(ledger.read_text(encoding="utf-8"), held)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_saved_shopify_appointment_draws_the_request_lines_when_it_omits_them(self) -> None:
        line = {
            "sku": "sku-serum-c",
            "location": "cape-town",
            "milligrams": 2000,
            "quantity": 1,
            "price": "25.00",
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                ShopifyB2BConnector = importlib.import_module(
                    "integrations.shopify.connector"
                ).ShopifyB2BConnector

                class _Posted(ShopifyB2BConnector):
                    def __init__(self):
                        self.posted = []
                        self.updated = []
                        self.responses = []
                        self.ENDPOINTS = {"orders": "orders.json", "order": "orders/{id}.json"}

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        return {"order": self.responses.pop(0)}

                    def put(self, endpoint, data=None):
                        self.updated.append(endpoint)
                        return {"order": self.responses.pop(0)}

                connector = _Posted()
                connector.responses.append({"id": 30, "financial_status": "pending"})
                opened = connector.create_appointment(
                    {"order_number": 30, "items": [line]}
                )
                self.assertEqual(opened.get("financial_status"), "pending")
                self.assertEqual(connector.posted, ["orders.json"])
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
                                        "milligrams": 24000,
                                    },
                                },
                                {
                                    "command": "define_formula",
                                    "args": {
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "units": 3,
                                        "allocations": [["glycerin", "lot-glycerin", 24000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 20000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                connector.responses.append({"id": 31, "fulfillment_status": "fulfilled"})
                created = connector.create_appointment({"order_number": 30, "items": [line]})
                self.assertEqual(created.get("id"), 31)
                self.assertNotIn("line_items", created)
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "31:0:sku-serum-c"', text)
                self.assertIn('"milligrams": 2000', text)
                self.assertIn('"location": "cape-town"', text)
                self.assertIn('"transfer_id": "xfer-cape-town"', text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', text)
                self.assertNotIn('"fulfillment_id": "30:0:sku-serum-c"', text)
                connector.responses.append({"id": 31, "fulfillment_status": "fulfilled"})
                again = connector.create_appointment({"order_number": 30, "items": [line]})
                self.assertEqual(again.get("id"), 31)
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                connector.responses.append(
                    {
                        "id": 32,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "paid",
                        "currency": "ZAR",
                    }
                )
                paid = connector.create_appointment({"order_number": 32, "items": [line]})
                self.assertEqual(paid.get("financial_status"), "paid")
                paid_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "32:0:sku-serum-c"', paid_text)
                self.assertIn('"amount_cents": 2500', paid_text)
                self.assertIn('"currency": "ZAR"', paid_text)
                connector.responses.append(
                    {
                        "id": 33,
                        "fulfillment_status": "fulfilled",
                        "line_items": [{**line, "milligrams": 1000}],
                    }
                )
                kept = connector.create_appointment({"order_number": 33, "items": [line]})
                self.assertEqual(kept["line_items"][0]["milligrams"], 1000)
                kept_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "33:0:sku-serum-c"', kept_text)
                self.assertIn('"milligrams": 1000', kept_text)
                self.assertEqual(kept_text.count('"fulfillment_id": "33:0:sku-serum-c"'), 1)
                connector.responses.append({"id": 34, "fulfillment_status": "fulfilled"})
                noted = connector.create_appointment(
                    {
                        "order_number": 34,
                        "items": [{"sku": "sku-serum-c", "quantity": 1, "price": "25.00"}],
                        "note_attributes": [
                            {"name": "location", "value": "cape-town"},
                            {"name": "milligrams", "value": "2000"},
                        ],
                    }
                )
                self.assertEqual(noted.get("id"), 34)
                self.assertNotIn("note_attributes", noted)
                noted_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "34:0:sku-serum-c"', noted_text)
                self.assertIn('"milligrams": 2000', noted_text)
                before_lots = ledger.read_text(encoding="utf-8")
                connector.responses.append(
                    {
                        "id": 35,
                        "fulfillment_status": "fulfilled",
                        "line_items": [{**line, "milligrams": "lots"}],
                    }
                )
                with self.assertRaises(IntegrationError):
                    connector.create_appointment({"order_number": 35, "items": [line]})
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_lots)
                self.assertNotIn('"fulfillment_id": "35:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                before_price = ledger.read_text(encoding="utf-8")
                connector.responses.append(
                    {
                        "id": 36,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "paid",
                        "currency": "ZAR",
                    }
                )
                with self.assertRaises(IntegrationError) as unpaid:
                    connector.create_appointment(
                        {
                            "order_number": 36,
                            "items": [
                                {
                                    "sku": "sku-serum-c",
                                    "location": "cape-town",
                                    "milligrams": 2000,
                                    "quantity": 1,
                                }
                            ],
                        }
                    )
                self.assertIn("amount", str(unpaid.exception))
                self.assertEqual(ledger.read_text(encoding="utf-8"), before_price)
                self.assertNotIn('"fulfillment_id": "36:0:sku-serum-c"', ledger.read_text(encoding="utf-8"))
                connector.responses.append({"id": 44, "fulfillment_status": "fulfilled"})
                already = connector.create_appointment(
                    {
                        "order_number": 9,
                        "fulfillment_status": "fulfilled",
                        "items": [line],
                    }
                )
                self.assertEqual(already.get("id"), 44)
                drawn = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "9:0:sku-serum-c"', drawn)
                self.assertNotIn('"fulfillment_id": "44:0:sku-serum-c"', drawn)
                connector.responses.append({"id": 41, "fulfillment_status": "fulfilled"})
                updated = connector.update_appointment("41", {"items": [line]})
                self.assertEqual(updated.get("id"), 41)
                self.assertEqual(connector.updated, ["orders/41.json"])
                moved = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "41:0:sku-serum-c"', moved)
                connector.responses.append({"id": 41, "fulfillment_status": "fulfilled"})
                repeated = connector.update_appointment("41", {"items": [line]})
                self.assertEqual(connector.updated, ["orders/41.json", "orders/41.json"])
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
                connector.responses.append(
                    {
                        "id": 42,
                        "order_number": 42,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "partially_refunded",
                        "line_items": [line],
                    }
                )
                refunded = connector.create_appointment(
                    {
                        "order_number": 42,
                        "items": [line],
                        "refunds": [
                            {
                                "refund_line_items": [
                                    {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    }
                )
                self.assertEqual(refunded.get("id"), 42)
                self.assertNotIn("refunds", refunded)
                refund_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "42:0:sku-serum-c"', refund_text)
                self.assertIn('"return_id": "return:42:0:sku-serum-c"', refund_text)
                self.assertIn('"transfer_id": "xfer-cape-town"', refund_text)
                self.assertNotIn('"return_id": "return:xfer-cape-town"', refund_text)
                connector.responses.append(
                    {
                        "id": 42,
                        "order_number": 42,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "partially_refunded",
                        "line_items": [line],
                    }
                )
                again_refund = connector.create_appointment(
                    {
                        "order_number": 42,
                        "items": [line],
                        "refunds": [
                            {
                                "refund_line_items": [
                                    {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    }
                )
                self.assertEqual(again_refund.get("id"), 42)
                self.assertEqual(ledger.read_text(encoding="utf-8"), refund_text)
                connector.responses.append(
                    {
                        "id": 43,
                        "order_number": 43,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "partially_refunded",
                        "line_items": [{**line, "quantity": 2}],
                    }
                )
                short_refund = connector.create_appointment(
                    {
                        "order_number": 43,
                        "items": [{**line, "quantity": 2}],
                        "refunds": [
                            {
                                "refund_line_items": [
                                    {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    }
                )
                self.assertEqual(short_refund.get("id"), 43)
                short_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "43:0:sku-serum-c"', short_text)
                self.assertNotIn('"return_id": "return:43:0:sku-serum-c"', short_text)
                connector.responses.append(
                    {
                        "order_number": 45,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "partially_refunded",
                    }
                )
                updated_refund = connector.update_appointment(
                    "45",
                    {
                        "order_number": 45,
                        "items": [line],
                        "refunds": [
                            {
                                "refund_line_items": [
                                    {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                ]
                            }
                        ],
                    },
                )
                self.assertEqual(updated_refund.get("order_number"), 45)
                self.assertNotIn("line_items", updated_refund)
                updated_refund_text = ledger.read_text(encoding="utf-8")
                self.assertIn('"fulfillment_id": "45:0:sku-serum-c"', updated_refund_text)
                self.assertIn('"return_id": "return:45:0:sku-serum-c"', updated_refund_text)
                connector.responses.append(
                    {
                        "id": 42,
                        "order_number": 42,
                        "fulfillment_status": "fulfilled",
                        "financial_status": "partially_refunded",
                        "line_items": [{**line, "location": "johannesburg"}],
                    }
                )
                before_changed_refund = list(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.update_appointment(
                        "42",
                        {
                            "order_number": 42,
                            "items": [{**line, "location": "johannesburg"}],
                            "refunds": [
                                {
                                    "refund_line_items": [
                                        {"quantity": 1, "line_item": {"sku": "sku-serum-c"}},
                                    ]
                                }
                            ],
                        },
                    )
                self.assertEqual(connector.posted, before_changed_refund)
                self.assertEqual(ledger.read_text(encoding="utf-8"), updated_refund_text)
                self.assertNotIn("johannesburg", ledger.read_text(encoding="utf-8"))
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub

    def test_a_wix_save_that_cancels_without_a_delivery_returns_the_one_just_drawn(self) -> None:
        delivery = {
            "sku_id": "sku-serum-c",
            "batch_id": "batch-1",
            "source": "plant",
            "destination": "cape-town",
            "milligrams": 2000,
        }
        services = [{"name": "Facial"}, {"delivery": delivery}]
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
                import importlib
                import types

                root = Path(__file__).resolve().parent / "AmazingSalonApp9ragbot3" / "integrations"
                current = sys.modules.get("integrations")
                if current is None or not getattr(current, "__path__", None):
                    package = types.ModuleType("integrations")
                    package.__path__ = [str(root)]
                    package.__package__ = "integrations"
                    sys.modules["integrations"] = package
                for name in (
                    "integrations.common",
                    "integrations.wix",
                    "integrations.opencart",
                    "integrations.shopify",
                ):
                    loaded = sys.modules.get(name)
                    if loaded is not None and getattr(loaded, "__file__", None) is None:
                        del sys.modules[name]
                IntegrationError = importlib.import_module("integrations.common.exceptions").IntegrationError
                WixBookingsConnector = importlib.import_module(
                    "integrations.wix.connector"
                ).WixBookingsConnector

                class _Posted(WixBookingsConnector):
                    def __init__(self):
                        self.posted = []
                        self.updated = []

                    def post(self, endpoint, data=None):
                        self.posted.append(endpoint)
                        body = (data or {}).get("booking", {})
                        service_id = ((body.get("bookedEntity") or {}).get("slot") or {}).get("serviceId")
                        if service_id == "cancel-echo":
                            return {"booking": {"id": "book-echo", "status": "CANCELED"}}
                        if service_id == "decline-echo":
                            return {"booking": {"id": "book-echo", "status": "DECLINED"}}
                        return {"booking": {"id": body.get("id") or "wix-created", "revision": "1"}}

                    def get(self, endpoint, params=None):
                        return {"booking": {"id": endpoint, "revision": "1"}}

                    def put(self, endpoint, data=None):
                        self.updated.append(endpoint)
                        body = (data or {}).get("booking", {})
                        if body.get("id") == "book-update":
                            return {"booking": {"id": "book-update", "status": "CANCELED"}}
                        return {"booking": {"id": body.get("id"), "revision": "2"}}

                connector = _Posted()
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
                                        "formula_id": "serum-c",
                                        "name": "Vitamin C serum",
                                        "lines": [["glycerin", 8000]],
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
                                        "allocations": [["glycerin", "lot-glycerin", 8000]],
                                    },
                                },
                                {
                                    "command": "transfer",
                                    "args": {
                                        "transfer_id": "xfer-cape-town",
                                        "sku_id": "sku-serum-c",
                                        "batch_id": "batch-1",
                                        "source": "plant",
                                        "destination": "cape-town",
                                        "milligrams": 1000,
                                    },
                                },
                            ]
                        }
                    ),
                    capture_output=True,
                    text=True,
                    check=False,
                    env=os.environ.copy(),
                )
                self.assertEqual(seeded.returncode, 0, seeded.stderr or seeded.stdout)
                created = connector.create_appointment(
                    {
                        "id": "book-draw",
                        "service_id": "cancel-echo",
                        "services": services,
                    }
                )
                self.assertEqual(created.get("id"), "book-echo")
                self.assertEqual(created.get("status"), "CANCELED")
                text = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-draw:1"', text)
                self.assertIn('"transfer_id": "return:book-draw:1"', text)
                self.assertNotIn('"transfer_id": "book-echo:0"', text)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', text)
                again = connector.create_appointment(
                    {
                        "id": "book-draw",
                        "service_id": "cancel-echo",
                        "services": services,
                    }
                )
                self.assertEqual(again.get("id"), "book-echo")
                self.assertEqual(ledger.read_text(encoding="utf-8"), text)
                declined = connector.create_appointment(
                    {
                        "id": "book-decline",
                        "service_id": "decline-echo",
                        "services": services,
                    }
                )
                self.assertEqual(declined.get("status"), "DECLINED")
                held = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-decline:1"', held)
                self.assertNotIn('"transfer_id": "return:book-decline:1"', held)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', held)
                before_changed = len(connector.posted)
                with self.assertRaises(IntegrationError):
                    connector.create_appointment(
                        {
                            "id": "book-draw",
                            "service_id": "cancel-echo",
                            "services": [
                                {"name": "Facial"},
                                {"delivery": {**delivery, "milligrams": 1000}},
                            ],
                        }
                    )
                self.assertEqual(len(connector.posted), before_changed)
                self.assertEqual(ledger.read_text(encoding="utf-8"), held)
                updated = connector.update_appointment(
                    "book-update",
                    {"services": services},
                )
                self.assertEqual(updated.get("status"), "CANCELED")
                moved = ledger.read_text(encoding="utf-8")
                self.assertIn('"transfer_id": "book-update:1"', moved)
                self.assertIn('"transfer_id": "return:book-update:1"', moved)
                self.assertNotIn('"transfer_id": "return:xfer-cape-town"', moved)
                repeated = connector.update_appointment(
                    "book-update",
                    {"services": services},
                )
                self.assertEqual(repeated.get("id"), "book-update")
                self.assertEqual(ledger.read_text(encoding="utf-8"), moved)
            finally:
                if previous_ledger is None:
                    os.environ.pop("SKINTWIN_CHAIN_LEDGER", None)
                else:
                    os.environ["SKINTWIN_CHAIN_LEDGER"] = previous_ledger
                if previous_hub is None:
                    os.environ.pop("SKINTWIN_HUB_ROOT", None)
                else:
                    os.environ["SKINTWIN_HUB_ROOT"] = previous_hub


if __name__ == "__main__":
    unittest.main()
