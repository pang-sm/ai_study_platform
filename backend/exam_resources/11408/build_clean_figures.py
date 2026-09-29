"""Build the clean, watermark-free past-paper figures served to learners.

WHY THIS REPLACES THE SCANNED IMAGES. The scraped ``images/`` and ``assets/`` trees are not a
usable figure set: every file in them is a watermarked screenshot taken from a commercial
exam-prep site, and — measured on 2026-09-28 — every file attached to a question is a
screenshot of a DIFFERENT question (``2025_q33_1.jpg`` holds question 37; ``2026_q37_1.jpg``
holds question 40). So they could not be used as-is and could not even be used as a reference
to redraw from. What each question actually specifies is its own text, and where that text
fixes the figure completely, the figure below is drawn from it.

These are VECTOR drawings written here, not traced or cropped scans: no third-party watermark
can survive, nothing is hot-linked, and the text stays crisp at any zoom.

YEAR CONVENTION — read this before looking for a source. Every ``year`` in this project, in the
database and in every filename here, is the **paper / admission year** (`paper_year`), NOT the
calendar year the exam was sat. The two differ by one:

    held_year = paper_year - 1

so the paper everyone calls "2026 考研 408" — the one the DB stores as ``year=2026`` — was sat in
**December 2025**. Searching for a "2026" paper as a December-2026 exam finds nothing, because
that exam is still in the future. Search "2026 考研 408 真题" / "2025年12月 408 真题" instead.
Do not rename the database column: its values are correct; only the search phrasing has to match.

Run (from ``backend/``):  python exam_resources/11408/build_clean_figures.py
Idempotent: it only writes the files listed in ``FIGURES``.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---- palette: neutral ink on white, matching the exam pages the figures sit in ----------
INK = "#1f2933"
MUTED = "#52606d"
LINE = "#3e4c59"
FILL = "#f5f7fa"
ACCENT = "#1f4e79"
FONT = "system-ui, 'Segoe UI', 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif"


def esc(value: str) -> str:
    return (value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, content, size=15, anchor="middle", fill=INK, weight="400"):
    return (f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'text-anchor="{anchor}" fill="{fill}" font-weight="{weight}">{esc(content)}</text>')


def rect(x, y, w, h, label="", rx=6, fill=FILL, stroke=LINE, size=14, dy=5):
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
           f'stroke="{stroke}" stroke-width="1.6"/>']
    if label:
        out.append(text(x + w / 2, y + h / 2 + dy, label, size=size, weight="600"))
    return "".join(out)


def ellipse(cx, cy, rx, ry, label="", fill=FILL, dy=5, size=14):
    out = [f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{fill}" '
           f'stroke="{LINE}" stroke-width="1.6"/>']
    if label:
        out.append(text(cx, cy + dy, label, size=size, weight="600"))
    return "".join(out)


def link(x1, y1, x2, y2, label="", dashed=False, lx=None, ly=None, size=13, color=MUTED):
    dash = ' stroke-dasharray="6 5"' if dashed else ""
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" '
           f'stroke-width="1.6"{dash}/>']
    if label:
        out.append(text(lx if lx is not None else (x1 + x2) / 2,
                        ly if ly is not None else (y1 + y2) / 2 - 8,
                        label, size=size, fill=color))
    return "".join(out)


def arrow(x1, y1, x2, y2, label="", lx=None, ly=None, size=13):
    """A left-to-right arrow used by the sequence diagrams."""
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="1.6" '
           f'marker-end="url(#ah)"/>']
    if label:
        out.append(text(lx if lx is not None else (x1 + x2) / 2,
                        ly if ly is not None else y1 - 7, label, size=size, fill=ACCENT))
    return "".join(out)


DEFS = (
    '<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
    'markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{LINE}"/></marker></defs>'
)


def svg(width, height, body, caption=""):
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'width="{width}" height="{height}" role="img">')
    cap = text(width / 2, height - 10, caption, size=13, fill=MUTED) if caption else ""
    return f'{head}{DEFS}<rect width="{width}" height="{height}" fill="#ffffff"/>{body}{cap}</svg>'


def table(x, y, widths, header, rows, row_h=42, size=14, first_col_anchor="middle"):
    """A plain ruled table — the carrier for every 表 question in this paper.

    Cells are drawn, not transcribed: the numbers come from the question's own data (the stored
    stem, or a verified external transcription), never from a screenshot of one.
    """
    total = sum(widths)
    out = []
    height = row_h * (len(rows) + 1)
    # header band
    out.append(f'<rect x="{x}" y="{y}" width="{total}" height="{row_h}" fill="#eef2f6"/>')
    for index in range(len(rows) + 1):
        line_y = y + row_h * index
        out.append(f'<line x1="{x}" y1="{line_y}" x2="{x + total}" y2="{line_y}" '
                   f'stroke="{LINE}" stroke-width="1.2"/>')
    cursor = x
    out.append(f'<line x1="{x}" y1="{y}" x2="{x}" y2="{y + height}" stroke="{LINE}" stroke-width="1.2"/>')
    for width in widths:
        cursor += width
        out.append(f'<line x1="{cursor}" y1="{y}" x2="{cursor}" y2="{y + height}" '
                   f'stroke="{LINE}" stroke-width="1.2"/>')
    for col, cell in enumerate(header):
        left = x + sum(widths[:col])
        out.append(text(left + widths[col] / 2, y + row_h / 2 + 5, cell, size=size, weight="600"))
    for row_index, row in enumerate(rows):
        top = y + row_h * (row_index + 1)
        for col, cell in enumerate(row):
            left = x + sum(widths[:col])
            anchor = first_col_anchor if col == 0 else "middle"
            out.append(text(left + widths[col] / 2, top + row_h / 2 + 5, cell, size=size,
                            weight="600" if col == 0 else "400", anchor=anchor))
    return "".join(out)


def bitfields(x, y, parts, height=64, size=14):
    """A horizontal bit-field strip — the address split of a paged system, or an instruction word."""
    out = []
    cursor = x
    for label, bits, sub in parts:
        width = max(64, 22 + 7 * bits)
        fill = "#eef3f8" if sub else "#f5f7fa"
        out.append(f'<rect x="{cursor}" y="{y}" width="{width}" height="{height}" fill="{fill}" '
                   f'stroke="{LINE}" stroke-width="1.4"/>')
        out.append(text(cursor + width / 2, y + height / 2 + 1, label, size=size, weight="600"))
        out.append(text(cursor + width / 2, y + height / 2 + 20, f"{bits} 位", size=12, fill=MUTED))
        cursor += width
    return "".join(out), cursor - x



def chain(width, hops, caption="", height=190, endpoints=None):
    """A left-to-right chain: host — router(s) — host, each hop labelled with its bandwidth.

    ``hops`` is the list of edge labels; there are len(hops)+1 boxes, the ends being hosts and
    the middle being routers — which is what every link-bandwidth question in this paper shows.
    ``endpoints`` optionally names the two end hosts (default H1 and H{len(hops)+1}); questions
    whose ends are not consecutively numbered (e.g. H1 … H2) pass their real labels here.
    """
    body = []
    count = len(hops) + 1
    margin = 90
    step = (width - 2 * margin) / (count - 1)
    y = height / 2 - 26
    xs = [margin + index * step for index in range(count)]
    for index, x in enumerate(xs):
        if index in (0, count - 1):
            label = (endpoints or (f"H1", f"H{count}"))[0 if index == 0 else 1]
            body.append(rect(x - 40, y - 22, 80, 48, label, size=15))
        else:
            body.append(rect(x - 36, y - 20, 72, 44, f"R{index}", size=15))
    for index, label in enumerate(hops):
        body.append(link(xs[index] + 40, y + 2, xs[index + 1] - 36, y + 2, label))
    return svg(width, height, "".join(body), caption)


# --------------------------------------------------------------------- computer_network

def cn_2023_q33():
    """H1 and H2 joined by a router; both hops are 100 Mb/s (the question states it)."""
    return chain(560, ["100 Mb/s", "100 Mb/s"], "")


def cn_2024_q33():
    """Three links in series; the middle one is the 1 Mb/s bottleneck."""
    return chain(620, ["10 Mb/s", "1 Mb/s", "10 Mb/s"], "瓶颈链路 1 Mb/s")


def cn_2025_q33():
    """H1—R1 10 Mb/s, R1—R2 100 Mb/s, R2—H2 1000 Mb/s (ends are H1 and H2, not H1/H4)."""
    return chain(640, ["10 Mb/s", "100 Mb/s", "1000 Mb/s"], "", endpoints=("H1", "H2"))


def _nat(width=660):
    """H —(192.168.0.3)— R2 —(195.123.0.34/30)— R1 — Internet, R2 doing NAT."""
    y = 96
    body = [
        rect(30, y - 24, 96, 52, "H", size=15),
        text(78, y + 52, "192.168.0.3", size=12, fill=MUTED),
        rect(240, y - 24, 96, 52, "R2", size=15),
        text(288, y + 52, "192.168.0.1", size=12, fill=MUTED),
        rect(450, y - 24, 96, 52, "R1", size=15),
        rect(600, y - 24, 96, 52, "Internet", size=14),
        link(126, y + 2, 240, y + 2, "192.168.0.1", ly=y - 14),
        link(336, y + 2, 450, y + 2, "195.123.0.34/30", ly=y - 14),
        link(546, y + 2, 600, y + 2, ""),
    ]
    body.append(text(288, y + 74, "NAT", size=13, fill=ACCENT, weight="600"))
    return svg(730, 200, "".join(body), "")


def cn_2023_q38():
    return _nat()


def cn_2022_q36():
    """Two routers in series; the right one serves a switch, with host H attached."""
    y = 92
    body = [
        rect(30, y - 24, 92, 52, "R1", size=15),
        rect(220, y - 24, 92, 52, "R2", size=15),
        rect(410, y - 24, 110, 52, "交换机", size=14),
        rect(600, y - 24, 80, 52, "H", size=15),
        link(122, y + 2, 220, y + 2, "192.168.1.1/30", ly=y - 14),
        link(312, y + 2, 410, y + 2, ""),
        link(520, y + 2, 600, y + 2, ""),
        text(465, y + 52, "192.168.1.62/27", size=12, fill=MUTED),
        text(640, y + 52, "192.168.1.60", size=12, fill=MUTED),
    ]
    return svg(710, 200, "".join(body), "")


def cn_2026_q36():
    """A switch split into two VLANs, each port labelled with its host's MAC suffix."""
    y = 70
    body = [
        rect(230, y - 26, 240, 60, "交换机", size=15),
        f'<line x1="350" y1="{y - 26}" x2="350" y2="{y + 34}" stroke="{ACCENT}" '
        f'stroke-width="1.6" stroke-dasharray="6 5"/>',
        text(290, y + 52, "VLAN 1", size=13, fill=ACCENT, weight="600"),
        text(410, y + 52, "VLAN 2", size=13, fill=ACCENT, weight="600"),
    ]
    left = [("H1", "01"), ("H2", "02"), ("H3", "03")]
    right = [("H4", "04"), ("H5", "05"), ("H6", "06")]
    for index, (name, mac) in enumerate(left):
        x = 90 + index * 90
        body.append(rect(x - 38, y + 92, 76, 46, name, size=14))
        body.append(link(x, y + 34, x, y + 92, ""))
        body.append(text(x, y + 158, f"…-{mac}", size=12, fill=MUTED))
    for index, (name, mac) in enumerate(right):
        x = 470 + index * 90
        body.append(rect(x - 38, y + 92, 76, 46, name, size=14))
        body.append(link(x, y + 34, x, y + 92, ""))
        body.append(text(x, y + 158, f"…-{mac}", size=12, fill=MUTED))
    return svg(730, 330, "".join(body), "H3 位于 VLAN 1")


