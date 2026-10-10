from pathlib import Path

from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


def create_certificate(path: Path, *, name: str, course_name: str, event_name: str,
                       issuer: str, completion_date: str) -> None:
    """Create the project's single, deliberately simple certificate design."""
    path.parent.mkdir(parents=True, exist_ok=True)
    page = landscape(letter)
    pdf = canvas.Canvas(str(path), pagesize=page)
    width, height = page

    pdf.setStrokeColorRGB(0.12, 0.27, 0.38)
    pdf.setLineWidth(3)
    pdf.roundRect(0.45 * inch, 0.45 * inch, width - 0.9 * inch, height - 0.9 * inch,
                  14, stroke=1, fill=0)
    pdf.setFillColorRGB(0.12, 0.27, 0.38)
    pdf.setFont("Helvetica-Bold", 28)
    pdf.drawCentredString(width / 2, height - 1.65 * inch, "CERTIFICATE OF COMPLETION")
    pdf.setFillColorRGB(0.25, 0.29, 0.32)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(width / 2, height - 2.45 * inch, "This certificate is presented to")
    pdf.setFillColorRGB(0.12, 0.27, 0.38)
    pdf.setFont("Helvetica-Bold", 30)
    pdf.drawCentredString(width / 2, height - 3.25 * inch, name)
    pdf.setFillColorRGB(0.25, 0.29, 0.32)
    pdf.setFont("Helvetica", 14)
    pdf.drawCentredString(width / 2, height - 4.0 * inch, f"for completing {course_name}")
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 4.4 * inch, f"Event: {event_name}  |  Completed: {completion_date}")
    pdf.setStrokeColorRGB(0.45, 0.52, 0.56)
    pdf.line(width / 2 - 1.5 * inch, 1.15 * inch, width / 2 + 1.5 * inch, 1.15 * inch)
    pdf.setFillColorRGB(0.25, 0.29, 0.32)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, 0.85 * inch, issuer)
    pdf.showPage()
    pdf.save()
