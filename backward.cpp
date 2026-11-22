// Construct fresh programs by searching backward from targets into a forward
// dictionary of reachable values. No external program is read by this solver.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <functional>
#include <iostream>
#include <limits>
#include <unordered_map>
#include <unordered_set>
#include <vector>
using Num=int64_t;
#include "cut_search.hpp"

using Step=std::pair<Num,Arithmetic>;
using Plan=std::vector<Step>;
struct DictionarySolver {
    Num limit;
    int radix,width;
    std::vector<Num> seeds,targets,history,constants;
    Values known;
    Plan program;

    void append(Num v,Arithmetic e) {
        if(known.insert(v).second){program.emplace_back(v,e);history.push_back(v);}
    }
    void basic(Num v) {
        if(known.count(v)) return;
        if(v==1){append(1,{seeds.front(),seeds.front(),'/'});return;}
        if(v<=radix){
            basic(v/2);append(v/2*2,{v/2,v/2,'+'});
            if(v%2){basic(1);append(v,{v-1,1,'+'});}
            return;
        }
        Num q=v/radix,r=v%radix;
        if(2*r>radix && q+1<=limit/radix){++q;r-=radix;}
        basic(q);basic(radix);append(q*radix,{q,radix,'*'});
        if(r){basic(std::abs(r));append(v,{q*radix,std::abs(r),r>0?'+':'-'});}
    }
    Plan fallback(Num v) {
        size_t before=program.size(), h=history.size();
        basic(v);
        Plan path(program.begin()+before,program.end());
        for(auto& [x,e]:path) known.erase(x);
        program.resize(before);history.resize(h);
        return path;
    }
    std::vector<Num> pool() const {
        std::vector<Num> p;
        Values seen;
        auto add=[&](Num x){if(seen.insert(x).second) p.push_back(x);};
        for(Num x:seeds) add(x);
        for(Num x:constants) add(x);
        for(auto i=history.rbegin();i!=history.rend() && p.size()<64;++i) add(*i);
        return p;
    }

    struct Table {
        const DictionarySolver& s;
        std::vector<Num> pivots, keys;
        Definitions one;
        explicit Table(const DictionarySolver& solver):s(solver),pivots(s.pool()) {
            auto add=[&](Num v,Arithmetic e){if(!s.known.count(v))one.emplace(v,e);};
            for(size_t i=0;i<pivots.size();++i) for(size_t j=0;j<=i;++j){
                Num a=pivots[i],b=pivots[j];
                if(a<=s.limit-b) add(a+b,{a,b,'+'});
                if(a<=s.limit/b) add(a*b,{a,b,'*'});
                if(a<b)std::swap(a,b);
                if(a>b)add(a-b,{a,b,'-'});
                if(a%b==0)add(a/b,{a,b,'/'});
            }
            for(auto& kv:one) keys.push_back(kv.first);
            for(Num x:s.known) keys.push_back(x);
            std::sort(keys.begin(),keys.end());
        }
        bool direct(Num v,Plan& p) const {
            if(s.known.count(v))return true;
            auto it=one.find(v);
            if(it==one.end())return false;
            p.emplace_back(v,it->second);return true;
        }
        bool two(Num v,Plan& p) const {
            if(direct(v,p))return true;
            for(Num a:pivots) if(inverse(v,a,s.limit,[&](Num x,Arithmetic e){
                if(x==v || !direct(x,p))return false;
                p.emplace_back(v,e);return true;
            }))return true;
            return false;
        }
        bool fork(Num v,Plan& p) const {
            for(Num a:keys) if(inverse(v,a,s.limit,[&](Num x,Arithmetic e){
                if(x==v || a==v || (!s.known.count(x) && !one.count(x)))return false;
                direct(a,p);if(x!=a)direct(x,p);p.emplace_back(v,e);return true;
            }))return true;
            return false;
        }
        double rank(Num v) const {
            auto it=std::lower_bound(keys.begin(),keys.end(),v);
            Num d=v;
            if(it!=keys.end()) d=std::min(d,*it-v);
            if(it!=keys.begin())d=std::min(d,v-*std::prev(it));
            if(!d)return -1;
            int trailing=__builtin_ctzll(static_cast<unsigned long long>(v));
            return std::min(std::log2(1.0+d)+2.0, std::log2(1.0+v)-0.82*trailing);
        }
    };
    struct State {Num v; int parent; Arithmetic e;};
    Plan backwards(Num t,const Table& table){
        Plan best=fallback(t),path;
        if(table.fork(t,path) && path.size()<best.size())best=path;
        std::vector<State> states{{t,-1,{0,0,'+'}}};
        std::vector<int> frontier{0};
        Values seen{t};
        for(int level=0;level<8 && level+1<(int)best.size();++level){
            std::vector<std::pair<double,int>> candidates;
            for(int idx:frontier){
                Num v=states[idx].v;
                Plan tail;
                bool hit=table.two(v,tail);
                if(!hit && level>0 && idx==frontier.front() && level+3<(int)best.size())
                    hit=table.fork(v,tail);
                if(!hit)tail=fallback(v);
                if(tail.size()+level<best.size()){
                    for(int j=idx;states[j].parent>=0;j=states[j].parent)
                        tail.emplace_back(states[states[j].parent].v,states[j].e);
                    best=std::move(tail);
                }
                if(level+2>=(int)best.size())continue;
                for(Num a:table.pivots) inverse(v,a,limit,[&](Num x,Arithmetic e){
                    if(seen.insert(x).second){
                        candidates.emplace_back(table.rank(x),states.size());
                        states.push_back({x,idx,e});
                    }
                    return false;
                });
            }
            size_t keep=std::min<size_t>(width,candidates.size());
            std::partial_sort(candidates.begin(),candidates.begin()+keep,candidates.end());
            frontier.clear();
            for(size_t i=0;i<keep;++i)frontier.push_back(candidates[i].second);
        }
        return best;
    }
    void run(){
        known.insert(seeds.begin(),seeds.end());
        for(Num x:{1,2,3,4,5,7,8,9,15,16,31,32,63,64,127,128,255,256,1024,4096,65536})
            if(x<=limit){basic(x);constants.push_back(x);}
        std::vector<Num> pending=targets;
        while(true){
            pending.erase(std::remove_if(pending.begin(),pending.end(),[&](Num v){return known.count(v);}),pending.end());
            if(pending.empty())return;
            Table table(*this);
            Plan best;
            Num next=0;
            double lowest=std::numeric_limits<double>::infinity();
            for(Num t:pending){
                Plan candidate;
                if(table.two(t,candidate) && (best.empty() || candidate.size()<best.size()))
                    best=std::move(candidate);
                double h=table.rank(t);
                if(h<lowest){next=t;lowest=h;}
            }
            if(best.empty())best=backwards(next,table);
            for(auto [v,e]:best)append(v,e);
        }
    }
};
int main(){
    DictionarySolver solver;
    int n,m;
    if(!(std::cin>>solver.limit>>n>>m>>solver.radix>>solver.width))return 1;
    for(int i=0;i<n;++i){Num x;std::cin>>x;solver.seeds.push_back(x);}
    for(int i=0;i<m;++i){Num x;std::cin>>x;solver.targets.push_back(x);}
    solver.run();
    for(auto [x,e]:solver.program)std::cout<<x<<' '<<e.a<<' '<<e.op<<' '<<e.b<<'\n';
}