def cn_2025_q36():
    """The DHCP exchange the figure shows: DHCPOFFER then DHCPREQUEST, each carrying
    yiaddr 192.168.5.9; server 192.168.5.1. (No DHCPDISCOVER is drawn in the paper.)"""
    left, right = 130, 600
    body = [
        text(left, 34, "主机 H", size=15, weight="600"),
        text(right, 34, "DHCP 服务器", size=15, weight="600"),
        text(right, 54, "192.168.5.1", size=12, fill=MUTED),
        f'<line x1="{left}" y1="66" x2="{left}" y2="292" stroke="{LINE}" stroke-width="1.6"/>',
        f'<line x1="{right}" y1="66" x2="{right}" y2="292" stroke="{LINE}" stroke-width="1.6"/>',
        text(left - 52, 300, "时间", size=12, fill=MUTED, anchor="start"),
        arrow(right - 6, 152, left + 6, 152, "DHCPOFFER"),
        text(right, 176, "yiaddr: 192.168.5.9", size=12, fill=MUTED),
        arrow(left + 6, 248, right - 6, 248, "DHCPREQUEST"),
        text(right, 272, "yiaddr: 192.168.5.9", size=12, fill=MUTED),
    ]
    return svg(720, 330, "".join(body), "")


def cn_2025_q38():
    """甲 → 乙: at t0 two 1000 B data segments (both seq = 2001); acknowledged at t1 by a
    segment with seq = 4001, ack_seq = 3001, rcvwnd = 4000 B."""
    left, right = 150, 590
    body = [
        text(left, 46, "主机甲", size=15, weight="600"),
        text(right, 46, "主机乙", size=15, weight="600"),
        f'<line x1="{left}" y1="62" x2="{left}" y2="270" stroke="{LINE}" stroke-width="1.6"/>',
        f'<line x1="{right}" y1="62" x2="{right}" y2="270" stroke="{LINE}" stroke-width="1.6"/>',
        text(left - 8, 110, "t0", size=13, fill=MUTED, anchor="end"),
        arrow(left + 6, 116, right - 6, 116, "seq=2001，1000B数据"),
        arrow(left + 6, 156, right - 6, 156, "seq=2001，1000B数据"),
        arrow(right - 6, 226, left + 6, 226, "seq=4001，ack_seq=3001，rcvwnd=4000B"),
        text(left - 8, 232, "t1", size=13, fill=MUTED, anchor="end"),
        text(left - 60, 286, "发送窗口 = 拥塞窗口 = 2000 B，阈值 8000 B，MSS = 1000 B",
             size=13, fill=MUTED, anchor="start"),
    ]
    return svg(740, 310, "".join(body), "")


def cn_2024_q47():
    """Four ASes: AS1 (RIP) holding R11–R16, with AS2/AS3/AS4 attached and a shared prefix."""
    bw, bh = 92, 46
    cols = {0: 150, 1: 390, 2: 630}
    rows = {0: 292, 1: 386}
    body = [
        rect(280, 18, 220, 58, "", rx=29, fill="#eef3f8"),
        text(390, 43, "Internet", size=14, weight="600"),
        text(390, 64, "136.5.16.0/20", size=13, fill=ACCENT),
    ]
    cardinals = [("AS2", "R22", 20), ("AS3", "R33", 315), ("AS4", "R44", 610)]
    for name, router, x in cardinals:
        body.append(rect(x, 116, 150, 62, "", rx=10, fill="#eef3f8"))
        body.append(text(x + 75, 144, name, size=14, weight="600"))
        body.append(text(x + 75, 164, router, size=12, fill=MUTED))
    body.append(rect(20, 236, 740, 250, "", rx=14, fill="#fbfcfd"))
    body.append(text(42, 262, "AS1（内部网关协议：RIP）", size=13, anchor="start",
                     fill=ACCENT, weight="600"))
    node = {}
    for col, name in enumerate(("R11", "R12", "R13")):
        node[name] = (cols[col], rows[0])
    for col, name in enumerate(("R14", "R15", "R16")):
        node[name] = (cols[col], rows[1])
    for name, (x, y) in node.items():
        body.append(rect(x - bw / 2, y, bw, bh, name, size=14))
    # R11–R16 are the AS's internal mesh; the question only needs their arrangement.
    for a, b in (("R11", "R12"), ("R12", "R13"), ("R14", "R15"), ("R15", "R16"),
                 ("R11", "R14"), ("R12", "R15"), ("R13", "R16")):
        (x1, y1), (x2, y2) = node[a], node[b]
        if y1 == y2:
            body.append(link(x1 + bw / 2, y1 + bh / 2, x2 - bw / 2, y2 + bh / 2, ""))
        else:
            body.append(link(x1, y1 + bh, x2, y2, ""))
    for router, x in (("R11", 95), ("R12", 390), ("R13", 685)):
        body.append(link(x, 178, node[router][0], rows[0], ""))
    body.append(rect(52, 448, 154, 34, "210.2.3.0/24", size=12, fill="#eef3f8"))
    body.append(link(node["R14"][0], rows[1] + bh, 129, 448, ""))
    body.append(rect(568, 448, 154, 34, "210.2.4.0/24", size=12, fill="#eef3f8"))
    body.append(link(node["R16"][0], rows[1] + bh, 645, 448, ""))
    return svg(780, 508, "".join(body), "")


def cn_2026_q37():
    """R1 with links S0–S4 to R2/R3/R4; link cost R1–R2 changes from 2 to ∞."""
    body = [
        rect(90, 150, 90, 54, "R1", size=15),
        rect(330, 60, 90, 54, "R2", size=15),
        rect(540, 150, 90, 54, "R3", size=15),
        rect(330, 250, 90, 54, "R4", size=15),
        link(180, 166, 330, 96, "S1（费用 2 → ∞）", ly=104),
        link(180, 186, 540, 166, "S2", ly=150),
        link(180, 196, 330, 272, "S3", ly=262),
        text(135, 226, "S0", size=12, fill=MUTED),
        text(300, 246, "S4", size=12, fill=MUTED),
        link(180, 204, 300, 262, ""),
    ]
    return svg(700, 340, "".join(body),
                "R1 到 R2 的链路断开后重新计算路由")


# ------------------------------------------------------------------ computer_organization

# ------------------------------------------------------------------------ operating_system

def os_2022_q46():
    """The 6-operation precedence graph the question describes: A,B → C; C,D → E; E → F."""
    body = [
        rect(60, 90, 60, 48, "A", size=16),
        rect(60, 190, 60, 48, "B", size=16),
        rect(230, 140, 60, 48, "C", size=16),
        rect(230, 250, 60, 48, "D", size=16),
        rect(400, 195, 60, 48, "E", size=16),
        rect(560, 195, 60, 48, "F", size=16),
        link(120, 114, 230, 156, ""),
        link(120, 214, 230, 172, ""),
        link(290, 188, 400, 208, ""),
        link(290, 274, 400, 230, ""),
        link(460, 219, 560, 219, ""),
        text(590, 290, "T1 执行 A、E、F　T2 执行 B、C、D", size=13, fill=MUTED),
    ]
    return svg(720, 330, "".join(body), "")


