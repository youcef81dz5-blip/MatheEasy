"""AI post-correction of extracted Markdown via free Gemini API."""

import os
import re

from google import genai
from google.genai import types

SYSTEM_PROMPT = (
    "You are an expert academic document editor. You receive a Markdown document "
    "that was extracted by OCR from a scientific document. It may contain Arabic "
    "text mixed with LaTeX formulas and HTML tables.\n"
    "Your tasks:\n"
    "1. Fix broken LaTeX (delimiters, unbalanced braces, unknown commands) so every "
    "formula renders correctly. Use $...$ for inline and $$...$$ for display math.\n"
    "2. Preserve the Arabic (or any natural-language) text exactly as-is. Do NOT "
    "translate, rephrase or summarize.\n"
    "3. Fix obvious OCR artifacts inside formulas only when confident (e.g. l vs 1, "
    "O vs 0, missing backslashes).\n"
    "4. Keep the Markdown structure (headings, lists, tables) intact.\n"
    "5. Output ONLY the corrected Markdown. No explanations, no code fences."
)


def gemini_configured() -> bool:
    return bool(os.getenv("GEMINI_API_KEY", "").strip())


def correct_markdown(md: str, api_key=None, model=None) -> str:
    key = (api_key or os.getenv("GEMINI_API_KEY", "")).strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY غير مضبوط. ضعه في ملف .env")
    model = (model or os.getenv("GEMINI_MODEL", "")).strip() or "gemini-3.6-flash"

    client = genai.Client(api_key=key)
    config = types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.1)
    response = client.models.generate_content(model=model, contents=md, config=config)
    text = (getattr(response, "text", None) or "").strip()

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip() or md
