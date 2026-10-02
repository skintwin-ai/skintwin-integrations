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
    record_synced_catalog,
    record_synced_sale,
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

                    def post(self, endpoint, data):
                        self.sent.append(("post", data["product"].get("title")))
                        return {"product": data["product"]}

                    def put(self, endpoint, data):
                        self.sent.append(("put", data["product"].get("title")))
                        return {"product": data["product"]}

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

                    def post(self, endpoint, data):
                        order = data["order"]
                        self.sent.append(("post", order.get("order_number")))
                        return {"order": order}

                    def put(self, endpoint, data):
                        order = data["order"]
                        self.sent.append(("put", order.get("order_number")))
                        return {"order": order}

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


if __name__ == "__main__":
    unittest.main()