def os_2025_q46():
    """The process address space, with the regions the question names."""
    regions = [
        ("内核区", "#e7ecf2"),
        ("用户栈", "#f5f7fa"),
        ("未占用", "#ffffff"),
        ("运行时堆", "#f5f7fa"),
        ("未占用", "#ffffff"),
        ("可读写数据段", "#f5f7fa"),
        ("只读代码段", "#e7ecf2"),
    ]
    body = [text(60, 34, "高地址", size=12, fill=MUTED, anchor="start")]
    y = 48
    for name, fill in regions:
        body.append(rect(60, y, 300, 44, name, rx=2, fill=fill, size=14))
        y += 44
    body.append(text(60, y + 22, "低地址", size=12, fill=MUTED, anchor="start"))
    return svg(430, y + 44, "".join(body), "")


# ------------------------------------------------- tables verified against the paper + answer
#
# A table is drawn here only when its numbers were (a) cross-checked against an independent
# transcription of the SAME (year, subject, question number) and (b) shown to REPRODUCE the
# answer this bank already stores for that question. (b) is what rules out the near-miss: a
# plausible-looking table that yields a different answer is not this question's table.

def os_2022_q25():
    """进程调度表 — three independent transcriptions agree; reproduces the stored answer C."""
    rows = [["P0", "0 ms", "15", "100 ms"], ["P1", "10 ms", "20", "60 ms"],
            ["P2", "10 ms", "10", "20 ms"], ["P3", "15 ms", "6", "10 ms"]]
    body = table(60, 40, [110, 200, 130, 170],
                 ["进程", "进入就绪队列的时刻", "优先级", "CPU 执行时间"], rows)
    return svg(670, 40 + 42 * 5 + 40, body, "值越小优先权越高")


def os_2022_q26():
    """银行家算法资源表 — Available (1,3,2) with these Need values yields exactly the two safe
    sequences the stored answer B counts."""
    rows = [["P0", "2, 0, 1", "0, 2, 1"], ["P1", "0, 2, 0", "1, 2, 3"],
            ["P2", "1, 0, 1", "0, 1, 3"]]
    body = table(60, 40, [110, 180, 180],
                 ["进程", "已分配资源数（A, B, C）", "尚需资源数（A, B, C）"], rows)
    body += text(60, 40 + 42 * 4 + 36, "当前可用资源数（A, B, C）=（1, 3, 2）",
                 size=14, anchor="start")
    return svg(700, 40 + 42 * 4 + 76, body, "")


def os_2023_q29():
    """进程调度表 — the 13 ms burst is the value that reproduces the stored answer B:
    (115 + 55 + 13) / 3 = 61 ms."""
    rows = [["P1", "0 ms", "1", "60 ms"], ["P2", "20 ms", "10", "42 ms"],
            ["P3", "30 ms", "100", "13 ms"]]
    body = table(60, 40, [110, 200, 130, 170],
                 ["进程", "进入就绪队列的时刻", "优先级", "CPU 执行时间"], rows)
    return svg(670, 40 + 42 * 4 + 40, body, "值越大优先权越高")


def os_2026_q28():
    """三级页表地址划分 — 25 + 9 + 9 + 9 + 12 = 64 bits; 2^9 x 2^9 third-level tables is the
    stored answer C."""
    body = [text(40, 30, "64 位虚拟地址划分", size=15, anchor="start", weight="600")]
    strip, width = bitfields(40, 46, [("补充位", 25, True), ("一级页表", 9, False),
                                      ("二级页表", 9, False), ("三级页表", 9, False),
                                      ("页内偏移", 12, False)])
    body.append(strip)
    body.append(text(40, 146, "页大小 4 KB（页内偏移 12 位）；每个页表项占 8 B",
                     size=14, anchor="start", fill=MUTED))
    return svg(width + 80, 186, "".join(body), "")


def os_2026_q45():
    """进程调度表（优先权 + 时间片轮转）— reproduces the stored answer: 10 time-slice
    interrupts, 7 dispatches, first dispatches P2(10ms) P4(20ms) P1(90ms) P3(140ms)."""
    rows = [["P1", "10", "3", "95"], ["P2", "10", "4", "20"],
            ["P3", "12", "2", "40"], ["P4", "14", "5", "60"]]
    body = table(60, 40, [110, 160, 130, 180],
                 ["进程", "到达时间（ms）", "优先权", "CPU 运行时间（ms）"], rows)
    body += text(60, 40 + 42 * 5 + 36, "时间片 50 ms；时间片中断间隔 10 ms",
                 size=14, anchor="start")
    return svg(660, 40 + 42 * 5 + 76, body, "优先权越大优先级越大")


def ds_2025_q11():
    """排序过程表 — these pass-by-pass sequences are what identify 希尔排序, the stored answer A."""
    rows = [["初始序列", "5, 25, 40, 30, 10, 20, 45, 15, 35"],
            ["第 1 趟排序后的序列", "5, 10, 20, 30, 15, 35, 45, 25, 40"],
            ["第 2 趟排序后的序列", "5, 10, 15, 25, 20, 30, 40, 35, 45"]]
    body = table(40, 40, [220, 400], ["序列", "关键字"], rows)
    return svg(680, 40 + 42 * 4 + 40, body, "")


def _tree_from_array(values):
    """The level-order array the question prints, read back as an actual tree.

    Node ``i`` (1-based) owns children ``2i`` and ``2i+1``, and ``-1`` means "no node here" —
    which is exactly the storage rule the question defines. Nothing is inferred: the shape is a
    function of the array.
    """
    def build(index):
        if index > len(values) or values[index - 1] == -1:
            return None
        return (values[index - 1], build(2 * index), build(2 * index + 1))
    return build(1)


def _draw_tree(node, x0, x1, y, dy, out):
    if node is None:
        return
    value, left, right = node
    cx = (x0 + x1) / 2
    if left is not None:
        lx = (x0 + cx) / 2
        out.append(link(cx, y + 22, lx, y + dy - 22, ""))
        _draw_tree(left, x0, cx, y + dy, dy, out)
    if right is not None:
        rx = (cx + x1) / 2
        out.append(link(cx, y + 22, rx, y + dy - 22, ""))
        _draw_tree(right, cx, x1, y + dy, dy, out)
    out.append(ellipse(cx, y, 23, 23, str(value), fill="#eef3f8", dy=5, size=14))


def ds_2022_q41():
    """两棵顺序存储的二叉树 T1 / T2 — both laid out from the arrays the stem itself prints."""
    t1 = _tree_from_array([40, 25, 60, -1, 30, -1, 80, -1, -1, 27])
    t2 = _tree_from_array([40, 50, 60, -1, 30, -1, -1, -1, -1, -1, 35])
    body = [text(230, 30, "T1", size=16, weight="600"), text(650, 30, "T2", size=16, weight="600")]
    _draw_tree(t1, 60, 400, 80, 88, body)
    _draw_tree(t2, 480, 820, 80, 88, body)
    body.append(text(40, 430, "T1.SqBiTNode = [40, 25, 60, -1, 30, -1, 80, -1, -1, 27]，ElemNum = 10",
                     size=13, anchor="start", fill=MUTED))
    body.append(text(40, 456, "T2.SqBiTNode = [40, 50, 60, -1, 30, -1, -1, -1, -1, -1, 35]，ElemNum = 11",
                     size=13, anchor="start", fill=MUTED))
    return svg(860, 484, "".join(body), "")


# ------------------------------------------- figures read from the official paper (2026-09-28)
#
# These were redrawn after viewing the question in the paper itself (downloaded for fact-checking
# only — no scan is ever shipped, cropped, or de-watermarked). Each one records what makes it
# trustworthy: the (year, subject, number) was re-read from the LIVE API immediately beforehand,
# the stem matches, and the drawing reproduces the answer the bank already stores.

def _darrow(x1, y1, x2, y2, label="", lx=None, ly=None, size=13, dx=0, dy=-8):
    """A directed edge for the graph questions."""
    out = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" stroke-width="1.6" '
           f'marker-end="url(#ah)"/>']
    if label:
        out.append(text(lx if lx is not None else (x1 + x2) / 2 + dx,
                        ly if ly is not None else (y1 + y2) / 2 + dy,
                        label, size=size, fill=ACCENT))
    return "".join(out)


def ds_2022_q7():
    """AOE 网. Edges and durations read from the paper; the slack they give is max at g, and the
    stored answer is B (g) — that agreement is the check, not the picture."""
    v = {1: (110, 250), 2: (250, 130), 3: (250, 330), 4: (410, 110), 5: (430, 330), 6: (580, 220)}
    body = [_darrow(*v[1], *v[2], "a=2", lx=165, ly=178),
            _darrow(*v[1], *v[3], "b=5", lx=168, ly=300),
            _darrow(*v[2], *v[3], "c=3", lx=228, ly=232),
            _darrow(*v[2], *v[4], "d=3", lx=330, ly=112),
            _darrow(*v[3], *v[4], "e=3", lx=330, ly=238),
            _darrow(*v[3], *v[5], "f=3", lx=348, ly=340),
            _darrow(*v[3], *v[6], "g=1", lx=462, ly=248),
            _darrow(*v[4], *v[5], "h=1", lx=392, ly=232),
            _darrow(*v[4], *v[6], "i=4", lx=506, ly=150),
            _darrow(*v[5], *v[6], "j=1", lx=520, ly=300)]
    for number, (x, y) in v.items():
        body.append(ellipse(x, y, 20, 20, str(number), fill="#eef3f8", dy=5, size=14))
    return svg(680, 400, "".join(body), "")


