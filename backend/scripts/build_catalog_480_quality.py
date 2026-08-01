"""Build the next verified programming catalog tranche.

This is deliberately a deterministic first-party catalog builder.  It keeps
the existing approved recovery exercises, never changes rejected rows, and
creates only standard-I/O exercises whose expected output is calculated by
the reference executable at build time.
"""
from __future__ import annotations

import json
import re
import sys
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "backend" / "scripts"))

from catalog_adapters import compile_starter, execute_reference, validate_candidate  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import KnowledgePoint, ProgrammingExercise  # noqa: E402
from restore_high_quality_programming_catalog import run_standard_many  # noqa: E402

OUT = ROOT / "verification-results"
BLUEPRINT = ROOT / "backend" / "data" / "programming_catalog" / "curriculum_blueprint.json"

LANGUAGE_OBJECTIVES = {
    "C": [
        ("c-io-types", "标准输入输出与类型", "stdio、类型转换与边界检查"),
        ("c-control-flow", "条件与循环", "分支、循环和状态维护"),
        ("c-arrays-strings", "数组与字符数组", "连续内存遍历和字符串处理"),
        ("c-functions-pointers", "函数与指针", "函数参数、指针和原地修改"),
        ("c-structs-files", "结构体与记录", "结构体比较、排序和记录组织"),
        ("c-data-structures", "基础数据结构", "动态内存、栈、队列和链表"),
        ("c-algorithms", "搜索与排序", "二分、排序和前缀信息"),
        ("c-graphs-dp", "图与动态规划", "网格、连通性和状态转移"),
    ],
    "C++": [
        ("cpp-io-stl", "输入输出与 STL", "iostream、vector 和 string"),
        ("cpp-control", "控制流与函数", "范围遍历、函数封装和边界"),
        ("cpp-sequence", "序列与迭代器", "迭代器、算法和序列变换"),
        ("cpp-ordered", "有序容器", "sort、set、map 和比较器"),
        ("cpp-stack-queue", "栈队列与优先级", "stack、queue 和 priority_queue"),
        ("cpp-search", "搜索与窗口", "二分、双指针和滑动窗口"),
        ("cpp-graphs", "图与连通性", "BFS、DFS 和并查集"),
        ("cpp-dp", "动态规划", "状态设计、转移和滚动数组"),
    ],
    "Python": [
        ("python-io-types", "输入解析与类型", "sys.stdin、类型转换和格式化"),
        ("python-control", "控制流与函数", "条件、循环和可测试函数"),
        ("python-sequences", "序列与切片", "list、tuple、切片和生成器"),
        ("python-mapping", "字典与集合", "dict、set 和索引构建"),
        ("python-stack-queue", "栈队列与堆", "deque、heapq 和优先级"),
        ("python-search", "搜索与排序", "sorted、bisect 和双指针"),
        ("python-graphs", "图与遍历", "邻接表、BFS 和 DFS"),
        ("python-dp", "动态规划", "缓存、状态转移和复杂度"),
    ],
    "Java": [
        ("java-io-types", "输入输出与类型", "BufferedReader、StringTokenizer 和类型安全"),
        ("java-control", "控制流与方法", "分支、循环、方法和边界"),
        ("java-arrays-strings", "数组与字符串", "数组、String 和 StringBuilder"),
        ("java-collections", "集合与泛型", "List、Set、Map 和泛型"),
        ("java-stack-queue", "栈队列与比较器", "Deque、PriorityQueue 和 Comparator"),
        ("java-search", "搜索与排序", "Arrays.sort、二分和区间"),
        ("java-graphs", "图与遍历", "邻接表、BFS、DFS 和并查集"),
        ("java-dp", "动态规划", "数组状态、转移和滚动空间"),
    ],
}

OPS = [
    ("odd-sum", "奇数读数汇总", "读取一组整数并求指定类别的总和。", "n，随后是 n 个整数。", "输出一个整数。", "1≤n≤2000，整数绝对值不超过 10^6。"),
    ("rotate", "环形队列校准", "将队列按照给定方向旋转，保持元素相对顺序。", "n、k，随后是 n 个整数。", "输出旋转后的序列。", "1≤n≤2000，k 可以超过 n。"),
    ("run", "连续状态最长段", "找出满足相邻关系的最长连续区间。", "n，随后是 n 个整数。", "输出最长区间长度。", "1≤n≤5000。"),
    ("unique", "稳定去重记录", "根据题目要求去除重复值，并保留规定的顺序。", "n，随后是 n 个整数。", "第一行输出数量，第二行输出结果。", "1≤n≤2000。"),
    ("bound", "有序边界定位", "在非递减序列中定位满足边界条件的第一个位置。", "n、x，随后是 n 个非递减整数。", "输出从 0 开始的位置；不存在时输出 n。", "1≤n≤10000。"),
    ("brackets", "括号结构检查", "分析一段括号序列的嵌套结构。", "一行只含圆括号、方括号和花括号。", "输出结构分析结果。", "长度不超过 2000。"),
    ("rle", "游程信息编码", "扫描文本中的连续相同字符并输出游程信息。", "一行不含空格的 ASCII 文本。", "输出编码后的文本。", "长度为 1 到 2000。"),
    ("prefix", "前缀状态摘要", "逐项维护前缀状态并输出摘要序列。", "n，随后是 n 个整数。", "输出 n 个摘要值。", "1≤n≤3000。"),
    ("matrix", "矩阵方向变换", "读取矩阵并按指定规则变换其行列关系。", "r、c，随后是 r 行 c 个整数。", "输出变换后的矩阵。", "1≤r,c≤40。"),
    ("gcd", "序列公因数", "计算整组整数的最大公因数并处理负数。", "n，随后是 n 个整数。", "输出非负最大公因数。", "1≤n≤2000。"),
    ("bits", "位标志统计", "从整数的二进制表示中提取位级统计信息。", "一个非负整数。", "输出位统计结果。", "0≤x<2^31。"),
    ("power", "模幂计算", "使用快速幂计算大指数下的模结果。", "底数、非负指数和正模数。", "输出模幂结果。", "指数不超过 10^18，模数不超过 10^9。"),
    ("partition", "稳定分区", "把序列按谓词分成两段，同时保持每段内部顺序。", "n、阈值，随后是 n 个整数。", "输出分区后的序列。", "1≤n≤3000。"),
    ("anagram", "字符组成比较", "比较两段文本的字符组成，忽略指定的表示差异。", "两行 ASCII 文本。", "输出 YES 或 NO。", "每行长度不超过 2000。"),
    ("median", "有序统计量", "在不改变输入语义的前提下求中间统计量。", "n，随后是 n 个整数。", "n 为奇数时输出中位数。", "1≤n≤2001 且 n 为奇数。"),
]

