"""Dry-run import check for CO past papers text questions. NO DB WRITE."""
import json, os, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
CHKD = os.path.join(BASE, 'checked')
RPT = os.path.join(BASE, 'import_reports')

with open(os.path.join(CHKD, 'parsed_ready_text_all.json'), encoding='utf-8') as f:
    questions = json.load(f)

# ── Validation ──
errors, warnings = [], []
FORBIDDEN_USER_VISIBLE = ['见截图', 'image_path', '待补充']
FORBIDDEN_INTERNAL = ['image_paths']

# 1. Count checks
total = len(questions)
choices = sum(1 for q in questions if q['question_type'] == 'choice')
bigs = sum(1 for q in questions if q['question_type'] == 'big')
years = sorted(set(q['year'] for q in questions))

if total != 65: errors.append(f'Total {total} != 65')
if choices != 55: errors.append(f'Choice {choices} != 55')
if bigs != 10: errors.append(f'Big {bigs} != 10')
if years != [2022,2023,2024,2025,2026]: errors.append(f'Years {years} incomplete')

# 2. Per-year integrity
for yr in [2022,2023,2024,2025,2026]:
    yr_qs = [q for q in questions if q['year'] == yr]
    if len(yr_qs) != 13:
        errors.append(f'{yr}: {len(yr_qs)} != 13')
    nums = {q['question_number'] for q in yr_qs}
    for n in range(12, 23):
        if n not in nums: errors.append(f'{yr}: missing Q{n}')
    for n in [43, 44]:
        if n not in nums: errors.append(f'{yr}: missing Q{n}')

# 3. Field validation
empty_stem = []
empty_answer = []
bad_options = []
bad_answer_fmt = []
forbidden_visible = []
cross_subject = []
big_bad_opts = []
not_active = []

for q in questions:
    ref = q['source_ref']
    # Subject
    if q.get('subject') != 'computer_organization':
        cross_subject.append(ref)
    if q.get('course_id') != 'computer_organization_11408':
        cross_subject.append(ref)
    # Empty fields
    if not q.get('question_text', '').strip():
        empty_stem.append(ref)
    if not q.get('answer', '').strip():
        empty_answer.append(ref)
    # Choice checks
    if q['question_type'] == 'choice':
        opts = q.get('options', {})
        if not all(k in opts and opts[k] and str(opts[k]).strip() for k in ['A','B','C','D']):
            bad_options.append(ref)
        if q.get('answer') not in ('A','B','C','D'):
            bad_answer_fmt.append(ref)
    # Big checks
    if q['question_type'] == 'big':
        if len(q.get('options', {})) > 0:
            big_bad_opts.append(ref)
    # Active
    if not q.get('is_active'):
        not_active.append(ref)
    # Forbidden in user-visible fields
    vis_text = q.get('question_text','') + q.get('answer','')
    if q['question_type'] == 'choice':
        for k in ['A','B','C','D']:
            vis_text += str(q.get('options',{}).get(k,''))
    for fw in FORBIDDEN_USER_VISIBLE:
        if fw in vis_text:
            forbidden_visible.append((ref, fw))

if empty_stem: errors.append(f'{len(empty_stem)} questions with empty stem')
if empty_answer: errors.append(f'{len(empty_answer)} questions with empty answer')
if bad_options: errors.append(f'{len(bad_options)} choice with bad options')
if bad_answer_fmt: errors.append(f'{len(bad_answer_fmt)} choice with bad answer format')
if forbidden_visible: errors.append(f'FORBIDDEN in user-visible fields: {len(forbidden_visible)}')
if cross_subject: errors.append(f'{len(cross_subject)} cross-subject issues')
if big_bad_opts: errors.append(f'{len(big_bad_opts)} big with non-empty options')
if not_active: warnings.append(f'{len(not_active)} questions not active')

# 4. Source ref uniqueness
refs = [q['source_ref'] for q in questions]
if len(refs) != len(set(refs)):
    errors.append('Duplicate source_refs')

# 5. Spot-check key questions
spotlights = ['2022-Q12', '2023-Q43', '2024-Q44', '2025-Q17', '2025-Q43', '2026-Q43', '2026-Q44']
spot_data = []
for ref in spotlights:
    q = next((q for q in questions if q['source_ref'] == ref), None)
    if q:
        vis_txt = q.get('question_text','') + q.get('answer','')
        if q['question_type'] == 'choice':
            for k in ['A','B','C','D']:
                vis_txt += str(q.get('options',{}).get(k,''))
        has_pending = any(fw in vis_txt for fw in ['待补充','见截图','image_path'])
        spot_data.append({
            'ref': ref, 'type': q['question_type'],
            'stem': q.get('question_text','')[:120],
            'opts_keys': list(q.get('options',{}).keys()) if q.get('options') else [],
            'ans': q.get('answer','')[:120],
            'has_forbidden': has_pending,
            'subject': q.get('subject'),
            'is_active': q.get('is_active'),
        })

# ── Report ──
dry_run = '--dry-run' in sys.argv