def ds_2022_q8():
    """5 阶 B 树 T. The root key list and the five leaves are read straight off the paper.

    Deleting 260 and rebalancing is what the question asks about; the drawing only has to show
    the tree as given.
    """
    root_keys = ["60", "90", "260", "350"]
    body = [text(40, 34, "5 阶 B 树 T", size=15, anchor="start", weight="600")]
    kw = 74
    rx = 110
    for index, key in enumerate(root_keys):
        body.append(rect(rx + index * kw, 60, kw, 44, key, rx=3))
    leaves = [["30", "50"], ["70", "80", "85"], ["100", "110"], ["280", "300"], ["400", "500"]]
    lx = 40
    for slot, leaf in enumerate(leaves):
        width = kw * len(leaf)
        for index, key in enumerate(leaf):
            body.append(rect(lx + index * kw, 190, kw, 44, key, rx=3))
        # Each child hangs off the root's own pointer slot — the slot sits before the first key
        # and between/after the rest, which is what makes it read as one node with five children
        # rather than five unrelated boxes.
        body.append(link(rx + slot * kw, 104, lx + width / 2, 190, ""))
        lx += width + 18
    # The root's five child slots are the gaps around its four keys.
    body.append(text(40, 268, "根结点 4 个关键字；5 个叶结点", size=13, anchor="start", fill=MUTED))
    return svg(lx + 20, 296, "".join(body), "")


def os_2022_q45():
    """文件系统 (a) 目录结构与 (b) 文件名/索引结点号/磁盘块号 表.

    The table reproduces the stored answer (doc shares inode 10 with course1, so x = 30) — the
    inconsistency a mis-transcribed table would show up as is exactly that x.
    """
    body = [text(60, 32, "题 45(a) 图　目录结构", size=14, anchor="start", weight="600")]
    body.append(rect(60, 60, 96, 40, "stu", rx=3))
    body.append(rect(240, 60, 110, 40, "course", rx=3))
    body.append(rect(240, 150, 110, 40, "doc", rx=3))
    body.append(link(156, 80, 240, 80, ""))
    body.append(link(156, 84, 240, 170, ""))
    body.append(rect(430, 30, 110, 40, "course1", rx=3))
    body.append(rect(430, 108, 110, 40, "course2", rx=3))
    body.append(link(350, 80, 430, 50, ""))
    body.append(link(350, 84, 430, 128, ""))

    rows = [["stu", "1", "10"], ["course", "2", "20"], ["course1", "10", "30"],
            ["course2", "100", "40"], ["doc", "10", "x"]]
    body.append(text(60, 250, "题 45(b) 图", size=14, anchor="start", weight="600"))
    body.append(table(60, 268, [170, 190, 170], ["文件名", "索引结点号", "磁盘块号"], rows))
    return svg(620, 268 + 42 * 6 + 40, "".join(body), "")


def cn_2022_q47():
    """网络拓扑. Every address and MAC is the one printed in the figure; 设备1 / 设备2 keep the
    paper's own labels, because identifying them is the question."""
    body = [
        ellipse(90, 130, 52, 26, "Internet", fill="#eef3f8", dy=5, size=13),
        rect(210, 110, 60, 42, "R", size=15),
        text(240, 104, "E0", size=12, fill=MUTED),
        text(250, 82, "192.168.0.1/25", size=12, fill=MUTED),
        text(250, 168, "00-11-11-11-11-A1", size=11, fill=MUTED),
        link(142, 130, 210, 130, ""),
        rect(400, 110, 60, 42, "S", size=15),
        link(270, 130, 400, 130, ""),
        rect(210, 230, 90, 44, "设备 1", size=14),
        rect(210, 330, 90, 44, "设备 2", size=14),
        link(240, 152, 240, 230, ""),
        link(240, 274, 240, 330, ""),
        rect(60, 234, 64, 40, "H1", size=14),
        link(124, 254, 210, 254, ""),
        rect(60, 336, 64, 40, "H2", size=14),
        rect(370, 336, 64, 40, "H3", size=14),
        link(124, 356, 210, 356, ""),
        link(300, 356, 370, 356, ""),
        # The AP / DHCP branch hangs off the switch.
        ellipse(392, 226, 26, 24, "AP", fill="#eef3f8", dy=5, size=12),
        link(400, 152, 392, 202, ""),
        text(322, 268, "00-11-11-11-11-C1", size=11, fill=MUTED, anchor="start"),
        # H4 and H5 are the two stations associated with the AP. The H4 link leaves to the
        # right of 设备2's branch, so it cannot be read as passing through H3.
        link(408, 246, 470, 244, ""),
        link(412, 248, 486, 350, ""),
        rect(480, 108, 150, 46, "DHCP 服务器", size=13),
        link(460, 130, 480, 130, ""),
        text(556, 172, "192.168.0.2/25", size=11, fill=MUTED),
        text(556, 190, "00-11-11-11-11-B1", size=11, fill=MUTED),
        rect(470, 244, 64, 40, "H5", size=14),
        rect(486, 350, 64, 40, "H4", size=14),
        text(486, 300, "192.168.0.4/25", size=11, fill=MUTED, anchor="start"),
        text(486, 318, "00-11-11-11-11-E1", size=11, fill=MUTED, anchor="start"),
        text(486, 412, "192.168.0.3/25", size=11, fill=MUTED, anchor="start"),
        text(486, 430, "00-11-11-11-11-D1", size=11, fill=MUTED, anchor="start"),
        text(240, 500, "H1 与 H2 同一广播域、不同冲突域；H2 与 H3 同一冲突域",
             size=12, fill=MUTED),
    ]
    return svg(680, 528, "".join(body), "")


def ds_2024_q7():
    """二叉搜索树. T is k3's RIGHT subtree, so every key in it satisfies k3 < x < k2 — the stored
    answer D. The figure forces exactly one option, which is what makes it checkable."""
    body = [ellipse(200, 60, 26, 26, "k1", fill="#eef3f8", dy=5, size=14),
            ellipse(330, 150, 26, 26, "k2", fill="#eef3f8", dy=5, size=14),
            ellipse(250, 250, 26, 26, "k3", fill="#eef3f8", dy=5, size=14),
            link(180, 80, 130, 150, ""), link(220, 80, 310, 130, ""),
            link(310, 170, 270, 232, ""), link(350, 170, 400, 240, ""),
            link(230, 270, 180, 330, ""), link(270, 270, 320, 330, "")]
    # The unlabelled subtrees are drawn as the paper draws them — triangles, not node lists,
    # because the question says nothing about their contents.
    for cx, cy in ((120, 190), (400, 280), (170, 370)):
        body.append(f'<polygon points="{cx - 26},{cy + 34} {cx + 26},{cy + 34} {cx},{cy - 26}" '
                    f'fill="#f5f7fa" stroke="{LINE}" stroke-width="1.5"/>')
    body.append(ellipse(320, 380, 26, 26, "T", fill="#eef3f8", dy=5, size=15))
    body.append(text(430, 380, "T 为 k3 的右子树", size=13, anchor="start", fill=MUTED))
    return svg(600, 430, "".join(body), "")


def cn_2024_q33():
    """分组交换网络. Redrawn faithfully to the paper: a diamond of four routers, not the
    straight chain an earlier revision drew from the 【图示信息】 summary alone."""
    body = [
        rect(40, 180, 76, 48, "H1", size=14),
        rect(190, 180, 90, 48, "路由器", size=13),
        rect(370, 80, 90, 48, "路由器", size=13),
        rect(370, 290, 90, 48, "路由器", size=13),
        rect(560, 180, 90, 48, "路由器", size=13),
        rect(700, 180, 76, 48, "H2", size=14),
        link(116, 204, 190, 204, "10 Mb/s", ly=194),
        link(280, 196, 370, 116, "1000 Mb/s", lx=322, ly=140),
        link(280, 214, 370, 300, "100 Mb/s", lx=318, ly=280),
        link(460, 104, 560, 190, "1000 Mb/s", lx=536, ly=132),
        link(460, 316, 560, 218, "100 Mb/s", lx=530, ly=300),
        # The paper also draws a DIRECT link between the two side routers, straight through
        # under the top one, labelled 1 Mb/s — that third path is what makes the access link
        # (10 Mb/s) the real bottleneck.
        link(280, 204, 560, 204, "1 Mb/s", lx=420, ly=224),
        link(650, 204, 700, 204, "10 Mb/s", ly=194),
    ]
    return svg(820, 380, "".join(body), "")


