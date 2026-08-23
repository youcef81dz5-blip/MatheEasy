"""MinerU Cloud API extractor.

Uses the official free MinerU Open API (https://mineru.net/apiManage/docs):
- Precision API (token, <=200MB / <=200 pages, formulas + tables + OCR)
- Flash/Agent API (no token, <=10MB / <=20 pages, markdown only)

Strategy: Precision when MINERU_TOKEN exists, automatic Flash fallback.
"""

import os
from pathlib import Path

try:
    from mineru import MinerU
except ImportError:  # pragma: no cover
    MinerU = None

FLASH_MAX_BYTES = 10 * 1024 * 1024
FLASH_MAX_PAGES = 20

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".jp2"}


class ExtractionResult:
    def __init__(self, markdown, images=None, meta=None):
        self.markdown = markdown or ""
        self.images = images or {}
        self.meta = meta or {}


def _page_count(path: Path):
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return 1
    if ext == ".pdf":
        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz

            with fitz.open(str(path)) as doc:
                return doc.page_count
        except Exception:
            return None
    return None


def _client(token):
    if MinerU is None:
        raise RuntimeError(
            "مكتبة mineru-open-sdk غير مثبتة. نفّذ: pip install mineru-open-sdk"
        )
    if token:
        try:
            return MinerU(token)
        except TypeError:
            return MinerU(token=token)
    return MinerU()


def _result_from(obj, meta):
    md = getattr(obj, "markdown", None) or ""
    images = getattr(obj, "images", None) or {}
    return ExtractionResult(md, images, meta)


def _flash(path: Path, language, errors):
    client = _client(None)
    try:
        result = client.flash_extract(str(path), language=language)
    except TypeError:
        result = client.flash_extract(str(path))
    return _result_from(result, {"api": "flash (بدون Token)", "language": language})


def _precision(path: Path, language, ocr, formula, table, timeout, token, errors):
    client = _client(token)
    kwargs = dict(
        language=language, ocr=ocr, formula=formula, table=table, timeout=timeout
    )
    try:
        result = client.extract(str(path), **kwargs)
    except TypeError:
        result = client.extract(str(path))
    return _result_from(
        result,
        {"api": "precision (vlm)", "language": language},
    )


def extract(
    file_path,
    language="ar",
    ocr=True,
    formula=True,
    table=True,
    force_flash=False,
    timeout=600,
) -> ExtractionResult:
    """Extract a document to Markdown (+ LaTeX formulas) via MinerU cloud API."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"الملف غير موجود: {path}")

    token = os.getenv("MINERU_TOKEN", "").strip() or None
    size = path.stat().st_size
    pages = _page_count(path)
    flash_ok = size <= FLASH_MAX_BYTES and (pages is None or pages <= FLASH_MAX_PAGES)
    errors = []

    if force_flash:
        if not flash_ok:
            raise RuntimeError(
                "الملف يتجاوز حدود Flash API (10MB / 20 صفحة). أزل خيار Flash أو استخدم Token."
            )
        return _flash(path, language, errors)

    if not token:
        if not flash_ok:
            raise RuntimeError(
                "لا يوجد MINERU_TOKEN والملف يتجاوز حدود Flash (10MB / 20 صفحة).\n"
                "احصل على Token مجاني من https://mineru.net/apiManage/token"
            )
        return _flash(path, language, errors)

    try:
        return _precision(path, language, ocr, formula, table, timeout, token, errors)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Precision API: {exc}")
        if flash_ok:
            try:
                result = _flash(path, language, errors)
                result.meta["fallback"] = True
                result.meta["errors"] = errors
                return result
            except Exception as exc2:  # noqa: BLE001
                errors.append(f"Flash API: {exc2}")
        raise RuntimeError("فشل الاستخراج:\n" + "\n".join(errors)) from exc