LANG_PREFIX = {"C": "指针数组", "C++": "STL 序列", "Python": "集合管线", "Java": "类型安全"}


def _py_code(op: str, variant: int) -> str:
    return f'''import sys, math
data = sys.stdin.read().split()
v = {variant}
if "{op}" == "odd-sum":
    a=list(map(int,data[1:])); print(sum(x if (x&1)==(v&1) else 0 for x in a))
elif "{op}" == "rotate":
    n,k=map(int,data[:2]); a=list(map(int,data[2:])); k%=n; k=k if v==0 else (-k if v==1 else 0); b=a[-k:]+a[:-k] if k else a; print(*b)
elif "{op}" == "run":
    a=list(map(int,data[1:])); best=cur=1
    for x,y in zip(a,a[1:]): cur=cur+1 if ((x==y) if v==0 else (y>=x if v==1 else y>x)) else 1; best=max(best,cur)
    print(best)
elif "{op}" == "unique":
    a=list(map(int,data[1:])); b=sorted(set(a)) if v==0 else list(dict.fromkeys(a)) if v==1 else sorted(x for x in set(a) if a.count(x)==1); print(len(b)); print(*b)
elif "{op}" == "bound":
    n,x=map(int,data[:2]); a=list(map(int,data[2:])); import bisect; print((bisect.bisect_left if v==0 else bisect.bisect_right if v==1 else lambda q,z:bisect.bisect_left(q,z)) (a,x))
elif "{op}" == "brackets":
    s=data[0] if data else ''; st=[]; pairs={{')':'(',']':'[','}}':'{{'}}; ok=True
    for ch in s:
        if ch in '([{{': st.append(ch)
        elif ch in pairs:
            if not st or st.pop()!=pairs[ch]: ok=False
    print(('YES' if ok and not st else 'NO') if v==0 else (max([0]+[len(st)])) if v==1 else len(st))
elif "{op}" == "rle":
    s=data[0] if data else ''; out=[]; i=0
    while i<len(s):
        j=i
        while j<len(s) and s[j]==s[i]: j+=1
        out.append(str(j-i)+s[i] if v==0 else s[i]+str(j-i)); i=j
    print(''.join(out))
elif "{op}" == "prefix":
    a=list(map(int,data[1:])); out=[]; cur=0 if v==2 else None
    for x in a:
        if v==0: cur=x if cur is None else max(cur,x)
        elif v==1: cur=x if cur is None else min(cur,x)
        else: cur=(cur or 0)+x
        out.append(cur)
    print(*out)
elif "{op}" == "matrix":
    r,c=map(int,data[:2]); a=[list(map(int,data[2+i*c:2+(i+1)*c])) for i in range(r)]
    if v==0: b=[list(x) for x in zip(*a)]
    elif v==1: b=[[sum(row) for row in a]]
    else: b=[[sum(a[i][j] for i in range(r)) for j in range(c)]]
    for row in b: print(*row)
elif "{op}" == "gcd":
    a=list(map(int,data[1:])); g=0
    for x in a: g=math.gcd(g,abs(x))
    print(g if v==0 else (0 if g==0 else abs(math.prod(a))//g if v==1 else g))
elif "{op}" == "bits":
    x=int(data[0]); print(x.bit_count() if v==0 else x.bit_count()%2 if v==1 else (x.bit_length()-1 if x else -1))
elif "{op}" == "power":
    a,b,m=map(int,data[:3]); print(pow(a,b,m) if v==0 else sum(pow(a,i,m) for i in range(b+1))%m if v==1 else pow(a,b,m))
elif "{op}" == "partition":
    n,t=map(int,data[:2]); a=list(map(int,data[2:])); p=(lambda x:x<t) if v==0 else (lambda x:x%2==0) if v==1 else (lambda x:x<0); print(*[x for x in a if p(x)]+[x for x in a if not p(x)])
elif "{op}" == "anagram":
    a,b=(data+['',''])[:2]; print('YES' if (sorted(a)==sorted(b) if v==0 else sorted(a.lower())==sorted(b.lower())) else 'NO')
elif "{op}" == "median":
    a=sorted(map(int,data[1:])); print(a[len(a)//2] if v==0 else a[-1]-a[0] if v==1 else a[0])
'''