def co_2022_q43():
    """CPU 数据通路. Components and control signals are exactly the ones the paper labels; the
    question asks about the wiring, so each signal keeps its own arrow."""
    bus_top, bus_inner = 70, 210
    body = [
        text(400, 40, "系统总线", size=13, weight="600"),
        f'<line x1="150" y1="{bus_top}" x2="640" y2="{bus_top}" stroke="{LINE}" stroke-width="2.4"/>',
        text(600, 200, "内部总线", size=13, weight="600", anchor="end"),
        f'<line x1="150" y1="{bus_inner}" x2="640" y2="{bus_inner}" stroke="{LINE}" stroke-width="2.4"/>',
        text(676, 66, "Read", size=12, fill=ACCENT, anchor="start"),
        text(676, 86, "Write", size=12, fill=ACCENT, anchor="start"),
        # 主存储器 hangs off the system bus on the far left.
        rect(40, 120, 76, 120, "", rx=3),
        text(78, 176, "主存", size=13, weight="600"),
        text(78, 196, "储器", size=13, weight="600"),
        link(116, 150, 150, 90, ""),
        rect(170, 118, 84, 44, "MAR", size=13),
        rect(300, 148, 84, 44, "MDR", size=13),
        rect(430, 118, 70, 44, "PC", size=13),
        rect(540, 118, 70, 44, "IR", size=13),
        link(212, 162, 212, 210, "MARin", ly=190, size=11),
        link(342, 192, 342, 210, "MDRin", ly=204, size=11),
        link(342, 148, 342, 118, "MDRout", ly=132, size=11),
        link(465, 162, 465, 210, "PCin", ly=190, size=11),
        link(465, 118, 465, 70, "PCout", ly=96, size=11),
        link(575, 118, 575, 70, "IRin", ly=96, size=11),
        text(618, 112, "送 CU 等部件", size=11, fill=ACCENT, anchor="start"),
        # Operand path: 内部总线 → Y → ALU, and GPRs on the right.
        rect(170, 240, 70, 44, "Y", size=13),
        link(205, 210, 205, 240, "Yin", ly=232, size=11),
        rect(300, 236, 110, 56, "ALU", size=14),
        text(355, 224, "A 16 | B 16", size=11, fill=MUTED),
        text(355, 312, "F 16", size=11, fill=MUTED),
        text(430, 264, "ALUop", size=11, fill=ACCENT, anchor="start"),
        link(240, 256, 300, 256, ""),
        link(355, 292, 355, 320, ""),
        rect(320, 320, 70, 44, "Z", size=13),
        link(355, 364, 420, 364, ""),
        text(400, 386, "Zout", size=11, fill=ACCENT, anchor="middle"),
        rect(170, 320, 110, 44, "", rx=3),
        text(186, 338, "FR", size=12, weight="600", anchor="start"),
        text(186, 356, "SF OF…", size=11, fill=MUTED, anchor="start"),
        link(355, 340, 280, 340, ""),
        rect(500, 240, 120, 70, "GPRs", size=14),
        link(500, 256, 460, 256, "rd 4", ly=248, size=11),
        text(626, 262, "rs 4", size=11, fill=MUTED, anchor="start"),
        link(560, 310, 560, 330, "GPRin", ly=326, size=11),
        link(620, 256, 656, 256, ""),
        text(660, 260, "GPRout", size=11, fill=ACCENT, anchor="start"),
    ]
    return svg(740, 420, "".join(body), "")


def _mux(x, y, inputs, control, size=13, w=54, h=44):
    """A trapezoid multiplexer with the signal that drives it drawn underneath."""
    body = [f'<polygon points="{x},{y} {x + w},{y + 8} {x + w},{y + h - 8} {x},{y + h}" '
            f'fill="#f5f7fa" stroke="{LINE}" stroke-width="1.5"/>']
    body.append(text(x + w / 2, y - 6, "MUX", size=10, fill=MUTED))
    for index, label in enumerate(inputs):
        ly = y + 10 + index * ((h - 20) / max(1, len(inputs) - 1) if len(inputs) > 1 else 0)
        body.append(text(x - 8, ly + 4, label, size=11, fill=MUTED, anchor="end"))
    body.append(text(x + w / 2, y + h + 16, control, size=11, fill=ACCENT))
    return "".join(body)


def os_2026_q26():
    """每个进程执行的操作. The figure is the operation block the question points at; with S = -2
    it gives n = 2 blocked and m = 5 at the resource, matching the stored answer A (5,2)."""
    steps = ["wait(S)", "访问资源", "signal(S)"]
    body = [text(240, 34, "进程执行的操作", size=14, weight="600")]
    for index, step in enumerate(steps):
        y = 60 + index * 76
        body.append(rect(150, y, 180, 52, step, rx=4, size=14))
        if index < len(steps) - 1:
            body.append(arrow(240, y + 52, 240, y + 76, ""))
    body.append(text(240, 60 + 3 * 76 + 22, "资源 S 的初值为 5", size=13, fill=MUTED))
    return svg(480, 60 + 3 * 76 + 60, "".join(body), "")


def co_2026_q44():
    """计算机 C 的部分数据通路. Every component and every control signal is the one the paper
    labels — most importantly ① and ②, which sit immediately above the general register file and
    hold the register NUMBER to write, i.e. they are multiplexers (the stored answer for (1))."""
    body = [
        text(470, 30, "题 44 图　数据通路", size=14, weight="600"),
        # ── register file and its two write-number selectors ──
        rect(150, 250, 200, 110, "", rx=4),
        text(250, 292, "GPRs", size=15, weight="600"),
        text(250, 314, "通用寄存器组", size=12, fill=MUTED),
        text(196, 240, "Ra", size=12, weight="600"),
        text(306, 240, "Rb", size=12, weight="600"),
        rect(175, 130, 62, 44, "", rx=3), text(206, 158, "①", size=15, weight="600"),
        rect(285, 130, 62, 44, "", rx=3), text(316, 158, "②", size=15, weight="600"),
        link(206, 174, 206, 250, "", dashed=True), link(316, 174, 316, 250, "", dashed=True),
        text(206, 118, "IR.rt", size=11, fill=ACCENT), text(316, 118, "IR.rs", size=11, fill=ACCENT),
        text(120, 112, "RegWr", size=11, fill=ACCENT, anchor="end"),
        link(128, 118, 150, 150, ""),
        # ── the register-number multiplexer driven by RegDst ──
        _mux(30, 268, ["0", "IR.rt"], "RegDst"),
        link(84, 290, 150, 290, ""),
        # ── operand buses into the ALU's two source multiplexers ──
        link(350, 276, 420, 276, "bus A", ly=268, size=11),
        link(350, 334, 420, 334, "bus B", ly=326, size=11),
        _mux(420, 250, ["0", "1", "2"], "ALUBsrc", w=52, h=64),
        _mux(420, 360, ["0", "1"], "ARLAsrc"),
        # ── ALU ──
        f'<polygon points="540,250 640,268 640,392 540,410" fill="#f5f7fa" stroke="{LINE}" stroke-width="1.5"/>',
        text(578, 320, "A", size=13, weight="600"), text(578, 350, "L", size=13, weight="600"),
        text(578, 380, "U", size=13, weight="600"),
        link(472, 282, 540, 300, ""), link(472, 382, 540, 360, ""),
        text(590, 430, "ALUCtr", size=11, fill=ACCENT),
        link(590, 410, 590, 424, "", dashed=True),
        # ── MAR / MDR / memory ──
        link(640, 330, 700, 330, ""),
        _mux(700, 300, ["0", "1"], "MARSrc"),
        rect(780, 306, 74, 44, "MAR", size=12), link(754, 322, 780, 322, ""),
        rect(880, 190, 84, 210, "", rx=3),
        text(922, 282, "主", size=13, weight="600"), text(922, 302, "存", size=13, weight="600"),
        text(922, 322, "储", size=13, weight="600"), text(922, 342, "器", size=13, weight="600"),
        link(854, 322, 880, 322, "ABus", ly=312, size=11),
        rect(780, 400, 74, 44, "MDR", size=12), link(854, 422, 880, 422, ""),
        # ── PC, IR, CU ──
        rect(560, 110, 74, 44, "PC", size=13), text(597, 100, "PCin", size=11, fill=ACCENT),
        link(597, 104, 597, 110, "", dashed=True),
        link(634, 132, 700, 132, ""), link(700, 132, 700, 300, ""),
        rect(700, 110, 62, 40, "IR", size=13), text(731, 100, "IRin", size=11, fill=ACCENT),
        link(731, 104, 731, 110, "", dashed=True),
        link(762, 130, 800, 130, ""),
        rect(800, 110, 62, 40, "CU", size=13),
        text(831, 92, "控制信号", size=11, fill=ACCENT),
        link(831, 110, 831, 96, "", dashed=True),
        link(862, 130, 900, 130, ""),
        # ── extender and the write-data multiplexer ──
        rect(300, 470, 96, 46, "扩展器", size=12),
        text(300, 462, "IR11-0", size=11, fill=ACCENT, anchor="end"),
        link(348, 498, 348, 512, "", dashed=True),
        text(348, 526, "ExtOp", size=11, fill=ACCENT),
        link(240, 470, 300, 492, ""), text(262, 512, "12", size=10, fill=MUTED),
        text(412, 492, "16", size=10, fill=MUTED),
        _mux(300, 546, ["1", "0"], "Regwsrc"),
        link(348, 516, 340, 546, ""),
        link(327, 590, 327, 630, ""), link(327, 630, 250, 630, ""), link(250, 630, 250, 360, ""),
        link(640, 330, 640, 460, ""), link(640, 460, 780, 460, ""), link(780, 460, 780, 444, ""),
    ]
    return svg(990, 660, "".join(body), "")


