// Macro-level successor generator for Heroes of Sokoban III on the team's native engine.
// A macro = switch to hero h (A presses) + shortest pure walk + one key that changes
// something other than h's own position ("effect"), or a pure walk to a "relevant" cell.
#pragma once
#include "../macro_scheduler/native_engine.hpp"
#include <memory>

struct Macro { DynState s; int cost; string keys; int hero; bool effect; };

inline int active_idx(const LevelMeta& M, const DynState& s){ for(int i=0;i<M.n;i++) if(is_act(s.obj[i])) return i; return -1; }
inline int hero_idx(const LevelMeta& M, const DynState& s, int h){ for(int i=0;i<M.n;i++) if(s.obj[i]==h || s.obj[i]==h+6) return i; return -1; }

// pure step: only the active hero moved by one cell
inline bool pure_change(const LevelMeta& M, const DynState& a, const DynState& b, int from, int to){
  for(int i=0;i<M.n;i++){
    if(i==from||i==to) continue;
    if(a.obj[i]!=b.obj[i]) return false;
  }
  return a.obj[from]==b.obj[to] && b.obj[from]==0 && a.obj[to]==0;
}

struct RelevanceFn { // which pure-walk endpoints become successors
  virtual bool operator()(const LevelMeta& M, const DynState& s, int hero, int cell) const = 0;
  virtual ~RelevanceFn(){}
};

// Generate all macros from s. heroes_mask selects heroes allowed to act (bit h-1).
inline void gen_macros(const LevelMeta& M, const DynState& s0, int heroes_mask, const RelevanceFn* rel, vector<Macro>& out){
  int ai = active_idx(M,s0); if(ai<0) return;
  int ah = s0.obj[ai];
  DynState cur = s0; string sw;
  for(int k=0;k<6;k++){
    int a = active_idx(M,cur); int h = cur.obj[a];
    if(k>0 && h==ah) break;
    if(heroes_mask & (1<<(h-1))){
      // BFS pure walk
      static thread_local vector<int> par; static thread_local vector<char> pk; static thread_local vector<DynState> st;
      par.assign(M.n,-2); pk.assign(M.n,0); st.resize(M.n);
      vector<int> q; q.reserve(M.n); q.push_back(a); par[a]=-1; st[a]=cur;
      for(size_t qi=0;qi<q.size();qi++){
        int c=q[qi]; const DynState& cs=st[c];
        auto path=[&](int x){ string p; while(par[x]>=0){ p.push_back(pk[x]); x=par[x]; } reverse(p.begin(),p.end()); return p; };
        for(int d=0;d<4;d++){
          DynState ns=cs; int r=step_state(M,ns,d,true);
          if(r<0) continue;
          int na=active_idx(M,ns);
          int nx=c%M.w+DX[d], ny=c/M.w+DY[d], expect=ny*M.w+nx;
          if(na==expect && pure_change(M,cs,ns,c,na)){
            if(par[na]==-2){ par[na]=c; pk[na]=DCH[d]; st[na]=ns; q.push_back(na);
              if(rel && (*rel)(M,ns,h,na)) out.push_back({ns,(int)sw.size()+(int)path(na).size(),sw+path(na),h,false}); }
          } else {
            out.push_back({ns,(int)sw.size()+(int)path(c).size()+1,sw+path(c)+DCH[d],h,true});
          }
        }
      }
    }
    DynState ns=cur; int r=step_state(M,ns,4,true); if(r<0) break; cur=ns; sw.push_back('A');
  }
}