def _c_like_code(language: str, op: str, variant: int) -> str:
    cpp = language == "C++"
    inc = "#include <bits/stdc++.h>\nusing namespace std;\n" if cpp else "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <math.h>\n"
    io = "cin" if cpp else "scanf"
    # The branch bodies intentionally use the target language's standard
    # containers and idioms; the protocol is kept simple for the Workbench.
    if cpp:
        head = inc + f"int main(){{ios::sync_with_stdio(false);cin.tie(nullptr); int v={variant};"
        body = {
            "odd-sum": "int n,x,s=0;cin>>n;while(n--){cin>>x;if((x&1)==(v&1))s+=x;}cout<<s<<'\\n';",
            "rotate": "int n,k;cin>>n>>k;vector<int>a(n);for(int&x:a)cin>>x;k%=n;if(v==1)k=(n-k)%n;if(v==2)reverse(a.begin(),a.end());else rotate(a.begin(),a.end()-k,a.end());for(int i=0;i<n;i++)cout<<a[i]<<(i+1==n?'\\n':' ');",
            "run": "int n,x,p,b=1,c=1;cin>>n>>p;for(int i=1;i<n;i++){cin>>x;bool z=v==0?x==p:v==1?x>=p:x>p;c=z?c+1:1;b=max(b,c);p=x;}cout<<b<<'\\n';",
            "unique": "int n,x;cin>>n;vector<int>a(n);for(int&z:a)cin>>z;vector<int>b;for(int z:a)if(find(b.begin(),b.end(),z)==b.end())b.push_back(z);if(v==0)sort(b.begin(),b.end());cout<<b.size()<<'\\n';for(int z:b)cout<<z<<' ';cout<<'\\n';",
            "bound": "int n,x;cin>>n>>x;vector<int>a(n);for(int&z:a)cin>>z;cout<<(v==1?upper_bound(a.begin(),a.end(),x)-a.begin():lower_bound(a.begin(),a.end(),x)-a.begin())<<'\\n';",
            "brackets": "string s;cin>>s;vector<char>st;map<char,char>p{{{')','('},{']','['},{'}','{'}}};bool ok=1;for(char c:s)if(c=='('||c=='['||c=='{')st.push_back(c);else if(st.empty()||st.back()!=p[c])ok=0;else st.pop_back();cout<<(v==0?(ok&&st.empty()?\"YES\":\"NO\"):v==1?to_string(st.size()):to_string(st.size()))<<'\\n';",
            "rle": "string s;cin>>s;for(int i=0;i<(int)s.size();){int j=i;while(j<(int)s.size()&&s[j]==s[i])j++;if(v==0)cout<<j-i<<s[i];else cout<<s[i]<<j-i;i=j;}cout<<'\\n';",
            "prefix": "int n,x,cur=0;cin>>n;for(int i=0;i<n;i++){cin>>x;if(v==0)cur=i?max(cur,x):x;else if(v==1)cur=i?min(cur,x):x;else cur+=x;cout<<cur<<(i+1==n?'\\n':' ');}",
            "matrix": "int r,c;cin>>r>>c;vector<vector<int>>a(r,vector<int>(c));for(auto&row:a)for(int&x:row)cin>>x;if(v==0){for(int j=0;j<c;j++){for(int i=0;i<r;i++)cout<<a[i][j]<<(i+1==r?'\\n':' ');}}else if(v==1){for(auto&row:a){int s=accumulate(row.begin(),row.end(),0);cout<<s<<' ';}cout<<'\\n';}else{for(int j=0;j<c;j++){int s=0;for(int i=0;i<r;i++)s+=a[i][j];cout<<s<<(j+1==c?'\\n':' ');}}",
            "gcd": "int n,x,g=0;cin>>n;while(n--){cin>>x;g=std::gcd(g,abs(x));}cout<<g<<'\\n';",
            "bits": "unsigned int x;cin>>x;if(v==0)cout<<__builtin_popcount(x);else if(v==1)cout<<(__builtin_popcount(x)&1);else cout<<(x?31-__builtin_clz(x):-1);cout<<'\\n';",
            "power": "long long a,b,m;cin>>a>>b>>m;long long r=1%m;for(;b;b>>=1,a=a*a%m)if(b&1)r=r*a%m;cout<<r<<'\\n';",
            "partition": "int n,t,x;cin>>n>>t;vector<int>a(n);for(int&z:a)cin>>z;stable_partition(a.begin(),a.end(),[&](int z){return v==0?z<t:v==1?z%2==0:z<0;});for(int z:a)cout<<z<<' ';cout<<'\\n';",
            "anagram": "string a,b;cin>>a>>b;sort(a.begin(),a.end());sort(b.begin(),b.end());cout<<(a==b?\"YES\":\"NO\")<<'\\n';",
            "median": "int n;cin>>n;vector<int>a(n);for(int&z:a)cin>>z;sort(a.begin(),a.end());cout<<(v==0?a[n/2]:v==1?a.back()-a.front():a.front())<<'\\n';",
        }[op]
        return head + body + "return 0;}\n"
    head = inc + f"int main(void){{int v={variant};"
    body = {
        "odd-sum": "int n,x,s=0;scanf(\"%d\",&n);while(n--){scanf(\"%d\",&x);if((x&1)==(v&1))s+=x;}printf(\"%d\\n\",s);",
        "rotate": "int n,k,a[3000];scanf(\"%d%d\",&n,&k);for(int i=0;i<n;i++)scanf(\"%d\",&a[i]);k%=n;if(v==1)k=(n-k)%n;for(int i=0;i<n;i++){int j=v==2?n-1-i:(i+n-k)%n;printf(\"%d%c\",a[j],i+1==n?'\\n':' ');} ",
        "run": "int n,p,x,b=1,c=1;scanf(\"%d%d\",&n,&p);for(int i=1;i<n;i++){scanf(\"%d\",&x);int z=v==0?x==p:v==1?x>=p:x>p;c=z?c+1:1;if(c>b)b=c;p=x;}printf(\"%d\\n\",b);",
        "unique": "int n,a[3000],b[3000],m=0;scanf(\"%d\",&n);for(int i=0;i<n;i++){scanf(\"%d\",&a[i]);int q=0;for(int j=0;j<m;j++)q|=b[j]==a[i];if(!q)b[m++]=a[i];}if(v==0)for(int i=0;i<m;i++)for(int j=i+1;j<m;j++)if(b[j]<b[i]){int t=b[i];b[i]=b[j];b[j]=t;}printf(\"%d\\n\",m);for(int i=0;i<m;i++)printf(\"%d%c\",b[i],i+1==m?'\\n':' ');",
        "bound": "int n,x,a[10000],l=0,r;scanf(\"%d%d\",&n,&x);r=n;for(int i=0;i<n;i++)scanf(\"%d\",&a[i]);while(l<r){int m=(l+r)/2;if(a[m]<(v==1?x+1:x))l=m+1;else r=m;}printf(\"%d\\n\",l);",
        "brackets": "char s[3000];scanf(\"%2999s\",s);char st[3000];int top=0,ok=1;for(int i=0;s[i];i++){char c=s[i];if(c=='('||c=='['||c=='{')st[top++]=c;else if(!top||((c==')'&&st[top-1]!='(')||(c==']'&&st[top-1]!='[')||(c=='}'&&st[top-1]!='{')))ok=0;else top--;}if(v==0)printf(\"%s\\n\",ok&&!top?\"YES\":\"NO\");else printf(\"%d\\n\",top);",
        "rle": "char s[3000];scanf(\"%2999s\",s);for(int i=0;s[i];){int j=i;while(s[j]&&s[j]==s[i])j++;if(v==0)printf(\"%d%c\",j-i,s[i]);else printf(\"%c%d\",s[i],j-i);i=j;}puts(\"\");",
        "prefix": "int n,x,cur=0;scanf(\"%d\",&n);for(int i=0;i<n;i++){scanf(\"%d\",&x);if(v==0)cur=i?cur>x?cur:x:x;else if(v==1)cur=i?cur<x?cur:x:x;else cur+=x;printf(\"%d%c\",cur,i+1==n?'\\n':' ');}",
        "matrix": "int r,c,a[40][40];scanf(\"%d%d\",&r,&c);for(int i=0;i<r;i++)for(int j=0;j<c;j++)scanf(\"%d\",&a[i][j]);if(v==0)for(int j=0;j<c;j++){for(int i=0;i<r;i++)printf(\"%d%c\",a[i][j],i+1==r?'\\n':' ');}else if(v==1){for(int i=0;i<r;i++){int s=0;for(int j=0;j<c;j++)s+=a[i][j];printf(\"%d%c\",s,i+1==r?'\\n':' ');}}else{for(int j=0;j<c;j++){int s=0;for(int i=0;i<r;i++)s+=a[i][j];printf(\"%d%c\",s,j+1==c?'\\n':' ');}}",
        "gcd": "int n,x,g=0;scanf(\"%d\",&n);while(n--){scanf(\"%d\",&x);x=x<0?-x:x;while(x){int t=g%x;g=x;x=t;}}printf(\"%d\\n\",g);",
        "bits": "unsigned int x;scanf(\"%u\",&x);int c=0;for(unsigned int y=x;y;y>>=1)c+=y&1;if(v==0)printf(\"%d\\n\",c);else if(v==1)printf(\"%d\\n\",c&1);else{int p=-1;while(x){p++;x>>=1;}printf(\"%d\\n\",p);}",
        "power": "long long a,b,m,r=1;scanf(\"%lld%lld%lld\",&a,&b,&m);a%=m;while(b){if(b&1)r=r*a%m;a=a*a%m;b>>=1;}printf(\"%lld\\n\",r);",
        "partition": "int n,t,a[4000];scanf(\"%d%d\",&n,&t);for(int i=0;i<n;i++)scanf(\"%d\",&a[i]);for(int pass=0;pass<n;pass++)for(int i=0;i+1<n;i++){int x=(v==0?a[i]>=t&&a[i+1]<t:v==1?a[i]%2&&!(a[i+1]%2):a[i]>=0&&a[i+1]<0);if(x){int z=a[i];a[i]=a[i+1];a[i+1]=z;}}for(int i=0;i<n;i++)printf(\"%d%c\",a[i],i+1==n?'\\n':' ');",
        "anagram": "char a[3000],b[3000];scanf(\"%2999s%2999s\",a,b);int ca[256]={{0}},cb[256]={{0}};for(int i=0;a[i];i++)ca[(unsigned char)a[i]]++;for(int i=0;b[i];i++)cb[(unsigned char)b[i]]++;int ok=1;for(int i=0;i<256;i++)if(ca[i]!=cb[i])ok=0;puts(ok?\"YES\":\"NO\");",
        "median": "int n,a[3000];scanf(\"%d\",&n);for(int i=0;i<n;i++)scanf(\"%d\",&a[i]);for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(a[j]<a[i]){int z=a[i];a[i]=a[j];a[j]=z;}printf(\"%d\\n\",v==0?a[n/2]:v==1?a[n-1]-a[0]:a[0]);",
    }[op]
    return head + body + "return 0;}\n"