def cn_2024_q35():
    """VLAN 交换机与各端口主机. Port membership and every IP/MAC are the paper's; the VLAN
    dividers are what make the ARP question answerable at all."""
    body = [rect(150, 60, 560, 130, "", rx=4),
            text(730, 122, "交换机", size=14, weight="600", anchor="start")]
    vlan_groups = [("VLAN1", 13, 17, 1, 5), ("VLAN2", 18, 20, 6, 8), ("VLAN3", 21, 24, 9, 12)]
    for name, up_lo, up_hi, lo_lo, lo_hi in vlan_groups:
        for port in range(up_lo, up_hi + 1):
            body.append(rect(160 + (port - 13) * 46, 84, 36, 30, str(port), rx=2, size=11))
        for port in range(lo_lo, lo_hi + 1):
            body.append(rect(160 + (port - 1) * 46, 138, 36, 30, str(port), rx=2, size=11))
        x = 160 + (up_lo - 13) * 46
        body.append(text(x + 40, 56, name, size=12, weight="600", fill=ACCENT))
    for after in (5, 8):  # the boundary after lower port 5 and after lower port 8
        dx = 160 + after * 46
        body.append(f'<line x1="{dx}" y1="70" x2="{dx}" y2="182" stroke="{ACCENT}" '
                    f'stroke-width="1.4" stroke-dasharray="7 4"/>')
    hosts = [("H1", "13", "192.168.3.91", "00-3E-C2-39-12-B5"),
             ("H2", "1", "192.168.3.81", "00-18-A2-3B-36-21"),
             ("H3", "2", "192.168.3.125", "00-E5-78-4A-09-B2"),
             ("H4", "5", "192.168.3.12", "00-35-6A-B1-4C-92"),
             ("H5", "8", "192.168.3.251", "00-1A-39-5B-E4-45"),
             ("H6", "9", "192.168.3.129", "00-08-6E-05-A7-82"),
             ("H7", "12", "192.168.3.190", "00-51-48-C9-63-A3")]
    for index, (name, port, ip, mac) in enumerate(hosts):
        px = int(port)
        cx = 160 + (px - 13) * 46 + 18 if px >= 13 else 160 + (px - 1) * 46 + 18
        cy = 99 if px >= 13 else 153
        hx = 40 + index * 108
        body.append(rect(hx, 300, 72, 40, name, size=13))
        body.append(link(hx + 36, 300, cx, cy + 30, ""))
        body.append(text(hx + 36, 360, ip, size=9, fill=MUTED))
        body.append(text(hx + 36, 376, mac, size=9, fill=MUTED))
    return svg(820, 400, "".join(body), "VLAN1 / VLAN2 / VLAN3 按端口划分")


def cn_2024_q37():
    """SR 滑动窗口时序图. Which frames were sent, which one never arrived, and which two the
    learner must identify at t1/t2 is the whole question — none of it is in the stem.

    The paper draws F0/F2/F3 as complete arrows and F1 as a stub that stops short with 丢失
    beside its tip; only ACK0 and ACK3 are drawn on the return path."""
    left, right, top = 190, 640, 70
    body = [text(left, 44, "甲", size=15, weight="600"), text(right, 44, "乙", size=15, weight="600"),
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="430" stroke="{LINE}" stroke-width="1.6"/>',
            f'<line x1="{right}" y1="{top}" x2="{right}" y2="430" stroke="{LINE}" stroke-width="1.6"/>',
            _darrow(left + 6, 100, right - 6, 110, ""), text(410, 96, "F0", size=13, fill=ACCENT),
            _darrow(left + 6, 140, left + 70, 146, ""), text(410, 136, "F1", size=13, fill=ACCENT),
            text(280, 156, "丢失", size=13, fill=ACCENT, anchor="start"),
            _darrow(left + 6, 180, right - 6, 190, ""), text(410, 176, "F2", size=13, fill=ACCENT),
            _darrow(left + 6, 220, right - 6, 230, ""), text(410, 216, "F3", size=13, fill=ACCENT),
            _darrow(right - 6, 300, left + 6, 250, ""), text(470, 256, "ACK0", size=13, fill=ACCENT),
            _darrow(right - 6, 350, left + 6, 330, ""), text(470, 356, "ACK3", size=13, fill=ACCENT),
            ellipse(left, 372, 8, 8, "", fill=ACCENT), text(left - 26, 376, "t1", size=12, fill=ACCENT),
            _darrow(left + 6, 378, left + 70, 384, ""), text(280, 366, "?", size=15, fill=ACCENT),
            text(left - 80, 408, "F1 超时", size=12, fill=ACCENT),
            ellipse(left, 404, 8, 8, "", fill=ACCENT), text(left - 26, 408, "t2", size=12, fill=ACCENT),
            _darrow(left + 6, 410, left + 70, 416, ""), text(280, 398, "?", size=15, fill=ACCENT),
            _darrow(left, 430, left, 462, ""), text(left, 484, "时间", size=13, fill=MUTED)]
    return svg(720, 500, "".join(body), "")


def co_2024_q43a():
    """题 43 图(a) — 指令格式表. add / slli / lw 的字段划分与编码."""
    body = [text(30, 30, "题 43 图（a）　指令格式", size=13, anchor="start", weight="600")]
    widths = [100, 126, 92, 92, 84, 76, 134]
    header = ["指令", "31　　25", "24　20", "19　15", "14　12", "11　7", "6　　　0"]
    rows = [["add", "0000000", "rs2", "rs1", "000", "rd", "0110011"],
            ["slli", "0000000", "shamt", "rs1", "010", "rd", "0010011"],
            ["lw", "imm", "—", "rs1", "010", "rd", "0000011"]]
    body.append(table(30, 46, widths, header, rows, row_h=34))
    body.append(text(780, 74, "指令功能说明", size=12, anchor="start", weight="600"))
    for index, desc in enumerate(["R[rd]←R[rs1]+R[rs2]", "R[rd]←R[rs1]<<shamt",
                                  "R[rd]←M[R[rs1]+imm]"]):
        body.append(text(780, 100 + index * 34, desc, size=12, anchor="start"))
    return svg(1010, 190, "".join(body), "")


def co_2024_q43b():
    """题 43 图(b) — 数据通路. A/B 两条 32 位输入、IR[31:20] 经扩展器进 MUX、ALU 与四个标志."""
    body = [text(30, 30, "题 43 图（b）　数据通路", size=13, anchor="start", weight="600"),
            text(120, 186, "A", size=14, weight="600"), text(176, 186, "32", size=11, fill=MUTED),
            link(130, 190, 480, 190, ""),
            text(120, 258, "B", size=14, weight="600"), text(176, 258, "32", size=11, fill=MUTED),
            link(130, 262, 380, 262, ""),
            text(60, 322, "IR[31:20]", size=12, weight="600", anchor="start"),
            text(60, 342, "12", size=11, fill=MUTED, anchor="start"),
            link(130, 330, 240, 330, ""),
            rect(240, 306, 96, 48, "扩展器", size=12),
            text(288, 380, "Ext", size=11, fill=ACCENT),
            link(288, 354, 288, 368, "", dashed=True),
            link(288, 384, 288, 394, "", dashed=True),
            text(348, 326, "32", size=11, fill=MUTED),
            link(336, 330, 380, 330, ""),
            _mux(380, 240, ["0", "1"], "ALUBsrc", w=58, h=110),
            link(438, 296, 480, 296, ""),
            f'<polygon points="480,150 580,170 580,340 480,360" fill="#f5f7fa" stroke="{LINE}" stroke-width="1.5"/>',
            text(516, 244, "A", size=13, weight="600"), text(516, 266, "L", size=13, weight="600"),
            text(516, 288, "U", size=13, weight="600"),
            text(536, 386, "ALUCtr", size=11, fill=ACCENT),
            link(530, 360, 530, 374, "", dashed=True),
            text(566, 390, "3", size=11, fill=MUTED),
            text(240, 424, "0：零扩展　　1：符号扩展", size=11, anchor="start", fill=MUTED),
            text(240, 444, "ALUCtr：000 加　　001 减　　010 逻辑左移", size=11, anchor="start", fill=MUTED)]
    for index, flag in enumerate(["OF", "SF", "ZF", "CF"]):
        y = 194 + index * 34
        body.append(link(580, y, 646, y, ""))
        body.append(text(656, y + 5, flag, size=12, anchor="start", weight="600"))
    body.append(link(580, 330, 720, 330, ""))
    body.append(text(730, 335, "F", size=14, weight="600", anchor="start"))
    body.append(text(670, 318, "32", size=11, fill=MUTED))
    return svg(790, 470, "".join(body), "")


def co_2024_q44():
    """题 44 图 — 从 0013DFF0H 起的存储单元内容. The byte at 0013E004 is what the answer turns on."""
    rows = [["0013 DFF0", "FF", "FF", "FF", "7C", "70", "FE", "FF", "FF"],
            ["0013 DFF8", "00", "00", "00", "0C", "3C", "02", "01", "FF"],
            ["0013 E000", "F0", "F1", "00", "00", "DC", "EC", "FF", "FF"],
            ["0013 E008", "FF", "FF", "01", "02", "00", "00", "01", "02"]]
    body = [text(40, 28, "题 44 图", size=13, anchor="start", weight="600")]
    body.append(table(40, 44, [140] + [64] * 8,
                      ["地址", "0", "1", "2", "3", "4", "5", "6", "7"], rows, row_h=38))
    return svg(730, 44 + 38 * 5 + 40, "".join(body), "小端方式；页大小 4KB")


