from __future__ import annotations

import pytest

from batchhelm_api.inventory_parser import (
    InventoryParseError,
    parse_inventory_csv,
)


def test_maps_header_aliases_and_builds_inventory_rows() -> None:
    parsed = parse_inventory_csv(
        b"Store Name,Item SKU,Product Name,Lot Code,UPC,Qty,Location,Supplier\n"
        b"Store A,SPN10Z,Spinach 10 oz,L2418,008500001010,6,"
        b"Back Room,Central Farms\n"
    )

    assert parsed.rows[0].id == "inventory-row-2"
    assert parsed.rows[0].store == "Store A"
    assert parsed.rows[0].on_hand == 6
    assert parsed.summary.mapped_headers["Store Name"] == "store"
    assert parsed.summary.accepted_rows == 1
    assert parsed.summary.stores == 1


def test_reports_invalid_rows_without_dropping_valid_rows() -> None:
    parsed = parse_inventory_csv(
        b"store,product,lot,on_hand\n"
        b"Store A,Spinach,L2418,6\n"
        b"Store B,Spinach,L2419,-2\n"
    )

    assert len(parsed.rows) == 1
    assert parsed.summary.rejected_rows == 1
    assert "row 3" in parsed.summary.warnings[0].lower()
    assert "-2" not in parsed.summary.warnings[0]


def test_rejects_duplicate_inventory_identity() -> None:
    parsed = parse_inventory_csv(
        b"store,sku,product,lot,on_hand,location\n"
        b"Store A,S1,Spinach,L1,2,Cooler\n"
        b"Store A,S1,Spinach,L1,3,Cooler\n"
    )

    assert parsed.summary.accepted_rows == 1
    assert parsed.summary.rejected_rows == 1
    assert "duplicate" in parsed.summary.warnings[0].lower()


def test_rejects_csv_with_no_valid_rows() -> None:
    with pytest.raises(InventoryParseError, match="valid inventory"):
        parse_inventory_csv(b"store,product,lot,on_hand\n,,,bad\n")


def test_rejects_missing_required_headers() -> None:
    with pytest.raises(InventoryParseError, match="required headers"):
        parse_inventory_csv(b"store,product,on_hand\nStore A,Spinach,2\n")


def test_rejects_two_headers_mapped_to_same_field() -> None:
    with pytest.raises(InventoryParseError, match="multiple headers"):
        parse_inventory_csv(
            b"store,branch,product,lot,on_hand\n"
            b"Store A,Store A,Spinach,L1,2\n"
        )


def test_rejects_more_than_5000_data_rows() -> None:
    rows = [b"Store A,Spinach,L1,1"] * 5001
    content = b"store,product,lot,on_hand\n" + b"\n".join(rows) + b"\n"

    with pytest.raises(InventoryParseError, match="5000"):
        parse_inventory_csv(content)


def test_rejects_more_than_128_columns() -> None:
    headers = [f"column_{index}" for index in range(125)]
    headers.extend(["store", "product", "lot", "on_hand"])
    content = (",".join(headers) + "\n" + ",".join(["x"] * 129)).encode()

    with pytest.raises(InventoryParseError, match="128"):
        parse_inventory_csv(content)
