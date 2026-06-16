"""Rebuild computer_organization chapter questions.
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

TXT = BASE / "exam_resources/11408/computer_organization/chapter_questions/raw/2027计算机组成原理_原创配套习题_全章总汇_带知识点标注.txt"
CHKD = BASE / "exam_resources/11408/computer_organization/chapter_questions/checked"
RPT = BASE / "exam_resources/11408/computer_organization/chapter_questions/import_reports"

SEC_TITLES = {
    "1.1":"计算机发展历程","1.2":"计算机系统层次结构","1.3":"计算机的性能指标",
    "2.1":"数制与编码","2.2":"运算方法和运算电路","2.3":"浮点数的表示与运算",
    "3.1":"存储器概述","3.2":"主存储器","3.3":"主存储器与CPU的连接","3.4":"外部存储器","3.5":"高速缓冲存储器","3.6":"虚拟存储器",
    "4.1":"指令系统","4.2":"寻址方式","4.3":"汇编程序的基本概念和表示","4.4":"CISC和RISC的基本概念",
    "5.1":"CPU的功能和基本结构","5.2":"指令执行过程","5.3":"数据通路的功能和基本结构","5.4":"控制器的功能和工作原理","5.5":"异常和中断机制","5.6":"指令流水线","5.7":"多处理器的基本概念",
    "6.1":"总线概述","6.2":"总线事务和定时",
    "7.1":"I/O系统基本概念","7.2":"I/O接口","7.3":"I/O方式",
}
CH_TITLES = {
    1:"计算机系统概述",2:"数据的表示和运算",3:"存储系统",4:"指令系统",
    5:"中央处理器",6:"总线",7:"输入/输出系统",
}
SUBJECT_KEY = "computer_organization"
SUBJECT_NAME = "计算机组成原理"

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
        # Track section header
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
            has_all_abcd = all(k in opts for k in ['A','B','C','D'])
            if has_all_abcd:
                qtype = "choice"
            elif len(opts) > 0:
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
    json.dump(rp,(RPT/"computer_organization_chapter_questions_report.json").open("w",encoding="utf-8"),ensure_ascii=False,indent=2)
    (RPT/"computer_organization_chapter_questions_report.md").write_text(f"# build report\n- total: {t} (choice={c}, big={b}, rejected={r})\n- choice_no_opts: {len(choice_no_opts)}\n- choice_missing_abcd: {len(choice_missing)}\n- no_kp: {len(no_kp)}\n"+"\n".join(f"- Ch{ch}: {chc[ch]}" for ch in sorted(chc)),encoding="utf-8")
    print("Reports saved")
    if dry_run:
        print("DRY-RUN: skipping DB import.")
        return
    # Import
    db=SessionLocal()
    db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.subject_key==SUBJECT_KEY,models.ExamQuestionBank.source_type=="chapter").update({"is_active":False})
    db.commit()
    ins=0
    for q in qs:
        it=models.ExamQuestionBank(subject_key=SUBJECT_KEY,subject_name=SUBJECT_NAME,source_type="chapter",visibility="public",
            knowledge_point_id=q["kp"],knowledge_point_name=q["kp_name"],knowledge_point_path=f"{q['ch_title']} / {q['kp_name']}",
            question_type="choice" if q["type"]=="choice" else "big",stem=q["stem"],options_json=json.dumps(q.get("opts",{}),ensure_ascii=False),
            standard_answer=q.get("ans",""),analysis="",difficulty="基础",source_ref=f"annotated:{q['raw_kp']}",is_active=True)
        db.add(it); ins+=1
    db.commit()
    act=db.query(models.ExamQuestionBank).filter(models.ExamQuestionBank.subject_key==SUBJECT_KEY,models.ExamQuestionBank.source_type=="chapter",models.ExamQuestionBank.is_active==True).count()
    db.close()
    print(f"DB: {ins} inserted, {act} active")

if __name__=="__main__": main()
