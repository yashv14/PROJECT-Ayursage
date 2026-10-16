"""Escaped, paginated ReportLab document from a detached approved snapshot."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape


def generate_pdf(snapshot):
    # Lazy import: ordinary startup never initializes document rendering.
    import reportlab
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether

    font_name = 'ClinicalVera'
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(Path(reportlab.__file__).parent / 'fonts' / 'Vera.ttf')))
    glyphs = pdfmetrics.getFont(font_name).face.charToGlyph
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ClinicalBody', fontName=font_name, fontSize=9, leading=14, spaceAfter=8, splitLongWords=True))
    styles.add(ParagraphStyle(name='ClinicalTitle', parent=styles['ClinicalBody'], fontSize=20, leading=25, textColor=colors.HexColor('#16564a'), spaceAfter=18))
    styles.add(ParagraphStyle(name='ClinicalHeading', parent=styles['ClinicalBody'], fontSize=12, leading=17, spaceBefore=12, keepWithNext=True))
    story = []

    def add(text, style='ClinicalBody'):
        text = str(text)
        if any(ord(char) not in glyphs for char in text if char not in '\n\r\t'):
            raise ValueError('Unsupported report character; no silent glyph substitution')
        story.append(Paragraph(escape(text).replace('\n', '<br/>'), styles[style]))

    add('AYUR-SAGE | Clinical report', 'ClinicalTitle')
    add(f"Patient #{snapshot['patient_id']}  |  Assessment #{snapshot['assessment_id']}  |  Report version 1")
    add(f"Assessment recorded: {snapshot['assessed_at']} UTC")
    add(f"Approved by doctor account #{snapshot['approval']['actor_user_id']} at {snapshot['approval']['decided_at']}")
    add(f"Issued: {snapshot['issued_at']}  |  Approval event #{snapshot['approval']['id']}")
    add('Assessment inputs', 'ClinicalHeading')
    if snapshot['inputs'] is None:
        add('No input values stored for this legacy assessment.')
    else:
        for name, value in snapshot['inputs'].items():
            add(f'{name}: {value}')
    add('Patient-supplied notes', 'ClinicalHeading')
    add(snapshot['patient_notes'] or 'No patient notes recorded.')
    add('Approved human clinical review', 'ClinicalHeading')
    review = snapshot['approval']
    add('Recommendation provenance: ' + review['origin'])
    add(review['clinical_notes'] or 'No clinical notes stored.')
    for name, value in (review['recommendations'] or {}).items():
        add(f'{name}: {value}')
    prescription_start = len(story)
    add('Doctor-authored prescriptions', 'ClinicalHeading')
    if not review['prescriptions']:
        add('No prescription stored.')
    for index, prescription in enumerate(review['prescriptions'] or [], 1):
        start = prescription_start if index == 1 else len(story)
        add(f'Prescription {index}', 'ClinicalHeading')
        for name in ('medication', 'dose', 'route', 'frequency', 'duration', 'instructions'):
            value = prescription[name]
            add(f'{name}: {value or "Not recorded"}')
        group = story[start:]
        del story[start:]
        story.append(KeepTogether(group))
    add('Review history and documented revisions', 'ClinicalHeading')
    for event in snapshot['history']:
        add(f"Review {event['sequence']}: {event['from_state']} -> {event['decision']}; doctor #{event['actor_user_id']}; {event['decided_at']}")
        if event['id'] != review['id']:
            add(event['clinical_notes'] or 'No earlier notes stored.')
            for name, value in (event['recommendations'] or {}).items():
                add(f'Earlier {name}: {value}')
            for index, prescription in enumerate(event['prescriptions'] or [], 1):
                add(f'Earlier prescription {index}: ' + '; '.join(f'{name}: {value}' for name, value in prescription.items()))
    add('Clinical context', 'ClinicalHeading')
    add('This report reproduces stored doctor-approved content. Recommendations and prescriptions are human-authored where classified as doctor_entered. Legacy content has unclassified provenance. No stored model predictions are available; no V17 inference is asserted. This document does not replace consultation with the treating clinician. Do not change prescribed care without consulting them.')
    story.append(Spacer(1, 10))
    output = BytesIO()

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(font_name, 8)
        canvas.setFillColor(colors.HexColor('#52605b'))
        canvas.drawString(42, 27, 'AYUR-SAGE - Private clinical report - Version 1')
        canvas.drawRightString(A4[0] - 42, 27, f'Page {document.page}')
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=42, bottomMargin=48,
        title='AYUR-SAGE clinical report', author='AYUR-SAGE', pageCompression=0).build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