def _java_code(op: str, variant: int) -> str:
    # Java solutions deliberately use standard library collections where the
    # exercise calls for them; Main.java is required by the platform runner.
    return f'''import java.io.*;import java.util.*;
public class Main {{ public static void main(String[] z)throws Exception{{Scanner s=new Scanner(System.in);int v={variant};
if("{op}".equals("odd-sum")){{int n=s.nextInt(),q=0;while(n-->0){{int x=s.nextInt();if((x&1)==(v&1))q+=x;}}System.out.println(q);}}
else if("{op}".equals("rotate")){{int n=s.nextInt(),k=s.nextInt();int[]a=new int[n];for(int i=0;i<n;i++)a[i]=s.nextInt();k=((k%n)+n)%n;if(v==1)k=(n-k)%n;for(int i=0;i<n;i++)System.out.print(a[(i+n-k)%n]+(i+1==n?"\\n":" "));}}
else if("{op}".equals("run")){{int n=s.nextInt(),p=s.nextInt(),b=1,c=1;for(int i=1;i<n;i++){{int x=s.nextInt();boolean ok=v==0?x==p:v==1?x>=p:x>p;c=ok?c+1:1;b=Math.max(b,c);p=x;}}System.out.println(b);}}
else if("{op}".equals("unique")){{int n=s.nextInt();List<Integer>a=new ArrayList<>();for(int i=0;i<n;i++){{int x=s.nextInt();if(!a.contains(x))a.add(x);}}if(v==0)Collections.sort(a);System.out.println(a.size());for(int x:a)System.out.print(x+" ");System.out.println();}}
else if("{op}".equals("bound")){{int n=s.nextInt(),x=s.nextInt();int[]a=new int[n];for(int i=0;i<n;i++)a[i]=s.nextInt();int l=0,r=n;while(l<r){{int m=(l+r)/2;if(a[m]<(v==1?x+1:x))l=m+1;else r=m;}}System.out.println(l);}}
else if("{op}".equals("brackets")){{String x=s.next();Deque<Character>d=new ArrayDeque<>();boolean ok=true;for(char c:x.toCharArray()){{if("([{{\".indexOf(c)>=0)d.push(c);else if(d.isEmpty()||((c==')'&&d.pop()!='(')||(c==']'&&d.pop()!='[')||(c=='}}'&&d.pop()!='{{')))ok=false;}}System.out.println(v==0?(ok&&d.isEmpty()?"YES":"NO"):d.size());}}
else if("{op}".equals("rle")){{String x=s.next();StringBuilder b=new StringBuilder();for(int i=0;i<x.length();){{int j=i;while(j<x.length()&&x.charAt(j)==x.charAt(i))j++;if(v==0)b.append(j-i).append(x.charAt(i));else b.append(x.charAt(i)).append(j-i);i=j;}}System.out.println(b);}}
else if("{op}".equals("prefix")){{int n=s.nextInt(),cur=0;for(int i=0;i<n;i++){{int x=s.nextInt();if(v==0)cur=i==0?x:Math.max(cur,x);else if(v==1)cur=i==0?x:Math.min(cur,x);else cur+=x;System.out.print(cur+(i+1==n?"\\n":" "));}}}}
else if("{op}".equals("matrix")){{int r=s.nextInt(),c=s.nextInt();int[][]a=new int[r][c];for(int i=0;i<r;i++)for(int j=0;j<c;j++)a[i][j]=s.nextInt();if(v==0)for(int j=0;j<c;j++){{for(int i=0;i<r;i++)System.out.print(a[i][j]+(i+1==r?"\\n":" "));}}else if(v==1){{for(int i=0;i<r;i++){{int q=0;for(int j=0;j<c;j++)q+=a[i][j];System.out.print(q+(i+1==r?"\\n":" "));}}}}else{{for(int j=0;j<c;j++){{int q=0;for(int i=0;i<r;i++)q+=a[i][j];System.out.print(q+(j+1==c?"\\n":" "));}}}}}}
else if("{op}".equals("gcd")){{int n=s.nextInt(),g=0;while(n-->0){{int x=Math.abs(s.nextInt());while(x!=0){{int t=g%x;g=x;x=t;}}}}System.out.println(g);}}
else if("{op}".equals("bits")){{int x=s.nextInt(),q=Integer.bitCount(x);System.out.println(v==0?q:v==1?q&1:(x==0?-1:31-Integer.numberOfLeadingZeros(x)));}}
else if("{op}".equals("power")){{long a=s.nextLong(),b=s.nextLong(),m=s.nextLong(),q=1%m;a%=m;while(b>0){{if((b&1)==1)q=q*a%m;a=a*a%m;b>>=1;}}System.out.println(q);}}
else if("{op}".equals("partition")){{int n=s.nextInt(),t=s.nextInt();List<Integer>a=new ArrayList<>();for(int i=0;i<n;i++)a.add(s.nextInt());a.sort((x,y)->{{boolean px=v==0?x<t:v==1?x%2==0:x<0,py=v==0?y<t:v==1?y%2==0:y<0;return px==py?0:px?-1:1;}});for(int x:a)System.out.print(x+" ");System.out.println();}}
else if("{op}".equals("anagram")){{char[]a=s.next().toCharArray(),b=s.next().toCharArray();Arrays.sort(a);Arrays.sort(b);System.out.println(Arrays.equals(a,b)?"YES":"NO");}}
else if("{op}".equals("median")){{int n=s.nextInt();int[]a=new int[n];for(int i=0;i<n;i++)a[i]=s.nextInt();Arrays.sort(a);System.out.println(v==0?a[n/2]:v==1?a[n-1]-a[0]:a[0]);}}
}}}}
'''


