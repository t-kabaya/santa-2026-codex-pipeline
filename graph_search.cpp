// Search exact integer expression graphs assembled from alternative legal programs.
#include <algorithm>
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <random>
#include <unordered_map>
#include <vector>

using Num = int64_t;
struct Recipe {
    int a, b;
    char op;
    bool operator==(const Recipe& r) const { return a==r.a && b==r.b && op==r.op; }
};
using Source = std::vector<std::pair<int,int>>;
struct Graph {
    std::vector<Num> val;
    std::unordered_map<Num,int> index;
    std::vector<std::vector<Recipe>> edges;
    std::vector<int> seeds, targets;
    std::vector<Source> sources;
    Num limit;

    int node(Num x) {
        auto [it,fresh]=index.emplace(x, val.size());
        if (fresh) { val.push_back(x); edges.emplace_back(); }
        return it->second;
    }
    int add(int dst, Recipe e) {
        if (dst==e.a || dst==e.b) return -1;
        if ((e.op=='+' || e.op=='*') && e.a>e.b) std::swap(e.a,e.b);
        auto& options=edges[dst];
        auto it=std::find(options.begin(), options.end(),e);
        if (it!=options.end()) return static_cast<int>(it-options.begin());
        options.push_back(e);
        return static_cast<int>(options.size())-1;
    }
    template<class F> void pairs(int a,int b,F consume) const {
        Num x=val[a],y=val[b];
        if(x<=limit-y) consume(x+y,Recipe{a,b,'+'});
        if(x<=limit/y) consume(x*y,Recipe{a,b,'*'});
        if(x<y) { std::swap(x,y); std::swap(a,b); }
        if(x>y) consume(x-y,Recipe{a,b,'-'});
        if(x%y==0) consume(x/y,Recipe{a,b,'/'});
    }
    void extend(bool bridges) {
        for (int i=1;i<=std::min<Num>(limit,64);++i) node(i);
        int core=val.size();
        for(int a=0;a<core;++a) for(int b=0;b<=a;++b) pairs(a,b,[&](Num x, Recipe e){
            auto it=index.find(x);
            if(it!=index.end()) add(it->second,e);
        });
        if (!bridges || sources.empty()) return;
        std::vector<int> pool=seeds;
        for(auto [v,k]:sources.front()) pool.push_back(v);
        std::sort(pool.begin(),pool.end());
        pool.erase(std::unique(pool.begin(),pool.end()),pool.end());
        std::unordered_map<Num,Recipe> one;
        for(int a:pool) for(int b:pool) if(b<=a) pairs(a,b,[&](Num x, Recipe e){
            if(index.find(x)==index.end()) one.emplace(x,e);
        });
        for(int t=0;t<core;++t) {
            Num v=val[t];
            if(v<=64) continue;
            int accepted=0;
            for(int a:pool) {
                if(a==t) continue;
                Num q=val[a];
                auto link=[&](Num missing,char op,bool first) {
                    if(accepted>=24 || missing<=0) return;
                    auto it=one.find(missing);
                    if(it==one.end()) return;
                    auto e=it->second;
                    if(e.a==t || e.b==t || e.a==a || e.b==a) return;
                    int m=node(missing);
                    add(m,e);
                    add(t,first ? Recipe{m,a,op}:Recipe{a,m,op});
                    ++accepted;
                };
                if(v>q) link(v-q,'+',true);
                if(q>v) link(q-v,'-',false);
                if(v<=limit-q) link(v+q,'-',true);
                if(v%q==0) link(v/q,'*',true);
                if(q%v==0) link(q/v,'/',false);
                if(v<=limit/q) link(v*q,'/',true);
            }
        }
    }
};

