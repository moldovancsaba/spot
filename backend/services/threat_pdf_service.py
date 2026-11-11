"""Branded, paginated PDFs from a saved human-confirmed case snapshot."""
from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab import __file__ as reportlab_file
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_NAME = 'SpotUnicode'
_FONT_LOCK = threading.Lock()
TEAL = colors.HexColor('#087F8C')
INK = colors.HexColor('#16313A')


def _font():
    with _FONT_LOCK:
        if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
            system = Path('/System/Library/Fonts/Supplemental/Arial Unicode.ttf')
            fallback = Path(reportlab_file).parent / 'fonts/Vera.ttf'
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(system if system.exists() else fallback)))
    return pdfmetrics.getFont(FONT_NAME)


def render_threat_pdf(snapshot: dict, output: Path) -> None:
    font = _font()
    unavailable = set()

    def safe(value):
        result = []
        for char in str(value if value is not None else ''):
            code = ord(char)
            if char in '\n\t\r' or (code >= 32 and code in font.face.charToGlyph):
                result.append(char)
            elif code >= 32:
                unavailable.add(code)
                result.append(f'[U+{code:04X}]')
        return escape(''.join(result)).replace('\n', '<br/>')

    def when(timestamp):
        return datetime.fromtimestamp(timestamp, ZoneInfo('Europe/Budapest')).strftime('%Y-%m-%d %H:%M:%S %Z')

    styles = {
        'body': ParagraphStyle('body', fontName=FONT_NAME, fontSize=10, leading=15, textColor=INK, spaceAfter=9, splitLongWords=True),
        'small': ParagraphStyle('small', fontName=FONT_NAME, fontSize=8, leading=12, textColor=colors.HexColor('#4F6269'), spaceAfter=6, splitLongWords=True),
        'label': ParagraphStyle('label', fontName=FONT_NAME, fontSize=8, leading=12, textColor=TEAL, spaceAfter=4),
        'section': ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=13, leading=17, textColor=INK, spaceBefore=15, spaceAfter=9, keepWithNext=True),
    }
    case = snapshot['case']
    is_ai = snapshot.get('report_kind') == 'ai_unconfirmed'
    findings = snapshot.get('findings') or []
    strongest = max(findings,key=lambda f:f['confidence']) if findings else None
    story = []

    def paragraph(value, style='body'):
        return Paragraph(safe(value), styles[style])

    def section(title):
        story.append(paragraph(title, 'section'))

    def header_footer(canvas, document):
        width, height = A4
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.setFont('Helvetica-Bold', 23)
        canvas.drawString(44, height - 46, '{spot}')
        canvas.setFillColor(INK)
        canvas.setFont('Helvetica-Bold', 10)
        canvas.drawRightString(width - 44, height - 38, 'AI-GENERATED FINDING REPORT' if is_ai else 'CONFIRMED THREAT REPORT')
        canvas.setFont('Helvetica', 8)
        canvas.drawRightString(width - 44, height - 53, 'Unconfirmed - automatic reporting' if is_ai else 'Human review record')
        canvas.setStrokeColor(TEAL)
        canvas.line(44, height - 65, width - 44, height - 65)
        canvas.setStrokeColor(colors.HexColor('#D5E2E5'))
        canvas.line(44, 43, width - 44, 43)
        canvas.setFillColor(colors.HexColor('#4F6269'))
        canvas.setFont('Helvetica', 7)
        canvas.drawString(44, 29, 'Report ' + snapshot['report_id'])
        canvas.drawRightString(width - 44, 29, f'Page {document.page}')
        canvas.restoreState()

    story.append(paragraph('AI-GENERATED / UNCONFIRMED' if is_ai else 'HUMAN-CONFIRMED THREAT', 'label'))
    story.append(paragraph(strongest['category'] if is_ai else case['human_category'], 'section'))
    if is_ai:
        story.append(paragraph('Automatically generated because at least one analysis assigned a positive antisemitism category with a confidence score of 30% or above. No human has confirmed this finding. Category confidence is a model score, not a calibrated probability that the post is harmful.'))
        details = [
            ('Status', 'AI-generated finding - unconfirmed'),
            ('Highest triggering score', f"{strongest['confidence']:.1%} category confidence"),
            ('Rule', 'Any positive analysis >= 30%, including disagreements and structural retries'),
            ('Final model classification', f"{case.get('assigned_category') or '-'} ({float(case.get('confidence_score') or 0):.1%})"),
            ('Report generated', when(snapshot['created_at'])),
        ]
    else:
        details = [('Reviewer (local account)',case['reviewer']),('Confirmed',when(case['reviewed_at'])),('Report generated',when(snapshot['created_at']))]
    details += [('Case', f"{snapshot['run_id']} / row {case['row_index']}"),('Source item',case.get('item_number') or '-'),('Run language',snapshot.get('language') or '-')]
    table = Table([[paragraph(key, 'small'), paragraph(value, 'body')] for key, value in details], colWidths=[145, A4[0] - 233], hAlign='LEFT')
    table.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 2), ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#EFF6F7'))]))
    story.append(table)
    section('Original post')
    original = case.get('post_text') or ''
    safe(original)
    if unavailable:
        story.append(paragraph('Symbols unavailable in the report font are represented by their Unicode code points. The complete original Unicode text is retained in the matching source snapshot in {spot}.', 'small'))
    for block in original.split('\n\n'):
        story.append(paragraph(block))
    if is_ai:
        section('Triggering analyses')
        for finding in findings:
            story.append(paragraph(f"{finding['stage']} - {finding['model']}"))
            story.append(paragraph(f"Category: {finding['category']} | Confidence: {finding['confidence']:.1%}"))
            for quote in finding.get('source_quotes') or []:
                story.append(paragraph('Source-exact quote: ' + quote, 'small'))
            if not finding.get('source_quotes'):
                story.append(paragraph('No source-exact supporting quotation was supplied by this analysis.', 'small'))
            if finding.get('warnings'):
                story.append(paragraph('Analysis warnings: ' + ', '.join(str(w) for w in finding['warnings']), 'small'))
        section('Current analyses and disagreements')
        trace = case.get('audit_trace') or {}
        for name in ('initial','alternate'):
            branch=trace.get(name) or {}
            if branch:
                story.append(paragraph(f"{branch.get('model') or name}: {branch.get('category') or '-'} ({float(branch.get('confidence') or 0):.1%})"))
        if trace.get('judge_verdict'):
            story.append(paragraph(f"Quality check: {trace.get('judge_verdict')} ({float(trace.get('judge_score') or 0):.1%}).", 'small'))
        story.append(paragraph('A negative final classification, disagreement, warning, or failed quality check does not block this report under the configured any-positive-analysis rule. All uncertainty remains part of the record.', 'small'))
    else:
        section('Human review rationale')
        note = case.get('decision_note') or 'No review note recorded.'
        for block in note.split('\n\n'):
            story.append(paragraph(block))
    section('Model proposal and analysis evidence')
    story.append(paragraph(f"{'Current final model category' if is_ai else 'Model category at confirmation'}: {case.get('assigned_category') or '-'}"))
    score = case.get('confidence_score')
    story.append(paragraph(f'Model-reported category confidence: {score if score is not None else "not supplied"}. No human decision is recorded in this AI report.' if is_ai else f'Model-reported score: {score if score is not None else "not supplied"}. This is separate from the saved human decision.', 'small'))
    if case.get('explanation'):
        story.append(paragraph(case['explanation']))
    story.append(paragraph('Flags: ' + (', '.join(case.get('flags') or []) or 'None recorded.'), 'small'))
    story.append(paragraph('Fallback events: ' + (', '.join(case.get('fallback_events') or []) or 'None recorded.'), 'small'))
    section('Evidence and provenance')
    for key, value in [
        ('Reporting rule' if is_ai else 'Decision ID', snapshot.get('rule_id') if is_ai else case['decision_id']),
        ('Source row', case.get('source_row_index') or case['row_index']),
        ('Source row hash', case.get('source_row_hash') or case.get('row_hash') or 'Not available'),
        ('Original post SHA-256 (UTF-8)', case['post_text_sha256']),
        ('Case evidence SHA-256', case['evidence_hash']),
        ('Canonical snapshot SHA-256', snapshot['snapshot_sha256']),
    ]:
        story.append(paragraph(f'{key}: {value}', 'small'))
    if is_ai:
        story.append(paragraph('Report evidence SHA-256: ' + snapshot['report_evidence_sha256'], 'small'))
    story.append(paragraph('This report records an unconfirmed automated finding at generation time. Later analyses or human decisions may supersede it. Verify its current status in {spot} using the report identifier.' if is_ai else 'This report records the saved human confirmation at the time of export. Later review changes may supersede it; verify the current case in {spot} using the decision and report identifiers.', 'small'))
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=44, leftMargin=44, topMargin=86, bottomMargin=62, title='{spot} AI-generated Unconfirmed Finding' if is_ai else '{spot} Confirmed Threat Report', author='{spot}', subject='Unconfirmed automated category-confidence threshold finding' if is_ai else 'Human-confirmed classification record', allowSplitting=True)
    document.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
