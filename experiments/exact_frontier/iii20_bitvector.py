#!/usr/bin/env python3
"""Experimental III-20 bounded SMT using whole-board bitvector transitions.

No beam scores or guide-distance pruning. Negative timeout results are not proofs.
This reduced rules model is III-20-specific (five distinct heroes, no Bard/doors).
Every candidate still needs replay in the pinned original PuzzleScript build.
"""
from __future__ import annotations
import argparse, copy, hashlib, json, multiprocessing, random, sys, time
from pathlib import Path
import z3

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from soko_mcp.flat_oracle import FlatBitmaskOracle

W,H,N=15,9,135
ROLES=(1,2,3,4,6)
KEYS='UDLRA'
ALL=(1<<N)-1
LEFT=sum(1<<(y*W) for y in range(H))
RIGHT=LEFT<<(W-1)
ZERO=z3.BitVecVal(0,N)
def bv(n): return z3.BitVecVal(n,N)
def bor(xs):
    v=ZERO
    for x in xs: v=v|x
    return v
def shift(x,d):
    if d==0: return z3.LShR(x,W)
    if d==1: return x<<W
    if d==2: return z3.LShR(x & bv(ALL^LEFT),1)
    return (x & bv(ALL^RIGHT))<<1
def shift_n(x,d,n):
    if d==0: return z3.LShR(x,W*n)
    if d==1: return x<<(W*n)
    mask=sum(1<<(y*W+x) for y in range(H) for x in range(W) if (x>=n if d==2 else x<W-n))
    return z3.LShR(x&bv(mask),n) if d==2 else (x&bv(mask))<<n
def ray_closure(seed,allowed,d):
    reached=seed&allowed; span=allowed
    for n in (1,2,4,8):
        reached=reached|(shift_n(reached,d,n)&span)
        span=span&shift_n(span,d,n)
    return reached
def adj(x): return bor(shift(x,d) for d in range(4))
def sel(k,xs):
    v=xs[-1]
    for i in reversed(range(len(xs)-1)): v=z3.If(k==i,xs[i],v)
    return v
def state(name):
    return [z3.BitVec(f'{name}_{r}',N) for r in ('f','t','w','p','d','g','c','wall')]+[z3.BitVec(name+'_active',3)]
def constants(sim):
    masks=[0]*8; active=-1
    for p,c in enumerate(sim.cells):
        if 1<=c<=12:
            role=c if c<=6 else c-6
            j=ROLES.index(role); masks[j]|=1<<p
            if c<=6: active=j
        elif c in (15,14,13): masks[{15:5,14:6,13:7}[c]]|=1<<p
    return [bv(v) for v in masks]+[z3.BitVecVal(active,3)]
def transition(s,key,allow_noops=False,allow_sacrifices=False):
    heroes=s[:5]; g,c,wall,a=s[5:]
    occ=bor(s[:8]); actor=sel(a,heroes)
    movable=(bor(heroes)&~actor)|g|c
    outcomes=[]; valids=[]
    for d in range(4):
        near=shift(actor,d)
        # Fighter pushes the contiguous movable chain by one tile.
        chain=ray_closure(near,movable,d)
        end=shift(chain|actor,d)&~(chain|actor)
        fv=z3.And(end!=ZERO,(end&occ)==ZERO)
        pushed=[(h&~(chain|actor))|shift(h&(chain|actor),d) for h in heroes]
        fg=(g&~chain)|shift(g&chain,d); fc=(c&~chain)|shift(c&chain,d)
        # Thief walks into empty space, pulling at most one object behind.
        behind=shift(actor,d^1)&movable
        tv=z3.And(near!=ZERO,(near&occ)==ZERO)
        pulled=[z3.If(a==j,near,(h&~behind)|shift(h&behind,d)) for j,h in enumerate(heroes)]
        tg=(g&~behind)|shift(g&behind,d); tc=(c&~behind)|shift(c&behind,d)
        # Wizard swaps with the first movable object on the ray; a wall/edge
        # instead causes the ordinary one-step walk if that tile is empty.
        empty_ray=ray_closure(near,~occ,d)
        target=(near|shift(empty_ray,d))&movable
        wd=z3.If(target!=ZERO,target,near)
        wv=z3.Or(target!=ZERO,z3.And(near!=ZERO,(near&occ)==ZERO))
        swapped=[z3.If(a==j,wd,(h&~target)|z3.If((h&target)!=ZERO,actor,ZERO)) for j,h in enumerate(heroes)]
        wg=(g&~target)|z3.If((g&target)!=ZERO,actor,ZERO)
        wc=(c&~target)|z3.If((c&target)!=ZERO,actor,ZERO)
        walked=[z3.If(a==j,near,h) for j,h in enumerate(heroes)]
        # Druid turns walls into crates and monsters/crates into walls.
        empty=(near&occ)==ZERO
        dv=z3.And(near!=ZERO,z3.Or(empty,(near&(wall|g|c))!=ZERO))
        dh=[z3.If(z3.And(a==j,empty),near,h) for j,h in enumerate(heroes)]
        dg=g&~near; dc=(c&~near)|(near&wall)
        dw=(wall&~near)|(near&(c|g))
        if allow_sacrifices:
            dv=near!=ZERO
            dh=[z3.If(a==j,z3.If(empty,near,h),h&~near) for j,h in enumerate(heroes)]
            dw=dw|(near&bor(heroes))
        out=[sel(a,[pushed[j],pulled[j],swapped[j],walked[j],dh[j]]) for j in range(5)]
        out += [sel(a,[fg,tg,wg,g,dg]),sel(a,[fc,tc,wc,c,dc]),z3.If(a==4,dw,wall),a]
        outcomes.append(out)
        valids.append(sel(a,[fv,tv,wv,tv,dv]))
    next_active=z3.If(a==4,0,a+1)
    if allow_sacrifices:
        next_active=a
        for offset in (4,3,2,1):
            candidate=sel(a,[z3.BitVecVal((j+offset)%5,3) for j in range(5)])
            next_active=z3.If(sel(candidate,heroes)!=ZERO,candidate,next_active)
    switch=s[:8]+[next_active]
    raw=[sel(key,[outcomes[d][j] for d in range(4)]+[switch[j]]) for j in range(9)]
    valid=sel(key,valids+[z3.BoolVal(True)])
    if allow_noops:
        raw=[z3.If(valid,raw[j],s[j]) for j in range(8)]+[raw[8]]
        valid=z3.BoolVal(True)
    # Goblin attacks are simultaneous; the Priest shields self and adjacent heroes.
    rawg=raw[5]; priest=raw[3]; shield=priest|adj(priest)
    alive=(bor(raw[:5])&adj(rawg)&~shield)==ZERO
    raw[5]=rawg&~adj(rawg)
    return raw,z3.And(valid,alive)

