"""生成用于 RAG 测试的示例 PDF(两份 5 页、含表格与图片的公司政策文档)。

运行(无需把 reportlab/pillow 写进项目依赖):
    uv run --with reportlab --with pillow python data/generate_sample_pdfs.py

输出:data/company-travel-policy.pdf、data/company-it-policy.pdf
文档正文为英文(对外可见内容,遵循 CLAUDE.md 语言纪律)。
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_DIR = Path(__file__).resolve().parent
IMG_DIR = Path(tempfile.mkdtemp(prefix="sample-pdf-img-"))

NAVY = colors.HexColor("#0F2A44")
ACCENT = colors.HexColor("#1F7A5A")
GREY = colors.HexColor("#5A6B7B")
LIGHT = colors.HexColor("#EEF2F6")
BORDER = colors.HexColor("#C9D4DE")

RGB_NAVY = (15, 42, 68)
RGB_TEAL = (31, 122, 90)
RGB_WHITE = (255, 255, 255)
LAYER_COLORS = [(15, 42, 68), (26, 74, 92), (31, 122, 90), (72, 152, 118)]

FONT_PATHS = {
    "regular": "/System/Library/Fonts/Supplemental/Arial.ttf",
    "bold": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
}


def _font(kind: str, size: int):
    """取系统字体,取不到时退回 Pillow 默认位图字体。"""
    try:
        return ImageFont.truetype(FONT_PATHS[kind], size)
    except OSError:
        return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# 图片生成(Pillow):横幅 / 柱状图 / 流程图 / 分层图
# --------------------------------------------------------------------------- #
def make_banner(name: str, title: str, subtitle: str) -> Path:
    w, h = 1600, 400
    img = PILImage.new("RGB", (w, h), RGB_NAVY)
    d = ImageDraw.Draw(img)
    for x in range(w):  # 横向渐变 navy -> teal
        t = x / w
        d.line(
            [(x, 0), (x, h)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(RGB_NAVY, RGB_TEAL)),
        )
    d.ellipse([1180, -120, 1560, 260], outline=(255, 255, 255), width=6)
    d.ellipse([1300, 40, 1520, 260], fill=(255, 255, 255, 30), outline=(210, 235, 225), width=4)
    for i in range(6):  # 装饰性"光伏板"网格
        x0 = 120 + i * 40
        d.line([(x0, 340), (x0 + 26, 250)], fill=(150, 200, 185), width=3)
    d.text((110, 120), title, font=_font("bold", 76), fill=RGB_WHITE)
    d.text((114, 220), subtitle, font=_font("regular", 34), fill=(198, 218, 214))
    path = IMG_DIR / f"{name}.png"
    img.save(path)
    return path


def make_bar_chart(name: str, title: str, labels: list[str], values: list[float], unit: str) -> Path:
    w, h = 1400, 760
    pad_l, pad_b, pad_t = 150, 130, 130
    img = PILImage.new("RGB", (w, h), RGB_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(201, 212, 222), width=3)
    d.text((60, 46), title, font=_font("bold", 44), fill=RGB_NAVY)

    top = max(values) * 1.25
    plot_h = h - pad_b - pad_t
    for i in range(5):  # 网格线与刻度
        y = pad_t + plot_h * i / 4
        d.line([(pad_l, y), (w - 70, y)], fill=(228, 234, 240), width=2)
        d.text((40, y - 16), f"{top * (4 - i) / 4:,.0f}", font=_font("regular", 26), fill=(120, 134, 148))

    n = len(values)
    slot = (w - 70 - pad_l) / n
    bw = slot * 0.52
    for i, (lab, val) in enumerate(zip(labels, values)):
        x0 = pad_l + slot * i + (slot - bw) / 2
        bar_h = plot_h * val / top
        y0 = pad_t + plot_h - bar_h
        d.rectangle([x0, y0, x0 + bw, pad_t + plot_h], fill=RGB_TEAL if i % 2 == 0 else RGB_NAVY)
        d.text((x0, y0 - 40), f"{val:,.0f}", font=_font("bold", 28), fill=RGB_NAVY)
        d.text((x0 - 10, pad_t + plot_h + 18), lab, font=_font("regular", 26), fill=(70, 86, 102))
    d.line([(pad_l, pad_t + plot_h), (w - 70, pad_t + plot_h)], fill=RGB_NAVY, width=3)
    d.text((60, h - 46), unit, font=_font("regular", 24), fill=(120, 134, 148))
    path = IMG_DIR / f"{name}.png"
    img.save(path)
    return path


def make_flow(name: str, title: str, steps: list[str]) -> Path:
    w, h = 1500, 420
    img = PILImage.new("RGB", (w, h), RGB_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(201, 212, 222), width=3)
    d.text((50, 40), title, font=_font("bold", 40), fill=RGB_NAVY)
    n = len(steps)
    bw, gap = 250, 45
    total = n * bw + (n - 1) * gap
    x = (w - total) / 2
    y0, y1 = 180, 320
    for i, step in enumerate(steps):
        fill = RGB_TEAL if i in (0, n - 1) else (238, 242, 246)
        txt = RGB_WHITE if i in (0, n - 1) else RGB_NAVY
        d.rounded_rectangle([x, y0, x + bw, y1], radius=16, fill=fill, outline=RGB_NAVY, width=3)
        for j, line in enumerate(step.split("\n")):
            d.text((x + 24, y0 + 34 + j * 38), line, font=_font("bold", 28), fill=txt)
        if i < n - 1:
            ax = x + bw
            d.line([(ax + 6, 250), (ax + gap - 12, 250)], fill=RGB_NAVY, width=5)
            d.polygon([(ax + gap - 4, 250), (ax + gap - 20, 240), (ax + gap - 20, 260)], fill=RGB_NAVY)
        x += bw + gap
    path = IMG_DIR / f"{name}.png"
    img.save(path)
    return path


def make_layers(name: str, title: str, layers: list[tuple[str, str]]) -> Path:
    w = 1500
    row_h = 110
    h = 130 + row_h * len(layers)
    img = PILImage.new("RGB", (w, h), RGB_WHITE)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(201, 212, 222), width=3)
    d.text((50, 40), title, font=_font("bold", 40), fill=RGB_NAVY)
    for i, (label, detail) in enumerate(layers):
        y = 120 + i * row_h
        inset = i * 70
        d.rounded_rectangle(
            [60 + inset, y, w - 60 - inset, y + row_h - 22],
            radius=14,
            fill=LAYER_COLORS[i % len(LAYER_COLORS)],
            outline=RGB_NAVY,
            width=2,
        )
        d.text((90 + inset, y + 16), label, font=_font("bold", 30), fill=RGB_WHITE)
        d.text((90 + inset, y + 52), detail, font=_font("regular", 24), fill=(224, 234, 232))
    path = IMG_DIR / f"{name}.png"
    img.save(path)
    return path


# --------------------------------------------------------------------------- #
# PDF 构件
# --------------------------------------------------------------------------- #
_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontName="Helvetica-Bold", fontSize=17,
                    leading=21, textColor=NAVY, spaceBefore=4, spaceAfter=8)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontName="Helvetica-Bold", fontSize=12.5,
                    leading=16, textColor=ACCENT, spaceBefore=10, spaceAfter=5)
BODY = ParagraphStyle("Body", parent=_ss["BodyText"], fontName="Helvetica", fontSize=9.7,
                      leading=14.2, textColor=colors.HexColor("#1B2733"), alignment=TA_JUSTIFY,
                      spaceAfter=6)
BULLET = ParagraphStyle("Bullet", parent=BODY, leftIndent=12, bulletIndent=3, spaceAfter=3)
CAPTION = ParagraphStyle("Caption", parent=BODY, fontSize=8.3, leading=11, textColor=GREY,
                         alignment=1, spaceBefore=3, spaceAfter=8)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.6, leading=11.5, alignment=0, spaceAfter=0)
CELL_H = ParagraphStyle("CellH", parent=CELL, fontName="Helvetica-Bold", textColor=colors.white)


def bullets(items: list[str]) -> list:
    return [Paragraph(t, BULLET, bulletText="•") for t in items]


def table(data: list[list[str]], widths: list[float]) -> Table:
    rows = [[Paragraph(c, CELL_H) for c in data[0]]]
    rows += [[Paragraph(c, CELL) for c in r] for r in data[1:]]
    t = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def picture(path: Path, width_mm: float, caption: str) -> KeepTogether:
    with PILImage.open(path) as im:
        w, h = im.size
    width = width_mm * mm
    img = Image(str(path), width=width, height=width * h / w)
    return KeepTogether([img, Paragraph(caption, CAPTION)])


def make_header_footer(doc_title: str, doc_code: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = A4
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 16 * mm, w, 16 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(18 * mm, h - 10.5 * mm, "Clenergy Australia Pty Ltd")
        canvas.setFont("Helvetica", 8.5)
        canvas.drawRightString(w - 18 * mm, h - 10.5 * mm, doc_title)
        canvas.setStrokeColor(BORDER)
        canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
        canvas.setFillColor(GREY)
        canvas.setFont("Helvetica", 8)
        canvas.drawString(18 * mm, 11 * mm, f"{doc_code} | Internal use only")
        canvas.drawRightString(w - 18 * mm, 11 * mm, f"Page {canvas.getPageNumber()} of 5")
        canvas.restoreState()

    return draw


def build(filename: str, doc_title: str, doc_code: str, story: list) -> Path:
    path = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=20 * mm,
        title=doc_title,
        author="Clenergy Australia Pty Ltd",
        subject=doc_code,
    )
    draw = make_header_footer(doc_title, doc_code)
    doc.build(story, onFirstPage=draw, onLaterPages=draw)
    return path


CONTROL_HEADER = ["Field", "Value"]
PAGE_W = A4[0] - 36 * mm


# --------------------------------------------------------------------------- #
# 文档 1:Company Travel Policy
# --------------------------------------------------------------------------- #
def travel_story() -> list:
    s: list = []
    s.append(picture(make_banner("travel_banner", "Company Travel Policy", "Clenergy Australia — Effective 1 July 2026"), 174, "Figure 1. Policy cover banner."))
    s.append(Paragraph("1. Purpose and Scope", H1))
    s.append(Paragraph(
        "This policy sets out how employees of Clenergy Australia Pty Ltd plan, approve, book and claim "
        "business travel. It applies to all permanent employees, fixed-term staff and contractors travelling "
        "on company business, whether domestic or international, and covers air travel, ground transport, "
        "accommodation, meals and incidental expenses.", BODY))
    s.append(Paragraph(
        "Travel is approved only where it delivers a clear business outcome that cannot reasonably be achieved "
        "by video conference. Managers are accountable for the travel budget of their cost centre.", BODY))
    s.append(Paragraph("2. Document Control", H1))
    s.append(table(
        [CONTROL_HEADER,
         ["Document ID", "CLE-HR-TRV-004"],
         ["Version", "4.2"],
         ["Owner", "People &amp; Culture — Head of HR Operations"],
         ["Approved by", "Chief Financial Officer"],
         ["Effective date", "1 July 2026"],
         ["Next review", "30 June 2027"],
         ["Classification", "Internal use only"]],
        [55 * mm, PAGE_W - 55 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("3. Key Principles", H1))
    s.extend(bullets([
        "<b>Necessity.</b> Travel must be the most effective way to achieve the business outcome.",
        "<b>Value for money.</b> Choose the lowest logical fare and reasonable accommodation.",
        "<b>Safety first.</b> No travel to a destination under a DFAT 'Do not travel' advisory.",
        "<b>Transparency.</b> Every expense must be supported by an itemised tax invoice.",
    ]))
    s.append(PageBreak())

    s.append(Paragraph("4. Booking and Approval", H1))
    s.append(Paragraph(
        "All travel must be booked through the corporate travel desk (Serko/Corporate Traveller) at least "
        "14 days before departure. Bookings made inside 7 days require written justification. Approval "
        "thresholds are based on the total estimated trip cost, including flights, accommodation and ground "
        "transport.", BODY))
    s.append(table(
        [["Trip type", "Estimated total cost", "Approver", "Lead time"],
         ["Domestic — intrastate", "Up to A$1,500", "Line manager", "7 days"],
         ["Domestic — interstate", "A$1,500 – A$5,000", "Department head", "14 days"],
         ["Trans-Tasman (NZ)", "A$3,000 – A$8,000", "Department head", "21 days"],
         ["International — Asia", "A$5,000 – A$12,000", "General Manager", "28 days"],
         ["International — other", "Above A$12,000", "CFO", "35 days"],
         ["Group travel (5+ staff)", "Any", "CFO", "35 days"]],
        [36 * mm, 40 * mm, 40 * mm, PAGE_W - 116 * mm]))
    s.append(Spacer(1, 8))
    s.append(picture(
        make_bar_chart("travel_spend", "FY2025 travel spend by category",
                       ["Air fares", "Hotels", "Ground", "Meals", "Other"],
                       [412000, 268000, 96000, 74000, 31000], "Figures in A$, group total, FY2025 (unaudited)"),
        150, "Figure 2. FY2025 travel spend by category."))
    s.append(Paragraph("4.1 Air travel class", H2))
    s.append(Paragraph(
        "Economy class is the standard for all flights under 6 hours. Premium economy may be approved for "
        "flights over 6 hours where the traveller works on the day of arrival. Business class requires prior "
        "CFO approval and is limited to flights over 10 hours.", BODY))
    s.append(PageBreak())

    s.append(Paragraph("5. Allowances and Caps", H1))
    s.append(Paragraph(
        "Meal allowances are paid as a reimbursement against actual expenditure, capped at the daily rates "
        "below. Where a meal is provided by the host, conference or airline, the corresponding portion of the "
        "allowance may not be claimed.", BODY))
    s.append(table(
        [["City / region", "Accommodation cap (per night)", "Meals (per day)", "Incidentals (per day)"],
         ["Sydney", "A$280", "A$130", "A$25"],
         ["Melbourne", "A$260", "A$125", "A$25"],
         ["Brisbane", "A$240", "A$115", "A$25"],
         ["Perth", "A$245", "A$115", "A$25"],
         ["Adelaide", "A$210", "A$105", "A$20"],
         ["Regional Australia", "A$190", "A$100", "A$20"],
         ["Auckland (NZ)", "NZ$300", "NZ$140", "NZ$28"],
         ["Singapore", "S$320", "S$95", "S$25"],
         ["Shanghai", "CNY 1,100", "CNY 400", "CNY 100"]],
        [42 * mm, 48 * mm, 34 * mm, PAGE_W - 124 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("5.1 Ground transport", H2))
    s.extend(bullets([
        "Rideshare and taxis are permitted for airport transfers and client meetings.",
        "Rental cars require a compact or mid-size class; excess reduction insurance is reimbursable.",
        "Private vehicle use is reimbursed at the ATO cents-per-kilometre rate (A$0.88/km for FY2026), capped at 5,000 km per employee per financial year.",
        "Parking and tolls are reimbursable with a receipt; traffic and parking fines are never reimbursable.",
    ]))
    s.append(Paragraph("5.2 Accommodation exceptions", H2))
    s.append(Paragraph(
        "If no compliant room is available within the cap (for example during a major conference), the traveller "
        "may book up to 25% above the cap with written approval from the department head recorded in the booking "
        "notes.", BODY))
    s.append(PageBreak())

    s.append(Paragraph("6. Approval and Reimbursement Workflow", H1))
    s.append(picture(
        make_flow("travel_flow", "Travel request to reimbursement",
                  ["Raise request\nin Workday", "Manager\napproval", "Book via\ntravel desk", "Submit claim\n(14 days)", "Payment\nnext cycle"]),
        174, "Figure 3. End-to-end travel approval and reimbursement workflow."))
    s.append(Paragraph("6.1 Expense claims", H1))
    s.append(Paragraph(
        "Claims must be submitted in Workday within 14 calendar days of returning. Each line requires an "
        "itemised tax invoice; credit card statements alone are not accepted. Claims older than 60 days are "
        "paid only with CFO approval.", BODY))
    s.append(table(
        [["Expense type", "Evidence required", "Reimbursable?"],
         ["Air fare, hotel, rental car", "Itemised tax invoice", "Yes"],
         ["Meals under A$50", "Receipt", "Yes"],
         ["Meals A$50 and above", "Itemised receipt + attendee list", "Yes"],
         ["Client entertainment", "Itemised receipt + business purpose", "Yes, with prior approval"],
         ["In-flight Wi-Fi", "Receipt", "Yes"],
         ["Mini-bar, in-room movies", "—", "No"],
         ["Airline lounge membership", "Invoice", "Only for staff travelling 12+ times/year"],
         ["Travel insurance", "Corporate policy", "Covered centrally — do not claim"],
         ["Partner or family travel costs", "—", "No"]],
        [44 * mm, 62 * mm, PAGE_W - 106 * mm]))
    s.append(PageBreak())

    s.append(Paragraph("7. Travel Safety and Insurance", H1))
    s.append(Paragraph(
        "All travellers are covered by the group corporate travel insurance policy (Policy CTI-2026-118, "
        "underwritten by Allianz Australia) from the moment they leave home until they return. Travellers must "
        "register their itinerary in the travel desk portal so the duty-of-care provider can locate them in an "
        "emergency.", BODY))
    s.append(table(
        [["Situation", "Contact", "Availability"],
         ["Medical emergency overseas", "Allianz Assistance +61 7 3305 7499", "24/7"],
         ["Lost passport", "Travel desk — travel@clenergy.com.au", "Business hours"],
         ["Flight disruption", "Corporate Traveller after-hours 1300 555 018", "24/7"],
         ["Security incident", "Head of Risk — risk@clenergy.com.au", "24/7 via on-call"]],
        [48 * mm, 66 * mm, PAGE_W - 114 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("8. Non-compliance", H1))
    s.append(Paragraph(
        "Expenses that breach this policy will not be reimbursed and, where already charged to a corporate card, "
        "must be repaid within 30 days. Repeated or deliberate breaches may result in withdrawal of the corporate "
        "card and disciplinary action under the Code of Conduct.", BODY))
    s.append(Paragraph("9. Frequently Asked Questions", H1))
    s.append(table(
        [["Question", "Answer"],
         ["Can I extend a business trip for personal leave?",
          "Yes, with manager approval. The company pays only the cost of the business-only itinerary; you cover the difference and your own insurance for the private portion."],
         ["Can I keep frequent flyer points?",
          "Yes. Points earned on business travel remain with the traveller, but a more expensive fare may never be chosen to earn points."],
         ["Who books travel for a candidate or contractor?",
          "The hiring manager raises the request; the travel desk books it against the recruiting cost centre."],
         ["What if my claim is rejected?",
          "Workday returns the claim with a reason. Correct and resubmit within 7 days, or escalate to Finance Shared Services."]],
        [58 * mm, PAGE_W - 58 * mm]))
    return s


# --------------------------------------------------------------------------- #
# 文档 2:Company IT Policy
# --------------------------------------------------------------------------- #
def it_story() -> list:
    s: list = []
    s.append(picture(make_banner("it_banner", "Company IT Policy", "Clenergy Australia — Effective 1 July 2026"), 174, "Figure 1. Policy cover banner."))
    s.append(Paragraph("1. Purpose and Scope", H1))
    s.append(Paragraph(
        "This policy defines how information technology assets, accounts and data are used and protected at "
        "Clenergy Australia Pty Ltd. It applies to every employee, contractor and third party who accesses "
        "company systems, on company-owned or personal devices, from any location.", BODY))
    s.append(Paragraph(
        "The policy supports our obligations under the Privacy Act 1988 (Cth), the Notifiable Data Breaches "
        "scheme, and our ISO/IEC 27001 certified information security management system.", BODY))
    s.append(Paragraph("2. Document Control", H1))
    s.append(table(
        [CONTROL_HEADER,
         ["Document ID", "CLE-IT-POL-011"],
         ["Version", "6.0"],
         ["Owner", "IT &amp; Security — Head of Information Security"],
         ["Approved by", "Chief Operating Officer"],
         ["Effective date", "1 July 2026"],
         ["Next review", "30 June 2027"],
         ["Classification", "Internal use only"]],
        [55 * mm, PAGE_W - 55 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("3. Acceptable Use", H1))
    s.extend(bullets([
        "Company systems are provided for business purposes; limited reasonable personal use is permitted.",
        "Never share your account credentials, including with IT staff — IT will never ask for your password.",
        "Do not install unapproved software, browser extensions or AI tools that process company data.",
        "Do not use personal cloud storage (Dropbox, personal Google Drive, WeChat) for company documents.",
    ]))
    s.append(PageBreak())

    s.append(Paragraph("4. Devices and Standard Build", H1))
    s.append(Paragraph(
        "IT issues a standard device based on role. All laptops are enrolled in Microsoft Intune, encrypted with "
        "BitLocker or FileVault, and must run the current supported OS release plus the Defender for Endpoint "
        "agent. Devices are refreshed on a 4-year cycle.", BODY))
    s.append(table(
        [["Role group", "Standard device", "Specification", "Refresh"],
         ["Office / admin", "Dell Latitude 5450", "i5 / 16 GB / 512 GB SSD", "4 years"],
         ["Engineering", "Dell Precision 3591", "i7 / 32 GB / 1 TB SSD", "4 years"],
         ["Design / simulation", "Dell Precision 5690", "i9 / 64 GB / 2 TB SSD + RTX", "3 years"],
         ["Sales / field", "MacBook Air 15\" M4", "16 GB / 512 GB SSD", "4 years"],
         ["Warehouse / site", "Zebra TC58 handheld", "Android, rugged", "3 years"],
         ["Executive", "MacBook Pro 14\" M4 Pro", "24 GB / 1 TB SSD", "3 years"]],
        [34 * mm, 44 * mm, 52 * mm, PAGE_W - 130 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("4.1 Mobile and BYOD", H2))
    s.append(Paragraph(
        "Staff who access email on a personal phone must enrol it in Intune app protection. The company can wipe "
        "company data only; personal photos and messages are never accessed. Rooted or jailbroken devices are "
        "blocked from all company services.", BODY))
    s.append(Paragraph("4.2 Loss or theft", H2))
    s.append(Paragraph(
        "Report a lost or stolen device to the Service Desk immediately (within 1 hour of discovery). IT will "
        "remotely lock and wipe the device and rotate the affected credentials.", BODY))
    s.append(PageBreak())

    s.append(Paragraph("5. Accounts, Passwords and Access", H1))
    s.append(Paragraph(
        "Access follows least privilege and is granted through role-based access groups in Microsoft Entra ID. "
        "Multi-factor authentication is mandatory for every account, including service accounts where technically "
        "supported.", BODY))
    s.append(picture(
        make_layers("it_tiers", "Access tiers and control requirements", [
            ("Tier 0 — Domain and cloud admin", "Dedicated admin account, PAM check-out, hardware key, 4-eyes approval"),
            ("Tier 1 — System and DB admin", "Privileged group, MFA + PIM, quarterly recertification"),
            ("Tier 2 — Application power user", "Role group membership, MFA, half-yearly recertification"),
            ("Tier 3 — Standard user", "SSO with MFA, default productivity apps only"),
        ]),
        168, "Figure 2. Access tiers and the controls required at each tier."))
    s.append(table(
        [["Control", "Requirement"],
         ["Password length", "Minimum 14 characters; passphrases encouraged"],
         ["Password reuse", "Last 10 passwords blocked; no reuse across systems"],
         ["Rotation", "No forced rotation; immediate reset on suspected compromise"],
         ["MFA", "Microsoft Authenticator number matching, or FIDO2 key for Tier 0/1"],
         ["Session timeout", "15 minutes idle lock on laptops; 8 hours for web sessions"],
         ["Joiner / mover / leaver", "Access provisioned within 1 business day; revoked within 2 hours of exit"]],
        [46 * mm, PAGE_W - 46 * mm]))
    s.append(PageBreak())

    s.append(Paragraph("6. Security Incidents", H1))
    s.append(Paragraph(
        "Any suspected incident — phishing, malware, lost device, accidental disclosure — must be reported to "
        "<b>security@clenergy.com.au</b> or the Service Desk on extension 4400. Staff who report an incident in "
        "good faith are never penalised, even where they caused it.", BODY))
    s.append(table(
        [["Severity", "Example", "Response target", "Escalation"],
         ["P1 — Critical", "Ransomware, data breach of customer PII", "15 minutes", "COO + CISO + legal, immediate"],
         ["P2 — High", "Compromised admin account, ERP outage", "1 hour", "Head of InfoSec"],
         ["P3 — Medium", "Single-user phishing click, malware detected and blocked", "4 business hours", "Security team"],
         ["P4 — Low", "Spam, policy question, false positive alert", "2 business days", "Service Desk"]],
        [30 * mm, 60 * mm, 30 * mm, PAGE_W - 120 * mm]))
    s.append(Spacer(1, 8))
    s.append(picture(
        make_bar_chart("it_incidents", "FY2025 reported security incidents by type",
                       ["Phishing", "Lost device", "Malware", "Misdirected email", "Other"],
                       [148, 37, 22, 19, 11], "Count of reported incidents, FY2025"),
        150, "Figure 3. FY2025 reported security incidents by type."))
    s.append(PageBreak())

    s.append(Paragraph("7. Data Classification and Handling", H1))
    s.append(table(
        [["Class", "Examples", "Storage", "External sharing"],
         ["Public", "Datasheets, published brochures", "Website, SharePoint", "Unrestricted"],
         ["Internal", "Policies, org charts, meeting notes", "SharePoint / Teams", "Staff and contractors only"],
         ["Confidential", "Contracts, pricing, source code", "SharePoint with restricted group", "NDA + manager approval"],
         ["Restricted", "Customer PII, payroll, board papers", "Encrypted, named-access site", "Prohibited without CISO approval"]],
        [26 * mm, 50 * mm, 44 * mm, PAGE_W - 120 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("8. Software and AI Tools", H1))
    s.append(Paragraph(
        "Software must be requested through the Service Desk catalogue and is licensed centrally. Generative AI "
        "tools may only be used through the company-approved tenant (Microsoft 365 Copilot and the internal "
        "Clenergy Knowledge Agent). Confidential or Restricted data must never be pasted into a public AI service.", BODY))
    s.append(table(
        [["Category", "Approved", "Requires approval", "Prohibited"],
         ["Productivity", "Microsoft 365, Teams", "Notion, Miro", "Personal cloud drives"],
         ["Development", "VS Code, Git, JetBrains", "Docker Desktop, WSL", "Cracked or unlicensed IDEs"],
         ["AI assistants", "M365 Copilot, Clenergy Knowledge Agent", "Approved vendor AI in contract", "Public chatbots with company data"],
         ["Remote access", "Company VPN, Intune-managed RDP", "Vendor support tools (time-boxed)", "TeamViewer personal, AnyDesk"]],
        [28 * mm, 48 * mm, 46 * mm, PAGE_W - 122 * mm]))
    s.append(Spacer(1, 6))
    s.append(Paragraph("9. Monitoring, Training and Compliance", H1))
    s.extend(bullets([
        "Company systems are logged and monitored for security purposes in line with the Privacy Policy.",
        "All staff complete security awareness training on induction and annually; simulated phishing runs quarterly.",
        "Breaches of this policy may lead to loss of access and disciplinary action under the Code of Conduct.",
        "Questions about this policy: <b>itsecurity@clenergy.com.au</b>.",
    ]))
    return s


def main() -> None:
    outputs = [
        build("company-travel-policy.pdf", "Company Travel Policy", "CLE-HR-TRV-004", travel_story()),
        build("company-it-policy.pdf", "Company IT Policy", "CLE-IT-POL-011", it_story()),
    ]
    for p in outputs:
        print(f"wrote {p} ({p.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
