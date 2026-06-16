"""Rebuild data_structure chapter questions with 2-level knowledge points.
Reads the annotated TXT, normalizes KPs to chapter+section level,
and imports into ExamQuestionBank.
"""
import json, os, re, sys
from pathlib import Path
from collections import defaultdict

BASE = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(BASE))
from database import SessionLocal
import models

TXT = BASE / "exam_resources/11408/data_structure/chapter_questions/raw/2027数据结构_原创配套习题_全章总汇_带知识点标注_修正版.txt"
CHKD = BASE / "exam_resources/11408/data_structure/chapter_questions/checked"
RPT = BASE / "exam_resources/11408/data_structure/chapter_questions/import_reports"

SEC_TITLES = {
    "1.1":"数据结构的基本概念","1.2":"算法和算法评价",
    "2.1":"线性表的定义和基本操作","2.2":"线性表的顺序表示","2.3":"线性表的链式表示",
    "3.1":"栈","3.2":"队列","3.3":"栈和队列的应用","3.4":"数组和特殊矩阵",
    "4.1":"串的定义和实现","4.2":"串的模式匹配",
    "5.1":"树的基本概念","5.2":"二叉树的概念","5.3":"二叉树的遍历和线索二叉树","5.4":"树、森林","5.5":"树与二叉树的应用",
    "6.1":"图的基本概念","6.2":"图的遍历","6.3":"图的存储及基本操作","6.4":"图的应用",
    "7.1":"查找的基本概念","7.2":"顺序查找和折半查找","7.3":"树形查找","7.4":"散列表",
    "8.1":"排序的基本概念","8.2":"插入排序","8.3":"交换排序","8.4":"选择排序","8.5":"归并排序和基数排序","8.6":"各种内部排序算法的比较","8.7":"外部排序",
}
CH_TITLES = {1:"绪论",2:"线性表",3:"栈、队列和数组",4:"串",5:"树与二叉树",6:"图",7:"查找",8:"排序"}

def norm(raw):
    m=re.match(r'(\d+)\.(\d+)',raw)
    if not m: return(0,"",raw)
    ch=int(m.group(1)); sec=f"{ch}.{m.group(2)}"
    return(ch,sec,SEC_TITLES.get(sec,raw),CH_TITLES.get(ch,f"第{ch}章"))

def parse(fp):
    qs=[]; rejected=[]
    lines=Path(fp).read_text(encoding="utf-8").split('\n')
    i=0; n=len(lines); kp=""; section="choice"
    while i<n:
        l=lines[i].strip()
        km=re.match(r'【知识点：(.+?)】',l)
        if km: kp=km.group(1).strip(); i+=1; continue
        # Track section header — only lines that START with the section marker
        if re.match(r'^[一二三四五六七八九十]、\s*单项选择题',l): section="choice"; i+=1; continue
        if re.match(r'^[一二三四五六七八九十]、\s*(?:综合应用题|综合应用|大题|简答题|算法题)',l): section="big"; i+=1; continue
        cm=re.match(r'^(\d{2,3})\.\s(.+)',l)
        if cm:
            s=cm.group(2).strip(); opts={}; ans=""; j=i+1
            while j<n and j<i+10:
                nl=lines[j].strip()
                om=re.match(r'^([A-D])[.．、]\s*(.+)',nl)
                if om: opts[om.group(1)]=om.group(2).strip()
                elif nl.startswith("答案："): ans=nl.replace("答案：","").strip(); j+=1; break
                elif re.match(r'^\d{2,3}\.\s',nl) or re.match(r'^【知识点：',nl): break
                j+=1
            ch,sec,sn,cn=norm(kp)
            # Determine type: all A/B/C/D → choice, partial → reject, none → big
            has_all_abcd = all(k in opts for k in ['A','B','C','D'])
            if has_all_abcd:
                qtype = "choice"
            elif len(opts) > 0:
                # Partial options — reject, don't put in ready
                rejected.append({"ch":ch,"kp":sec,"kp_name":sn,"ch_title":cn,"raw_kp":kp,
                    "type":"choice_partial","stem":s,"opts":opts,"ans":ans,
                    "reason":f"partial options: {sorted(opts.keys())}"})
                i=j; continue
            else:
                qtype = "big"
            qs.append({"ch":ch,"kp":sec,"kp_name":sn,"ch_title":cn,"raw_kp":kp,"type":qtype,"stem":s,"opts":opts,"ans":ans}); i=j; continue
        bm=re.match(r'^综合(\d{1,2})[.．]\s*(.+)',l)
        if bm:
            s=bm.group(2).strip(); ans=""; j=i+1
            while j<n and j<i+5:
                nl=lines[j].strip()
                if nl.startswith("答案："): ans=nl.replace("答案：","").strip(); j+=1; break
                if re.match(r'^\d{2,3}\.\s',nl) or re.match(r'^【知识点：',nl): break
                j+=1
            ch,sec,sn,cn=norm(kp)
            qs.append({"ch":ch,"kp":sec,"kp_name":sn,"ch_title":cn,"raw_kp":kp,"type":"big","stem":s,"opts":{},"ans":ans}); i=j; continue
        i+=1
    return qs, rejected

