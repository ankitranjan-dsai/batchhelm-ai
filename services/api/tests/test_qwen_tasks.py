from __future__ import annotations

from batchhelm_api import qwen_tasks
from batchhelm_api.models import OutputSource, Severity
from batchhelm_api.sample_data import build_demo_incident
from batchhelm_api.workflow import analyze_recall_incident
from tests.conftest import fallback_gateway, scripted_gateway


async def test_extract_recall_falls_back_without_key() -> None:
    outcome = await qwen_tasks.extract_recall(fallback_gateway(), build_demo_incident())

    assert outcome.used_fallback is True
    assert outcome.source == OutputSource.deterministic
    assert outcome.value.affected_lots == ["L2418", "L2419", "L2420", "L2421", "L2422"]


async def test_extract_recall_uses_live_qwen_output() -> None:
    gateway = scripted_gateway(
        {
            "product_name": "Spinach 10 oz",
            "affected_lots": ["L2418", "L2419"],
            "upcs": ["008500001010"],
            "supplier": "Central Farms",
            "risk_level": "critical",
            "urgency": "Remove now",
            "summary": "Contamination risk",
            "confidence": 94}
    )

    outcome = await qwen_tasks.extract_recall(gateway, build_demo_incident())

    assert outcome.used_fallback is False
    assert outcome.source == OutputSource.qwen
    assert outcome.value.risk_level == Severity.critical
    assert outcome.value.confidence == 94


async def test_invalid_qwen_output_repairs_to_fallback() -> None:
    # confidence over 100 violates the schema -> must repair, not crash.
    gateway = scripted_gateway(
        {"product_name": "X", "risk_level": "high", "confidence": 999}
    )

    outcome = await qwen_tasks.extract_recall(gateway, build_demo_incident())

    assert outcome.used_fallback is True
    assert outcome.source == OutputSource.deterministic


async def test_generate_briefing_carries_source_metadata() -> None:
    incident = build_demo_incident()
    analysis = analyze_recall_incident(incident)

    outcome = await qwen_tasks.generate_briefing(fallback_gateway(), incident, analysis)

    assert outcome.value.source == OutputSource.deterministic
    assert outcome.value.used_fallback is True
    assert outcome.value.headline


async def test_draft_customer_notice_live() -> None:
    gateway = scripted_gateway(
        {
            "subject": "Recall notice",
            "body": "Please return the product.",
            "audience": "All customers",
            "confidence": 80}
    )

    outcome = await qwen_tasks.draft_customer_notice(gateway, build_demo_incident(), 23)

    assert outcome.source == OutputSource.qwen
    assert outcome.value.subject == "Recall notice"
