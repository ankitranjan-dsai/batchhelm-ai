from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

MAX_PDF_PAGES = 10
MAX_NOTICE_CHARACTERS = 100_000
SCANNED_TEXT_THRESHOLD = 200
MAX_RENDERED_PAGES = 3
MAX_PAGE_CONTENT_STREAM_BYTES = 8 * 1024 * 1024
MAX_RENDERED_PIXELS = 25_000_000
IMAGE_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}


class NoticeParseError(ValueError):
    pass


@dataclass(frozen=True)
class NoticeTextPage:
    locator: str
    text: str


@dataclass(frozen=True)
class RenderedNoticePage:
    locator: str
    png_bytes: bytes
    media_type: str = "image/png"


@dataclass(frozen=True)
class ParsedNotice:
    normalized_text: str
    page_count: int
    text_pages: tuple[NoticeTextPage, ...]
    rendered_pages: tuple[RenderedNoticePage, ...]
    warnings: tuple[str, ...]


def _normalize_text(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", normalized)
    return normalized.strip()


def _enforce_character_limit(value: str) -> None:
    if len(value) > MAX_NOTICE_CHARACTERS:
        raise NoticeParseError(
            f"Recall notice text exceeds {MAX_NOTICE_CHARACTERS} characters."
        )


def _parse_text(content: bytes) -> ParsedNotice:
    try:
        normalized = _normalize_text(content.decode("utf-8-sig"))
    except UnicodeDecodeError as exc:
        raise NoticeParseError("Recall notice text could not be read.") from exc
    _enforce_character_limit(normalized)
    pages = (
        (NoticeTextPage(locator="document", text=normalized),)
        if normalized
        else ()
    )
    return ParsedNotice(
        normalized_text=normalized,
        page_count=1,
        text_pages=pages,
        rendered_pages=(),
        warnings=(),
    )


def _parse_image(content: bytes) -> ParsedNotice:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as source:
                width, height = source.size
                if width * height > MAX_RENDERED_PIXELS:
                    raise NoticeParseError(
                        "Recall notice image exceeds the pixel limit."
                    )
                source.load()
                target = source.convert(
                    "RGBA" if source.mode in {"RGBA", "LA"} else "RGB"
                )
                output = BytesIO()
                target.save(output, format="PNG")
    except NoticeParseError:
        raise
    except (
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise NoticeParseError("Recall notice image could not be read.") from exc

    return ParsedNotice(
        normalized_text="",
        page_count=1,
        text_pages=(),
        rendered_pages=(
            RenderedNoticePage(
                locator="image 1",
                png_bytes=output.getvalue(),
            ),
        ),
        warnings=(),
    )


def _page_contains_image(page: Any) -> bool:
    try:
        return len(page.images) > 0
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def _check_page_content_size(page: Any) -> None:
    contents = page.get_contents()
    if contents is None:
        return
    decoded = contents.get_data()
    if len(decoded) > MAX_PAGE_CONTENT_STREAM_BYTES:
        raise NoticeParseError("A PDF page exceeds the decoded content limit.")


def _render_pdf_pages(content: bytes, page_count: int) -> tuple[RenderedNoticePage, ...]:
    rendered: list[RenderedNoticePage] = []
    document: Any | None = None
    try:
        document = pdfium.PdfDocument(content)
        for index in range(min(page_count, MAX_RENDERED_PAGES)):
            page = document[index]
            bitmap: Any | None = None
            try:
                width, height = page.get_size()
                if width * 2 * height * 2 > MAX_RENDERED_PIXELS:
                    raise NoticeParseError(
                        "A rendered PDF page exceeds the pixel limit."
                    )
                bitmap = page.render(scale=2)
                image = bitmap.to_pil()
                output = BytesIO()
                image.save(output, format="PNG")
                rendered.append(
                    RenderedNoticePage(
                        locator=f"page {index + 1}",
                        png_bytes=output.getvalue(),
                    )
                )
            finally:
                if bitmap is not None:
                    bitmap.close()
                page.close()
    except NoticeParseError:
        raise
    except Exception as exc:
        raise NoticeParseError("Scanned PDF pages could not be rendered.") from exc
    finally:
        if document is not None:
            document.close()
    return tuple(rendered)


def _parse_pdf(content: bytes) -> ParsedNotice:
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        if reader.is_encrypted:
            try:
                decrypted = reader.decrypt("")
            except Exception as exc:
                raise NoticeParseError(
                    "A password-protected PDF notice is not supported."
                ) from exc
            if not decrypted:
                raise NoticeParseError(
                    "A password-protected PDF notice is not supported."
                )

        page_count = len(reader.pages)
        if page_count == 0:
            raise NoticeParseError("Recall notice PDF contains no pages.")
        if page_count > MAX_PDF_PAGES:
            raise NoticeParseError(
                f"Recall notice PDF cannot exceed {MAX_PDF_PAGES} pages."
            )

        text_pages: list[NoticeTextPage] = []
        page_text: list[str] = []
        source_pages: list[Any] = []
        for index, page in enumerate(reader.pages, start=1):
            _check_page_content_size(page)
            normalized = _normalize_text(page.extract_text() or "")
            page_text.append(normalized)
            source_pages.append(page)
            if normalized:
                text_pages.append(
                    NoticeTextPage(
                        locator=f"page {index}",
                        text=normalized,
                    )
                )
            combined = _normalize_text("\n\n".join(page_text))
            _enforce_character_limit(combined)

        normalized_text = _normalize_text("\n\n".join(page_text))
        sampled_text = "".join(page_text[:MAX_RENDERED_PAGES])
        sampled_characters = sum(
            1 for character in sampled_text if not character.isspace()
        )
        sampled_pages = source_pages[:MAX_RENDERED_PAGES]
        appears_scanned = sampled_characters < SCANNED_TEXT_THRESHOLD and (
            sampled_characters == 0
            or any(_page_contains_image(page) for page in sampled_pages)
        )
        rendered_pages = (
            _render_pdf_pages(content, page_count) if appears_scanned else ()
        )
        parse_warnings = (
            ("Low-text PDF pages were rendered for visual extraction.",)
            if appears_scanned
            else ()
        )
        return ParsedNotice(
            normalized_text=normalized_text,
            page_count=page_count,
            text_pages=tuple(text_pages),
            rendered_pages=rendered_pages,
            warnings=parse_warnings,
        )
    except NoticeParseError:
        raise
    except (FileNotDecryptedError, PdfReadError, EOFError, OSError, ValueError) as exc:
        raise NoticeParseError("Recall notice PDF could not be read.") from exc
    except Exception as exc:
        raise NoticeParseError("Recall notice PDF could not be read.") from exc


def parse_notice(*, media_type: str, content: bytes) -> ParsedNotice:
    if media_type == "text/plain":
        return _parse_text(content)
    if media_type in IMAGE_MEDIA_TYPES:
        return _parse_image(content)
    if media_type == "application/pdf":
        return _parse_pdf(content)
    raise NoticeParseError("Recall notice media type is not supported.")