def frames(grid,route):
    sim=FlatBitmaskOracle(3,grid); result=[constants(sim)]
    for k in route:
        dead,win=sim.step(k)
        result.append(constants(sim))
    return result

def build(instance,horizon):
    """Build the unrestricted III-20 winning-plan formula, without running search.

    Returns (solver, action_booleans, states), matching the shared model contract.
    A solved frame absorbs subsequent actions, so horizon means at most horizon
    actual keys. No reference route, prefix, switch schedule, or heuristic enters
    this builder. Losing hero sacrifices and removable pre-win no-ops are omitted.
    """
    if not isinstance(horizon,int) or horizon<0: raise ValueError('horizon must be nonnegative')
    grid=instance['grid']
    if instance.get('part',3)!=3 or len(grid)!=H or any(len(row)!=W for row in grid):
        raise ValueError('this backend currently supports the 15x9 Part III room')
    if any(ch not in '.#GFTWPD12346O*' for row in grid for ch in row):
        raise ValueError('unsupported object: this reduced backend has no Bard, doors, or dragons')
    sim=FlatBitmaskOracle(3,grid)
    initial=constants(sim)
    if any(z3.is_true(z3.simplify(h==ZERO)) for h in initial[:5]) or sim.goals_mask.bit_count()!=5:
        raise ValueError('all five distinct roles and exactly five goals are required')
    solver=z3.Solver(); states=[state(f'frame_{t}') for t in range(horizon+1)]
    actions=[[z3.Bool(f'action_{t}_{ch}') for ch in KEYS] for t in range(horizon)]
    solver.add(*[x==y for x,y in zip(states[0],initial)])
    goals=bv(sim.goals_mask)
    for t,flags in enumerate(actions):
        key=z3.BitVec(f'action_code_{t}',3)
        solver.add(z3.ULE(key,4),*[flag==(key==j) for j,flag in enumerate(flags)])
        out,legal=transition(states[t],key)
        won=bor(states[t][:5])==goals
        solver.add(z3.Implies(z3.Not(won),z3.And(legal,*[x==y for x,y in zip(states[t+1],out)])))
        solver.add(z3.Implies(won,z3.And(*[x==y for x,y in zip(states[t+1],states[t])])) )
    solver.add(bor(states[-1][:5])==goals)
    return solver,actions,states

