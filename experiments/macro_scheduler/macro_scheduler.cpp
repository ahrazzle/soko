#include "native_engine.hpp"
#include <fstream>
#include <sstream>
#include <cassert>
#include <sys/resource.h>

// Full-state FIFO macro scheduling, with collision-safe exact deduplication.
// Input: part width height max_cost seconds memory_MiB, grid rows, route.
// A macro is one maximal directional run by one hero in the reference route.
// Only macro order changes; each hero's own macro order remains fixed.

uint64_t fold(uint64_t acc,const LevelMeta&M,const DynState&s){
 for(int i=0;i<M.n;i++){uint8_t b=(s.obj[i]&31)|(s.has_n(i)?32:0);acc=(acc^b)*1099511628211ULL;}
 acc=(acc^(s.y_op|(s.p_op<<1)))*1099511628211ULL;
 return (acc^255)*1099511628211ULL;
}
int active(const LevelMeta&M,const DynState&s){for(int i=0;i<M.n;i++)if(is_act(s.obj[i]))return s.obj[i]-1;return -1;}
string key(const LevelMeta&M,const DynState&s,uint32_t progress,int actions=-1){
 string out;out.reserve(4+M.n+(M.n+7)/8+2);
 for(int j=0;j<4;j++)out.push_back((progress>>(j*8))&255);
 out.append((const char*)s.obj,M.n);
 out.append((const char*)s.notes,((M.n+63)/64)*8);
 out.push_back(s.y_op);out.push_back(s.p_op);if(actions>=0)out.push_back(actions);return out;
}
struct Node{DynState s;uint32_t progress,parent;uint16_t cost;uint8_t hero,switches,actions;};
int main(int argc,char**argv){
 int part,w,h,bound,seconds,memory;cin>>part>>w>>h>>bound>>seconds>>memory;
 struct rlimit memory_limit{(rlim_t)memory*1024*1024,(rlim_t)memory*1024*1024};
 if(setrlimit(RLIMIT_AS,&memory_limit)){cerr<<"setrlimit failed"<<endl;return 2;}
 string dummy,route;getline(cin,dummy);vector<string>rows(h);for(auto&r:rows)getline(cin,r);getline(cin,route);
 auto[M,initial]=parse_lv(part,w,h,rows);auto began=chrono::steady_clock::now();
 auto elapsed=[&](){return chrono::duration<double>(chrono::steady_clock::now()-began).count();};
 auto rss=[](){struct rusage r;getrusage(RUSAGE_SELF,&r);return r.ru_maxrss;};
 bool calibrate=false,omit_noops=false,control_only=false,goal_directed=false,priority_self_test=false;int action_cap=-1;
 for(int i=1;i<argc;i++){string arg=argv[i];if(arg=="--calibrate")calibrate=true;else if(arg=="--omit-noops")omit_noops=true;else if(arg=="--control-only")control_only=true;else if(arg=="--goal-directed")goal_directed=true;else if(arg=="--priority-self-test")priority_self_test=true;else if(arg=="--action-cap"&&i+1<argc)action_cap=stoi(argv[++i]);else{cerr<<"unknown argument"<<endl;return 2;}}
 vector<string> runs[6];vector<pair<int,string>> order;
 auto st=initial;uint64_t digest=fold(14695981039346656037ULL,M,st);
 if(calibrate)cout<<"{\"step\":0,\"digest\":"<<digest<<",\"won\":"<<(check_win(M,st)?"true":"false")<<"}"<<endl;
 string current;int owner=-1;bool baseline_win=false;
 for(size_t t=0;t<route.size();t++){
  char ch=route[t];int a=active(M,st);
  if(ch=='A'&&!current.empty()){runs[owner].push_back(current);order.push_back({owner,current});current.clear();}
  if(ch!='A'){if(current.empty())owner=a;else if(owner!=a){cerr<<"active role changed inside directional run"<<endl;return 3;}current+=ch;}
  int result=step_state(M,st,d_idx(ch),false);digest=fold(digest,M,st);
  if(calibrate)cout<<"{\"step\":"<<t+1<<",\"digest\":"<<digest<<",\"alive\":"<<(result>=0?"true":"false")<<",\"won\":"<<(result==1?"true":"false")<<"}"<<endl;
  if(result<0||((result==1)!=(t+1==route.size()))){cerr<<"invalid baseline at "<<t+1<<endl;return 4;}
  baseline_win=result==1;
 }
 if(!current.empty()){runs[owner].push_back(current);order.push_back({owner,current});}
 if(!baseline_win)return 5;
 if(calibrate)return 0;
 int total_dirs=0,total_macros=0;uint32_t strides[6];uint32_t combinations=1;
 for(int hero=0;hero<6;hero++){strides[hero]=combinations;combinations*=runs[hero].size()+1;total_macros+=runs[hero].size();for(auto&r:runs[hero])total_dirs+=r.size();}
 auto direction_cost=[&](uint32_t progress){int count=0;for(int hero=0;hero<6;hero++){int done=(progress/strides[hero])%(runs[hero].size()+1);for(int j=0;j<done;j++)count+=runs[hero][j].size();}return count;};
 int switch_bound=bound-total_dirs;
 if(omit_noops)switch_bound=action_cap>=0?action_cap:count(route.begin(),route.end(),'A');
 if(switch_bound>255||switch_bound<0){cerr<<"invalid Action cap"<<endl;return 2;}
 auto priority_for=[&](int actual_cost,uint32_t progress){return goal_directed?actual_cost+total_dirs-direction_cost(progress):(omit_noops?actual_cost:actual_cost-direction_cost(progress));};
 auto within_budget=[&](int actual_cost,int actions){return actual_cost<=bound&&actions<=switch_bound;};
 cerr<<"{\"inventory\":[";for(int hero=0;hero<6;hero++){if(hero)cerr<<",";cerr<<runs[hero].size();}cerr<<"],\"macros\":"<<total_macros<<",\"directions\":"<<total_dirs<<",\"progress_combinations\":"<<combinations<<"}"<<endl;
 // Execute the actual rule transition first. An omitted key is sound only if
 // *every* state component is unchanged; merely blocked hero movement is not enough.
 auto apply_macro=[&](DynState&s,int hero,const string&macro,string&emitted,int&switches){
  switches=0;
  while(active(M,s)!=hero&&switches<6){auto before=s;int r=step_state(M,s,4,false);switches++;if(r<0)return -1;if(!omit_noops||!s.eq(before,M.n,M.has_bard))emitted+='A';if(r==1)return 1;}
  if(active(M,s)!=hero)return -1;
  for(char ch:macro){auto before=s;int r=step_state(M,s,d_idx(ch),false);if(r<0)return -1;if(!omit_noops||!s.eq(before,M.n,M.has_bard))emitted+=ch;if(r==1)return 1;}
  return 0;
 };
 // Positive control: the baseline macro order, normalized under this objective.
 auto control=initial;string control_route;int control_steps=0;
 for(auto&[hero,macro]:order){
  int switches=0;if(apply_macro(control,hero,macro,control_route,switches)<0){cerr<<"baseline macro failed"<<endl;return 6;}
 }
 if(!check_win(M,control)){cerr<<"baseline macro control failed"<<endl;return 9;}
 cerr<<"{\"baseline_macro_control\":\"passed\",\"length\":"<<control_route.size()<<",\"identical_to_reference\":"<<(control_route==route?"true":"false")<<",\"omit_noops\":"<<(omit_noops?"true":"false")<<"}"<<endl;
 if(priority_self_test){
  assert(goal_directed&&omit_noops);
  // A queue score above the input bound must still be retained. The same
  // predicate is used on every real generated successor below.
  assert(priority_for(bound-1,0)>bound&&within_budget(bound-1,switch_bound));
  assert(!within_budget(bound+1,switch_bound)&&!within_budget(bound,switch_bound+1));
  priority_queue<int,vector<int>,greater<int>> test;
  int old_g=bound-1,new_g=bound-2;test.push(priority_for(old_g,0));test.push(priority_for(new_g,0));
  assert(test.top()==priority_for(new_g,0));test.pop();assert(test.top()!=priority_for(new_g,0));
  cout<<"{\"status\":\"priority_unit_passed\",\"score_above_bound_retained\":true,\"lower_g_reopens\":true,\"stale_higher_g_discarded\":true,\"first_goal_optimality_claim\":false}"<<endl;return 0;
 }
 if(control_only){cout<<"{\"status\":\"baseline_control_passed\",\"length\":"<<control_route.size()<<",\"identical_to_reference\":"<<(control_route==route?"true":"false")<<",\"route\":\""<<control_route<<"\"}"<<endl;return 0;}
 if(control_route.size()<=bound){cout<<"{\"candidate\":\""<<control_route<<"\",\"length\":"<<control_route.size()<<",\"kind\":\"minimal-switch baseline macro order\"}"<<endl;return 0;}
 auto limit=memory*1024L;vector<Node> nodes;nodes.reserve(200000);
 unordered_map<string,uint32_t> seen;seen.reserve(250000);
 using Item=pair<int,uint32_t>;priority_queue<Item,vector<Item>,greater<Item>> queue;
 nodes.push_back({initial,0,UINT32_MAX,0,255,0,0});seen.emplace(key(M,initial,0,omit_noops?0:-1),0);queue.push({priority_for(0,0),0});
 uint64_t expanded=0,generated=0,dead=0,pruned=0,omitted=0;int last_report=0,max_cost=0;
 auto reconstruct=[&](uint32_t index){vector<string> pieces;while(nodes[index].parent!=UINT32_MAX){const auto&n=nodes[index];const auto&p=nodes[n.parent];int done=(p.progress/strides[n.hero])%(runs[n.hero].size()+1);auto replay=p.s;string edge;int switches=0;if(apply_macro(replay,n.hero,runs[n.hero][done],edge,switches)<0||!replay.eq(n.s,M.n,M.has_bard))throw runtime_error("parent edge reconstruction diverged");pieces.push_back(edge);index=n.parent;}string path;for(auto i=pieces.rbegin();i!=pieces.rend();i++)path+=*i;return path;};
 auto finish=[&](const string&status){cout<<"{\"status\":\""<<status<<"\",\"objective\":\""<<(omit_noops?"emitted inputs with full-state noops omitted":"Action count with fixed directional inventory")<<"\",\"queue_priority\":\""<<(goal_directed?"g plus remaining literal keys (ordering only)":"objective cost")<<"\",\"first_goal_optimality_claim\":false,\"action_cap\":"<<switch_bound<<",\"expanded\":"<<expanded<<",\"generated\":"<<generated<<",\"states\":"<<nodes.size()<<",\"queue\":"<<queue.size()<<",\"max_popped_cost\":"<<max_cost<<",\"dead_macros\":"<<dead<<",\"bound_pruned\":"<<pruned<<",\"omitted_inputs_seen\":"<<omitted<<",\"elapsed_seconds\":"<<elapsed()<<",\"peak_rss_kib\":"<<rss()<<",\"original_optimality_claim\":false}"<<endl;};
 try{
  while(!queue.empty()){
   if(elapsed()>seconds){finish("time_limit");return 0;}
   if(rss()>limit-65536){finish("memory_limit");return 0;}
   auto[priority,index]=queue.top();queue.pop();int cost=nodes[index].cost;
   if(priority_for(cost,nodes[index].progress)!=priority)continue;
   Node cur=nodes[index];expanded++;max_cost=max(max_cost,cost);
   if((int)elapsed()>=last_report+5){last_report=elapsed();cerr<<"{\"expanded\":"<<expanded<<",\"states\":"<<nodes.size()<<",\"queue\":"<<queue.size()<<",\"cost\":"<<cost<<",\"elapsed\":"<<elapsed()<<",\"rss_kib\":"<<rss()<<"}"<<endl;}
   for(int hero=0;hero<6;hero++){
    int done=(cur.progress/strides[hero])%(runs[hero].size()+1);if(done==(int)runs[hero].size())continue;
    const auto&macro=runs[hero][done];auto next=cur.s;string edge;int switches=0;
    int result=apply_macro(next,hero,macro,edge,switches);int next_actions=cur.actions+switches;
    if(result<0){dead++;continue;}
    if(!within_budget(cost+edge.size(),next_actions)){pruned++;continue;}
    if(result==1){string candidate=reconstruct(index)+edge;cout<<"{\"candidate\":\""<<candidate<<"\",\"length\":"<<candidate.size()<<",\"actions\":"<<next_actions<<",\"expanded\":"<<expanded<<",\"elapsed_seconds\":"<<elapsed()<<",\"original_optimality_claim\":false}"<<endl;return 0;}
    omitted+=macro.size()+switches-edge.size();
    generated++;uint32_t progress=cur.progress+strides[hero];uint16_t nc=cost+edge.size();string encoded=key(M,next,progress,omit_noops?next_actions:-1);auto found=seen.find(encoded);
    // Priority is never a bound. In particular remaining literal keys can be
    // omitted later, so a large priority cannot justify discarding this state.
    int next_priority=priority_for(nc,progress);
    if(found!=seen.end()){
     uint32_t old=found->second;if(nodes[old].cost<=nc)continue;
     nodes[old].cost=nc;nodes[old].parent=index;nodes[old].hero=hero;nodes[old].switches=switches;nodes[old].actions=next_actions;queue.push({next_priority,old});
    }else{
     uint32_t id=nodes.size();nodes.push_back({next,progress,index,nc,(uint8_t)hero,(uint8_t)switches,(uint8_t)next_actions});seen.emplace(move(encoded),id);queue.push({next_priority,id});
    }
   }
  }
  finish("exhausted_macro_space");
 }catch(const bad_alloc&){finish("memory_allocation_limit");}
}
