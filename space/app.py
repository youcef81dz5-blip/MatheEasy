"""DocExtract — استخراج المستندات العلمية (عربي + معادلات) إلى Markdown قابل للتحرير.

Run:  python app.py
"""

import html
import json
import os
import re
from pathlib import Path

import gradio as gr

from src.corrector import correct_markdown, gemini_configured
from src.exporter import export
from src.extractor_mineru import extract

# ---------------------------------------------------------------- env loading

def _load_env(path=".env"):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        os.environ.setdefault(key.strip(), val.strip())

_load_env()

# ---------------------------------------------------------------- preview

_PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="__KATEX_CSS__">
<style>
 body{font-family:'Tajawal','Segoe UI',Tahoma,Arial,sans-serif;padding:20px 24px;line-height:2;color:#1e293b;background:#fff}
 img{max-width:100%} table{border-collapse:collapse;margin:10px 0} td,th{border:1px solid #dbe2ea;padding:5px 12px}
 h1,h2,h3{color:#0f172a;border-bottom:1px solid #eef2f7;padding-bottom:6px} .katex{font-size:1.1em}
 ::selection{background:#c7d2fe}
</style></head>
<body><div id="c" dir="__DIR__"></div>
<script src="__MARKED__"></script>
<script src="__KATEX_JS__"></script>
<script src="__RENDER__"></script>
<script>
var md = __MD__;
var c = document.getElementById('c');
try { c.innerHTML = marked.parse(md); } catch(e) { c.textContent = md; }
if (window.renderMathInElement) {
  renderMathInElement(c, {
    delimiters: [
      {left:'$$', right:'$$', display:true},
      {left:'\\[', right:'\\]', display:true},
      {left:'\\(', right:'\\)', display:false},
      {left:'$', right:'$', display:false}
    ],
    throwOnError: false
  });
}
</script></body></html>"""

_PREVIEW_TEMPLATE = _PREVIEW_TEMPLATE.replace(
    "__KATEX_CSS__", "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css"
).replace("__KATEX_JS__", "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"
).replace("__RENDER__", "https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"
).replace("__MARKED__", "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js")


_EMPTY_STATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
 body{height:100vh;margin:0;display:flex;align-items:center;justify-content:center;
 font-family:'Tajawal','Segoe UI',Tahoma,sans-serif;background:#f8fafc;color:#94a3b8;text-align:center}
 .box{max-width:420px} .ic{font-size:52px;margin-bottom:12px} p{font-size:1.05rem;line-height:2;margin:0}
</style></head><body><div class="box">
 <div class="ic">📄✨</div>
 <p><b>لا توجد معاينة بعد</b><br>ارفع ملفاً واضغط «استخراج النص والمعادلات»<br>ستظهر هنا المعاينة المنسقة مع المعادلات</p>
</div></body></html>"""


def render_preview(md, rtl=True):
    if not md or not md.strip():
        doc = _EMPTY_STATE
    else:
        payload = json.dumps(md, ensure_ascii=False).replace("</", "<\\/")
        direction = "rtl" if rtl else "ltr"
        doc = _PREVIEW_TEMPLATE.replace("__MD__", payload).replace("__DIR__", direction)
    return (
        '<iframe srcdoc="' + html.escape(doc, quote=True) + '" '
        'style="width:100%;height:640px;border:1px solid #e5e7eb;'
        'border-radius:14px;background:#fff;box-shadow:0 2px 10px rgba(15,23,42,.05)"></iframe>'
    )

# ---------------------------------------------------------------- handlers

def do_extract(file, language, ocr, formula, force_flash, progress=gr.Progress()):
    if not file:
        raise gr.Error("الرجاء رفع ملف أولاً (PDF / صورة / DOCX ...)")
    progress(0.15, "جاري إرسال الملف إلى MinerU Cloud API...")
    result = extract(
        file,
        language=language,
        ocr=ocr,
        formula=formula,
        force_flash=force_flash,
    )
    md = result.markdown
    if not md.strip():
        raise gr.Error("لم يُرجع المحرك أي نص. جرّب تفعيل OCR أو محركاً آخر.")
    progress(1.0, "تم")
    api = result.meta.get("api", "؟")
    note = " (بعد fallback)" if result.meta.get("fallback") else ""
    status = (
        "<div class='status-ok'>✅ <b>تم الاستخراج بنجاح</b> — المحرك: "
        f"<code>{api}</code>{note} — اللغة: <code>{language}</code>"
        " — راجع المعاينة ثم حرّر/صدّر النتيجة</div>"
    )
    return md, md, render_preview(md, True), status


def do_correct(md, progress=gr.Progress()):
    if not md or not md.strip():
        raise gr.Error("لا يوجد نص للتصحيح — استخرج ملفاً أولاً")
    if not gemini_configured():
        raise gr.Error("ضع GEMINI_API_KEY في ملف .env أولاً")
    progress(0.3, "جاري تصحيح المعادلات عبر Gemini...")
    fixed = correct_markdown(md)
    progress(1.0, "تم")
    return fixed, fixed, render_preview(fixed, True), (
        "<div class='status-ok'>✨ <b>تم التصحيح عبر Gemini</b> — أُصلحت صيغ LaTeX "
        "مع الحفاظ على النص العربي كما هو</div>"
    )


def make_exporter(fmt):
    def _export(md):
        try:
            return export(md, fmt)
        except ValueError as exc:
            raise gr.Error(str(exc))
        except RuntimeError as exc:
            raise gr.Error(str(exc))
    return _export


def refresh_preview(md, direction):
    return render_preview(md, direction == "RTL")

# ---------------------------------------------------------------- theme & CSS

THEME = gr.themes.Soft(
    primary_hue="indigo",
    secondary_hue="violet",
    neutral_hue="slate",
    font=[gr.themes.GoogleFont("Tajawal"), "Segoe UI", "Tahoma", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("JetBrains Mono"), "Consolas", "monospace"],
)

CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap');

.gradio-container {direction: rtl !important;}

/* ---------- hero header ---------- */
.hero {
  background: linear-gradient(135deg, #4338ca 0%, #6d28d9 55%, #9333ea 100%);
  border-radius: 22px; padding: 30px 26px 26px; color: #fff; text-align: center;
  box-shadow: 0 14px 34px rgba(79, 70, 229, .28); margin-bottom: 10px;
  position: relative; overflow: hidden;
}
.hero::before {
  content: ''; position: absolute; inset: 0;
  background: radial-gradient(circle at 85% 15%, rgba(255,255,255,.14) 0, transparent 42%);
  pointer-events: none;
}
.hero .logo {
  width: 62px; height: 62px; margin: 0 auto 10px; border-radius: 18px;
  background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.4);
  display: flex; align-items: center; justify-content: center; font-size: 30px;
  backdrop-filter: blur(4px);
}
.hero h1 {margin: 0; font-size: 1.9rem; font-weight: 800; color: #fff; letter-spacing: .3px;}
.hero h1 span {background: rgba(255,255,255,.16); border-radius: 10px; padding: 0 10px;}
.hero p {margin: 8px auto 0; color: #e0e7ff; font-size: 1.02rem; max-width: 640px; line-height: 1.8;}
.hero .badges {display: flex; gap: 8px; justify-content: center; margin-top: 16px; flex-wrap: wrap;}
.hero .badge {
  background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.35);
  padding: 4px 14px; border-radius: 999px; font-size: .84rem; color: #fff;
}
.hero .badge b {color: #fde68a;}

/* ---------- steps ---------- */
.steps {display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; margin: 14px 0 4px;}
.step {
  display: flex; align-items: center; gap: 9px; background: #fff;
  border: 1px solid #e2e8f0; border-radius: 999px; padding: 7px 18px 7px 20px;
  font-size: .92rem; font-weight: 500; color: #334155;
  box-shadow: 0 1px 3px rgba(15,23,42,.06);
}
.step .n {
  width: 26px; height: 26px; border-radius: 50%; color: #fff;
  background: linear-gradient(135deg, #4f46e5, #8b5cf6);
  display: flex; align-items: center; justify-content: center;
  font-size: .8rem; font-weight: 700;
}

/* ---------- cards ---------- */
.card {
  background: #fff !important; border: 1px solid #e5e7eb !important;
  border-radius: 18px !important; box-shadow: 0 4px 16px rgba(15,23,42,.05) !important;
  padding: 16px !important;
}
.card .label-wrap, .card span[data-testid="block-info"] {font-weight: 700 !important;}

/* ---------- buttons ---------- */
#extract-btn {
  height: 58px !important; font-size: 1.18rem !important; font-weight: 800 !important;
  border-radius: 16px !important; border: none !important;
  background: linear-gradient(135deg, #4f46e5, #7c3aed) !important;
  box-shadow: 0 10px 24px rgba(79, 70, 229, .35) !important;
  transition: all .2s ease;
}
#extract-btn:hover {filter: brightness(1.08); transform: translateY(-1px);}
#correct-btn {
  height: 48px !important; border-radius: 13px !important; font-weight: 700 !important;
  background: linear-gradient(135deg, #0ea5e9, #6366f1) !important;
  border: none !important; color: #fff !important;
  box-shadow: 0 6px 16px rgba(14, 165, 233, .28) !important;
}
#correct-btn:hover {filter: brightness(1.07);}
.export-bar button {
  border-radius: 12px !important; font-weight: 600 !important;
  border: 1.5px solid #c7d2fe !important; background: #eef2ff !important;
  color: #4338ca !important;
}
.export-bar button:hover {background: #e0e7ff !important;}

/* ---------- status ---------- */
.status-ok {
  background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46;
  border-radius: 12px; padding: 10px 16px; font-size: .95rem;
}
.status-ok code {background: #d1fae5; border-radius: 6px; padding: 1px 8px;}

/* ---------- tabs ---------- */
.tabnav button {font-size: 1rem !important; font-weight: 700 !important; border-radius: 12px 12px 0 0 !important;}

/* ---------- misc ---------- */
footer {display: none !important;}
.footer-credit {
  text-align: center; color: #64748b; font-size: .85rem;
  margin-top: 20px; padding: 16px 8px; border-top: 1px solid #e5e7eb; line-height: 1.9;
}
.footer-credit b {color: #4338ca;}
.tip {
  background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
  border-radius: 12px; padding: 10px 16px; font-size: .88rem; line-height: 1.9;
}
"""

HERO = """
<div class="hero">
  <div class="logo">📄</div>
  <h1>Doc<span>Extract</span></h1>
  <p>حوّل مستنداتك العلمية — PDF ممسوح ضوئياً، صور، Office — إلى نصّ <b>Markdown + معادلات LaTeX</b> قابل للنسخ والتحرير، مع تصحيح ذكي بالذكاء الاصطناعي</p>
  <div class="badges">
    <span class="badge">⚡ محرك <b>MinerU</b> السحابي</span>
    <span class="badge">✨ تصحيح <b>Gemini</b> للمعادلات</span>
    <span class="badge">🆓 مجاني بالكامل</span>
  </div>
</div>
"""

STEPS = """
<div class="steps">
  <div class="step"><span class="n">1</span> ارفع الملف</div>
  <div class="step"><span class="n">2</span> اضغط «استخراج النص»</div>
  <div class="step"><span class="n">3</span> صحّح المعادلات بـ Gemini</div>
  <div class="step"><span class="n">4</span> انسخ أو صدّر النتيجة</div>
</div>
"""

HELP = """
### ❓ كيف أستخدم DocExtract؟

| الخطوة | التفاصيل |
|---|---|
| **الرفع** | PDF (حتى 200 صفحة)، صور PNG/JPG، ملفات DOCX / PPTX / XLSX |
| **اللغة** | اختر لغة المستند — `ar` للعربية (تُفعّل OCR المناسب لها) |
| **OCR** | فعّله للمستندات الممسوحة ضوئياً أو الصور؛ أوقفه لملفات PDF النصية الأصلية (أسرع) |
| **المعادلات** | تُستخرج تلقائياً كـ LaTeX بين `$...$` و `$$...$$` |
| **التصحيح** | زر Gemini يصلح صيغ LaTeX المكسورة دون المساس بالعربية |

### 💡 ملاحظات
- بدون `MINERU_TOKEN` يعمل وضع **Flash** التلقائي (حتى 10MB / 20 صفحة)
- احصل على Token مجاني (1000 صفحة يومياً): [mineru.net/apiManage/token](https://mineru.net/apiManage/token)
- مفتاح Gemini المجاني: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
"""

FOOTER = """
<div class="footer-credit">
  <b>DocExtract</b> — مشروع أكاديمي مفتوح المصدر · مدعوم بواسطة
  <b>MinerU Cloud API</b> و <b>Google Gemini</b><br>
  التقييم: <code>evaluation/evaluate.py</code> — CER للنصوص ودقة المعادلات
</div>
"""

# ---------------------------------------------------------------- UI

with gr.Blocks(title="DocExtract — استخراج المستندات العلمية") as demo:
    gr.HTML(HERO)
    gr.HTML(STEPS)

    state = gr.State("")

    with gr.Row(equal_height=False):
        with gr.Column(scale=3, elem_classes="card"):
            gr.Markdown("### 📤 الملف المصدر")
            file_in = gr.File(
                label="اسحب الملف هنا أو انقر للاختيار",
                type="filepath",
                height=140,
            )
            extract_btn = gr.Button(
                "🚀 استخراج النص والمعادلات", variant="primary", elem_id="extract-btn"
            )
        with gr.Column(scale=2, elem_classes="card"):
            gr.Markdown("### ⚙️ إعدادات الاستخراج")
            lang = gr.Dropdown(
                choices=[("العربية", "ar"), ("الإنجليزية", "en"), ("الفرنسية", "fr"),
                         ("الألمانية", "de"), ("الإسبانية", "es"), ("الروسية", "ru"),
                         ("الصينية", "zh"), ("اليابانية", "ja")],
                value="ar",
                label="لغة المستند",
                info="توجّه محرك OCR للغة الصحيحة",
            )
            ocr_cb = gr.Checkbox(
                True, label="OCR — للمستندات الممسوحة ضوئياً والصور"
            )
            formula_cb = gr.Checkbox(
                True, label="التعرف على المعادلات وتحويلها إلى LaTeX"
            )
            flash_cb = gr.Checkbox(
                False,
                label="⚡ وضع Flash السريع",
                info="بدون Token — حتى 10MB / 20 صفحة فقط",
            )

    status_md = gr.HTML()

    with gr.Tabs():
        with gr.Tab("👁 المعاينة المنسقة"):
            with gr.Row():
                direction = gr.Radio(
                    ["RTL", "LTR"], value="RTL",
                    label="اتجاه المعاينة", scale=0,
                )
            preview = gr.HTML(render_preview("", True))
        with gr.Tab("✏️ محرر Markdown"):
            editor = gr.Textbox(
                label="النص المستخرج — قابل للتحرير والنسخ المباشر",
                lines=20,
                buttons=["copy"],
                placeholder="سيظهر هنا النص المستخرج بصيغة Markdown مع المعادلات بصيغة LaTeX...",
            )

    gr.Markdown("### 📥 التصدير والمشاركة")
    with gr.Row(elem_classes="export-bar"):
        correct_btn = gr.Button("✨ تصحيح المعادلات عبر Gemini", elem_id="correct-btn")
        dl_md = gr.DownloadButton("⬇️ Markdown .md")
        dl_tex = gr.DownloadButton("⬇️ LaTeX .tex")
        dl_docx = gr.DownloadButton("⬇️ Word .docx")

    with gr.Accordion("❓ مساعدة وسيناريو الاستخدام", open=False):
        gr.Markdown(HELP)

    gr.HTML(FOOTER)

    # events
    extract_btn.click(
        do_extract,
        [file_in, lang, ocr_cb, formula_cb, flash_cb],
        [state, editor, preview, status_md],
        show_progress_on=[preview],
    )
    correct_btn.click(
        do_correct, [state], [state, editor, preview, status_md]
    )
    direction.change(refresh_preview, [state, direction], preview)
    editor.change(lambda md: md or "", editor, state)

    dl_md.click(make_exporter("md"), [state], dl_md)
    dl_tex.click(make_exporter("tex"), [state], dl_tex)
    dl_docx.click(make_exporter("docx"), [state], dl_docx)


if __name__ == "__main__":
    demo.queue()
    demo.launch(theme=THEME, css=CUSTOM_CSS, ssr_mode=False)