def co_2025_q44a():
    """题 44 图(a) — 机器级代码片段. The stem only points at it, so it has to be drawn."""
    code = ["...", "//x 在 R2 中，i 在 R4 中", "//数组 d 的首地址在 R3 中",
            "mov   R1, (R3+R4*4)   //R1←d[i]",
            "sccov R1              //{R0, R1}←SEXT(R1)",
            "idiv  R1, R2          //R1←{R0, R1}/R2", "..."]
    body = [text(40, 28, "题 44 图（a）", size=13, anchor="start", weight="600")]
    for index, line in enumerate(code):
        body.append(text(40, 58 + index * 26, line, size=12, anchor="start"))
    return svg(520, 58 + len(code) * 26 + 26, "".join(body), "")


def co_2025_q44b():
    """题 44 图(b) — 补码除法器逻辑结构. 控制逻辑 holds the counter, which is part of the question."""
    body = [text(40, 28, "题 44 图（b）", size=13, anchor="start", weight="600"),
            rect(300, 50, 150, 36, "除数寄存器 Y", size=12),
            text(285, 92, "32", size=11, fill=MUTED, anchor="end"),
            link(375, 86, 375, 120, ""),
            f'<polygon points="290,120 460,120 430,190 320,190" fill="#f5f7fa" stroke="{LINE}" stroke-width="1.5"/>',
            text(375, 158, "32 位 ALU", size=12, weight="600"),
            text(455, 106, "32", size=11, fill=MUTED, anchor="start"),
            link(240, 120, 290, 132, ""), text(238, 116, "32", size=11, fill=MUTED, anchor="end"),
            text(500, 128, "ALUop", size=11, fill=ACCENT, anchor="start"),
            link(470, 128, 600, 128, "", dashed=True),
            text(363, 206, "32", size=11, fill=MUTED, anchor="end"),
            link(375, 190, 375, 226, ""),
            rect(180, 226, 190, 40, "余数寄存器 R", size=12),
            rect(370, 226, 190, 40, "余数/商寄存器 Q", size=12),
            text(375, 286, "32 位", size=11, fill=MUTED),
            text(600, 236, "左移", size=12, fill=ACCENT, anchor="start"),
            text(600, 260, "写使能", size=12, fill=ACCENT, anchor="start"),
            link(600, 226, 565, 230, ""), link(600, 250, 565, 248, ""),
            ellipse(660, 300, 62, 40, "控制逻辑", fill="#eef3f8", dy=5, size=12),
            link(660, 340, 660, 366, ""), text(660, 384, "时钟", size=12, fill=ACCENT),
            link(600, 128, 660, 128, ""), link(660, 128, 660, 260, "", dashed=True),
            link(180, 246, 100, 246, ""), link(100, 246, 100, 132, ""),
            link(100, 132, 240, 132, ""), text(120, 122, "32", size=11, fill=MUTED, anchor="start"),
            link(370, 286, 370, 320, ""), link(370, 320, 620, 320, ""),
            link(620, 320, 620, 296, "")]
    return svg(760, 410, "".join(body), "")


def ds_2023_q5():
    """二叉树的树型. The paper draws it UNLABELLED — the shape is the information, and the
    letters come from the traversal in the stem, so labelling it would give the answer away."""
    body = [ellipse(260, 60, 28, 28, "", fill="#eef3f8"),
            ellipse(170, 165, 28, 28, "", fill="#eef3f8"),
            ellipse(360, 165, 28, 28, "", fill="#eef3f8"),
            ellipse(110, 270, 28, 28, "", fill="#eef3f8"),
            ellipse(240, 270, 28, 28, "", fill="#eef3f8"),
            ellipse(170, 375, 28, 28, "", fill="#eef3f8"),
            link(240, 82, 190, 142, ""), link(280, 82, 340, 142, ""),
            link(152, 188, 124, 246, ""), link(190, 188, 224, 246, ""),
            link(126, 296, 152, 350, "")]
    return svg(480, 440, "".join(body), "树型如图；后序遍历为 f，d，b，e，c，a")


def ds_2025_q42():
    """AOE 网. The wiring is confirmed by the paper's own ve/vl tables: this graph reproduces
    ve = 0,9,2,5,12,6,9 and vl = 0,10,2,5,12,8,9 exactly."""
    v = {3: (110, 260), 1: (280, 150), 2: (560, 140), 4: (420, 250),
         5: (700, 250), 6: (280, 360), 7: (560, 360)}
    body = [_darrow(*v[3], *v[1], "a=2", lx=190, ly=196),
            _darrow(*v[1], *v[2], "b=5", lx=420, ly=136),
            _darrow(*v[3], *v[6], "c=1", lx=190, ly=330),
            _darrow(*v[1], *v[4], "d=3", lx=352, ly=186),
            _darrow(*v[3], *v[4], "e=3", lx=260, ly=246),
            _darrow(*v[4], *v[2], "f=4", lx=500, ly=182),
            _darrow(*v[4], *v[6], "g=1", lx=356, ly=314),
            _darrow(*v[6], *v[7], "h=1", lx=420, ly=384),
            _darrow(*v[4], *v[5], "j=1", lx=560, ly=258),
            _darrow(*v[2], *v[5], "k=2", lx=644, ly=176),
            _darrow(*v[4], *v[7], "m=4", lx=492, ly=330),
            _darrow(*v[7], *v[5], "n=3", lx=634, ly=318)]
    for number, (x, y) in v.items():
        body.append(ellipse(x, y, 22, 22, str(number), fill="#eef3f8", dy=5, size=14))
    return svg(800, 430, "".join(body), "共 12 个活动")


def co_2026_q43():
    """题 43 表 — the four-instruction table the question's part (4) depends on.

    This is the ONLY figure this question needs. An earlier revision drew the R/I/M instruction
    formats instead, which the stem already states verbatim; that figure was withdrawn. What is
    missing is this table.

    It is drawn with the BLANKS IN PLACE. The published answers (①=1110, ②=0000 0100,
    ③=1111 1011, ④=0000 0000 0010) were used only to check that the layout is right — they are
    deliberately NOT rendered, because the learner's task is to fill ①–④.
    """
    x0, col_w = 40, 132
    groups_x = [x0 + 150 + index * col_w for index in range(4)]
    body = [text(x0, 30, "题 43 表", size=14, anchor="start", weight="600"),
            text(x0, 56, "指令", size=12, weight="600", anchor="start")]
    for index, label in enumerate(["15 ~ 12", "11 ~ 8", "7 ~ 4", "3 ~ 0"]):
        body.append(text(groups_x[index] + col_w / 2, 56, label, size=11, fill=MUTED))

    # (指令, [(text, spans_columns), ...]) — a blank spans the bit width the answer needs, which
    # is what tells the learner how wide the field is.
    rows = [("I1", [("①", 1), ("0000", 1), ("0000", 1), ("0000", 1)]),
            ("I2", [("0000", 1), ("②", 2), ("0010", 1)]),
            ("I3", [("0100", 1), ("0000", 1), ("③", 2)]),
            ("I4", [("1111", 1), ("④", 3)])]
    y = 72
    for name, cells in rows:
        body.append(text(x0, y + 32, name, size=13, weight="600", anchor="start"))
        col = 0
        for value, span in cells:
            left = groups_x[col]
            width = col_w * span
            blank = value in ("①", "②", "③", "④")
            body.append(rect(left, y, width, 44, "", rx=3,
                             fill="#ffffff" if blank else FILL))
            if blank:
                body.append(f'<line x1="{left + 14}" y1="{y + 30}" x2="{left + width - 14}" '
                            f'y2="{y + 30}" stroke="{LINE}" stroke-width="1.2"/>')
            body.append(text(left + width / 2, y + 27, value, size=13, weight="600"))
            col += span
        y += 52
    body.append(text(x0, y + 12, "①～④ 待填写", size=11, anchor="start", fill=MUTED))
    return svg(1000, y + 36, "".join(body), "")