def solve_cadical(source,horizon,timeout_ms,export_cnf=None):
    """Bound CNF compilation and external SAT together with an honest wall cap."""
    context=multiprocessing.get_context('fork'); parent,child=context.Pipe(duplex=False)
    def worker():
        try:
            from cnf_search import compile_cnf
            from pysat.formula import CNF
            from pysat.solvers import Solver
            child.send({'backend_stage':'compiling'})
            dimacs,aliases=compile_cnf(source)
            for t in range(horizon):
                for ch in KEYS:
                    if f'action_{t}_{ch}' not in aliases: raise ValueError(f'missing action alias {t}/{ch}')
            cnf=CNF(from_string=dimacs)
            if export_cnf: Path(export_cnf).write_text(dimacs)
            child.send({'backend_stage':'solving','variables':cnf.nv,'clauses':len(cnf.clauses),
                        'cnf_sha256':hashlib.sha256(dimacs.encode()).hexdigest()})
            with Solver(name='cadical195',bootstrap_with=cnf.clauses) as sat:
                accepted=sat.solve()
                result={'status':'sat' if accepted else 'unsat','statistics':sat.accum_stats()}
                if accepted:
                    positive={n for n in sat.get_model() if n>0}; middle=''
                    for t in range(horizon):
                        chosen=[ch for ch in KEYS if aliases[f'action_{t}_{ch}'] in positive]
                        if len(chosen)!=1: raise ValueError(f'non-one-hot action alias at frame {t}')
                        middle+=chosen[0]
                    result['replacement']=middle
                child.send(result)
        except BaseException as exc: child.send({'status':'error','error':repr(exc)})
        finally: child.close()
    process=context.Process(target=worker); process.start(); child.close()
    began=time.monotonic(); report={}; complete=False
    while time.monotonic()-began<timeout_ms/1000:
        if parent.poll(min(0.5,max(0.01,timeout_ms/1000-(time.monotonic()-began)))):
            try: update=parent.recv()
            except EOFError: break
            report.update(update)
            if 'status' in update: complete=True; break
        elif not process.is_alive(): break
    if process.is_alive(): process.terminate()
    process.join(); parent.close()
    if not complete: report.update(status='unknown',reason_unknown='wall_timeout' if time.monotonic()-began>=timeout_ms/1000 else 'backend_worker_exited')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--instance',type=Path,default=ROOT/'evidence/2026-11-12-frontier/iii20-live-instance.json')
    p.add_argument('--calibrate',action='store_true')
    p.add_argument('--fuzz',type=int,default=0,help='Deterministic random differential one-step checks from the baseline trajectory')
    p.add_argument('--start',type=int,default=24); p.add_argument('--end',type=int,default=60)
    p.add_argument('--save',type=int,default=1); p.add_argument('--timeout-ms',type=int,default=30000)
    p.add_argument('--fixed-switches',action='store_true')
    p.add_argument('--delete-index',type=int,help='Absolute baseline key index to omit from the preserved switch template')
    p.add_argument('--output',type=Path)
    p.add_argument('--export-smt2',type=Path)
    p.add_argument('--fix-baseline',action='store_true')
    p.add_argument('--keep-states',action='store_true',help='Keep per-step state variables through bit blasting')
    p.add_argument('--backend',choices=('z3','cadical195'),default='z3')
    p.add_argument('--export-cnf',type=Path)
    args=p.parse_args(); inst=json.loads(args.instance.read_text()); route=inst['route']
    fs=frames(inst['grid'],route); began=time.monotonic()
    report={'approach':'whole-board bitvector SMT','instance':'III-20','baseline_length':len(route),'proof_claim':None,
            'z3_version':z3.get_version_string(),
            'model_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'oracle_sha256':hashlib.sha256((ROOT/'soko_mcp/flat_oracle.py').read_bytes()).hexdigest(),
            'excluded_actions':['unchanged directional input','irreversible Druid destruction of a hero']}
    if args.fuzz:
        sims=[]; sim=FlatBitmaskOracle(3,inst['grid']); sims.append(copy.deepcopy(sim))
        for k in route: sim.step(k); sims.append(copy.deepcopy(sim))
        rng=random.Random(20261112); passed=0; noops=0; sacrifices=0
        for t in range(args.fuzz):
            sim=copy.deepcopy(rng.choice(sims[:-1])); before=constants(sim); k=rng.choice(KEYS)
            out,valid=transition(before,z3.BitVecVal(KEYS.index(k),3))
            alive,won=sim.step(k); after=constants(sim)
            legal=z3.is_true(z3.simplify(valid))
            mismatch=[j for j in range(9) if not z3.is_true(z3.simplify(out[j]==after[j]))]
            unchanged=all(z3.is_true(z3.simplify(x==y)) for x,y in zip(before,after))
            # The actual Druid may destroy an inactive hero. Such states have
            # fewer than five heroes forever, so cannot cover all five goals.
            sacrifice=any(z3.is_true(z3.simplify(h==ZERO)) for h in after[:5])
            if legal and (not alive or mismatch) or (not legal and alive and not unchanged and not sacrifice):
                report.update(calibration='failed',case=t,key=k,model_legal=legal,oracle_alive=alive,mismatches=mismatch);break
            passed+=1; noops+=int(unchanged); sacrifices+=int(sacrifice)
        else: report.update(calibration='passed',random_cases=passed,removable_noops=noops,irreversible_hero_loss_pruned=sacrifices,seed=20261112)
    elif args.calibrate:
        for t,k in enumerate(route):
            out,valid=transition(fs[t],z3.BitVecVal(KEYS.index(k),3))
            good=z3.is_true(z3.simplify(valid))
            mismatch=[j for j in range(9) if not z3.is_true(z3.simplify(out[j]==fs[t+1][j]))]
            if not good or mismatch:
                report.update(calibration='failed',step=t+1,key=k,legal=good,mismatches=mismatch);break
        else: report.update(calibration='passed',compared_frames=len(route)+1)
    else:
        start,end=args.start,args.end; horizon=end-start-args.save
        template=route[start:end]
        if args.delete_index is not None:
            q=args.delete_index-start
            if args.save!=1 or not 0<=q<len(template): raise ValueError('delete-index must lie inside the window and save must be one')
            template=template[:q]+template[q+1:]
        else: template=template[:horizon]
        active_schedule=[]; active=z3.simplify(fs[start][8]).as_long()
        for ch in template:
            active_schedule.append(z3.BitVecVal(active,3))
            if ch=='A': active=(active+1)%5
        stages=['simplify','propagate-values']+([] if args.keep_states else ['solve-eqs','simplify'])+['bit-blast','sat']
        solver=z3.Then(*stages).solver()
        solver.set(timeout=args.timeout_ms)
        ss=[state(f's{t}') for t in range(horizon+1)]; kk=[z3.BitVec(f'k{t}',3) for t in range(horizon)]
        solver.add(*[x==y for x,y in zip(ss[0],fs[start])])
        for t,key in enumerate(kk):
            solver.add(z3.ULE(key,4))
            for d,ch in enumerate(KEYS): solver.add(z3.Bool(f'action_{t}_{ch}')==(key==d))
            if args.fix_baseline: solver.add(key==KEYS.index(template[t]))
            if args.fixed_switches:
                # Preserve switch times from the prefix, allowing arbitrary direction repairs.
                solver.add((key==4)==(template[t]=='A'))
            source=ss[t]
            if args.fixed_switches or args.fix_baseline:
                source=ss[t][:8]+[active_schedule[t]]
                solver.add(ss[t][8]==active_schedule[t])
            stepkey=z3.BitVecVal(KEYS.index(template[t]),3) if args.fix_baseline or (args.fixed_switches and template[t]=='A') else key
            out,valid=transition(source,stepkey)
            solver.add(z3.simplify(valid),*[x==z3.simplify(y) for x,y in zip(ss[t+1],out)])
        if end==len(route):
            goals=bv(sum(1<<(y*W+x) for y,row in enumerate(inst['grid']) for x,k in enumerate(row) if k=='G'))
            solver.add(bor(ss[-1][:5])==goals)
        else: solver.add(*[x==y for x,y in zip(ss[-1],fs[end])])
        report.update(start=start,end=end,horizon=horizon,timeout_ms=args.timeout_ms,fixed_switches=args.fixed_switches,delete_index=args.delete_index,build_seconds=round(time.monotonic()-began,3))
        if args.export_smt2: args.export_smt2.write_text(solver.to_smt2())
        report['backend']=args.backend
        if args.backend=='cadical195':
            report.update(solve_cadical(solver,horizon,args.timeout_ms,args.export_cnf))
            if report['status']=='sat':
                middle=report['replacement']; report['route']=route[:start]+middle+route[end:]
        else:
            status=solver.check(); report['status']=str(status)
            if status==z3.sat:
                m=solver.model(); middle=''.join(KEYS[m.eval(k).as_long()] for k in kk)
                report.update(route=route[:start]+middle+route[end:],replacement=middle)
            if status==z3.unknown: report['reason_unknown']=solver.reason_unknown()
            report['statistics']=str(solver.statistics())
        if report.get('route'):
            sim=FlatBitmaskOracle(3,inst['grid']); finalwin=False; firstwin=None; alive=True
            for i,k in enumerate(report['route']):
                alive,finalwin=sim.step(k)
                if finalwin:
                    firstwin=i+1
                    report['route']=report['route'][:firstwin]
                    break
                if not alive: break
            report['local_replay']=bool(alive and finalwin and firstwin==len(report['route']))
            report['length']=len(report['route'])
    report['elapsed_seconds']=round(time.monotonic()-began,3)
    text=json.dumps(report,indent=2); print(text,flush=True)
    if args.output: args.output.write_text(text+'\n')
    return 1 if report.get('calibration')=='failed' or report.get('status')=='error' or report.get('local_replay') is False else 0
if __name__=='__main__': raise SystemExit(main())
