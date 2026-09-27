import { describe, expect, it } from 'vitest';
import { questionNeedsFigure } from './question-figure';

describe('questionNeedsFigure', () => {
  // Every one of these is a real CS408 stem (2022–2026, four subjects) whose question cannot be
  // answered without the figure or table it names.
  it.each([
    // 「下图是一个…」 carries no 所示/中 suffix. Matching only the suffixed form is exactly how
    // a needed figure gets hidden — this stem reached the browser once and was drawn without one.
    '7.下图是一个有 10 个活动的AOE网，时间余量最大的活动是（）',
    '26.系统中有8个进程，执行右图的操作，资源S的初始值为5。',
    '在下图所示的 5 阶 B 树 T 中，删除关键字 260 之后……',
    '已知一棵二叉树的树型如下图所示，若其后序遍历序列为 f，d，b，e，c，a',
    '无向图 G=(V, E) 的邻接多重表如下图所示，则 G 中顶点 b 与 d 的度分别是',
    '一棵二叉搜索树如图 7 所示，k1、k2、k3 分别是对应结点中保存的关键字。',
    '若序列的变化情况如下表所示，则下列排序算法中，采用的是：',
    '某网络拓扑如题 47 图所示，R 为路由器，S 为以太网交换机',
    '和 lw 的格式、编码和功能说明如题 43(a) 图所示',
    '某工程包含12个活动，使用题42图所示的AOE网描述',
    '将图中出度大于入度的顶点称为 K 顶点',
    '现 y=16*x-5 的 4 条指令 I1～I4 如表所示，写出①～④处内容。',
  ])('keeps the figure for %s', (stem) => {
    expect(questionNeedsFigure(stem)).toBe(true);
  });

  // Real stems that LOOK like references and are not. A bare 表中/图中 must not fire: these are
  // ordinary prose, and drawing a scan of the question would not answer anything.
  it.each([
    '7. 已知查找表中有 400 个元素，查找每个元素的概率相同，采用分块查找',
    '等字段。在 TLB 表项与主存页表同步时，若主存页表中页号 22 对应的页表项中 P=0',
    '6.对于无向图 G=<V,E>，下列选项中，正确的是（）',
    '3.若采用三元组表存储结构存储稀疏矩阵M，则除三元组表外，下列数据中还需要保存的是',
    '下列关于二叉树及森林的叙述中，正确的是（ ）。',
  ])('hides the redundant scan for %s', (stem) => {
    expect(questionNeedsFigure(stem)).toBe(false);
  });

  it('keeps the figure when there is no stem to judge', () => {
    // A record with no text and a picture: the picture is the only information there is.
    expect(questionNeedsFigure('')).toBe(true);
    expect(questionNeedsFigure('   \n ')).toBe(true);
    expect(questionNeedsFigure(undefined)).toBe(true);
    expect(questionNeedsFigure(null)).toBe(true);
  });
});
