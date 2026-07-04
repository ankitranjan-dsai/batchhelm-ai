from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from io import StringIO

from batchhelm_api.intake_models import InventoryImportSummary
from batchhelm_api.models import InventoryItem

MAX_ROWS = 5_000
MAX_COLUMNS = 128

HEADER_ALIASES = {
    "store": {"store", "store_name", "location_name", "branch"},
    "sku": {"sku", "item_sku", "stock_code"},
    "product": {"product", "product_name", "item", "description"},
    "lot": {"lot", "lot_code", "batch", "batch_code"},
    "upc": {"upc", "barcode", "gtin"},
    "on_hand": {"on_hand", "qty", "quantity", "stock"},
    "location": {"location", "bin", "stock_location"},
    "supplier_alias": {"supplier", "supplier_alias", "vendor"},
}
REQUIRED = {"store", "product", "lot", "on_hand"}


class InventoryParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedInventory:
    rows: tuple[InventoryItem, ...]
    summary: InventoryImportSummary


def _normalize_header(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", normalized).strip("_")


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    if len(fieldnames) > MAX_COLUMNS:
        raise InventoryParseError(
            f"Inventory CSV cannot exceed {MAX_COLUMNS} columns."
        )

    mapped: dict[str, str] = {}
    claimed: dict[str, str] = {}
    for original in fieldnames:
        normalized = _normalize_header(original)
        canonical = next(
            (
                name
                for name, aliases in HEADER_ALIASES.items()
                if normalized in aliases
            ),
            None,
        )
        if canonical is None:
            continue
        if canonical in claimed:
            raise InventoryParseError(
                "Inventory CSV has multiple headers for the same field."
            )
        claimed[canonical] = original
        mapped[original] = canonical

    missing = REQUIRED - set(claimed)
    if missing:
        raise InventoryParseError(
            "Inventory CSV is missing required headers."
        )
    return mapped


def _value(
    row: dict[str | None, str | list[str] | None],
    source_by_field: dict[str, str],
    field: str,
) -> str:
    raw = row.get(source_by_field[field], "")
    return raw.strip() if isinstance(raw, str) else ""


def parse_inventory_csv(content: bytes) -> ParsedInventory:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InventoryParseError("Inventory CSV must use UTF-8 encoding.") from exc

    try:
        reader = csv.DictReader(StringIO(text, newline=""))
        if not reader.fieldnames:
            raise InventoryParseError("Inventory CSV must include a header row.")

        fieldnames = [field or "" for field in reader.fieldnames]
        mapped_headers = _map_headers(fieldnames)
        source_by_field = {
            canonical: original
            for original, canonical in mapped_headers.items()
        }
        rows: list[InventoryItem] = []
        warnings: list[str] = []
        identities: set[tuple[str, str, str, str]] = set()
        rejected = 0

        for row_number, row in enumerate(reader, start=2):
            if row_number - 1 > MAX_ROWS:
                raise InventoryParseError(
                    f"Inventory CSV cannot exceed {MAX_ROWS} data rows."
                )

            store = _value(row, source_by_field, "store")
            product = _value(row, source_by_field, "product")
            lot = _value(row, source_by_field, "lot")
            quantity = _value(row, source_by_field, "on_hand")
            if not store or not product or not lot:
                rejected += 1
                warnings.append(
                    f"Row {row_number} was rejected because required values are missing."
                )
                continue
            if not re.fullmatch(r"\d+", quantity):
                rejected += 1
                warnings.append(
                    f"Row {row_number} was rejected because on_hand must be "
                    "a non-negative integer."
                )
                continue

            sku = _value(row, source_by_field, "sku") if "sku" in source_by_field else ""
            upc = _value(row, source_by_field, "upc") if "upc" in source_by_field else ""
            location = (
                _value(row, source_by_field, "location")
                if "location" in source_by_field
                else ""
            )
            supplier_alias = (
                _value(row, source_by_field, "supplier_alias")
                if "supplier_alias" in source_by_field
                else ""
            )
            identity = tuple(
                value.casefold() for value in (store, sku, lot, location)
            )
            if identity in identities:
                rejected += 1
                warnings.append(
                    f"Row {row_number} was rejected as a duplicate inventory record."
                )
                continue

            identities.add(identity)
            rows.append(
                InventoryItem(
                    id=f"inventory-row-{row_number}",
                    store=store,
                    sku=sku,
                    product=product,
                    lot=lot,
                    upc=upc,
                    on_hand=int(quantity),
                    location=location,
                    supplier_alias=supplier_alias,
                )
            )
    except InventoryParseError:
        raise
    except csv.Error as exc:
        raise InventoryParseError("Inventory CSV could not be parsed.") from exc

    if not rows:
        raise InventoryParseError(
            "Inventory CSV does not contain any valid inventory rows."
        )

    summary = InventoryImportSummary(
        accepted_rows=len(rows),
        rejected_rows=rejected,
        stores=len({item.store for item in rows}),
        mapped_headers=mapped_headers,
        warnings=warnings,
    )
    return ParsedInventory(rows=tuple(rows), summary=summary)