def main():
    dry_run = "--dry-run" in sys.argv
    qs, rejected = parse(TXT)
    t=len(qs); c=sum(1 for q in qs if q["type"]=="choice"); b=t-c; r=len(rejected)
    print(f"Parsed: {t} (choice={c}, big={b}, rejected={r})")
    # Validation
    choice_no_opts = [q for q in qs if q["type"]=="choice" and len(q.get("opts",{}))==0]
    choice_missing = [q for q in qs if q["type"]=="choice" and not all(k in q.get("opts",{}) for k in ['A','B','C','D'])]
    no_kp = [q for q in qs if not q.get("kp")]
    if choice_no_opts: print(f"WARNING: {len(choice_no_opts)} choice with empty opts!")
    if choice_missing: print(f"WARNING: {len(choice_missing)} choice missing A/B/C/D!")
    if no_kp: print(f"WARNING: {len(no_kp)} no knowledge point!")
    chc=defaultdict(int); sec=defaultdict(int)
    for q in qs: chc[q["ch"]]+=1; sec[q["kp"]]+=1
    for ch in sorted(chc): print(f"  Ch{ch}: {chc[ch]}")
    for k in sorted(sec): print(f"  {k}: {sec[k]}")
    CHKD.mkdir(parents=True,exist_ok=True); RPT.mkdir(parents=True,exist_ok=True)
    json.dump(qs,(CHKD/"parsed_ready.json").open("w",encoding="utf-8"),ensure_ascii=False,indent=2)
    json.dump(rejected,(CHKD/"parsed_rejected.json").open("w",encoding="utf-8"),ensure_ascii=False,indent=2)
    rp={"total":t,"choice":c,"big":b,"rejected":r,"choice_no_opts":len(choice_no_opts),"choice_missing_abcd":len(choice_missing),"no_kp":len(no_kp),"per_chapter":{str(k):v for k,v in sorted(chc.items())},"per_section":{k:v for k,v in sorted(sec.items())}}
    json.dump(rp,(RPT/"data_structure_annotated_build_report.json").open("w",encoding="utf-8"),ensure_ascii=False,indent=2)
    (RPT/"data_structure_annotated_build_report.md").write_text(f"# build report\n- total: {t} (choice={c}, big={b}, rejected={r})\n- choice_no_opts: {len(choice_no_opts)}\n- choice_missing_abcd: {len(choice_missing)}\n- no_kp: {len(no_kp)}\n"+"\n".join(f"- Ch{ch}: {chc[ch]}" for ch in sorted(chc)),encoding="utf-8")
    print("Reports saved")
    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return
    # Import
    db=SessionLocal()
    db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.subject_key=="data_structure",models.ExamQuestionBank.source_type=="chapter").update({"is_active":False})
    db.commit()
    ins=0
    for q in qs:
        it=models.ExamQuestionBank(subject_key="data_structure",subject_name="数据结构",source_type="chapter",visibility="public",
            knowledge_point_id=q["kp"],knowledge_point_name=q["kp_name"],knowledge_point_path=f"{q['ch_title']} / {q['kp_name']}",
            question_type="choice" if q["type"]=="choice" else "big",stem=q["stem"],options_json=json.dumps(q.get("opts",{}),ensure_ascii=False),
            standard_answer=q.get("ans",""),analysis="",difficulty="基础",source_ref=f"annotated:{q['raw_kp']}",is_active=True)
        db.add(it); ins+=1
    db.commit()
    act=db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.subject_key=="data_structure",models.ExamQuestionBank.source_type=="chapter",models.ExamQuestionBank.is_active==True).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active")

if __name__=="__main__": main()
