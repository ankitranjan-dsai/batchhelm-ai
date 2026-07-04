from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import pytest

from batchhelm_api.intake_extraction import (
    IntakeCompilationError,
    compile_incident_snapshot,
    extract_notice_draft,
    safe_literal_extraction,
)
from batchhelm_api.intake_models import (
    IntakeArtifact,
    IntakeArtifactRole,
    RecallCriteriaDraft,
    RecallIncidentDraft,
)
from batchhelm_api.inventory_parser import parse_inventory_csv
from batchhelm_api.models import (
    IncidentStatus,
    ModelImageJSONRequest,
    ModelJSONRequest,
    ModelJSONResponse,
    OutputSource,
    Severity,
)
from batchhelm_api.notice_parser import (
    NoticeTextPage,
    ParsedNotice,
    RenderedNoticePage,
)
from batchhelm_api.qwen import QwenGateway
from tests.conftest import fallback_gateway, make_settings, scripted_gateway

NOTICE = (
    "Spinach 10 oz\n"
    "Central Farms supplier alert\n"
    "Affected lots L2418 and L2419\n"
    "UPC 008500001010. Possible contamination risk."
)


class SequenceGateway(QwenGateway):
    def __init__(self, image_responses: list[dict[str, object]]) -> None:
        super().__init__(make_settings(api_key="test-key"))
        self.image_responses = list(image_responses)
        self.image_calls = 0

    async def complete_json(self, request: ModelJSONRequest) -> ModelJSONResponse:
        raise AssertionError("Text completion was not expected.")

    async def complete_image_json(
        self,
        request: ModelImageJSONRequest,
    ) -> ModelJSONResponse:
        response = self.image_responses[self.image_calls]
        self.image_calls += 1
        return ModelJSONResponse(
            provider="qwen",
            model=self.settings.qwen_vision_model,
            used_fallback=False,
            content=response,
        )


def notice_artifact() -> IntakeArtifact:
    return IntakeArtifact(
        id="notice-1",
        intake_id="intake-1",
        role=IntakeArtifactRole.recall_notice,
        original_filename="notice.pdf",
        stored_filename="notice-1.pdf",
        media_type="application/pdf",
        size_bytes=100,
        sha256="a" * 64,
        relative_path="intakes/intake-1/notice-1.pdf",
        created_at="2026-07-04T08:00:00+00:00",
    )


def parsed_text_notice(text: str = NOTICE) -> ParsedNotice:
    return ParsedNotice(
        normalized_text=text,
        page_count=1,
        text_pages=(NoticeTextPage(locator="page 1", text=text),),
        rendered_pages=(),
        warnings=(),
    )


def structured_extraction(
    *,
    product: str = "Spinach 10 oz",
    confidence: int = 94,
) -> dict[str, object]:
    return {
        "product_name": {"value": product, "confidence": confidence},
        "affected_lots": {
            "value": ["L2418", "L2419"],
            "confidence": confidence,
        },
        "upcs": {"value": ["008500001010"], "confidence": confidence},
        "risk_level": {"value": "high", "confidence": confidence},
        "reason": {
            "value": "Possible contamination",
            "confidence": confidence,
        },
        "source": {"value": "Central Farms", "confidence": confidence},
    }


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


@pytest.mark.asyncio
async def test_qwen_text_extraction_returns_field_evidence() -> None:
    result = await extract_notice_draft(
        gateway=scripted_gateway(structured_extraction()),
        parsed_notice=parsed_text_notice(),
        notice_artifact=notice_artifact(),
    )

    assert result.criteria.product_name == "Spinach 10 oz"
    assert result.criteria.affected_lots == ["L2418", "L2419"]
    assert result.review_required is False
    assert all(item.source == OutputSource.qwen for item in result.evidence)
    assert {item.locator for item in result.evidence} == {"page 1"}


@pytest.mark.asyncio
async def test_unavailable_qwen_returns_literal_review_draft() -> None:
    result = await extract_notice_draft(
        gateway=fallback_gateway(),
        parsed_notice=parsed_text_notice(),
        notice_artifact=notice_artifact(),
    )

    assert result.review_required is True
    assert result.criteria.affected_lots == ["L2418", "L2419"]
    assert all(
        item.source == OutputSource.deterministic for item in result.evidence
    )


@pytest.mark.asyncio
async def test_hallucinated_text_values_are_discarded() -> None:
    response = structured_extraction(product="Kale")
    response["affected_lots"] = {
        "value": ["L2418", "X9999"],
        "confidence": 99,
    }

    result = await extract_notice_draft(
        gateway=scripted_gateway(response),
        parsed_notice=parsed_text_notice(),
        notice_artifact=notice_artifact(),
    )

    assert result.criteria.product_name == "Spinach 10 oz"
    assert "X9999" not in result.criteria.affected_lots
    assert "Kale" not in result.criteria.product_name
    assert result.review_required is True


@pytest.mark.asyncio
async def test_high_confidence_image_extraction_stops_after_first_page() -> None:
    gateway = SequenceGateway(
        [structured_extraction(), structured_extraction(product="Kale")]
    )
    parsed = ParsedNotice(
        normalized_text="",
        page_count=2,
        text_pages=(),
        rendered_pages=(
            RenderedNoticePage(locator="page 1", png_bytes=b"page-one"),
            RenderedNoticePage(locator="page 2", png_bytes=b"page-two"),
        ),
        warnings=(),
    )

    result = await extract_notice_draft(
        gateway=gateway,
        parsed_notice=parsed,
        notice_artifact=notice_artifact(),
    )

    assert gateway.image_calls == 1
    assert result.criteria.product_name == "Spinach 10 oz"
    assert {item.locator for item in result.evidence} == {"page 1"}


@pytest.mark.asyncio
async def test_conflicting_image_pages_require_review() -> None:
    gateway = SequenceGateway(
        [
            structured_extraction(product="Spinach 10 oz", confidence=70),
            structured_extraction(product="Kale 10 oz", confidence=70),
        ]
    )
    parsed = ParsedNotice(
        normalized_text="",
        page_count=2,
        text_pages=(),
        rendered_pages=(
            RenderedNoticePage(locator="page 1", png_bytes=b"page-one"),
            RenderedNoticePage(locator="page 2", png_bytes=b"page-two"),
        ),
        warnings=(),
    )

    result = await extract_notice_draft(
        gateway=gateway,
        parsed_notice=parsed,
        notice_artifact=notice_artifact(),
    )

    product_evidence = [
        item
        for item in result.evidence
        if item.field_path == "criteria.product_name"
    ]
    assert gateway.image_calls == 2
    assert result.review_required is True
    assert product_evidence
    assert all(item.requires_review for item in product_evidence)


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