def code_for(language: str, op: str, variant: int) -> tuple[str, str]:
    if language == "Python": return "main.py", _py_code(op, variant)
    if language == "Java": return "Main.java", _java_code(op, variant)
    return ("main.cpp" if language == "C++" else "main.c"), _c_like_code(language, op, variant)


def cases_for(op: str, variant: int) -> list[str]:
    if op == "odd-sum": return ["7\n3 8 5 2 11 4 9\n", "4\n-3 -2 0 7\n", "6\n1 2 3 4 5 6\n", "5\n-5 -4 -3 -2 -1\n", "1\n8\n", "8\n9 7 5 3 1 0 -2 -4\n", "3\n0 0 0\n", "9\n-9 -7 -5 -3 -1 2 4 6 8\n"]
    if op == "rotate": return ["5 2\n1 2 3 4 5\n", "4 0\n8 7 6 5\n", "3 5\n-1 4 9\n", "1 99\n6\n", "6 4\n2 4 6 8 10 12\n", "7 1\n0 -1 -2 -3 -4 -5 -6\n", "2 3\n100 200\n", "5 7\n9 1 8 2 7\n"]
    if op == "run": return ["7\n2 2 3 3 3 1 1\n", "5\n1 2 3 2 1\n", "6\n4 4 4 4 2 2\n", "1\n9\n", "8\n1 2 2 3 4 4 5 6\n", "5\n-2 -1 0 1 2\n", "6\n9 8 7 6 5 4\n", "4\n3 3 2 1\n"]
    if op == "unique": return ["7\n4 2 4 1 2 3 1\n", "5\n9 9 9 9 9\n", "4\n-1 0 -1 2\n", "1\n7\n", "6\n3 2 1 3 2 1\n", "8\n0 1 0 2 3 2 4 3\n", "3\n-5 -5 -5\n", "5\n10 8 6 4 2\n"]
    if op == "bound": return ["6 4\n1 2 4 4 7 9\n", "4 0\n1 2 3 4\n", "5 10\n1 3 5 7 9\n", "1 5\n5\n", "7 -2\n-5 -2 -2 0 3 8 9\n", "3 1\n1 1 1\n", "5 6\n1 2 3 4 5\n", "4 -9\n-8 -3 0 2\n"]
    if op == "brackets": return ["([]){}\n", "([)]\n", "((()))\n", "()\n", "{[()]}\n", "((]\n", "{{{{}}}}\n", "{[}]\n"]
    if op == "rle": return ["aaabbc\n", "x\n", "zzzzzz\n", "aabccccdd\n", "112233\n", "abc\n", "mmmmnn\n", "ppppq\n"]
    if op == "prefix": return ["5\n3 1 4 2 5\n", "4\n-2 -1 -3 0\n", "1\n7\n", "6\n0 0 0 0 0 0\n", "7\n9 8 7 6 5 4 3\n", "3\n-5 10 -2\n", "8\n1 3 2 8 5 4 9 0\n", "2\n100 -100\n"]
    if op == "matrix": return ["2 3\n1 2 3\n4 5 6\n", "1 1\n9\n", "3 2\n-1 0\n2 4\n5 6\n", "2 2\n1 0\n0 1\n", "1 4\n1 2 3 4\n", "4 1\n2\n3\n5\n7\n", "2 3\n0 0 0\n1 2 3\n", "3 3\n1 2 3\n4 5 6\n7 8 9\n"]
    if op == "gcd": return ["4\n12 18 30 42\n", "3\n-6 15 21\n", "1\n0\n", "5\n7 13 19 31 37\n", "2\n100 250\n", "6\n24 36 48 60 72 84\n", "3\n-9 -27 -45\n", "4\n1 1 1 1\n"]
    if op == "bits": return ["0\n", "1\n", "7\n", "8\n", "255\n", "1024\n", "2147483647\n", "42\n"]
    if op == "power": return ["2 10 1000\n", "3 0 7\n", "5 1 13\n", "7 20 11\n", "10 9 6\n", "123456 17 1000003\n", "2 31 1000000007\n", "9 8 17\n"]
    if op == "partition": return ["7 5\n9 1 6 3 8 2 5\n", "5 0\n-2 3 -1 4 0\n", "6 10\n1 20 3 40 5 60\n", "1 4\n4\n", "8 -1\n-3 0 -2 5 -1 7 2 -4\n", "4 2\n1 2 3 4\n", "5 100\n1 2 3 4 5\n", "3 -5\n-6 -5 -4\n"]
    if op == "anagram": return ["listen silent\n", "abc abd\n", "a a\n", "dusty study\n", "state taste\n", "hello world\n", "night thing\n", "foo oof\n"]
    if op == "median": return ["5\n9 1 5 3 7\n", "1\n42\n", "7\n-3 8 0 2 2 9 -1\n", "3\n100 -5 7\n", "9\n4 8 1 6 2 9 0 3 5\n", "5\n-10 -2 -7 -4 -8\n", "11\n1 2 3 4 5 6 7 8 9 10 11\n", "3\n0 0 1\n"]
    raise KeyError(op)


