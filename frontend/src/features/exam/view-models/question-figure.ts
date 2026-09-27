/**
 * Whether a question's own figure carries information its text cannot.
 *
 * A past-paper question is stored twice: as structured text (stem + options) and as the scan it
 * was read from. When the text is the whole question, the scan is a second copy of what is
 * already on screen and is not drawn. When the question is ABOUT a figure — a B-tree, an AOE
 * network, a network topology, a scheduling table — the scan IS the information, and dropping
 * it would leave the question unanswerable.
 *
 * What decides it is the paper's own prose. A 408 question that depends on a figure says so:
 * 「在下图所示的 5 阶 B 树 T 中」, 「如题 47 图所示」, 「如下表所示」. A question that does not
 * say so is answerable from its text — that is the whole convention of the paper.
 *
 * This is NOT a guess about what an image contains: nothing here inspects pixels, runs OCR, or
 * invents a figure. It reads the question's own reference and trusts it.
 *
 * Validation: across the 235 real CS408 questions (20 papers, 4 subjects) 39 carry such a
 * reference and 196 do not. The two near-misses a looser pattern would have caught —
 * 「查找表中」 and 「主存页表中」 — are ordinary prose, so a bare 「表中」 is deliberately NOT a
 * trigger; only a demonstrative one (下表 / 如上表 / 表 2 所示) is.
 */
const FIGURE_REFERENCE = new RegExp(
  [
    // 下图 / 上图 / 如图 / 见图 / 该图 — bare, with no requirement on what follows. 「下图是一个
    // 有 10 个活动的 AOE 网」 is as much a reference as 「如下图所示」, and matching only the
    // suffixed form is how a needed figure gets hidden. 图中 is the same reference without a
    // prefix. Missing one hides a figure the question cannot do without; drawing a spare scan
    // costs a line of vertical space. The asymmetry is deliberate.
    '(?:下|上|如|见|该|右|左)图',
    '图中',
    '图\\s*\\d+',
    // 题 43 图 / 题 43(a) 图 / 如题 47 图所示
    '题\\s*\\d+\\s*[（(]?\\s*[a-z]?\\s*[)）]?\\s*图',
    // 下表 / 上表 / 如表 / 见表 / 该表 / 表 2 所示 / 表中所示
    '(?:下|上|如|见|该)表',
    '表\\s*\\d*\\s*所示',
    '表中所示',
  ].join('|'),
);

export function questionNeedsFigure(stem: string | null | undefined): boolean {
  const text = (stem ?? '').trim();
  // An empty stem cannot be judged. The figure is then the only information there is, so it stays.
  if (!text) return true;
  return FIGURE_REFERENCE.test(text);
}
