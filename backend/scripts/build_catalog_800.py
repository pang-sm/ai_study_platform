"""Resumable first-party catalog builder; begins with verified C arithmetic cases."""
from __future__ import annotations
import argparse,json,subprocess,sys,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; STATE=ROOT/'backend/data/programming_catalog/build_state.json'; LIVE=ROOT/'verification-results/catalog-build-live-progress.json'
def save(state):
 STATE.parent.mkdir(parents=True,exist_ok=True);STATE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8');LIVE.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf8')
def c_candidate(i):
 ops=[('加法校验','a+b','+'),('差值计算','a-b','-'),('乘积计算','a*b','*'),('较大值选择','a>b?a:b','>'),('较小值选择','a<b?a:b','<')];title,expr,op=ops[i]
 ref=f'#include <stdio.h>\nint main(){{long long a,b;if(scanf("%lld%lld",&a,&b)==2)printf("%lld\\n",{expr});}}\n'
 cases=[('1 2\n',str(eval('1'+op+'2') if op in '+-*' else (2 if op=='>' else 1))+'\n'),('5 3\n',str(eval('5'+op+'3') if op in '+-*' else (5 if op=='>' else 3))+'\n'),('-2 4\n',str(eval('-2'+op+'4') if op in '+-*' else (4 if op=='>' else -2))+'\n')]
 return {'source_key':f'first_party_c_v2:arithmetic-{i}','language':'C','title':title,'reference':ref,'cases':cases}
def verify(x):
 d=ROOT/'backend/data/programming_catalog/c';d.mkdir(parents=True,exist_ok=True);p=d/(x['source_key'].split(':')[-1]+'.c');p.write_text(x['reference'],encoding='utf8');exe=p.with_suffix('.exe');subprocess.run(['gcc',str(p),'-o',str(exe)],check=True)
 for inp,out in x['cases']:
  got=subprocess.run([str(exe)],input=inp,text=True,capture_output=True,check=True).stdout
  if got!=out:raise RuntimeError(x['source_key'])
def main():
 a=argparse.ArgumentParser();a.add_argument('--resume',action='store_true');a.add_argument('--target-per-language',type=int,default=200);args=a.parse_args();state={'current_language':'C','target':args.target_per_language,'generated':0,'validated':0,'written':0,'updated_at':datetime.datetime.now().isoformat(),'complete':False}
 from seed_first_party_catalog import seed
 items=[]
 for i in range(5): x=c_candidate(i);verify(x);items.append(x);state['generated']+=1;state['validated']+=1
 state['written']=seed(items)
 save(state);print(json.dumps(state))
if __name__=='__main__':main()
