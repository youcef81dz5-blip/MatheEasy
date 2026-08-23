# -*- coding: utf-8 -*-
"""Smoke tests — تعمل بدون شبكة أو مفاتيح. تُستخدم في CI وللتشغيل المحلي."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_imports():
    import app  # noqa: F401
    from src import corrector, exporter, extractor_mineru  # noqa: F401


def test_export_md():
    from src.exporter import export

    p = export("# T\n\nhello", "md")
    assert Path(p).read_text(encoding="utf-8").startswith("# T")


def test_export_docx_equations():
    import re
    import zipfile

    from src.exporter import export

    p = export("Formula: $$E=mc^2$$", "docx")
    xml = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8")
    assert len(re.findall(r"<m:oMath[ >]", xml)) == 1


def test_evaluate():
    from evaluation.evaluate import evaluate

    r = evaluate("$$a^2+b^2=c^2$$ text", "$$a^{2}+b^{2}=c^{2}$$ text")
    assert r["formula_acc"] == 1.0
    assert r["text_CER"] < 0.01


def test_extract_math_tokens():
    from src.exporter import _extract_math

    body, formulas = _extract_math("x $$a+b$$ y $c$ z")
    assert "\u27e6M0\u27e7" in body and "\u27e6M1\u27e7" in body
    assert formulas["0"] == "a+b" and formulas["1"] == "c"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS {name}")
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"FAIL {name}: {exc}")
    sys.exit(1 if failed else 0)
