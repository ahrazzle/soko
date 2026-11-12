#include <cassert>
#define main archived_main
#include "archive/cpp/frontier_iii14_iii20_prover.cpp"
#undef main
int main(){
 State14 s=init_state14();
 std::string route="LLULULULRURURURURUAUDRRDDAUARRDLRAULDLDRARURDUUR";
 for(size_t k=0;k<route.size();k++){
  auto old=s; int mv=d_idx(route[k]);int result=s.step(mv);
  if(old.ah!=5||mv==4||result<0)continue;
  vector<int> staying,moving;
  for(int i=0;i<98;i++) if(tst128(old.crates,i)&&abs(i%14-old.bx)<=2&&abs(i/14-old.by)<=2){
   if(tst128(s.crates,i) && tst128(old.walls, i+DX[mv]+14*DY[mv]))staying.push_back(i);
   if(!tst128(s.crates,i)&&tst128(s.crates,i+DX[mv]+14*DY[mv]))moving.push_back(i);
  }
  if(!staying.empty()&&!moving.empty()){
   cout<<"{\"step\":"<<k+1<<",\"key\":\""<<route[k]<<"\",\"prefix\":\""<<route.substr(0,k)<<"\",\"stationary_charmed_crate\":["<<staying[0]%14<<","<<staying[0]/14<<"],\"moving_charmed_crate_from\":["<<moving[0]%14<<","<<moving[0]/14<<"],\"moving_charmed_crate_to\":["<<moving[0]%14+DX[mv]<<","<<moving[0]/14+DY[mv]<<"]}"<<endl;return 0;
  }
 }
 cout<<"No mixed blocked/moving crates found on the 48-key route\n";
}
