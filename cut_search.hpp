// Exact one-to-three-operation resynthesis of the exclusive ancestors of one value.
// Other targets and every operand feeding them remain available as possible anchors.
#include <unordered_set>
#include <functional>

struct Arithmetic { Num a, b; char op; };
using Definitions = std::unordered_map<Num,Arithmetic>;
using Values = std::unordered_set<Num>;

template<class F> bool inverse(Num target,Num operand,Num limit,F probe) {
    if(target>operand && probe(target-operand,Arithmetic{operand,target-operand,'+'})) return true;
    if(operand>target && probe(operand-target,Arithmetic{operand,operand-target,'-'})) return true;
    if(target<=limit-operand && probe(target+operand,Arithmetic{target+operand,operand,'-'})) return true;
    if(target%operand==0 && probe(target/operand,Arithmetic{operand,target/operand,'*'})) return true;
    if(operand%target==0 && probe(operand/target,Arithmetic{operand,operand/target,'/'})) return true;
    return target<=limit/operand && probe(target*operand,Arithmetic{target*operand,operand,'/'});
}

struct CutSearch {
    Num limit;
    Values seeds;
    std::vector<Num> roots;
    Definitions graph;
    int depth;

    std::vector<Num> trace(Num stop) const {
        std::vector<Num> order;
        Values seen=seeds;
        std::function<void(Num)> visit=[&](Num v){
            if(!seen.insert(v).second) return;
            if(v!=stop) {
                auto e=graph.at(v);
                visit(e.a); visit(e.b);
            }
            order.push_back(v);
        };
        for(auto r:roots) visit(r);
        return order;
    }
    using Patch = std::vector<std::pair<Num,Arithmetic>>;
    bool synthesize(Num t,const std::vector<Num>& pool,const Values& forbidden,int budget,Patch& out) const {
        Values free(pool.begin(),pool.end());
        Definitions one;
        one.reserve(pool.size()*pool.size()*2);
        std::vector<Num> keys;
        auto add=[&](Num v,Num a,Num b,char op){
            if(!free.count(v) && !forbidden.count(v) && one.emplace(v,Arithmetic{a,b,op}).second)
                keys.push_back(v);
        };
        for(size_t i=0;i<pool.size();++i) for(size_t j=0;j<=i;++j) {
            Num a=pool[i],b=pool[j];
            if(a<=limit-b) add(a+b,a,b,'+');
            if(a<=limit/b) add(a*b,a,b,'*');
            if(a<b) std::swap(a,b);
            if(a>b) add(a-b,a,b,'-');
            if(a%b==0) add(a/b,a,b,'/');
        }
        auto single=one.find(t);
        if(single!=one.end()){out={{t,single->second}};return true;}
        if(budget<2) return false;
        // Split the root into one synthesized operand and one free operand.
        for(Num a:pool) if(inverse(t,a,limit,[&](Num x,Arithmetic root){
            auto it=one.find(x);
            if(it==one.end() || x==t) return false;
            out={{x,it->second},{t,root}};
            return true;
        })) return true;
        if(budget<3) return false;
        // Two independent one-operation branches feeding the root.
        for(Num x:keys) if(inverse(t,x,limit,[&](Num y,Arithmetic root){
            auto it=one.find(y);
            if(it==one.end() || y==t) return false;
            out={{x,one.at(x)}};
            if(y!=x) out.emplace_back(y,it->second);
            out.emplace_back(t,root);
            return true;
        })) return true;
        // Or a three-operation chain.
        for(Num a:pool) if(inverse(t,a,limit,[&](Num y,Arithmetic root){
            if(y==t || forbidden.count(y) || free.count(y)) return false;
            for(Num b:pool) if(inverse(y,b,limit,[&](Num x,Arithmetic mid){
                auto it=one.find(x);
                if(x==y || x==t || it==one.end()) return false;
                out={{x,it->second},{y,mid},{t,root}};
                return true;
            })) return true;
            return false;
        })) return true;
        if(budget<4) return false;
        // Four-operation fork. Add a free operand to a pair of one-step branches.
        // Prefer small pivots: they cover common affine/factor decompositions.
        std::vector<Num> pivots=pool;
        std::sort(pivots.begin(),pivots.end());
        if(pivots.size()>24) pivots.resize(24);
        for(Num a:pivots) if(inverse(t,a,limit,[&](Num z,Arithmetic root){
            if(z==t || forbidden.count(z) || free.count(z)) return false;
            for(Num x:keys) if(x!=z && x!=t && inverse(z,x,limit,[&](Num y,Arithmetic fork){
                auto it=one.find(y);
                if(it==one.end() || y==z || y==t) return false;
                out={{x,one.at(x)}};
                if(y!=x) out.emplace_back(y,it->second);
                out.emplace_back(z,fork);out.emplace_back(t,root);
                return true;
            })) return true;
            return false;
        })) return true;
        return false;
    }
    void run(){
        for(int pass=0;pass<4;++pass) {
            bool changed=false;
            auto live=trace(0);
            for(auto iter=live.rbegin();iter!=live.rend();++iter) {
                Num v=*iter;
                auto active=trace(0);
                if(std::find(active.begin(),active.end(),v)==active.end()) continue;
                auto kept=trace(v);
                int freed=static_cast<int>(active.size()-kept.size());
                if(freed<2) continue; // One-step rewrites already searched on the union graph.
                Values depends{v};
                std::vector<Num> pool(seeds.begin(),seeds.end());
                std::sort(pool.begin(),pool.end());
                for(Num x:kept) {
                    if(x==v) continue;
                    auto e=graph.at(x);
                    if(depends.count(e.a)||depends.count(e.b)) depends.insert(x);
                    else pool.push_back(x);
                }
                depends.erase(v); // Root may be produced at the last step.
                Patch patch;
                if(synthesize(v,pool,depends,std::min(freed,depth),patch)){
                    for(auto [x,e]:patch) graph[x]=e;
                    changed=true;
                }
            }
            if(!changed) break;
        }
    }
};
