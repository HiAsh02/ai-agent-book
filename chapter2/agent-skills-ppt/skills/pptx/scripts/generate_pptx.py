"""
Executable script bundled with pptx Skill: uses python-pptx to generate a real .pptx file from a structured outline.

This is part of the third layer (details / bundled tool) of Agent Skills "Progressive Disclosure":
After reading SKILL.md, the Agent learns that it needs to call this script via the run_skill_script tool,
and pass the slide outline according to the agreed JSON schema. This script is responsible for materializing the outline into PowerPoint.

payload JSON schema (described by SKILL.md to the Agent):
{
  "title":     "Presentation main title (string)",
  "subtitle":  "Subtitle, usually author/source (string, optional)",
  "slides": [
    {"title": "Slide title", "bullets": ["Bullet1", "Bullet2", ...]},
    ...
  ]
}

Can be used both as a library (import build_presentation) and run directly as a CLI:
    python generate_pptx.py outline.json output/deck.pptx
"""

import json
import sys
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt, Inches
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


#  A simple brand color scheme as a design starting point (corresponding to the "template / design starting point" mentioned in SKILL.md)
ACCENT = RGBColor(0x1F, 0x4E, 0x79)   #  Deep blue
DARK = RGBColor(0x22, 0x22, 0x22)     #  Near-black body text
LIGHT = RGBColor(0xF2, 0xF5, 0xFA)    #  Light background bar


def _set_slide_bg(slide, rgb):
    """Fill the entire slide with a solid background color."""
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = rgb


def _add_title_slide(prs, title, subtitle):
    slide = prs.slides.add_slide(prs.slide_layouts[6])  #  6 = Blank layout
    _set_slide_bg(slide, ACCENT)

    #  Main title
    box = slide.shapes.add_textbox(Inches(0.8), Inches(2.2), Inches(8.4), Inches(2.0))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = title
    run.font.size = Pt(40)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    #  Subtitle
    if subtitle:
        sbox = slide.shapes.add_textbox(Inches(0.8), Inches(4.3), Inches(8.4), Inches(1.0))
        stf = sbox.text_frame
        stf.word_wrap = True
        sp = stf.paragraphs[0]
        sp.alignment = PP_ALIGN.CENTER
        srun = sp.add_run()
        srun.text = subtitle
        srun.font.size = Pt(20)
        srun.font.color.rgb = RGBColor(0xD5, 0xDE, 0xEB)


def _add_content_slide(prs, title, bullets):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _set_slide_bg(slide, RGBColor(0xFF, 0xFF, 0xFF))

    #  Top title color bar
    bar = slide.shapes.add_shape(
        1,  # MSO_SHAPE.RECTANGLE
        Inches(0), Inches(0), Inches(10), Inches(1.1),
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()

    tf = bar.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.5)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = title
    run.font.size = Pt(26)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    #  Body bullets
    body = slide.shapes.add_textbox(Inches(0.7), Inches(1.5), Inches(8.6), Inches(5.2))
    btf = body.text_frame
    btf.word_wrap = True
    for i, bullet in enumerate(bullets):
        para = btf.paragraphs[0] if i == 0 else btf.add_paragraph()
        para.space_after = Pt(10)
        r = para.add_run()
        r.text = "•  " + str(bullet)
        r.font.size = Pt(18)
        r.font.color.rgb = DARK


def build_presentation(payload: dict, out_path: str) -> dict:
    """Build pptx from outline payload, return {path, num_slides, titles} for verification."""
    title = payload.get("title", "Untitled Presentation")
    subtitle = payload.get("subtitle", "")
    slides = payload.get("slides", [])
    if not slides:
        raise ValueError("payload.slides is empty, at least one slide is required")

    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)

    titles = []

    #  Title slide
    _add_title_slide(prs, title, subtitle)
    titles.append(title)

    #  Content slide
    for s in slides:
        s_title = s.get("title", "")
        bullets = s.get("bullets", [])
        _add_content_slide(prs, s_title, bullets)
        titles.append(s_title)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))

    return {"path": str(out), "num_slides": len(list(prs.slides)), "titles": titles}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_pptx.py <outline.json> <output.pptx>", file=sys.stderr)
        sys.exit(1)
    payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    result = build_presentation(payload, sys.argv[2])
    print(json.dumps(result, ensure_ascii=False, indent=2))