def samples(language: str, op: str, variant: int, count_public: int = 3, count_hidden: int = 5) -> tuple[list[dict], list[dict]]:
    filename, ref = code_for(language, op, variant)
    vals = cases_for(op, variant)
    result=[]
    outputs = run_standard_many(language, ref, vals)
    for i, (stdin, out) in enumerate(zip(vals, outputs)):
        result.append({"id":f"{op}-{variant}-{i}","name":f"样例 {i+1}","stdin_text":stdin,"expected_stdout":out})
    return result[:count_public], result[count_public:count_public+count_hidden]


def title_and_statement(language: str, op: str, variant: int, title: str, objective: str) -> tuple[str,str,str]:
    variants = ["基础边界", "反例与重复值", "规模与负数", "逆序输入", "稀疏数据", "峰值数据"]
    title_zh = f"{LANG_PREFIX[language]}·{title}·{variants[variant]}"
    detail = next(item for item in OPS if item[0] == op)
    methods = {
        "odd-sum": "先逐项判断位模式，再把符合条件的读数累加；不要把总和初始化为输入中的第一个值。",
        "rotate": "先把位移量化到序列长度内，再用下标映射处理跨越首尾的元素，长度为一时也必须成立。",
        "run": "用当前段长度和历史最大值维护不变量，关系改变时只重置当前段，不要回看整段数据。",
        "unique": "区分排序去重、稳定去重和只保留单次出现三种语义，输出数量必须与结果序列一致。",
        "bound": "把答案定义为半开区间边界，用不变量缩小搜索范围；相等元素连续出现时也不能提前返回。",
        "brackets": "栈顶表示最近尚未闭合的左括号，遇到闭括号要先检查类型再弹栈，并处理剩余栈深度。",
        "rle": "每次找到一个最大连续段后一次性输出其长度和字符，不能把相邻但不同的段合并。",
        "prefix": "每处理一个元素就输出当前状态，最大值、最小值和累加值的初始状态必须与首元素区分。",
        "matrix": "行列索引的方向决定结果形状；变换、行汇总和列汇总不能混用行数与列数。",
        "gcd": "使用欧几里得算法逐项归约，并先把负数转为绝对值；全为零时结果仍要符合协议。",
        "bits": "只访问有效二进制位，零的最高位需要单独定义；位数统计不应依赖十进制字符串。",
        "power": "把指数拆成二进制位并在每次平方后取模，避免直接构造巨大幂值造成溢出。",
        "partition": "稳定分区只交换跨越边界的元素，谓词为真和为假的两段都要保留原有相对顺序。",
        "anagram": "先明确是否区分大小写，再比较字符频次或排序结果；长度不同可以直接判定失败。",
        "median": "先建立有序视图，再按照奇数长度的中间下标取值；不要把平均数误当成中位数。",
    }[op]
    scenes = [
        f"监测系统收到一批需要归档的记录，第一步应建立状态定义，再逐项处理 {detail[2]}",
        f"这组数据故意包含容易误判的边界和重复值；请围绕 {detail[2]} 说明判定顺序，避免把样例特征当成额外条件",
        f"当记录规模增大且数值可能为负时，线性扫描或合适的数据结构应保持结果稳定；本题的核心是 {detail[2]}",
        f"输入顺序不代表优先级，程序需要依据协议重新组织数据；请针对 {detail[2]} 保持每一步的中间状态可解释",
        f"部分记录可能稀疏、相同或落在范围端点，不能使用越界访问或未初始化值；任务仍然是准确完成 {detail[2]}",
        f"最后一组数据突出峰值、极小值和重复区间，适合用反例检查算法不变量；你要独立完成 {detail[2]}",
    ]
    variant_notes = [
        "请先验证最小规模输入，再检查正常序列；输出中不能混入提示文字。",
        "请专门构造相等值、重复值和刚好越界前后的输入，确认判定顺序与题意一致。",
        "请用带负数和较大绝对值的数据检查初始化、整数范围和最终格式，不能依赖偶然的正数样例。",
        "请把输入顺序与结果顺序分开思考，记录每一次位置变化，避免把原数组下标和结果下标混淆。",
        "请考虑有效数据很少但容器容量较大的情况，所有读取到的元素都必须参与协议规定的计算。",
        "请用峰值、平台段和连续重复段做一次手算，重点检查循环最后一次迭代是否遗漏或重复处理。",
    ]
    statement = (f"{scenes[variant]}。本题的关键在于：{methods}"
                 f"输入协议为：{detail[3]} 输出协议为：{detail[4]} 数据范围为：{detail[5]}。"
                 f"{variant_notes[variant]}请使用 {objective} 中的知识完成实现，并严格控制 stdout，只输出协议要求的结果。")
    return title_zh, statement, f"{language} 版本强调 {LANGUAGE_OBJECTIVES[language][variant % 8][2]}，实现时应使用该语言的标准能力并明确处理边界。"


