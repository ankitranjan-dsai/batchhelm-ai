from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from batchhelm_api.intake_extraction import (
    IntakeCompilationError,
    compile_incident_snapshot,
    safe_literal_extraction,
)
from batchhelm_api.intake_models import RecallCriteriaDraft, RecallIncidentDraft
from batchhelm_api.inventory_parser import parse_inventory_csv
from batchhelm_api.models import IncidentStatus, OutputSource, Severity

NOTICE = (
    "Spinach 10 oz\n"
    "Central Farms supplier alert\n"
    "Affected lots L2418 and L2419\n"
    "UPC 008500001010. Possible contamination risk."
)


def valid_draft() -> RecallIncidentDraft:
    inventory = parse_inventory_csv(
        b"store,product,lot,on_hand\n"
        b"Store B,Spinach,L2418,6\n"
        b"Store A,Spinach,L2419,2\n"
    )
    return RecallIncidentDraft(
        criteria=RecallCriteriaDraft(
            product_name="Spinach",
            affected_lots=["L2418"],
            upcs=["008500001010"],
            risk_level=Severity.high,
            reason="Possible contamination",
            source="Central Farms alert",
        ),
        notice_text=NOTICE,
        inventory=list(inventory.rows),
        stores=["Store B", "Store A", "Store A"],
        import_summary=inventory.summary,
        review_required=False,
    )


def test_safe_extraction_uses_only_verbatim_notice_values() -> None:
    result = safe_literal_extraction(NOTICE)

    assert result.criteria.affected_lots == ["L2418", "L2419"]
    assert result.criteria.upcs == ["008500001010"]
    assert result.criteria.product_name == "Spinach 10 oz"
    assert result.review_required is True
    assert all(item.confidence <= 65 for item in result.evidence)
    assert all(item.source == OutputSource.deterministic for item in result.evidence)


def test_safe_extraction_never_copies_demo_values() -> None:
    result = safe_literal_extraction("Recall notice without identifiers")

    assert result.criteria.product_name == ""
    assert result.criteria.affected_lots == []
    assert result.criteria.upcs == []
    assert result.criteria.risk_level is None


def test_safe_extraction_does_not_treat_reference_date_as_upc() -> None:
    result = safe_literal_extraction(
        "Product: Frozen peas\nReference 20260618\nNo barcode was provided."
    )

    assert result.criteria.upcs == []


def test_generic_heading_is_not_used_as_product() -> None:
    result = safe_literal_extraction(
        "URGENT RECALL NOTICE\nProduct: Frozen peas\nAffected lot FP2401"
    )

    assert result.criteria.product_name == ""
    assert result.criteria.affected_lots == ["FP2401"]


def test_compiler_requires_confirmed_criteria_and_inventory() -> None:
    snapshot = compile_incident_snapshot(
        "intake-1",
        valid_draft(),
        now=datetime(2026, 7, 4, 8, 30, tzinfo=timezone.utc),
    )

    assert snapshot.id.startswith("intake-intake-1-")
    assert snapshot.status == IncidentStatus.active
    assert snapshot.opened_at == "2026-07-04T08:30:00+00:00"
    assert snapshot.stores == ["Store A", "Store B"]
    assert snapshot.inventory[0].lot == "L2418"


def test_compiler_identity_is_stable_for_same_intake() -> None:
    now = datetime(2026, 7, 4, 8, 30, tzinfo=timezone.utc)

    first = compile_incident_snapshot("intake-1", valid_draft(), now=now)
    replay = compile_incident_snapshot("intake-1", valid_draft(), now=now)

    assert replay.id == first.id


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda draft: setattr(draft.criteria, "product_name", ""), "product"),
        (
            lambda draft: (
                setattr(draft.criteria, "affected_lots", []),
                setattr(draft.criteria, "upcs", []),
            ),
            "lot or UPC",
        ),
        (lambda draft: setattr(draft.criteria, "risk_level", None), "risk"),
        (lambda draft: setattr(draft.criteria, "reason", ""), "reason"),
        (lambda draft: setattr(draft.criteria, "source", ""), "source"),
        (lambda draft: setattr(draft, "notice_text", ""), "notice"),
        (lambda draft: setattr(draft, "inventory", []), "inventory"),
    ],
)
def test_compiler_rejects_incomplete_snapshot(
    mutation: Callable[[RecallIncidentDraft], object],
    message: str,
) -> None:
    draft = valid_draft()
    mutation(draft)

    with pytest.raises(IntakeCompilationError, match=message):
        compile_incident_snapshot("intake-1", draft)
