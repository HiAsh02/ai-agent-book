"""
Offline sample generator

Generate a "report with chart" as a multimodal sample for experiments 3-7 comparing three extraction paradigms.
The output includes:
  - test_files/sample_chart.png   only the chart (image modality)
  - test_files/sample_report.pdf  chart + text description (document modality, the "PDF report with chart" in the book)

Key design: precise values in the chart (e.g., quarterly revenue) appear only on the bar chart, not written out in the text.
Thus in experiments:
  - Native multimodal mode can directly "read" the bars and extract values;
  - Text extraction mode, if using a generic captioner to transcribe the image, often loses precise values and spatial relationships;
So the trade-offs among the three paradigms can be directly measured, rather than guessed.

This script is fully offline and requires no API Key.
"""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  #  No GUI backend, purely offline chart generation
import matplotlib.pyplot as plt


#  Chart data: only annotated on the bar chart, text does not repeat these precise numbers
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]
REVENUE = [120, 150, 95, 180]  #  Unit: millions of dollars ($M)


def create_chart(output_path: Path) -> Path:
    """Generate a bar chart using matplotlib (image modality sample)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    bars = ax.bar(QUARTERS, REVENUE, color=["#4C72B0", "#55A868", "#C44E52", "#8172B3"])

    #  Annotate precise values at the top of bars—this information exists only in the image
    for bar, value in zip(bars, REVENUE):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 3,
            f"${value}M",
            ha="center",
            va="bottom",
            fontsize=11,
            fontweight="bold",
        )

    ax.set_title("Acme Corp Quarterly Revenue 2024", fontsize=13, fontweight="bold")
    ax.set_ylabel("Revenue (in $M)")
    ax.set_ylim(0, 210)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()

    fig.savefig(output_path)
    plt.close(fig)
    return output_path


def create_report_pdf(chart_path: Path, output_path: Path) -> Path:
    """Combine the chart with a text description into a PDF report (document modality sample)."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Image as RLImage,
        )
    except ImportError:
        print("Tip: reportlab not installed, skip PDF generation (pip install reportlab).")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()

    #  The text deliberately provides only qualitative descriptions, not writing out each quarter's precise values—values are only in the chart
    body_text = (
        "This internal report summarizes Acme Corp's revenue performance in 2024. "
        "Overall the year showed healthy growth, with a mid-year dip followed by a "
        "strong recovery in the final quarter. The chart below breaks down revenue "
        "by quarter; management attributes the fourth-quarter surge to the launch of "
        "the new enterprise product line."
    )

    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    story = [
        Paragraph("Acme Corp 2024 Revenue Report", styles["Title"]),
        Spacer(1, 0.4 * cm),
        Paragraph(body_text, styles["BodyText"]),
        Spacer(1, 0.6 * cm),
        RLImage(str(chart_path), width=14 * cm, height=9.3 * cm),
    ]
    doc.build(story)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Offline generation of multimodal samples with charts (image + PDF report) for experiments 3-7. No API Key required."
    )
    parser.add_argument(
        "--output-dir",
        default="test_files",
        help="Sample output directory (default: test_files)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Generate only PNG chart, not PDF report",
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    chart_path = create_chart(out_dir / "sample_chart.png")
    print(f"Generated chart: {chart_path}")

    if not args.no_pdf:
        pdf_path = create_report_pdf(chart_path, out_dir / "sample_report.pdf")
        if pdf_path:
            print(f"Generated report: {pdf_path}")

    print(
        "\nTip: precise quarterly revenue on the chart exists only in the image, not written out in the text.\n"
        "Use the following questions to compare the three paradigms (native / extract as text / with tools):\n"
        '  "Which quarter had the highest revenue, and what was the exact value?"'
    )


if __name__ == "__main__":
    main()