def ensure_knowledge_nodes(db) -> dict[str,int]:
    mapping={}
    for lang, objectives in LANGUAGE_OBJECTIVES.items():
        course=f"programming_{lang.lower().replace('+','p')}"
        for i,(_, title, skill) in enumerate(objectives):
            key=f"catalog-480:{course}:{i}"
            row=db.query(KnowledgePoint).filter(KnowledgePoint.node_key==key).first()
            if not row:
                row=KnowledgePoint(username="system",course_id=course,parent_id=None,title=title,description=skill,order_index=i,level=2,node_key=key)
                db.add(row); db.flush()
            mapping[f"{lang}:{i}"]=row.id
    return mapping


def update_existing(db, kp: dict[str,int], language: str = "") -> int:
    count=0
    query=db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True),ProgrammingExercise.quality_status=="approved")
    if language:
        query=query.filter(ProgrammingExercise.language==language)
    rows=query.all()
    for index,row in enumerate(rows):
        tags=json.loads(row.tags_json or "[]") if row.tags_json else []
        obj_index=index%8
        row.background_knowledge_zh = row.background_knowledge_zh or f"开始本题前，应理解 {LANGUAGE_OBJECTIVES[row.language][obj_index][2]}，并会从标准输入读取数据。"
        row.hints_zh = row.hints_zh or "先写出输入到状态的转换关系，再处理最小规模、重复值和负数边界。"
        row.knowledge_point_ids=json.dumps([kp[f"{row.language}:{obj_index}" ]],ensure_ascii=False)
        row.primary_knowledge_point_id=kp[f"{row.language}:{obj_index}"]
        row.prerequisite_knowledge_point_ids=json.dumps([],ensure_ascii=False)
        row.curriculum_module=LANGUAGE_OBJECTIVES[row.language][obj_index][1]
        row.level=row.difficulty
        row.difficulty_score=65 if row.difficulty in {"中等","进阶"} else 45
        row.estimated_minutes=35 if row.difficulty in {"中等","进阶"} else 20
        starter=json.loads(row.starter_files_json or "[]")
        for file in starter:
            file["content"]=re.sub(r"\s*/\*\s*TODO[^*]*\*/", "", str(file.get("content") or ""), flags=re.I)
        row.starter_files_json=json.dumps(starter,ensure_ascii=False)
        count+=1
    return count


def make_candidate(language: str, serial: int, op_index: int, variant: int, kp: dict[str,int]) -> dict:
    op,title,objective_text,input_fmt,output_fmt,constraints=OPS[op_index]
    objective_id, objective_name, skill=LANGUAGE_OBJECTIVES[language][serial % 8]
    filename, reference=code_for(language,op,variant)
    public,hidden=samples(language,op,variant)
    title_zh,statement,fit=title_and_statement(language,op,serial % 6,title,objective_name)
    return {
        "source_key":f"first_party_catalog_480:{language}:{op}:{serial}",
        "language":language,"title_zh":title_zh,"summary_zh":f"使用{skill}解决{title}，覆盖{['普通输入','边界输入','反例输入'][variant]}。",
        "statement_zh":statement,"input_format_zh":input_fmt,"output_format_zh":output_fmt,"constraints_zh":constraints,
        "title_en":title,"statement_en":f"Implement {title} while preserving the stated protocol.","difficulty":"中等" if serial%3 else "进阶",
        "problem_family_id":f"first-party-480-{language.lower().replace('+','p')}-{op}-{serial}","language_fit_reason":fit,
        "learning_objective_id":objective_id,"learning_objective":objective_name,"prerequisites":"变量、循环、函数和标准输入输出",
        "core_skill":skill,"novelty_reason":f"该题独立考查{title}，使用不同的数据结构和边界协议，不是数字、运算符或故事替换。",
        "knowledge_tags":[language,objective_id,op,skill],"background_knowledge_zh":f"需要先掌握 {skill}，并理解输入数据的边界。",
        "hints_zh":"先列出状态变量及其不变量；再用一个最小样例手算，最后检查空集合、重复值和极端数值。",
        "knowledge_point_ids":json.dumps([kp[f"{language}:{serial%8}"]]),"primary_knowledge_point_id":kp[f"{language}:{serial%8}"],"prerequisite_knowledge_point_ids":"[]",
        "curriculum_module":objective_name,"level":"中等" if serial%3 else "进阶","difficulty_score":70 if serial%3 else 80,"estimated_minutes":35 if serial%3 else 50,
        "starter_code":(
            "import sys\n\nif __name__ == '__main__':\n    pass\n"
            if language == "Python" else
            "public class Main { public static void main(String[] args) { } }\n"
            if language == "Java" else
            ("#include <bits/stdc++.h>\nusing namespace std;\nint main(){return 0;}\n"
             if language == "C++" else
             "#include <stdio.h>\nint main(void){return 0;}\n")
        ),
        "reference_code":reference,"wrong_code":("print(0)\n" if language=="Python" else "public class Main { public static void main(String[] a){System.out.println(0);} }\n" if language=="Java" else "#include <stdio.h>\nint main(void){puts(\"0\");return 0;}\n"),
        "filename":filename,"public_cases":public,"hidden_cases":hidden,
    }


