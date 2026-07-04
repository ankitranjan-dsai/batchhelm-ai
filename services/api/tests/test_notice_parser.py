from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen.canvas import Canvas

from batchhelm_api import notice_parser
from batchhelm_api.notice_parser import NoticeParseError, parse_notice


def text_pdf(text: str) -> bytes:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    canvas.drawString(72, 720, text)
    canvas.save()
    return buffer.getvalue()


def image_notice() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (640, 480), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def encrypted_pdf() -> bytes:
    reader = PdfReader(BytesIO(text_pdf("Private recall notice")))
    writer = PdfWriter()
    writer.add_page(reader.pages[0])
    writer.encrypt("secret")
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def empty_pdf() -> bytes:
    writer = PdfWriter()
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extracts_text_and_page_locator_from_pdf() -> None:
    parsed = parse_notice(
        media_type="application/pdf",
        content=text_pdf("Spinach lot L2418 UPC 008500001010"),
    )

    assert "Spinach lot L2418" in parsed.normalized_text
    assert parsed.page_count == 1
    assert parsed.rendered_pages == ()
    assert parsed.text_pages[0].locator == "page 1"


def test_treats_image_only_pdf_as_scanned(tmp_path: Path) -> None:
    source = tmp_path / "scan.png"
    source.write_bytes(image_notice())
    pdf = BytesIO()
    canvas = Canvas(pdf)
    canvas.drawImage(str(source), 72, 240, width=468, height=360)
    canvas.save()

    parsed = parse_notice(
        media_type="application/pdf",
        content=pdf.getvalue(),
    )

    assert parsed.normalized_text == ""
    assert parsed.page_count == 1
    assert len(parsed.rendered_pages) == 1
    assert parsed.rendered_pages[0].locator == "page 1"
    assert parsed.rendered_pages[0].png_bytes.startswith(b"\x89PNG")


def test_accepts_image_notice_without_fabricated_text() -> None:
    parsed = parse_notice(media_type="image/png", content=image_notice())

    assert parsed.normalized_text == ""
    assert len(parsed.rendered_pages) == 1
    assert parsed.rendered_pages[0].locator == "image 1"
    assert parsed.rendered_pages[0].media_type == "image/png"


def test_normalizes_plain_text_without_changing_words() -> None:
    parsed = parse_notice(
        media_type="text/plain",
        content=b"Recall\r\n\r\n\r\n\r\nSpinach lot L2418\r\n",
    )

    assert parsed.normalized_text == "Recall\n\nSpinach lot L2418"
    assert parsed.text_pages[0].locator == "document"


def test_rejects_pdf_over_page_limit() -> None:
    buffer = BytesIO()
    canvas = Canvas(buffer)
    for _index in range(11):
        canvas.drawString(72, 720, "Recall")
        canvas.showPage()
    canvas.save()

    with pytest.raises(NoticeParseError, match="10 pages"):
        parse_notice(media_type="application/pdf", content=buffer.getvalue())


def test_rejects_malformed_pdf() -> None:
    with pytest.raises(NoticeParseError, match="could not be read"):
        parse_notice(media_type="application/pdf", content=b"%PDF-not-valid")


def test_rejects_pdf_without_pages() -> None:
    with pytest.raises(NoticeParseError, match="no pages"):
        parse_notice(media_type="application/pdf", content=empty_pdf())


def test_rejects_password_protected_pdf() -> None:
    with pytest.raises(NoticeParseError, match="password"):
        parse_notice(media_type="application/pdf", content=encrypted_pdf())


def test_rejects_malformed_image() -> None:
    with pytest.raises(NoticeParseError, match="image could not be read"):
        parse_notice(media_type="image/png", content=b"\x89PNG\r\n\x1a\nbroken")


def test_rejects_text_over_character_limit() -> None:
    with pytest.raises(NoticeParseError, match="100000"):
        parse_notice(
            media_type="text/plain",
            content=("x" * 100_001).encode("utf-8"),
        )


def test_rejects_oversized_decoded_page_before_extracting_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    extracted = False

    class FakeContent:
        def get_data(self) -> bytes:
            return b"x" * (notice_parser.MAX_PAGE_CONTENT_STREAM_BYTES + 1)

    class FakePage:
        def get_contents(self) -> FakeContent:
            return FakeContent()

        def extract_text(self) -> str:
            nonlocal extracted
            extracted = True
            return "must not run"

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    monkeypatch.setattr(
        notice_parser,
        "PdfReader",
        lambda *_args, **_kwargs: FakeReader(),
    )

    with pytest.raises(NoticeParseError, match="content limit"):
        parse_notice(media_type="application/pdf", content=b"%PDF-1.4")
    assert extracted is False
