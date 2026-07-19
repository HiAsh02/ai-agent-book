---
name: pptx
description: Generate a PowerPoint (.pptx) presentation from a paper, outline, or structured text. Use when the user needs to turn a paper/article/outline into slides, slides, presentation, PPT, deck. Don't use when only plain text summary, Word/PDF generation, or modifying individual pixel-level styles of an existing pptx is needed.
---

# pptx Skill —— Generate a Presentation from a Paper

## Core Process (Layer 2)

Convert a source text (paper/outline) into an 8-12 slide presentation by following these steps:

1. **Read the source thoroughly**: Understand the paper's title, authors, problem background, method, key results, and conclusion.
2. **Plan the slide sequence**: A qualified presentation should have 8-12 slides in total, covering at least——
   - Title slide (paper title + author/source as subtitle)
   - Table of Contents / Outline slide
   - Research Background / Problem Motivation
   - Method Overview (**must be split into 2 slides**, e.g., "Overall Approach" and "Key Mechanism")
   - Key Results / Experimental Findings (**must be split into 2 slides**, e.g., "Efficiency Metrics" and "Performance Comparison")
   - Limitations / Discussion
   - Summary / Conclusion slide (bullet-point summary of the entire paper)
3. **Extract key points**: 3-5 bullets per slide, one sentence each, avoid copying entire paragraphs from the source.
4. **Generate the file**: Call the script bundled with this Skill `scripts/generate_pptx.py` (via the `run_skill_script` tool), passing the JSON payload as defined below.

## Bundled Script Calling Convention

Tool: `run_skill_script(name="pptx", script="generate_pptx.py", payload=<JSON string>)`

JSON schema for the payload:

```json
{
  "title": "Main title of the presentation (usually the paper title)",
  "subtitle": "Subtitle, usually the author or source, can be left empty",
  "slides": [
    {"title": "Slide title", "bullets": ["Key point 1", "Key point 2", "Key point 3"]}
  ]
}
```

Constraints:
- `slides` **must have at least 8 items** (plus the auto-generated title slide, total slides fall within the 8-12 range).
- The first item should usually be "Table of Contents / Outline", and the last item should be "Summary / Conclusion".
- It is recommended to have 3-5 `bullets` per slide.

## More Detailed Style and Implementation Details (Layer 3)

For details on layout, color scheme, python-pptx implementation, or troubleshooting generation issues,
use `read_skill_file` to read the following files within this Skill:
- `reference.md` —— Layout, color scheme, and python-pptx technical details
- `scripts/generate_pptx.py` —— The generator source code itself
