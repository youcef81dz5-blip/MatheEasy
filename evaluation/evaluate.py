"""تقييم جودة الاستخراج: CER للنص + دقة المعادلات.

Usage:
    python evaluation/evaluate.py ground_truth.md extracted_1.md [extracted_2.md ...]
"""

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

DISPLAY_FORMULA = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]", re.S)
INLINE_FORMULA = re.compile(r"\\\((.+?)\\\)|(?<!\$)\$(?!\$)([^$\n]+?)\$(?!\$)", re.S)


def normalize(s: str) -> str:
    return re.sub(r"\s+", "", s)


def canonical(s: str) -> str:
    """تطبيع مكافئ رياضياً: a^{2} == a^2"""
    s = normalize(s)
    return s.replace("{", "").replace("}", "")


def plain_text(md: str) -> str:
    md = DISPLAY_FORMULA.sub(" ", md)
    md = INLINE_FORMULA.sub(" ", md)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", md)  # images
    md = re.sub(r"[#>*_`|~-]", " ", md)
    return normalize(md)


def formulas(md: str):
    out = []
    for m in DISPLAY_FORMULA.finditer(md):
        out.append(canonical(m.group(1) or m.group(2) or ""))
    for m in INLINE_FORMULA.finditer(md):
        out.append(canonical(m.group(1) or m.group(2) or ""))
    return [f for f in out if f]


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0
    return 1.0 - SequenceMatcher(None, ref, hyp).ratio()


def formula_accuracy(ref_fs, hyp_fs):
    if not ref_fs:
        return None, 0
    matched = 0
    for rf in ref_fs:
        best = max(
            (SequenceMatcher(None, rf, hf).ratio() for hf in hyp_fs),
            default=0.0,
        )
        if best >= 0.9:
            matched += 1
    return matched / len(ref_fs), len(ref_fs)


def evaluate(truth: str, hyp: str) -> dict:
    t_cer = cer(plain_text(truth), plain_text(hyp))
    acc, n = formula_accuracy(formulas(truth), formulas(hyp))
    return {
        "text_CER": t_cer,
        "formula_acc": acc,
        "formulas_in_truth": n,
        "formulas_extracted": len(formulas(hyp)),
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    truth = Path(sys.argv[1]).read_text(encoding="utf-8")
    print(f"{'System':<30} {'CER':>8} {'FormulaAcc':>12} {'#Frm':>6}")
    print("-" * 60)
    for path in sys.argv[2:]:
        hyp = Path(path).read_text(encoding="utf-8")
        r = evaluate(truth, hyp)
        acc = f"{r['formula_acc']:.2%}" if r["formula_acc"] is not None else "n/a"
        print(f"{Path(path).name:<30} {r['text_CER']:>8.2%} {acc:>12} "
              f"{r['formulas_extracted']:>4}/{r['formulas_in_truth']}")


if __name__ == "__main__":
    main()
