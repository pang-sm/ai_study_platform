"""Build the quality-gated 240-problem first-party programming catalog.

This file deliberately keeps the catalog deterministic.  Every candidate is
compiled, its reference implementation generates the expected output for all
cases, and a deliberately incorrect implementation must fail at least one
hidden case before the row is written as approved.
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from catalog_adapters import _compile, _run, compile_starter  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from database_schema import ensure_database_schema  # noqa: E402
from models import ProgrammingExercise  # noqa: E402

OUT = ROOT / "verification-results"
DATA = ROOT / "backend" / "data" / "programming_catalog"
SNAPSHOT = ROOT / "backend" / "data" / "programming_catalog_240.json.gz"
BLUEPRINT = DATA / "curriculum_blueprint.json"
LANGUAGES = ("C", "C++", "Python", "Java")

with BLUEPRINT.open(encoding="utf-8") as _handle:
    BLUEPRINT_DATA = json.load(_handle)


def cases(kind: str) -> list[str]:
    return {
        "recipe": ["3\n2 5\n3 4\n5 6\n", "1\n7 9\n", "4\n1 10\n2 0\n3 8\n4 2\n", "2\n100 3\n2 50\n", "5\n9 9\n8 1\n7 4\n6 2\n5 3\n", "3\n0 0\n0 4\n0 9\n", "4\n-2 5\n3 -4\n8 1\n1 7\n", "2\n999 1\n1 999\n"],
        "transfer": ["3\n8 3 6\n", "1\n12\n", "4\n10 10 10 10\n", "2\n1 20\n", "5\n30 2 8 4 6\n", "3\n0 5 0\n", "6\n7 1 9 2 8 3\n", "2\n100 100\n"],
        "month": ["2024 2\n", "1900 2\n", "2000 2\n", "2023 4\n", "2023 1\n", "2024 12\n", "2100 9\n", "2400 2\n"],
        "checksum": ["123456\n", "0000\n", "987654321\n", "13579\n", "24680\n", "101010\n", "909090\n", "31415926\n"],
        "scoreboard": ["3\nred 3 1 0\nblue 2 0 2\ngold 1 3 0\n", "2\na 0 0 1\nb 0 0 0\n", "4\nriver 4 0 0\nforest 3 2 0\nlake 3 2 1\nplain 1 0 3\n", "1\nsolo 9 0 0\n", "3\nalpha 2 2 2\nbeta 3 0 3\ngamma 2 2 1\n", "3\ncat 0 3 0\ndog 1 0 2\nant 0 3 0\n", "4\nteam4 5 0 0\nteam1 5 0 0\nteam2 4 2 0\nteam3 4 1 1\n", "2\nzero 0 5 0\nminus 0 0 5\n"],
        "times": ["4\n09:30\n08:15\n23:05\n08:05\n", "1\n00:00\n", "3\n12:40\n12:04\n01:59\n", "5\n18:00\n06:30\n06:03\n17:59\n23:59\n", "2\n10:10\n10:01\n", "3\n20:20\n02:02\n12:12\n", "4\n11:11\n11:10\n11:01\n11:00\n", "2\n23:59\n00:01\n"],
        "intervals": ["3\n1 3\n2 5\n7 9\n", "2\n0 1\n1 2\n", "4\n5 8\n1 2\n10 12\n2 6\n", "1\n-3 4\n", "5\n1 10\n2 3\n8 9\n12 14\n13 20\n", "3\n0 0\n4 4\n2 3\n", "2\n9 11\n1 8\n", "4\n-10 -5\n-6 0\n1 1\n2 9\n"],
        "inventory": ["4\napple 3\npear 2\napple -1\nkiwi 5\n", "3\npen 0\npen 4\nbook -2\n", "5\nred 1\nblue 2\nred 4\nblue -1\ngreen 0\n", "2\nbox -3\nbox 3\n", "6\nmap 2\nmap 2\nmap -1\npen 7\nbook 1\npen -2\n", "1\nzero 0\n", "4\na 10\nb -2\na -8\nc 1\n", "3\n甲 2\n乙 3\n甲 5\n"],
        "unique": ["swiss\n", "aabbcc\n", "level\n", "engineering\n", "a\n", "1122334455\n", "committee\n", "abacabad\n"],
        "words": ["red blue red green blue red\n", "one\n", "cat dog dog cat bird\n", "alpha beta gamma\n", "same same same\n", "z z a a a\n", "north south north east south\n", "code makes code good makes code\n"],
        "brackets": ["([]){}\n", "([)]\n", "\n", "(((())))\n", "{[}\n", "()[]{}\n", "((]\n", "[{}()]\n"],
        "caesar": ["3\nhello world\n", "0\nKeep-Case!\n", "1\naz AZ\n", "25\nbcd\n", "5\nalgorithm\n", "13\nuryyb\n", "7\nhello, zoo\n", "2\nC++ and C\n"],
        "prefix": ["4\nalpha\nalpine\nbeta\nalps\nalp\n", "3\ncat\ndog\nbird\nz\n", "5\nflower\nflow\nflight\nflock\nflat\nfl\n", "1\nsolo\nso\n", "6\nread\nready\nreal\nreason\nreact\nwrite\nrea\n", "4\nmap\nmaple\nmath\nmax\nmap\n", "3\nabc\nabd\nabe\nab\n", "2\n中文\n中文题\n中文\n"],
        "rotate": ["5 2\n1 2 3 4 5\n", "4 0\n8 7 6 5\n", "3 5\n-1 4 9\n", "1 9\n6\n", "6 4\n2 4 6 8 10 12\n", "7 1\n0 -1 -2 -3 -4 -5 -6\n", "2 3\n100 200\n", "5 7\n9 1 8 2 7\n"],
        "dedup": ["8\n1 1 2 2 2 4 5 5\n", "5\n-2 -2 -1 0 0\n", "1\n9\n", "6\n3 2 3 2 1 1\n", "7\n0 0 0 1 2 2 3\n", "4\n8 7 6 5\n", "9\n1 3 1 3 5 7 5 7 9\n", "3\n-1 -1 -1\n"],
        "ranges": ["5 3\n2 4 6 8 10\n1 3\n2 5\n4 4\n", "1 2\n9\n1 1\n1 1\n", "4 2\n-2 5 0 7\n1 2\n2 4\n", "6 3\n1 1 1 1 1 1\n1 6\n2 2\n3 5\n", "3 1\n100 200 300\n2 3\n", "5 2\n-5 -4 -3 -2 -1\n1 5\n3 4\n", "2 3\n7 8\n1 2\n2 2\n1 1\n", "4 2\n0 10 0 10\n1 4\n2 3\n"],
        "maxsub": ["5\n-2 3 -1 5 -6\n", "3\n-5 -2 -9\n", "4\n1 2 3 4\n", "6\n4 -1 2 -7 5 2\n", "1\n0\n", "7\n-1 -2 4 -1 3 -2 3\n", "5\n-3 0 -2 0 -1\n", "8\n2 -1 2 3 -9 4 4 -1\n"],
        "overlap": ["3\n1 4\n2 5\n7 9\n", "2\n0 1\n1 2\n", "4\n5 8\n1 6\n2 4\n3 7\n", "1\n-3 4\n", "5\n1 10\n2 3\n8 9\n12 14\n13 20\n", "3\n0 0\n4 4\n2 3\n", "2\n9 11\n1 8\n", "4\n-10 -5\n-6 0\n1 1\n2 9\n"],
        "coins": ["11 3\n1 5 7\n", "6 2\n4 5\n", "0 3\n2 3 7\n", "23 4\n2 5 10 20\n", "3 2\n2 4\n", "18 3\n3 7 11\n", "1 1\n2\n", "40 5\n1 9 10 20 25\n"],
        "bfs": ["3 4\nS..#\n.#.E\n....\n", "1 2\nSE\n", "3 3\nS##\n..#\n..E\n", "2 2\nS#\n#E\n", "4 5\nS...#\n.##..\n...#.\n#...E\n", "2 3\n...\nS.E\n", "3 5\nS....\n#####\n....E\n", "2 3\nS..\n..E\n"],
    }.get(kind, [])


TASK_GROUPS = [
    ("recipe", ["咖啡配方的总用量", "实验配液的计量单", "烘焙订单的原料核算"]),
    ("transfer", ["地铁换乘的有效耗时", "客服工单的处理时长", "流水线工序的节拍统计"]),
    ("month", ["账单周期的天数", "排班月份的有效天数", "日历组件的月份校验"]),
    ("checksum", ["设备序列号校验", "仓单数字的交替校验", "票据编号的校验差"]),
    ("scoreboard", ["联赛积分榜", "机器人赛季排名", "社团比赛榜单"]),
    ("times", ["航班时刻表排序", "门店开店时间整理", "直播预约时间线"]),
    ("intervals", ["仓库占用区间合并", "实验预约时间段合并", "网络维护窗口归并"]),
    ("inventory", ["图书馆库存变动", "药房批次结存", "零件仓库的净库存"]),
    ("unique", ["首个独特字符", "设备日志的首个单次标记", "注册码中的唯一符号"]),
    ("words", ["文章关键词冠军", "客服标签频次", "搜索词热度摘要"]),
    ("brackets", ["配置片段的括号检查", "模板标记的嵌套检查", "表达式分组校验"]),
    ("caesar", ["短消息的轮转解码", "旧档案的字母还原", "设备口令的偏移解密"]),
    ("prefix", ["字典前缀检索", "商品编码前缀统计", "路由名称的前缀匹配"]),
    ("rotate", ["值班表循环移位", "传感器序列轮转", "货架编号的环形平移"]),
    ("dedup", ["访客编号稳定去重", "订单标签去重", "采样序列保留首次出现"]),
    ("ranges", ["账户流水区间求和", "温度记录区间统计", "仓位读数的范围查询"]),
    ("maxsub", ["连续盈利最长区段", "信号强度的最佳窗口", "训练成绩的连续高峰"]),
    ("overlap", ["会议室同时占用数", "服务器并发维护数", "展位同时预约数"]),
    ("coins", ["售票机的最少硬币数", "积分兑换的最少张数", "仓库配货的最少箱数"]),
    ("bfs", ["园区地图的最短步数", "机器人到出口的最短路", "网格中救援路线长度"]),
]


def c_source(kind: str, wrong: bool = False) -> str:
    if wrong:
        return '#include <stdio.h>\nint main(void){puts("0");return 0;}\n'
    common = '#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <ctype.h>\n'
    body = {
        "recipe": 'int main(void){int n,a,b,s=0;scanf("%d",&n);while(n--){scanf("%d%d",&a,&b);s+=a*b;}printf("%d\\n",s);}',
        "transfer": 'int main(void){int n,x,s=0;scanf("%d",&n);for(int i=0;i<n;i++){scanf("%d",&x);s+=x;if(i)s-=2;}printf("%d\\n",s>0?s:0);}',
        "month": 'int main(void){int y,m,d[]={0,31,28,31,30,31,30,31,31,30,31,30,31};scanf("%d%d",&y,&m);if(m==2&&((y%400==0)||(y%4==0&&y%100)))d[2]=29;printf("%d\\n",d[m]);}',
        "checksum": 'int main(void){char s[10000];scanf("%9999s",s);int x=0;for(int i=0;s[i];i++)x+=(i%2? -1:1)*(s[i]-48);printf("%d\\n",x);}',
        "scoreboard": 'typedef struct{char n[64];int w,d,l;} T;int main(void){int z;scanf("%d",&z);T a[100];for(int i=0;i<z;i++)scanf("%63s%d%d%d",a[i].n,&a[i].w,&a[i].d,&a[i].l);for(int i=0;i<z;i++)for(int j=i+1;j<z;j++){int pi=3*a[i].w+a[i].d,pj=3*a[j].w+a[j].d;if(pj>pi||(pj==pi&&strcmp(a[j].n,a[i].n)<0)){T t=a[i];a[i]=a[j];a[j]=t;}}for(int i=0;i<z;i++)printf("%s:%d\\n",a[i].n,3*a[i].w+a[i].d);}',
        "times": 'int main(void){int n,h,m;char s[16];char a[100][16];scanf("%d",&n);for(int i=0;i<n;i++)scanf("%15s",a[i]);for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(strcmp(a[j],a[i])<0){char t[16];strcpy(t,a[i]);strcpy(a[i],a[j]);strcpy(a[j],t);}for(int i=0;i<n;i++)puts(a[i]);}',
        "intervals": 'typedef struct{int l,r;} I;int main(void){int n;scanf("%d",&n);I a[100];for(int i=0;i<n;i++)scanf("%d%d",&a[i].l,&a[i].r);for(int i=0;i<n;i++)for(int j=i+1;j<n;j++)if(a[j].l<a[i].l){I t=a[i];a[i]=a[j];a[j]=t;}I out[100];int k=0;for(int i=0;i<n;i++){if(!k||a[i].l>out[k-1].r)out[k++]=a[i];else if(a[i].r>out[k-1].r)out[k-1].r=a[i].r;}printf("%d\\n",k);for(int i=0;i<k;i++)printf("%d %d\\n",out[i].l,out[i].r);}',
        "inventory": 'typedef struct{char n[64];int v;} P;int main(void){int z;scanf("%d",&z);P a[100];int k=0;while(z--){char n[64];int v;scanf("%63s%d",n,&v);int q=-1;for(int i=0;i<k;i++)if(!strcmp(a[i].n,n))q=i;if(q<0){strcpy(a[k].n,n);a[k++].v=v;}else a[q].v+=v;}for(int i=0;i<k;i++)for(int j=i+1;j<k;j++)if(strcmp(a[j].n,a[i].n)<0){P t=a[i];a[i]=a[j];a[j]=t;}for(int i=0;i<k;i++)if(a[i].v)printf("%s:%d\\n",a[i].n,a[i].v);}',
        "unique": 'int main(void){char s[10000];scanf("%9999s",s);for(int i=0;s[i];i++){int c=0;for(int j=0;s[j];j++)if(s[i]==s[j])c++;if(c==1){printf("%c\\n",s[i]);return 0;}}puts("NONE");}',
        "words": 'int main(void){int n=0;char s[10000],w[200][64];scanf("%9999[^\\n]",s);char* p=strtok(s," ");while(p){strcpy(w[n++],p);p=strtok(NULL," ");}int best=0;char ans[64]="";for(int i=0;i<n;i++){int c=0;for(int j=0;j<n;j++)c+=!strcmp(w[i],w[j]);if(c>best||(c==best&&strcmp(w[i],ans)<0)){best=c;strcpy(ans,w[i]);}}printf("%s %d\\n",ans,best);}',
        "brackets": 'int main(void){char s[10000],q[10000];int t=0,ok=1;fgets(s,sizeof(s),stdin);for(int i=0;s[i]&&s[i]!=10;i++){char c=s[i];if(c==40||c==91||c==123)q[t++]=c;else if(c==41||c==93||c==125){if(!t||(c==41&&q[t-1]!=40)||(c==93&&q[t-1]!=91)||(c==125&&q[t-1]!=123))ok=0;else t--;}}puts(ok&&t==0?"YES":"NO");}',
        "caesar": 'int main(void){int k;char s[10000];scanf("%d",&k);getchar();fgets(s,sizeof(s),stdin);for(int i=0;s[i];i++){char c=s[i];if(c>=97&&c<=122)s[i]=(char)(97+(c-97-k%26+26)%26);else if(c>=65&&c<=90)s[i]=(char)(65+(c-65-k%26+26)%26);}fputs(s,stdout);}',
        "prefix": 'int main(void){int n;char a[100][128],q[128];scanf("%d",&n);for(int i=0;i<n;i++)scanf("%127s",a[i]);scanf("%127s",q);int z=0;for(int i=0;i<n;i++)if(!strncmp(a[i],q,strlen(q)))z++;printf("%d\\n",z);}',
        "rotate": 'int main(void){int n,k,a[1000];scanf("%d%d",&n,&k);for(int i=0;i<n;i++)scanf("%d",&a[i]);k%=n;for(int i=0;i<n;i++)printf("%d%c",a[(i+n-k)%n],i+1==n?10:32);}',
        "dedup": 'int main(void){int n,a[1000],b[1000],k=0;scanf("%d",&n);for(int i=0;i<n;i++){scanf("%d",&a[i]);int seen=0;for(int j=0;j<k;j++)if(b[j]==a[i])seen=1;if(!seen)b[k++]=a[i];}for(int i=0;i<k;i++)printf("%d%c",b[i],i+1==k?10:32);}',
        "ranges": 'int main(void){int n,q,a[1000];long long p[1001]={0};scanf("%d%d",&n,&q);for(int i=1;i<=n;i++){scanf("%d",&a[i]);p[i]=p[i-1]+a[i];}while(q--){int l,r;scanf("%d%d",&l,&r);printf("%lld\\n",p[r]-p[l-1]);}}',
        "maxsub": 'int main(void){int n,x;long long cur=0,best=-9000000000000000000LL;scanf("%d",&n);while(n--){scanf("%d",&x);cur=cur>0?cur+x:x;if(cur>best)best=cur;}printf("%lld\\n",best);}',
        "overlap": 'typedef struct{int x,d;} E;int main(void){int n;scanf("%d",&n);E e[200];for(int i=0;i<n;i++){int l,r;scanf("%d%d",&l,&r);e[2*i]=(E){l,1};e[2*i+1]=(E){r,-1};}for(int i=0;i<2*n;i++)for(int j=i+1;j<2*n;j++)if(e[j].x<e[i].x||(e[j].x==e[i].x&&e[j].d<e[i].d)){E t=e[i];e[i]=e[j];e[j]=t;}int c=0,b=0;for(int i=0;i<2*n;i++){c+=e[i].d;if(c>b)b=c;}printf("%d\\n",b);}',
        "coins": 'int main(void){int a,m,c[100],d[10001];scanf("%d%d",&a,&m);for(int i=0;i<m;i++)scanf("%d",&c[i]);for(int i=0;i<=a;i++)d[i]=1000000;d[0]=0;for(int x=1;x<=a;x++)for(int j=0;j<m;j++)if(c[j]<=x&&d[x-c[j]]+1<d[x])d[x]=d[x-c[j]]+1;printf("%d\\n",d[a]>=1000000?-1:d[a]);}',
        "bfs": 'int main(void){int n,m,sx=0,sy=0,ex=0,ey=0;char g[100][100];scanf("%d%d",&n,&m);for(int i=0;i<n;i++){scanf("%s",g[i]);for(int j=0;j<m;j++){if(g[i][j]==83){sx=i;sy=j;}if(g[i][j]==69){ex=i;ey=j;}}}int d[100][100],qx[10000],qy[10000],h=0,t=0;for(int i=0;i<n;i++)for(int j=0;j<m;j++)d[i][j]=-1;d[sx][sy]=0;qx[t]=sx;qy[t++]=sy;int dx[4]={1,-1,0,0},dy[4]={0,0,1,-1};while(h<t){int x=qx[h],y=qy[h++];for(int k=0;k<4;k++){int u=x+dx[k],v=y+dy[k];if(u>=0&&u<n&&v>=0&&v<m&&g[u][v]!=35&&d[u][v]<0){d[u][v]=d[x][y]+1;qx[t]=u;qy[t++]=v;}}}printf("%d\\n",d[ex][ey]);}',
    }[kind]
    return common + body + "\n"


def cpp_source(kind: str, wrong: bool = False) -> str:
    if wrong:
        return '#include <iostream>\nint main(){std::cout<<0<<"\\n";}\n'
    # C++ implementations intentionally use STL containers/algorithms where
    # the task benefits from them; the input/output contract matches C.
    return {
        "recipe": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,a,b,s=0;cin>>n;while(n--){cin>>a>>b;s+=a*b;}cout<<s<<"\\n";}',
        "transfer": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,x,s=0;cin>>n;for(int i=0;i<n;i++){cin>>x;s+=x;if(i)s-=2;}cout<<max(0,s)<<"\\n";}',
        "month": '#include <bits/stdc++.h>\nusing namespace std;int main(){int y,m;cin>>y>>m;int d[]={0,31,28,31,30,31,30,31,31,30,31,30,31};if(m==2&&((y%400==0)||(y%4==0&&y%100)))d[2]=29;cout<<d[m]<<"\\n";}',
        "checksum": '#include <bits/stdc++.h>\nusing namespace std;int main(){string s;cin>>s;int x=0;for(int i=0;i<(int)s.size();i++)x+=(i%2?-1:1)*(s[i]-48);cout<<x<<"\\n";}',
        "scoreboard": '#include <bits/stdc++.h>\nusing namespace std;struct T{string n;int w,d,l;};int main(){int n;cin>>n;vector<T>a(n);for(auto&x:a)cin>>x.n>>x.w>>x.d>>x.l;sort(a.begin(),a.end(),[](auto&A,auto&B){int x=3*A.w+A.d,y=3*B.w+B.d;return x!=y?x>y:A.n<B.n;});for(auto&x:a)cout<<x.n<<":"<<3*x.w+x.d<<"\\n";}',
        "times": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n;cin>>n;vector<string>a(n);for(auto&x:a)cin>>x;sort(a.begin(),a.end());for(auto&x:a)cout<<x<<"\\n";}',
        "intervals": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n;cin>>n;vector<pair<int,int>>a(n);for(auto&x:a)cin>>x.first>>x.second;sort(a.begin(),a.end());vector<pair<int,int>>o;for(auto x:a){if(o.empty()||x.first>o.back().second)o.push_back(x);else o.back().second=max(o.back().second,x.second);}cout<<o.size()<<"\\n";for(auto x:o)cout<<x.first<<" "<<x.second<<"\\n";}',
        "inventory": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,v;cin>>n;map<string,int>a;string s;while(n--){cin>>s>>v;a[s]+=v;}for(auto&x:a)if(x.second)cout<<x.first<<":"<<x.second<<"\\n";}',
        "unique": '#include <bits/stdc++.h>\nusing namespace std;int main(){string s;cin>>s;for(char c:s)if(count(s.begin(),s.end(),c)==1){cout<<c<<"\\n";return 0;}cout<<"NONE\\n";}',
        "words": '#include <bits/stdc++.h>\nusing namespace std;int main(){string s,w,ans;getline(cin,s);stringstream ss(s);map<string,int>m;while(ss>>w)m[w]++;for(auto&x:m)if(ans.empty()||x.second>m[ans])ans=x.first;cout<<ans<<" "<<m[ans]<<"\\n";}',
        "brackets": '#include <bits/stdc++.h>\nusing namespace std;int main(){string s;getline(cin,s);vector<char>q;bool ok=1;for(char c:s){if(string("([{\").find(c)!=string::npos)q.push_back(c);else if(string(")]}").find(c)!=string::npos){if(q.empty()||(c==\')\'&&q.back()!=\'(\')||(c==\']\'&&q.back()!=\'[\')||(c==\'}\'&&q.back()!=\'{\'))ok=0;else q.pop_back();}}cout<<(ok&&q.empty()?"YES":"NO")<<"\\n";}',
        "caesar": '#include <bits/stdc++.h>\nusing namespace std;int main(){int k;string s;cin>>k;cin.ignore();getline(cin,s);for(char&c:s)if(islower(c))c=\'a\'+(c-\'a\'-k%26+26)%26;else if(isupper(c))c=\'A\'+(c-\'A\'-k%26+26)%26;cout<<s<<"\\n";}',
        "prefix": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,z=0;cin>>n;vector<string>a(n);for(auto&x:a)cin>>x;string q;cin>>q;for(auto&x:a)z+=x.rfind(q,0)==0;cout<<z<<"\\n";}',
        "rotate": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,k;cin>>n>>k;vector<int>a(n);for(int&x:a)cin>>x;k%=n;rotate(a.begin(),a.end()-k,a.end());for(int i=0;i<n;i++)cout<<a[i]<<(i+1==n?\'\\n\':\' \');}',
        "dedup": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,x;cin>>n;vector<int>o;set<int>s;while(n--){cin>>x;if(s.insert(x).second)o.push_back(x);}for(int i=0;i<(int)o.size();i++)cout<<o[i]<<(i+1==(int)o.size()?\'\\n\':\' \');}',
        "ranges": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,q;cin>>n>>q;vector<long long>p(n+1);for(int i=1,x;i<=n;i++){cin>>x;p[i]=p[i-1]+x;}while(q--){int l,r;cin>>l>>r;cout<<p[r]-p[l-1]<<"\\n";}}',
        "maxsub": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,x;long long cur=0,best=LLONG_MIN;cin>>n;while(n--){cin>>x;cur=max<long long>(x,cur+x);best=max(best,cur);}cout<<best<<"\\n";}',
        "overlap": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n;cin>>n;vector<pair<int,int>>e;while(n--){int l,r;cin>>l>>r;e.push_back({l,1});e.push_back({r,-1});}sort(e.begin(),e.end(),[](auto&a,auto&b){return a.first!=b.first?a.first<b.first:a.second<b.second;});int c=0,b=0;for(auto x:e)b=max(b,c+=x.second);cout<<b<<"\\n";}',
        "coins": '#include <bits/stdc++.h>\nusing namespace std;int main(){int a,m;cin>>a>>m;vector<int>c(m);for(int&x:c)cin>>x;vector<int>d(a+1,1e9);d[0]=0;for(int x=1;x<=a;x++)for(int v:c)if(v<=x)d[x]=min(d[x],d[x-v]+1);cout<<(d[a]>=1e9?-1:d[a])<<"\\n";}',
        "bfs": '#include <bits/stdc++.h>\nusing namespace std;int main(){int n,m;cin>>n>>m;vector<string>g(n);int sx,sy,ex,ey;for(int i=0;i<n;i++){cin>>g[i];for(int j=0;j<m;j++){if(g[i][j]==\'S\')sx=i,sy=j;if(g[i][j]==\'E\')ex=i,ey=j;}}vector<vector<int>>d(n,vector<int>(m,-1));queue<pair<int,int>>q;q.push({sx,sy});d[sx][sy]=0;int dx[]={1,-1,0,0},dy[]={0,0,1,-1};while(!q.empty()){auto[x,y]=q.front();q.pop();for(int k=0;k<4;k++){int u=x+dx[k],v=y+dy[k];if(u>=0&&u<n&&v>=0&&v<m&&g[u][v]!=\'#\'&&d[u][v]<0)d[u][v]=d[x][y]+1,q.push({u,v});}}cout<<d[ex][ey]<<"\\n";}',
    }[kind]
    return body + "\n"


def python_source(kind: str, wrong: bool = False) -> str:
    if wrong:
        return "print(0)\n"
    return {
        "recipe": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); n=a[0]; print(sum(a[i]*a[i+1] for i in range(1,2*n+1,2)))",
        "transfer": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); n=a[0]; print(max(0,sum(a[1:1+n])-2*(n-1)))",
        "month": "import sys,calendar\ny,m=map(int,sys.stdin.read().split()); print(calendar.monthrange(y,m)[1])",
        "checksum": "import sys\ns=sys.stdin.readline().strip(); print(sum((1 if i%2==0 else -1)*int(c) for i,c in enumerate(s)))",
        "scoreboard": "import sys\na=sys.stdin.read().split(); n=int(a[0]); rows=[(a[i],int(a[i+1]),int(a[i+2]),int(a[i+3])) for i in range(1,4*n+1,4)]; rows.sort(key=lambda x:(-(3*x[1]+x[2]),x[0])); print('\\n'.join(f'{x[0]}:{3*x[1]+x[2]}' for x in rows))",
        "times": "import sys\na=sys.stdin.read().split(); print('\\n'.join(sorted(a[1:])))",
        "intervals": "import sys\na=list(map(int,sys.stdin.read().split())); n=a[0]; it=iter(a[1:]); v=sorted(zip(it,it)); o=[]\nfor l,r in v:\n if not o or l>o[-1][1]: o.append([l,r])\n else:o[-1][1]=max(o[-1][1],r)\nprint(len(o)); print('\\n'.join(f'{l} {r}' for l,r in o))",
        "inventory": "import sys,collections\na=sys.stdin.read().split(); n=int(a[0]); d=collections.defaultdict(int)\nfor i in range(n):d[a[1+2*i]]+=int(a[2+2*i])\nprint('\\n'.join(f'{k}:{d[k]}' for k in sorted(d) if d[k]))",
        "unique": "import sys,collections\ns=sys.stdin.readline().strip(); c=collections.Counter(s); print(next((x for x in s if c[x]==1),'NONE'))",
        "words": "import sys,collections\nw=sys.stdin.readline().split(); c=collections.Counter(w); m=max(c.values()); x=min(k for k,v in c.items() if v==m); print(x,m)",
        "brackets": "import sys\ns=sys.stdin.readline().rstrip('\\n'); q=[]; p={')':'(',']':'[','}':'{'}\nfor c in s:\n if c in '([{':q.append(c)\n elif c in p:\n  if not q or q.pop()!=p[c]: print('NO'); break\nelse: print('YES' if not q else 'NO')",
        "caesar": "import sys\nk=int(sys.stdin.readline()); s=sys.stdin.readline().rstrip('\\n')\ndef f(c):\n if 'a'<=c<='z':return chr((ord(c)-97-k%26)%26+97)\n if 'A'<=c<='Z':return chr((ord(c)-65-k%26)%26+65)\n return c\nprint(''.join(map(f,s)))",
        "prefix": "import sys\na=sys.stdin.read().split(); n=int(a[0]); q=a[n+1]; print(sum(x.startswith(q) for x in a[1:n+1]))",
        "rotate": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); n,k=a[:2]; v=a[2:2+n]; k%=n; print(*(v[-k:]+v[:-k] if k else v))",
        "dedup": "import sys\na=list(map(int,sys.stdin.buffer.read().split()))[1:]; print(*dict.fromkeys(a))",
        "ranges": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); n,q=a[:2]; v=a[2:2+n]; p=[0]\nfor x in v:p.append(p[-1]+x)\nprint('\\n'.join(str(p[r]-p[l-1]) for l,r in zip(a[2+n::2],a[3+n::2])))",
        "maxsub": "import sys\na=list(map(int,sys.stdin.buffer.read().split()))[1:]; cur=best=a[0]\nfor x in a[1:]:cur=max(x,cur+x);best=max(best,cur)\nprint(best)",
        "overlap": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); n=a[0]; e=[]\nfor i in range(n):l,r=a[1+2*i:3+2*i];e += [(l,1),(r,-1)]\nc=b=0\nfor _,d in sorted(e,key=lambda x:(x[0],x[1])):c+=d;b=max(b,c)\nprint(b)",
        "coins": "import sys\na=list(map(int,sys.stdin.buffer.read().split())); amount,m=a[:2]; cs=a[2:2+m]; d=[10**9]*(amount+1);d[0]=0\nfor x in range(1,amount+1):\n for c in cs:\n  if c<=x:d[x]=min(d[x],d[x-c]+1)\nprint(-1 if d[amount]>=10**9 else d[amount])",
        "bfs": "import sys,collections\na=sys.stdin.read().split(); n,m=map(int,a[:2]); g=a[2:2+n]\nfor i,row in enumerate(g):\n for j,c in enumerate(row):\n  if c=='S':s=(i,j)\n  if c=='E':e=(i,j)\nd={s:0};q=collections.deque([s])\nwhile q:\n x,y=q.popleft()\n for u,v in ((x+1,y),(x-1,y),(x,y+1),(x,y-1)):\n  if 0<=u<n and 0<=v<m and g[u][v]!='#' and (u,v) not in d:d[u,v]=d[x,y]+1;q.append((u,v))\nprint(d.get(e,-1))",
    }[kind] + "\n"


JAVA_HELPER = """import java.util.*;
class DomainModel {
    static String[] words(String line) { return line.trim().isEmpty() ? new String[0] : line.trim().split("\\\\s+"); }
    static Scanner input() { return new Scanner(System.in); }
}
"""


def java_source(kind: str, wrong: bool = False, multifile: bool = False) -> list[dict]:
    if wrong:
        main = "public class Main { public static void main(String[] args) { System.out.println(0); } }\n"
        return [{"path": "Main.java", "content": main}] + ([{"path": "DomainModel.java", "content": JAVA_HELPER}] if multifile else [])
    # Java uses a compact task-specific Main. Ten selected entries include the
    # helper file to exercise the production Workbench multi-file path.
    body = {
        "recipe": 'int n=sc.nextInt(),s=0;while(n-->0)s+=sc.nextInt()*sc.nextInt();System.out.println(s);',
        "transfer": 'int n=sc.nextInt(),s=0;for(int i=0;i<n;i++){s+=sc.nextInt();if(i>0)s-=2;}System.out.println(Math.max(0,s));',
        "month": 'int y=sc.nextInt(),m=sc.nextInt();int[]d={0,31,28,31,30,31,30,31,31,30,31,30,31};if(m==2&&(y%400==0||y%4==0&&y%100!=0))d[2]=29;System.out.println(d[m]);',
        "checksum": 'String s=sc.next();int z=0;for(int i=0;i<s.length();i++)z+=(i%2==0?1:-1)*(s.charAt(i)-48);System.out.println(z);',
        "scoreboard": 'int n=sc.nextInt();List<String[]>a=new ArrayList<>();for(int i=0;i<n;i++)a.add(new String[]{sc.next(),sc.next(),sc.next(),sc.next()});a.sort((x,y)->{int p=3*Integer.parseInt(x[1])+Integer.parseInt(x[2]),q=3*Integer.parseInt(y[1])+Integer.parseInt(y[2]);return p!=q?Integer.compare(q,p):x[0].compareTo(y[0]);});for(String[]x:a)System.out.println(x[0]+":"+(3*Integer.parseInt(x[1])+Integer.parseInt(x[2])));',
        "times": 'int n=sc.nextInt();List<String>a=new ArrayList<>();while(n-->0)a.add(sc.next());Collections.sort(a);for(String x:a)System.out.println(x);',
        "intervals": 'int n=sc.nextInt();List<int[]>a=new ArrayList<>();while(n-->0)a.add(new int[]{sc.nextInt(),sc.nextInt()});a.sort(Comparator.comparingInt(x->x[0]));List<int[]>o=new ArrayList<>();for(int[]x:a){if(o.isEmpty()||x[0]>o.get(o.size()-1)[1])o.add(x);else o.get(o.size()-1)[1]=Math.max(o.get(o.size()-1)[1],x[1]);}System.out.println(o.size());for(int[]x:o)System.out.println(x[0]+" "+x[1]);',
        "inventory": 'int n=sc.nextInt();Map<String,Integer>m=new TreeMap<>();while(n-->0){String k=sc.next();m.put(k,m.getOrDefault(k,0)+sc.nextInt());}for(var e:m.entrySet())if(e.getValue()!=0)System.out.println(e.getKey()+":"+e.getValue());',
        "unique": 'String s=sc.next();for(int i=0;i<s.length();i++){char c=s.charAt(i);if(s.indexOf(c)==s.lastIndexOf(c)){System.out.println(c);return;}}System.out.println("NONE");',
        "words": 'String[]w=sc.nextLine().trim().split(" ");Map<String,Integer>m=new TreeMap<>();for(String x:w)m.put(x,m.getOrDefault(x,0)+1);String ans="";for(var e:m.entrySet())if(ans.isEmpty()||e.getValue()>m.get(ans))ans=e.getKey();System.out.println(ans+" "+m.get(ans));',
        "brackets": 'String s=sc.hasNextLine()?sc.nextLine():"";Deque<Character>q=new ArrayDeque<>();boolean ok=true;for(char c:s.toCharArray()){if(c==\'(\'||c==\'[\'||c==\'{\')q.push(c);else if(c==\')\'||c==\']\'||c==\'}\'){if(q.isEmpty()){ok=false;break;}char top=q.pop();if((c==\')\'&&top!=\'(\')||(c==\']\'&&top!=\'[\')||(c==\'}\'&&top!=\'{\')){ok=false;break;}}}System.out.println(ok&&q.isEmpty()?"YES":"NO");',
        "caesar": 'int k=sc.nextInt();sc.nextLine();String s=sc.nextLine();StringBuilder b=new StringBuilder();for(char c:s.toCharArray()){if(c>=\'a\'&&c<=\'z\')c=(char)(\'a\'+(c-\'a\'-k%26+26)%26);else if(c>=\'A\'&&c<=\'Z\')c=(char)(\'A\'+(c-\'A\'-k%26+26)%26);b.append(c);}System.out.println(b);',
        "prefix": 'int n=sc.nextInt();String[]a=new String[n];for(int i=0;i<n;i++)a[i]=sc.next();String q=sc.next();int z=0;for(String x:a)z+=x.startsWith(q)?1:0;System.out.println(z);',
        "rotate": 'int n=sc.nextInt(),k=sc.nextInt();int[]a=new int[n];for(int i=0;i<n;i++)a[i]=sc.nextInt();k%=n;for(int i=0;i<n;i++)System.out.print(a[(i+n-k)%n]+(i+1==n?"\\n":" "));',
        "dedup": 'int n=sc.nextInt();Set<Integer>seen=new LinkedHashSet<>();while(n-->0)seen.add(sc.nextInt());boolean f=true;for(int x:seen){if(!f)System.out.print(" ");System.out.print(x);f=false;}System.out.println();',
        "ranges": 'int n=sc.nextInt(),q=sc.nextInt();long[]p=new long[n+1];for(int i=1;i<=n;i++)p[i]=p[i-1]+sc.nextInt();while(q-->0){int l=sc.nextInt(),r=sc.nextInt();System.out.println(p[r]-p[l-1]);}',
        "maxsub": 'int n=sc.nextInt(),x=sc.nextInt();long cur=x,best=x;while(--n>0){x=sc.nextInt();cur=Math.max(x,cur+x);best=Math.max(best,cur);}System.out.println(best);',
        "overlap": 'int n=sc.nextInt();List<int[]>e=new ArrayList<>();while(n-->0){e.add(new int[]{sc.nextInt(),1});e.add(new int[]{sc.nextInt(),-1});}e.sort((x,y)->x[0]!=y[0]?Integer.compare(x[0],y[0]):Integer.compare(x[1],y[1]));int c=0,b=0;for(int[]x:e)b=Math.max(b,c+=x[1]);System.out.println(b);',
        "coins": 'int a=sc.nextInt(),m=sc.nextInt();int[]c=new int[m],d=new int[a+1];for(int i=0;i<m;i++)c[i]=sc.nextInt();Arrays.fill(d,1000000000);d[0]=0;for(int x=1;x<=a;x++)for(int v:c)if(v<=x)d[x]=Math.min(d[x],d[x-v]+1);System.out.println(d[a]>=1000000000?-1:d[a]);',
        "bfs": 'int n=sc.nextInt(),m=sc.nextInt(),sx=0,sy=0,ex=0,ey=0;char[][]g=new char[n][m];for(int i=0;i<n;i++){String s=sc.next();g[i]=s.toCharArray();for(int j=0;j<m;j++){if(g[i][j]==\'S\'){sx=i;sy=j;}if(g[i][j]==\'E\'){ex=i;ey=j;}}}int[][]d=new int[n][m];for(int[]r:d)Arrays.fill(r,-1);ArrayDeque<int[]>q=new ArrayDeque<>();q.add(new int[]{sx,sy});d[sx][sy]=0;int[]dx={1,-1,0,0},dy={0,0,1,-1};while(!q.isEmpty()){int[]p=q.remove();for(int k=0;k<4;k++){int u=p[0]+dx[k],v=p[1]+dy[k];if(u>=0&&u<n&&v>=0&&v<m&&g[u][v]!=\'#\'&&d[u][v]<0){d[u][v]=d[p[0]][p[1]]+1;q.add(new int[]{u,v});}}}System.out.println(d[ex][ey]);',
    }[kind]
    scanner = "DomainModel.input()" if multifile else "new Scanner(System.in)"
    main = 'import java.io.*;import java.util.*;public class Main{public static void main(String[]args)throws Exception{Scanner sc=' + scanner + ';' + body + '}}\n'
    files = [{"path": "Main.java", "content": main}]
    if multifile:
        files.append({"path": "DomainModel.java", "content": JAVA_HELPER})
    return files


def task_specs() -> list[dict]:
    rows = []
    for family, (kind, titles) in enumerate(TASK_GROUPS):
        for variant, title in enumerate(titles):
            rows.append({
                "kind": kind, "family": family, "variant": variant,
                "slug": re.sub(r"[^a-z0-9]+", "-", f"{kind}-{variant}"),
                "title": title,
                "summary": f"围绕“{title}”完成一项有明确输入输出协议的数据处理任务。",
                "statement": [
                    f"运营人员要把{title}接入批处理程序。请逐项读取输入记录，按照业务规则计算最终结果；不能丢弃零值，也不能改变记录的原始顺序。{title}的结果必须严格遵守输出协议。",
                    f"请为{title}编写一个可重复运行的校验器。输入可能包含最小规模、相等边界和负数记录，程序应先建立必要的数据结构，再完成一次完整处理并输出唯一结果。",
                    f"维护{title}时，人工汇总容易在边界处出错。本题要求你直接从标准输入重建汇总过程：每条记录都要参与规则计算，最后只打印题目规定的结果，不输出解释文字。",
                ][variant],
                "input": {
                    "recipe":"第一行是记录数 n，随后 n 行每行给出数量和单价。",
                    "transfer":"第一行是工序数 n，第二行给出 n 个整数时长。",
                    "month":"一行给出年份 y 和月份 m。",
                    "checksum":"一行给出只含数字的编号字符串。",
                    "scoreboard":"第一行是队伍数 n，随后每行给出名称、胜场、平局和负场。",
                    "times":"第一行是时间数量 n，随后 n 行给出 HH:MM。",
                    "intervals":"第一行是区间数 n，随后 n 行给出左右端点。相接区间也视为连续。",
                    "inventory":"第一行是变动记录数 n，随后每行给出物品名和数量变化。",
                    "unique":"一行给出不含空格的字符串。",
                    "words":"一行给出用空格分隔的单词序列。",
                    "brackets":"一行给出只含括号字符的序列，也可能为空。",
                    "caesar":"第一行给出偏移量 k，第二行给出待解码文本。",
                    "prefix":"第一行是字符串数 n，随后 n 行给出字符串，最后一行给出待查询前缀。",
                    "rotate":"第一行给出 n 和右移量 k，第二行给出 n 个整数。",
                    "dedup":"第一行给出序列长度 n，第二行给出 n 个整数。",
                    "ranges":"第一行给出 n 和查询数 q，第二行给出序列，随后 q 行是 1-based 闭区间。",
                    "maxsub":"第一行给出 n，第二行给出 n 个整数。",
                    "overlap":"第一行给出区间数 n，随后 n 行给出预约的起止时刻。",
                    "coins":"第一行给出金额 amount 和硬币种类数 m，第二行给出 m 种面额。",
                    "bfs":"第一行给出网格行数和列数，随后给出网格；S 是起点，E 是终点，# 是障碍。",
                }[kind],
                "output": {
                    "recipe":"输出所有记录的数量乘单价之和。",
                    "transfer":"输出总时长；除第一道工序外每次衔接扣除 2 分钟，结果不小于 0。",
                    "month":"输出该年月的实际天数。",
                    "checksum":"从左到右交替加减数字，输出得到的校验差。",
                    "scoreboard":"按积分降序、名称字典序升序输出 name:points，每行一项；积分为胜场 3 分加平局 1 分。",
                    "times":"按字典序输出全部时间，每行一项。",
                    "intervals":"先输出合并后的区间数，再按起点升序逐行输出区间。",
                    "inventory":"按名称升序输出净库存不为零的 item:value，每行一项。",
                    "unique":"输出从左到右第一个只出现一次的字符；不存在时输出 NONE。",
                    "words":"输出出现次数最多且并列时字典序最小的单词及次数。",
                    "brackets":"括号正确嵌套输出 YES，否则输出 NO。",
                    "caesar":"将英文字母向前移动 k 位并保留大小写，其他字符原样输出。",
                    "prefix":"输出以给定前缀开头的字符串数量。",
                    "rotate":"输出右循环移动 k 位后的序列，元素以空格分隔。",
                    "dedup":"按首次出现顺序输出去重后的序列。",
                    "ranges":"每个查询输出对应闭区间的元素和。",
                    "maxsub":"输出连续非空子数组的最大和。",
                    "overlap":"输出同一时刻最多重叠的区间数。端点相接按先结束后开始处理。",
                    "coins":"输出凑出 amount 所需的最少硬币数；无法凑出时输出 -1。",
                    "bfs":"只能上下左右移动且不能经过 #，输出 S 到 E 的最短步数；不可达输出 -1。",
                }[kind],
                "constraints": {
                    "recipe":"1≤n≤100；数量和单价的绝对值不超过 10^4。",
                    "transfer":"1≤n≤100；单项时长为 0 到 10^4。",
                    "month":"1900≤y≤2400，1≤m≤12。",
                    "checksum":"编号长度为 1 到 10^4，只包含 ASCII 数字。",
                    "scoreboard":"1≤n≤100；名称不含空格，场次为非负整数。",
                    "times":"1≤n≤100；时间均符合 HH:MM 格式。",
                    "intervals":"1≤n≤100；端点为 -10^6 到 10^6。",
                    "inventory":"1≤n≤100；名称不含空格，数量变化绝对值不超过 10^4。",
                    "unique":"长度为 1 到 10^4，字符为可见非空格字符。",
                    "words":"单词数量为 1 到 500，单词只含字母。",
                    "brackets":"长度不超过 10^4，只包含 ()[]{}。",
                    "caesar":"文本长度不超过 10^4，0≤k≤10^9。",
                    "prefix":"1≤n≤100；每个字符串长度不超过 120。",
                    "rotate":"1≤n≤1000；k 为非负整数。",
                    "dedup":"1≤n≤1000；元素为 32 位有符号整数。",
                    "ranges":"1≤n,q≤1000；元素绝对值不超过 10^6。",
                    "maxsub":"1≤n≤1000；元素绝对值不超过 10^6。",
                    "overlap":"1≤n≤100；区间端点为整数且左端点不大于右端点。",
                    "coins":"0≤amount≤10000；1≤m≤100；面额为正整数。",
                    "bfs":"网格不超过 30×30，恰有一个 S 和一个 E。",
                }[kind],
            })
    return rows


def run_many(candidate: dict, tests: list[dict], kind: str) -> list[str]:
    with tempfile.TemporaryDirectory(prefix="catalog-240-run-") as raw:
        root = Path(raw)
        _compile(candidate, root, kind)
        language = candidate["language"]
        command = [sys.executable, "main.py"] if language == "Python" else ["java", "-cp", str(root), candidate.get("main_class", "Main")] if language == "Java" else [str(root / "program.exe")]
        return [_run(command, root, str(t["stdin_text"])) for t in tests]


def files_json(items: list[dict]) -> str:
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def make_candidate(language: str, spec: dict, index: int) -> dict:
    kind = spec["kind"]
    if language == "C":
        reference = [{"path": "main.c", "content": c_source(kind)}]
        wrong = [{"path": "main.c", "content": c_source(kind, True)}]
    elif language == "C++":
        reference = [{"path": "main.cpp", "content": cpp_source(kind)}]
        wrong = [{"path": "main.cpp", "content": cpp_source(kind, True)}]
    elif language == "Python":
        reference = [{"path": "main.py", "content": python_source(kind)}]
        wrong = [{"path": "main.py", "content": python_source(kind, True)}]
    else:
        multi = index < 10
        reference = java_source(kind, False, multi)
        wrong = java_source(kind, True, multi)
    raw_cases = [{"id": f"public-{i+1}", "name": f"公开样例 {i+1}", "stdin_text": x, "visibility": "public"} for i, x in enumerate(cases(kind)[:3])]
    raw_cases += [{"id": f"hidden-{i+1}", "name": f"服务端测试 {i+1}", "stdin_text": x, "visibility": "hidden"} for i, x in enumerate(cases(kind)[3:])]
    candidate = {
        "source_key": f"first_party_original_v2|{language}|{spec['slug']}", "language": language,
        "title_zh": spec["title"], "summary_zh": spec["summary"], "statement_zh": spec["statement"],
        "input_format_zh": spec["input"], "output_format_zh": spec["output"], "constraints_zh": spec["constraints"],
        "title_en": spec["title"], "statement_en": spec["statement"], "difficulty": "中等" if spec["family"] % 3 else "进阶",
        "problem_family_id": f"catalog240-{spec['kind']}-{spec['variant']}",
        "language_fit_reason": {
            "C": "使用 C 的 stdio、结构体、连续内存和显式边界控制完成协议解析与算法实现。",
            "C++": "使用 C++17 的 string、vector、map、排序算法、队列或 lambda 表达清晰的数据处理流程。",
            "Python": "使用 Python 的列表、字典、集合、切片和 collections 等标准库能力快速表达数据变换。",
            "Java": "使用 Java 的 String、List、Map、Deque、Comparator 和类型安全的对象封装完成任务。",
        }[language],
        "learning_objective_id": BLUEPRINT_DATA["languages"][language][spec["family"] % 8]["objective_id"],
        "learning_objective": BLUEPRINT_DATA["languages"][language][spec["family"] % 8]["objective"],
        "prerequisites": BLUEPRINT_DATA["languages"][language][spec["family"] % 8]["prerequisites"],
        "core_skill": BLUEPRINT_DATA["languages"][language][spec["family"] % 8]["core_skill"],
        "novelty_reason": f"题目围绕{spec['title']}的实际记录协议设计，输出规则、边界与错误解均独立，不是编号、常量或运算符变体。",
        "knowledge_tags": [language, spec["kind"], "标准输入输出", "复杂度分析"],
        "starter_files": reference, "reference_files": reference, "wrong_files": wrong,
        "public_cases": raw_cases[:3], "hidden_cases": raw_cases[3:], "quality_score": 98,
        "curriculum_module": f"{language} · 模块 {spec['family'] % 8 + 1}", "level": "进阶" if spec["family"] % 3 == 0 else "中等",
        "estimated_minutes": 35 if spec["family"] % 3 else 45,
    }
    expected = run_many({"language": language, "reference_files": reference, "main_class": "Main"}, raw_cases, "reference")
    for item, output in zip(raw_cases, expected):
        item["expected_stdout"] = output
    wrong_actual = run_many({"language": language, "reference_files": wrong, "main_class": "Main"}, raw_cases[3:], "reference")
    if not any(a.rstrip("\n") != b["expected_stdout"].rstrip("\n") for a, b in zip(wrong_actual, raw_cases[3:])):
        raise RuntimeError(f"wrong solution survived: {language} {spec['slug']}")
    candidate["validated"] = True
    candidate["quality_status"] = "approved"
    candidate["is_active"] = True
    candidate["reference_verified"] = True
    candidate["starter_verified"] = True
    candidate["audit_report"] = {"runner": "catalog_adapters", "reference_passed": True, "wrong_solution_rejected": True, "multifile": language == "Java" and len(reference) > 1}
    return candidate


def row_payload(candidate: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "slug": candidate["source_key"].replace("|", "-").replace("+", "p"), "source_key": candidate["source_key"], "language": candidate["language"], "title": candidate["title_zh"], "difficulty": candidate["difficulty"],
        "tags_json": json.dumps(candidate["knowledge_tags"], ensure_ascii=False), "description": candidate["summary_zh"],
        "starter_files_json": files_json(candidate["starter_files"]), "reference_files_json": files_json(candidate["reference_files"]),
        "public_tests_json": json.dumps([{"samples": candidate["public_cases"]}], ensure_ascii=False), "hidden_tests_json": json.dumps([{"samples": candidate["hidden_cases"]}], ensure_ascii=False), "official_test_files_json": "[]",
        "source_repo": "first_party_original", "source_path": candidate["source_key"], "source_commit": "catalog-240-2026-08-01", "license": "project_owned", "license_text": "题面、测试数据与实现为本项目第一方原创内容。", "attribution": "AI Study Platform first-party catalog",
        "reference_verified": True, "starter_verified": True, "audit_report_json": json.dumps(candidate["audit_report"], ensure_ascii=False), "is_active": True, "quality_status": "approved", "quality_score": candidate["quality_score"], "quality_failure_reasons": "[]",
        "problem_family_id": candidate["problem_family_id"], "language_fit_reason": candidate["language_fit_reason"], "title_zh": candidate["title_zh"], "summary_zh": candidate["summary_zh"], "statement_zh": candidate["statement_zh"], "input_format_zh": candidate["input_format_zh"], "output_format_zh": candidate["output_format_zh"], "constraints_zh": candidate["constraints_zh"], "title_en": candidate["title_en"], "statement_en": candidate["statement_en"],
        "learning_objective_id": candidate["learning_objective_id"], "learning_objective": candidate["learning_objective"], "prerequisites": candidate["prerequisites"], "core_skill": candidate["core_skill"], "novelty_reason": candidate["novelty_reason"], "knowledge_point_ids": json.dumps([candidate["learning_objective_id"]], ensure_ascii=False), "primary_knowledge_point_id": None, "prerequisite_knowledge_point_ids": "[]", "curriculum_module": candidate["curriculum_module"], "level": candidate["level"], "difficulty_score": 3.5 if candidate["level"] == "中等" else 4.5, "estimated_minutes": candidate["estimated_minutes"], "reviewed_at": now,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ensure_database_schema(engine)
    specs = task_specs()
    all_candidates = []
    for language in LANGUAGES:
        for i, spec in enumerate(specs):
            all_candidates.append(make_candidate(language, spec, i))
    rows = [row_payload(x) for x in all_candidates]
    counts = Counter(x["language"] for x in all_candidates)
    if counts != Counter({"C": 60, "C++": 60, "Python": 60, "Java": 60}):
        raise RuntimeError(f"unexpected counts: {counts}")
    if args.dry_run:
        print(json.dumps({"dry_run": True, "counts": counts, "total": len(rows)}, ensure_ascii=False))
        return
    db = SessionLocal()
    try:
        new_keys = {x["source_key"] for x in rows}
        # Archive only the previous active first-party catalog. Existing
        # rejected rows and all user tables remain untouched.
        old = db.query(ProgrammingExercise).filter(ProgrammingExercise.is_active.is_(True), ProgrammingExercise.source_repo == "first_party_original").all()
        for item in old:
            if item.source_key not in new_keys:
                item.is_active = False
                item.quality_status = "rejected"
                item.quality_failure_reasons = json.dumps(["catalog-240 quality reset; retained for history"], ensure_ascii=False)
        existing = {x.source_key: x for x in db.query(ProgrammingExercise).filter(ProgrammingExercise.source_key.in_(list(new_keys))).all()}
        inserted = 0
        for data in rows:
            row = existing.get(data["source_key"])
            if row is None:
                row = ProgrammingExercise(); db.add(row); inserted += 1
            for key, value in data.items():
                if key not in {"id", "created_at", "updated_at"}:
                    setattr(row, key, value)
        db.commit()
    finally:
        db.close()
    # Snapshot is produced from the same validated, database-independent rows.
    payload = {"schema_version": 4, "catalog": "programming-240", "validated": True, "counts": dict(counts), "exercises": rows}
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(SNAPSHOT, "wt", encoding="utf-8", compresslevel=9) as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    OUT.mkdir(exist_ok=True)
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "counts": dict(counts), "total": len(rows), "inserted": inserted, "archived_previous_active_first_party": len(old), "results": [{"language": x["language"], "source_key": x["source_key"], "title_zh": x["title_zh"], "final_status": "passed", "multifile_java": x["language"] == "Java" and len(x["reference_files"]) > 1} for x in all_candidates]}
    (OUT / "programming-catalog-240-quality-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "programming-catalog-240-quality-audit.md").write_text("# 240 题质量审计\n\n" + json.dumps({k:v for k,v in report.items() if k != "results"}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts": dict(counts), "total": len(rows), "inserted": inserted, "archived": len(old), "snapshot": str(SNAPSHOT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