def ds_2024_q4():
    """无向图 G=(V,E) 的邻接多重表. Every firstedge, ilink and jlink is reproduced.

    Read from the paper's own figure at native resolution (the embedded image is 664x414; the page
    renders I tried earlier were upsampled and carried no extra detail), with the vertex chains
    cross-checked against an independent transcription (CodeBrick) that publishes the SAME edge set
    (e1 a-b, e2 a-d, e3 b-d, e4 c-a, e5 d-c, e6 e-c, e7 e-d) and the same chains. Seven of the
    links were readable straight off the scan and all seven agree with that transcription; the
    remaining ones are the only assignment that closes all five chains with no omission and no
    repeat, which is what makes this the paper's structure rather than an equivalent one.
    """
    CW, CH = 58, 46
    colA, colB = 250, 620
    rows = {"N1": (colA, 50), "N2": (colB, 50), "N3": (colA, 110), "N4": (colA, 170),
            "N5": (colA, 230), "N6": (colA, 290), "N7": (colB, 290)}
    # edge id -> (ivex, jvex, ilink, jlink) for the seven edge nodes
    NODES = {"N1": ("a", "b", "N2", None), "N2": ("a", "d", "N4", "N3"),
             "N3": ("b", "d", "N1", None), "N4": ("c", "a", "N5", None),
             "N5": ("d", "c", "N7", "N6"), "N6": ("e", "c", "N7", None),
             "N7": ("e", "d", None, "N2")}
    body = [text(40, 34, "顶点表", size=13, anchor="start", weight="600")]

    def cellx(node, index):
        return rows[node][0] + index * CW

    def cy(node):
        return rows[node][1] + CH / 2 + 5

    for index, name in enumerate(["a", "b", "c", "d", "e"]):
        y = 50 + index * 60
        body.append(rect(40, y, 70, CH, f"{index} {name}", size=12))
        body.append(rect(110, y, 80, CH, "", rx=3, fill="#ffffff"))
    for node, (x, y) in rows.items():
        ivex, jvex, ilink, jlink = NODES[node]
        for index in range(5):
            body.append(rect(x + index * CW, y, CW, CH, "", rx=0, fill="#ffffff"))
        body.append(text(cellx(node, 1) + CW / 2, cy(node), ivex, size=13, weight="600"))
        body.append(text(cellx(node, 3) + CW / 2, cy(node), jvex, size=13, weight="600"))
        body.append(text(cellx(node, 4) + CW / 2, cy(node), "∧" if jlink is None else "",
                         size=14, fill=MUTED))
        body.append(text(cellx(node, 2) + CW / 2, cy(node), "∧" if ilink is None else "",
                         size=14, fill=MUTED))
        # the pointer stubs the paper draws inside the two link cells
        if ilink:
            body.append(link(cellx(node, 2) + CW - 12, y + 12, cellx(node, 2) + CW - 12, y + CH - 12, ""))
        if jlink:
            body.append(link(cellx(node, 4) + CW - 12, y + 12, cellx(node, 4) + CW - 12, y + CH - 12, ""))

    # ── firstedge ──
    for index, (name, node) in enumerate(zip("abcde", ["N1", "N3", "N4", "N5", "N6"])):
        y = 50 + index * 60 + CH / 2
        body.append(_darrow(190, y, rows[node][0] - 2, y, ""))

    def path(points, label=""):
        d = " ".join(f"{'M' if i == 0 else 'L'} {x} {y}" for i, (x, y) in enumerate(points))
        out = [f'<path d="{d}" fill="none" stroke="{LINE}" stroke-width="1.5" '
               f'marker-end="url(#ah)"/>']
        return "".join(out)

    il = lambda node: cellx(node, 2) + CW - 12      # ilink stub x
    jl = lambda node: cellx(node, 4) + CW - 12      # jlink stub x
    top = lambda node: rows[node][1]
    bot = lambda node: rows[node][1] + CH

    body.append(path([(il("N1"), top("N1")), (il("N1"), 28), (il("N2"), 28), (il("N2"), top("N2"))]))
    body.append(path([(il("N3"), top("N3")), (il("N3"), 103), (565, 103), (565, 74), (540, 74)]))
    body.append(path([(il("N2"), bot("N2")), (il("N2"), 194), (540, 194)]))
    body.append(path([(jl("N2"), bot("N2")), (jl("N2"), 134), (540, 134)]))
    body.append(path([(il("N4"), bot("N4")), (il("N4"), 222), (565, 222), (565, 254), (540, 254)]))
    body.append(path([(il("N5"), bot("N5")), (il("N5"), 282), (565, 282), (565, 352),
                      (colB + 2.5 * CW, 352), (colB + 2.5 * CW, bot("N7"))]))
    body.append(path([(jl("N5"), bot("N5")), (jl("N5"), top("N6"))]))
    body.append(path([(il("N6"), bot("N6")), (il("N6"), 364), (colA + 2.3 * CW, 364),
                      (colA + 2.3 * CW, bot("N7"))]))
    body.append(path([(colB + 5 * CW, cy("N7")), (960, cy("N7")), (960, 74), (colB + 5 * CW, 74)]))
    body.append(text(colA + 2.5 * CW, 410, "顶点表 firstedge → 边结点；ilink / jlink 指向依附于 ivex / jvex 的下一条边；∧ 为链尾",
                     size=11, fill=MUTED))
    return svg(1010, 430, "".join(body), "")


# --------------------------------------------------------------------------------- registry

FIGURES = {
    ("computer_network", 2023, 33): ("2023_q33_1.svg", cn_2023_q33),
    ("computer_network", 2024, 33): ("2024_q33_1.svg", cn_2024_q33),
    ("computer_network", 2025, 33): ("2025_q33_1.svg", cn_2025_q33),
    ("computer_network", 2022, 36): ("2022_q36_1.svg", cn_2022_q36),
    ("computer_network", 2026, 36): ("2026_q36_1.svg", cn_2026_q36),
    ("computer_network", 2025, 36): ("2025_q36_1.svg", cn_2025_q36),
    ("computer_network", 2025, 38): ("2025_q38_1.svg", cn_2025_q38),
    # NOTE: computer_network 2022 Q38 is deliberately ABSENT. That question is a TCP
    # congestion-window calculation with no figure; an earlier revision attached a NAT diagram
    # to it by mistake. Do not re-add a figure for a question whose stem does not ask for one.
    ("computer_network", 2023, 38): ("2023_q38_1.svg", cn_2023_q38),
    ("operating_system", 2022, 25): ("2022_q25_1.svg", os_2022_q25),
    ("operating_system", 2022, 26): ("2022_q26_1.svg", os_2022_q26),
    ("operating_system", 2023, 29): ("2023_q29_1.svg", os_2023_q29),
    ("operating_system", 2026, 28): ("2026_q28_1.svg", os_2026_q28),
    ("operating_system", 2026, 45): ("2026_q45_1.svg", os_2026_q45),
    ("data_structure", 2025, 11): ("2025_q11_1.svg", ds_2025_q11),
    ("data_structure", 2022, 41): ("2022_q41_1.svg", ds_2022_q41),
    ("data_structure", 2022, 7): ("2022_q7_1.svg", ds_2022_q7),
    ("data_structure", 2022, 8): ("2022_q8_1.svg", ds_2022_q8),
    ("operating_system", 2022, 45): ("2022_q45_1.svg", os_2022_q45),
    ("computer_network", 2022, 47): ("2022_q47_1.svg", cn_2022_q47),
    ("data_structure", 2024, 4): ("2024_q4_1.svg", ds_2024_q4),
    ("data_structure", 2024, 7): ("2024_q7_1.svg", ds_2024_q7),
    ("computer_organization", 2022, 43): ("2022_q43_1.svg", co_2022_q43),
    ("computer_network", 2024, 47): ("2024_q47_1.svg", cn_2024_q47),
    ("computer_network", 2026, 37): ("2026_q37_1.svg", cn_2026_q37),
    ("computer_organization", 2026, 44): ("2026_q44_1.svg", co_2026_q44),
    # The table that 2026 Q43 part (4) depends on — the format diagram that used to live here was
    # withdrawn, not this.
    ("computer_organization", 2026, 43): ("2026_q43_1.svg", co_2026_q43),
    ("operating_system", 2026, 26): ("2026_q26_1.svg", os_2026_q26),
    # --- figures read from the official papers, second batch (2026-09-29) ---
    ("computer_network", 2024, 35): ("2024_q35_1.svg", cn_2024_q35),
    ("computer_network", 2024, 37): ("2024_q37_1.svg", cn_2024_q37),
    ("computer_organization", 2024, 43): [("2024_q43_1.svg", co_2024_q43a),
                                           ("2024_q43_2.svg", co_2024_q43b)],
    ("computer_organization", 2024, 44): ("2024_q44_1.svg", co_2024_q44),
    ("computer_organization", 2025, 44): [("2025_q44_1.svg", co_2025_q44a),
                                          ("2025_q44_2.svg", co_2025_q44b)],
    ("data_structure", 2023, 5): ("2023_q5_1.svg", ds_2023_q5),
    # NOTE: data_structure 2024 Q4 is deliberately ABSENT. The adjacency multilist is drawn
    # again here only once its ilink / jlink chains can be transcribed exactly: the links ARE the
    # structure, and a multilist rendered without them shows the edge nodes but not the thing the
    # question is about. An approximation is not shipped in its place.
    ("data_structure", 2025, 42): ("2025_q42_1.svg", ds_2025_q42),
    ("operating_system", 2022, 46): ("2022_q46_1.svg", os_2022_q46),
    ("operating_system", 2025, 46): ("2025_q46_1.svg", os_2025_q46),
}


def main() -> int:
    written = 0
    for (subject, year, _number), entry in FIGURES.items():
        # A question with several sub-figures ((a) / (b)) registers a list; the resolver already
        # accepts more than one file per question, so the registry just has to allow it too.
        parts = entry if isinstance(entry, list) else [entry]
        directory = HERE / subject / "past_papers" / "figures" / str(year)
        directory.mkdir(parents=True, exist_ok=True)
        for filename, builder in parts:
            (directory / filename).write_text(builder(), encoding="utf-8")
            written += 1
    print(f"[figures] wrote {written} clean figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
