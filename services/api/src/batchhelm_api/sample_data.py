from __future__ import annotations

from batchhelm_api.models import (
    IncidentStatus,
    InventoryItem,
    RecallCriteria,
    RecallIncidentInput,
    Severity,
)


DEMO_NOTICE_TEXT = """
Supplier alert CF-2026-06-18: Central Farms spinach 10 oz clamshells may be
affected by a contamination event. Affected lots are L2418, L2419, L2420,
L2421, and L2422. Product UPC 008500001010 must be removed from sale,
quarantined, and held for supplier disposition instructions.
"""


def build_demo_incident() -> RecallIncidentInput:
    return RecallIncidentInput(
        id="recall-spinach-2026-06",
        product="Spinach 10 oz",
        lot_range="L2418-L2422",
        status=IncidentStatus.active,
        opened_at="Today 8:12 AM",
        stores=["Store A", "Store B"],
        criteria=RecallCriteria(
            product_name="Spinach 10 oz",
            affected_lots=["L2418", "L2419", "L2420", "L2421", "L2422"],
            upcs=["008500001010"],
            risk_level=Severity.high,
            reason="Possible contamination risk",
            source="Supplier alert CF-2026-06-18",
        ),
        notice_text=DEMO_NOTICE_TEXT.strip(),
        inventory=[
            InventoryItem(
                id="inv-1",
                store="Store A",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2418",
                upc="008500001010",
                on_hand=6,
                location="Back Room 1",
                supplier_alias="CF Baby Spinach 10OZ",
            ),
            InventoryItem(
                id="inv-2",
                store="Store A",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2419",
                upc="008500001010",
                on_hand=4,
                location="Back Room 1",
                supplier_alias="CF Baby Spinach 10OZ",
            ),
            InventoryItem(
                id="inv-3",
                store="Store A",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2420",
                upc="008500001010",
                on_hand=3,
                location="Cooler A",
                supplier_alias="Central Farms Greens 10OZ",
            ),
            InventoryItem(
                id="inv-4",
                store="Store B",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2418",
                upc="008500001010",
                on_hand=5,
                location="Back Room 2",
                supplier_alias="CF Baby Spinach 10OZ",
            ),
            InventoryItem(
                id="inv-5",
                store="Store B",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2421",
                upc="008500001010",
                on_hand=2,
                location="Cooler B",
                supplier_alias="Central Farms Greens 10OZ",
            ),
            InventoryItem(
                id="inv-6",
                store="Store B",
                sku="SPN10Z",
                product="Spinach 10 oz",
                lot="L2422",
                upc="008500001010",
                on_hand=3,
                location="Back Room 2",
                supplier_alias="CF Baby Spinach 10OZ",
            ),
        ],
    )
