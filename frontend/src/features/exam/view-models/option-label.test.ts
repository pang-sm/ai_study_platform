import { describe, expect, it } from 'vitest';
import { optionLabel } from './option-label';

describe('optionLabel', () => {
  it.each([
    ['A', 'A. O(log n)', 'O(log n)'],
    ['A', 'A. T1 与 T2 的结点数相同', 'T1 与 T2 的结点数相同'],
    ['A', 'A．|V|>E时，G一定是连通的', '|V|>E时，G一定是连通的'],
    ['B', 'B、T1 的高度大于 T2 的高度', 'T1 的高度大于 T2 的高度'],
    ['C', 'C)出现频次不同的字符', '出现频次不同的字符'],
    ['A', 'A.e', 'e'],
    ['a', 'A. O(log n)', 'O(log n)'],
  ])('drops the key %s repeats in %s', (key, label, expected) => {
    expect(optionLabel(key, label)).toBe(expected);
  });

  it.each([
    // The letter is not this option's key — it is the text.
    ['B', 'A. O(log n)'],
    ['A', 'B. O(n)'],
    // Ordinary prose that merely starts with a capital Latin letter.
    ['A', 'AOE 网的时间余量'],
    ['B', 'B 树是一种平衡的多路查找树'],
    ['C', 'CPU 的执行时间'],
    ['D', 'DMA 控制器控制的数据传输通路位于'],
    // No separator after the letter, so it is not a key prefix at all.
    ['A', 'A组和 B 组的比较'],
    // A label that is nothing but its own letter must not become an empty row.
    ['A', 'A.'],
  ])('leaves %s untouched', (key, label) => {
    expect(optionLabel(key, label)).toBe(label);
  });
});