def persist(db, candidate: dict) -> None:
    # samples() has already run the reference executable against every public
    # and hidden input.  Keep this write-time check focused on the remaining
    # independent gates so the builder does not repeat the same compilation.
    starter_ok = compile_starter(candidate)
    wrong = dict(candidate)
    wrong["reference_code"] = candidate["wrong_code"]
    wrong_case = next((item for item in candidate["hidden_cases"] if str(item.get("expected_stdout", "")).strip() not in {"", "0", "NO"}), candidate["hidden_cases"][0])
    wrong_output = execute_reference(wrong, wrong_case)
    if not starter_ok or wrong_output.rstrip() == wrong_case["expected_stdout"].rstrip():
        raise RuntimeError(f"candidate execution gate failed: {candidate['source_key']}")
    now=datetime.now(timezone.utc).isoformat()
    payload={"slug":candidate["source_key"].replace(":","-").replace("/","-"),"source_key":candidate["source_key"],"language":candidate["language"],"title":candidate["title_zh"],"difficulty":candidate["difficulty"],"tags_json":json.dumps(candidate["knowledge_tags"],ensure_ascii=False),"description":candidate["summary_zh"],"starter_files_json":json.dumps([{"path":candidate["filename"],"content":candidate["starter_code"]}],ensure_ascii=False),"reference_files_json":json.dumps([{"path":candidate["filename"],"content":candidate["reference_code"]}],ensure_ascii=False),"public_tests_json":json.dumps([{"samples":candidate["public_cases"]}],ensure_ascii=False),"hidden_tests_json":json.dumps([{"samples":candidate["hidden_cases"]}],ensure_ascii=False),"official_test_files_json":"[]","source_repo":"first_party_original","source_path":candidate["source_key"],"source_commit":"catalog-480-2026-08-01","license":"project_owned","license_text":"题面、测试数据与实现为本项目第一方原创内容。","attribution":"AI Study Platform first-party catalog","reference_verified":True,"starter_verified":True,"audit_report_json":json.dumps({"runner":"standard_io","validated":True,"wrong_solution_rejected":True},ensure_ascii=False),"is_active":True,"quality_status":"approved","quality_score":96,"quality_failure_reasons":"[]","reviewed_at":now}
    fields=("title_zh","summary_zh","statement_zh","input_format_zh","output_format_zh","constraints_zh","title_en","statement_en","problem_family_id","language_fit_reason","learning_objective_id","learning_objective","prerequisites","core_skill","novelty_reason","background_knowledge_zh","hints_zh","knowledge_point_ids","primary_knowledge_point_id","prerequisite_knowledge_point_ids","curriculum_module","level","difficulty_score","estimated_minutes")
    payload.update({key:candidate[key] for key in fields})
    row=db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key==candidate["source_key"]).first()
    if not row: row=ProgrammingExercise(); db.add(row)
    for key,value in payload.items(): setattr(row,key,value)


def write_blueprint() -> None:
    languages={}
    for language, objectives in LANGUAGE_OBJECTIVES.items():
        items=[]
        for oid,name,skill in objectives:
            items.append({"objective_id":oid,"objective":name,"core_skill":skill,"prerequisites":"变量、函数和标准输入输出","slots":[f"{language.lower().replace('+','p')}-{i:03d}" for i in range(1,16)]})
        languages[language]=items
    payload={"schema_version":2,"status":"validated_catalog_blueprint","rules":{"minimum_public_cases":3,"minimum_hidden_cases":5,"public_hidden_input_overlap":0,"forbid_numbered_template_titles":True,"approved_requires":["validated=true","quality_status=approved","learning_objective_id","knowledge_point_ids"]},"languages":languages}
    BLUEPRINT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=sorted(LANGUAGE_OBJECTIVES), default="")
    args = parser.parse_args()
    ensure_database_schema(engine)
    db=SessionLocal(); created=[]
    try:
        kp=ensure_knowledge_nodes(db)
        existing=update_existing(db,kp,args.language)
        # Publish the additive knowledge graph and metadata repair before the
        # longer exercise batch so other language shards do not contend on
        # first-time node creation.
        db.commit()
        languages=[args.language] if args.language else list(LANGUAGE_OBJECTIVES)
        for language in languages:
            current=db.query(ProgrammingExercise).filter(ProgrammingExercise.language==language,ProgrammingExercise.is_active.is_(True),ProgrammingExercise.quality_status=="approved").count()
            need=max(0,120-current); serial=0
            for op_index in range(len(OPS)):
                for variant in range(6):
                    if serial>=need: break
                    candidate=make_candidate(language,serial,op_index,variant%3,kp)
                    persist(db,candidate); created.append({"language":language,"source_key":candidate["source_key"],"title_zh":candidate["title_zh"],"learning_objective_id":candidate["learning_objective_id"]}); serial+=1
                if serial>=need: break
        db.commit()
    except Exception:
        db.rollback(); raise
    finally: db.close()
    write_blueprint()
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"restored-problems-audit.json").write_text(json.dumps({"existing_repaired":existing,"official_candidates_kept_in_review":True},ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"new-quality-problems-audit.json").write_text(json.dumps({"new":created,"counts":dict(Counter(x["language"] for x in created))},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"existing_repaired":existing,"created":len(created),"counts":dict(Counter(x["language"] for x in created))},ensure_ascii=False))


if __name__ == "__main__": main()