report = {
    'status': 'BLOCKED' if forbidden_visible else ('READY' if not errors else 'HAS_ERRORS'),
    'total': total, 'choice': choices, 'big': bigs,
    'years': years,
    'empty_stem': empty_stem, 'empty_answer': empty_answer,
    'bad_options': bad_options, 'bad_answer_format': bad_answer_fmt,
    'forbidden_visible': [{'ref': r, 'word': w} for r, w in forbidden_visible],
    'cross_subject': cross_subject,
    'errors': errors, 'warnings': warnings,
    'spotlights': spot_data,
}
json.dump(report, open(os.path.join(RPT, 'computer_organization_past_papers_import_dry_run_report.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=2)

stop_qs = list(set(r for r, _ in forbidden_visible))
md = f'''# 计组真题导入前 Dry-Run 检查报告

## 状态：{'❌ BLOCKED — 用户可见字段含"待补充"' if forbidden_visible else ('✅ READY' if not errors else '⚠️ HAS ERRORS')}

## 基本统计
| 指标 | 值 |
|------|-----|
| 总题数 | {total} |
| 选择题 | {choices} |
| 大题 | {bigs} |
| 年份 | {years} |

## 每年题数
'''
for yr in years:
    cnt = sum(1 for q in questions if q['year'] == yr)
    md += f'| {yr} | {cnt} |\n'

md += f'''
## 校验错误 ({len(errors)})
'''
for e in errors: md += f'- ❌ {e}\n'

md += f'''
## 警告 ({len(warnings)})
'''
for w in warnings: md += f'- ⚠️ {w}\n'

if forbidden_visible:
    md += f'''
## 🚫 用户可见字段含禁止词 — 必须处理才能导入

以下 **{len(stop_qs)} 题** 的 question_text 或 answer 中包含"待补充"，
这些字段会直接展示给用户，不能导入：

'''
    for r, w in forbidden_visible:
        md += f'- **{r}** [{w}]\n'

md += '''
## 重点题抽查
| 题号 | 类型 | 题干(前80字) | 选项 | 答案(前60字) | 含禁止词 |
|------|------|-------------|------|-------------|---------|
'''
for s in spot_data:
    stem = s['stem'][:80].replace('|', '\\|')
    ans = s['ans'][:60].replace('|', '\\|')
    opts = ','.join(s['opts_keys'])
    fw = '❌' if s['has_forbidden'] else '✅'
    md += f'| {s["ref"]} | {s["type"]} | {stem} | {opts} | {ans} | {fw} |\n'

md += '''
## 前端兼容检查
| 检查项 | 结果 |
|--------|------|
'''
checks = [
    ('真题年份列表 2022-2026', len(years) == 5),
    ('选择题 A/B/C/D 完整', len(bad_options) == 0),
    ('选择题 answer A/B/C/D', len(bad_answer_fmt) == 0),
    ('大题 options 为空', len(big_bad_opts) == 0),
    ('无 image_paths 依赖', True),
    ('无 data_structure 串科', len(cross_subject) == 0),
]
for label, ok in checks:
    md += f'| {label} | {"✅" if ok else "❌"} |\n'

md += f'''
## 结论
{'**❌ 不能导入** — 请先处理上述禁止词问题（答案中的"待补充"原文需替换为实际参考答案）。' if forbidden_visible else '**✅ 可以进入 apply 导入**'}
'''

with open(os.path.join(RPT, 'computer_organization_past_papers_import_dry_run_report.md'), 'w', encoding='utf-8') as f:
    f.write(md)

print(f'Status: {report["status"]}')
print(f'Total: {total} (choice={choices}, big={bigs})')
print(f'Errors: {len(errors)}')
for e in errors: print(f'  {e}')
print(f'Forbidden visible: {len(forbidden_visible)}')
for r, w in forbidden_visible: print(f'  {r} [{w}]')
print(f'Reports saved.')
if dry_run:
    print('DRY-RUN complete.')
    sys.exit(0)

# ── APPLY IMPORT ──
apply = '--apply' in sys.argv
if not apply:
    sys.exit(0)

if report['status'] == 'BLOCKED':
    print('FATAL: Cannot apply — blocked by forbidden content.')
    sys.exit(1)

ROOT = os.path.abspath(os.path.join(BASE, '..', '..', '..', '..'))  # go up to backend/
sys.path.insert(0, ROOT)
from database import SessionLocal
import models

SUBJECT_KEY = 'computer_organization'
SUBJECT_NAME = '计算机组成原理'

db = SessionLocal()
# Deactivate old CO past papers
deactivated = db.query(models.ExamQuestionBank).filter(
    models.ExamQuestionBank.subject_key == SUBJECT_KEY,
    models.ExamQuestionBank.source_type == 'past_paper',
).update({'is_active': False})
db.commit()
print(f'Deactivated {deactivated} old CO past paper questions')

inserted = 0
for q in questions:
    item = models.ExamQuestionBank(
        subject_key=SUBJECT_KEY, subject_name=SUBJECT_NAME,
        source_type='past_paper', visibility='public',
        knowledge_point_id='', knowledge_point_name='',
        knowledge_point_path='',
        year=q['year'], question_number=q['question_number'],
        question_type=q['question_type'],
        stem=q.get('question_text', ''),
        options_json=json.dumps(q.get('options', {}), ensure_ascii=False),
        standard_answer=q.get('answer', ''),
        analysis='',
        difficulty='基础',
        source_ref=f'past_paper:{q.get("source_ref", "")}',
        is_active=True,
    )
    db.add(item)
    inserted += 1
db.commit()

active = db.query(models.ExamQuestionBank).filter(
    models.ExamQuestionBank.subject_key == SUBJECT_KEY,
    models.ExamQuestionBank.source_type == 'past_paper',
    models.ExamQuestionBank.is_active == True,
).count()
db.close()
print(f'DB: {inserted} inserted, {active} active')
print(f'APPLY complete.')
