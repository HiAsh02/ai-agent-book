# pptx Skill — Technical Details (Layer 3 / Deepest Progressive Disclosure)

This file corresponds to the third layer of the book's "progressive disclosure": it is only read when the Agent needs to control layout, color schemes, or troubleshoot generation issues; it does not occupy context during normal use.

## Layout Conventions

The generator uses the blank layout of python-pptx (`slide_layouts[6]`) and manually positions text boxes, thereby fully controlling the layout without relying on template placeholders:

- Canvas size: 10 x 7.5 inches (4:3).
- **Title slide**: Dark blue background (RGB 1F4E79), white centered large title (40pt) + light blue subtitle (20pt).
- **Content slides**: White background, page title (26pt white text) inside a dark blue bar at the top, with a bullet list (18pt) below.

## Color Scheme

| Name   | RGB      | Usage                |
|--------|----------|----------------------|
| ACCENT | #1F4E79  | Title slide background / color bar |
| DARK   | #222222  | Body text            |
| LIGHT  | #F2F5FA  | Alternate light background |

## python-pptx Key Points

- `Presentation()` creates a new presentation; `prs.slides.add_slide(layout)` adds a slide.
- Text must be placed inside a `text_frame`, using `add_paragraph()` for each paragraph and `add_run()` for each run to set fonts.
- Solid page background: call `slide.background.fill.solid()` then set `fore_color.rgb`.
- Shape type `1` corresponds to a rectangle (MSO_SHAPE.RECTANGLE), used for the top color bar.
- Save: `prs.save(path)`, the extension must be `.pptx`.

## Validation Suggestions

Reopen the file after generation to verify validity:

```python
from pptx import Presentation
prs = Presentation("output/deck.pptx")
print(len(list(prs.slides)))               # Number of slides
for s in prs.slides:                        # First text on each slide
    for shp in s.shapes:
        if shp.has_text_frame and shp.text_frame.text.strip():
            print(shp.text_frame.text.strip().splitlines()[0]); break
```