struct Search {
    Graph& g;
    std::mt19937 rng;
    std::vector<int> pick, initial;
    std::vector<char> seed;
    std::vector<int> best_order, best_pick;
    int best=100000;
    explicit Search(Graph& graph,unsigned key):g(graph),rng(key),seed(g.val.size(),false) {
        for(auto s:g.seeds) seed[s]=true;
        initial.assign(seed.size(),-1);
        estimate(initial,std::vector<char>(seed.size(),false));
    }
    // Select cheap derivations for dormant values. Live values have zero cost.
    void estimate(std::vector<int>& recipes,const std::vector<char>& live) {
        const int infinity=5000;
        std::vector<int> d(seed.size(),infinity);
        for(size_t i=0;i<d.size();++i) if(seed[i]||live[i]) d[i]=0;
        for(int pass=0;pass<32;++pass) {
            bool changed=false;
            for(int i=0;i<(int)d.size();++i) {
                if(!d[i]) continue;
                for(int j=0;j<(int)g.edges[i].size();++j) {
                    const auto& e=g.edges[i][j];
                    int cost=1+d[e.a]+(e.a==e.b?0:d[e.b]);
                    if(cost<d[i]) { d[i]=cost; recipes[i]=j; changed=true; }
                }
            }
            if(!changed) break;
        }
    }
    void visit(int v,int blocked,std::vector<char>& mark,std::vector<int>& order) const {
        if(seed[v] || mark[v]) return;
        mark[v]=1;
        if(v!=blocked) {
            auto e=g.edges[v][pick[v]];
            visit(e.a,blocked,mark,order);
            visit(e.b,blocked,mark,order);
        }
        order.push_back(v);
    }
    std::vector<int> trace(int blocked,std::vector<char>& mark) const {
        std::vector<int> order;
        for(int t:g.targets) visit(t,blocked,mark,order);
        return order;
    }
    // Price a replacement against all values still required by the other targets.
    // Nodes depending on the edited value are forbidden to preserve acyclicity.
    int extra(int v,const std::vector<char>& kept,const std::vector<char>& forbidden,
              std::vector<unsigned>& stamp,unsigned tag,int budget) const {
        if(forbidden[v]) return 100000;
        if(seed[v] || kept[v] || stamp[v]==tag) return 0;
        if(budget<=0 || pick[v]<0) return 100000;
        stamp[v]=tag;
        const auto e=g.edges[v][pick[v]];
        int a=extra(e.a,kept,forbidden,stamp,tag,budget-1);
        if(a>=budget) return 100000;
        return 1+a+extra(e.b,kept,forbidden,stamp,tag,budget-1-a);
    }
    void save(const std::vector<int>& order) {
        if((int)order.size()<best) { best=order.size(); best_pick=pick; best_order=order; }
    }
    void optimize(const Source& source,int plateau) {
        pick=initial;
        for(auto [v,j]:source) pick[v]=j;
        std::vector<unsigned> stamp(seed.size());
        unsigned tag=0;
        for(int pass=0;pass<9;++pass) {
            std::vector<char> live(seed.size());
            auto order=trace(-1,live);
            save(order);
            estimate(pick,live);
            std::shuffle(order.begin(),order.end(),rng);
            bool any=false;
            int current=order.size();
            for(int v:order) {
                if(!live[v] || g.edges[v].size()<2) continue;
                std::vector<char> kept(seed.size()),bad(seed.size());
                auto remaining=trace(v,kept);
                int freed=current-static_cast<int>(remaining.size());
                if(freed==0 && !plateau) continue;
                bad[v]=1;
                for(int x:remaining) {
                    if(x==v) continue;
                    auto e=g.edges[x][pick[x]];
                    bad[x]=bad[e.a]||bad[e.b];
                }
                int win=freed, which=pick[v];
                for(int j=0;j<(int)g.edges[v].size();++j) {
                    if(j==pick[v]) continue;
                    auto e=g.edges[v][j];
                    ++tag;
                    int a=extra(e.a,kept,bad,stamp,tag,win);
                    if(a>win) continue;
                    int cost=a+extra(e.b,kept,bad,stamp,tag,win-a);
                    if(cost<win || (plateau && cost==win && rng()%12==0)) {
                        win=cost; which=j;
                    }
                }
                if(which!=pick[v]) {
                    pick[v]=which;
                    std::fill(live.begin(),live.end(),0);
                    auto updated=trace(-1,live);
                    current=updated.size();
                    save(updated);
                    any=true;
                }
            }
            if(!any) break;
        }
    }
};
#include "cut_search.hpp"

int main() {
    std::ios::sync_with_stdio(false);
    Graph g;
    int n,m,k,bridges,rounds,depth;
    unsigned random_seed;
    if(!(std::cin>>g.limit>>n>>m>>k>>bridges>>rounds>>depth>>random_seed)) return 1;
    for(int j=0;j<n;++j){Num x;std::cin>>x;g.seeds.push_back(g.node(x));}
    for(int j=0;j<m;++j){Num x;std::cin>>x;g.targets.push_back(g.node(x));}
    for(int s=0;s<k;++s){
        int size;std::cin>>size;
        Source source;
        for(int j=0;j<size;++j){
            Num x,y,t;char op;std::cin>>t>>x>>op>>y;
            int dst=g.node(t),a=g.node(x),b=g.node(y);
            int edge=g.add(dst,{a,b,op});
            if(edge>=0) source.emplace_back(dst,edge);
        }
        g.sources.push_back(std::move(source));
    }
    g.extend(bridges);
    Search search(g,random_seed);
    for(auto& s:g.sources) search.optimize(s,0);
    for(int r=0;r<rounds;++r) {
        Source incumbent;
        for(int v:search.best_order) incumbent.emplace_back(v,search.best_pick[v]);
        search.optimize(incumbent,1);
    }
    CutSearch cut{g.limit,{},{},{},depth};
    for(int v:g.seeds) cut.seeds.insert(g.val[v]);
    for(int v:g.targets) cut.roots.push_back(g.val[v]);
    for(int v:search.best_order) {
        auto e=g.edges[v][search.best_pick[v]];
        cut.graph[g.val[v]]={g.val[e.a],g.val[e.b],e.op};
    }
    if(depth>0) cut.run();
    for(Num v:cut.trace(0)) {
        auto e=cut.graph.at(v);
        std::cout<<v<<' '<<e.a<<' '<<e.op<<' '<<e.b<<'\n';
    }
}
