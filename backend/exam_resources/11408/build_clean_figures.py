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



def chain(width, hops, caption="", height=190):
    """A left-to-right chain: host — router(s) — host, each hop labelled with its bandwidth.

    ``hops`` is the list of edge labels; there are len(hops)+1 boxes, the ends being hosts and
    the middle being routers — which is what every link-bandwidth question in this paper shows.
    """
    body = []
    count = len(hops) + 1
    margin = 90
    step = (width - 2 * margin) / (count - 1)
    y = height / 2 - 26
    xs = [margin + index * step for index in range(count)]
    for index, x in enumerate(xs):
        if index in (0, count - 1):
            body.append(rect(x - 40, y - 22, 80, 48, f"H{index + 1}", size=15))
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
    """H1—R1 10 Mb/s, R1—R2 100 Mb/s, R2—H2 1000 Mb/s."""
    return chain(640, ["10 Mb/s", "100 Mb/s", "1000 Mb/s"], "")


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
    """The DHCP exchange: DISCOVER/OFFER, then REQUEST; server 192.168.5.1, yiaddr .5.9."""
    left, right = 130, 600
    body = [
        text(left, 34, "主机 H", size=15, weight="600"),
        text(right, 34, "DHCP 服务器", size=15, weight="600"),
        text(right, 54, "192.168.5.1", size=12, fill=MUTED),
        f'<line x1="{left}" y1="66" x2="{left}" y2="292" stroke="{LINE}" stroke-width="1.6"/>',
        f'<line x1="{right}" y1="66" x2="{right}" y2="292" stroke="{LINE}" stroke-width="1.6"/>',
        text(left - 52, 300, "时间", size=12, fill=MUTED, anchor="start"),
        arrow(left + 6, 120, right - 6, 120, "DHCPDISCOVER"),
        arrow(right - 6, 186, left + 6, 186, "DHCPOFFER"),
        text(right, 210, "yiaddr: 192.168.5.9", size=12, fill=MUTED),
        arrow(left + 6, 262, right - 6, 262, "DHCPREQUEST"),
    ]
    return svg(720, 330, "".join(body), "")


def cn_2025_q38():
    """甲 → 乙 with the acknowledged segment: ack_seq 3001, rcvwnd 4000 B."""
    left, right = 150, 590
    body = [
        text(left, 46, "主机甲", size=15, weight="600"),
        text(right, 46, "主机乙", size=15, weight="600"),
        f'<line x1="{left}" y1="62" x2="{left}" y2="270" stroke="{LINE}" stroke-width="1.6"/>',
        f'<line x1="{right}" y1="62" x2="{right}" y2="270" stroke="{LINE}" stroke-width="1.6"/>',
        arrow(left + 6, 110, right - 6, 110, "t0 起：2 个 1000 B 数据段（seq 1 / seq 1001）"),
        arrow(right - 6, 180, left + 6, 180, "t1：确认段 ack_seq = 3001，rcvwnd = 4000 B"),
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

def co_2026_q43():
    """The three instruction formats C defines — R / I / M — with their field widths."""
    rows = [
        ("R 型", ["0000", "rt", "rs / num", "op1"], "4 位", "4 位", "4 位", "4 位"),
        ("I 型", ["op2", "rt", "imm8"], "4 位", "4 位", "8 位", None),
        ("M 型", ["op3", "offset"], "4 位", "12 位", None, None),
    ]
    body = [text(30, 34, "指令格式（16 位定长指令字）", size=15, anchor="start", weight="600")]
    y = 56
    for name, fields, *widths in rows:
        body.append(text(30, y + 30, name, size=14, anchor="start", weight="600"))
        x = 110
        for index, field in enumerate(fields):
            width = 90 if widths[index] and widths[index] == "8 位" else (90 if widths[index] == "12 位" else 74)
            body.append(rect(x, y, width, 42, "", rx=4))
            body.append(text(x + width / 2, y + 26, field, size=13, weight="600"))
            if widths[index]:
                body.append(text(x + width / 2, y + 58, widths[index], size=12, fill=MUTED))
            x += width
        y += 84
    return svg(520, 320, "".join(body), "")


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
        link(460, 104, 560, 190, "1 Mb/s", lx=530, ly=132),
        link(460, 316, 560, 218, "100 Mb/s", lx=530, ly=300),
        link(650, 204, 700, 204, "10 Mb/s", ly=194),
    ]
    return svg(820, 380, "".join(body), "瓶颈链路为 1 Mb/s")


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
    ("data_structure", 2024, 7): ("2024_q7_1.svg", ds_2024_q7),
    ("computer_organization", 2022, 43): ("2022_q43_1.svg", co_2022_q43),
    ("computer_network", 2024, 47): ("2024_q47_1.svg", cn_2024_q47),
    ("computer_network", 2026, 37): ("2026_q37_1.svg", cn_2026_q37),
    ("computer_organization", 2026, 43): ("2026_q43_1.svg", co_2026_q43),
    ("operating_system", 2022, 46): ("2022_q46_1.svg", os_2022_q46),
    ("operating_system", 2025, 46): ("2025_q46_1.svg", os_2025_q46),
}


def main() -> int:
    written = 0
    for (subject, year, _number), (filename, builder) in FIGURES.items():
        directory = HERE / subject / "past_papers" / "figures" / str(year)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / filename).write_text(builder(), encoding="utf-8")
        written += 1
    print(f"[figures] wrote {written} clean figures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
