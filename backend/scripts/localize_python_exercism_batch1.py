"""Idempotently localize the first ten enabled Python Exercism exercises."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from database import SessionLocal
from models import ProgrammingExercise

CN = {
 "ledger": ("账本格式化", "重构账本输出代码，按货币和地区格式化交易记录。", "完善 `create_entry` 与 `format_entries`，将交易日期、描述和金额按美元/欧元及美式/荷兰式地区规则格式化。保持测试规定的列宽、排序与负数表示。"),
 "markdown": ("Markdown 解析", "重构 Markdown 到 HTML 的解析函数。", "完善 `parse(markdown)`：把测试覆盖的标题、段落和列表 Markdown 语法转换为对应 HTML，同时保持代码清晰可维护。"),
 "bob": ("Bob 的回答", "根据一句话的语气返回 Bob 的固定答复。", "实现 `response(hey_bob)`：问句返回 `Sure.`；全大写喊话返回 `Whoa, chill out!`；喊话问句返回 `Calm down, I know what I'm doing!`；空白输入返回 `Fine. Be that way!`；其余返回 `Whatever.`。"),
 "hello-world": ("你好，世界", "返回固定问候语。", "实现 `hello()`，返回固定字符串 `Hello, World!`。"),
 "reverse-string": ("反转字符串", "返回输入文本的字符逆序。", "实现 `reverse(text)`，返回 `text` 按字符倒序后的新字符串。"),
 "acronym": ("首字母缩略词", "将短语转换为大写缩写。", "实现 `abbreviate(words)`：连字符与空白分词，忽略其余标点，返回每个词首字母组成的大写缩写。"),
 "anagram": ("字谜词筛选", "从候选词中找出与目标词同字母异序的词。", "实现 `find_anagrams(word, candidates)`：不区分大小写比较字母组成，排除目标词自身，并按原大小写与候选顺序返回匹配项。"),
 "armstrong-numbers": ("阿姆斯特朗数", "判断数字是否等于各位数字幂和。", "实现 `is_armstrong_number(number)`：若每位数字的位数次幂之和等于原数则返回 True，否则返回 False。"),
 "binary-search": ("二分查找", "在升序列表中定位目标值。", "实现 `find(search_list, value)`：仅对升序列表使用二分查找，找到时返回索引，未找到时按测试接口抛出规定异常。"),
 "black-jack": ("二十一点规则", "实现二十一点的牌值、比较和决策规则。", "完成 `value_of_card`、`higher_card`、`value_of_ace`、`is_blackjack`、`can_split_pairs`、`can_double_down` 等函数；牌面 `A`、`J`、`Q`、`K` 保持原协议。"),
}
def main():
 db=SessionLocal()
 try:
  rows=db.query(ProgrammingExercise).filter(ProgrammingExercise.language=='Python', ProgrammingExercise.source_repo!='first_party_original', ProgrammingExercise.is_active.is_(True)).order_by(ProgrammingExercise.id).limit(10).all()
  assert len(rows)==10
  for row in rows:
   title, summary, statement=CN[row.slug.replace('python-','')]
   row.title_en=row.title_en or row.title; row.statement_en=row.statement_en or row.description
   row.title_zh=title; row.summary_zh=summary; row.statement_zh=statement
   row.input_format_zh='通过测试调用对应函数；参数、类型与返回值以函数签名和测试接口为准。'
   row.output_format_zh='返回测试接口要求的结果；不使用标准输入输出。'
   row.constraints_zh='输入范围、边界条件和异常行为以随题测试接口为准。'
  db.commit(); print('localized',len(rows),'Python Exercism exercises')
 finally: db.close()
if __name__=='__main__': main()
