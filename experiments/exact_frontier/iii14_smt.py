#!/usr/bin/env python3
"""III-14 bitvector bounded model. Uses z3-solver; see iii14_smt.md."""
import argparse, random, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import z3
from soko_mcp.oracle import PuzzleScriptOracle, FRONTIER_ROOMS

W,H=15,7; N=W*H; ALL=(1<<N)-1
ROWS=FRONTIER_ROOMS['III-14-15x7']['grid']
ROUTE=FRONTIER_ROOMS['III-14']['reference_route']
def mask(c): return sum(1<<(y*W+x) for y,row in enumerate(ROWS) for x,ch in enumerate(row) if ch==c)
SW=mask('}'); DOOR=mask(']'); GOAL=mask('G')
BV=lambda n:z3.BitVecVal(n,N)
Z=BV(0); FULL=BV(ALL)
EDGES={'L':sum(1<<(y*W) for y in range(H)), 'R':sum(1<<(y*W+W-1) for y in range(H)), 'U':(1<<W)-1, 'D':((1<<W)-1)<<((H-1)*W)}
def shift(v,d):
    v=v & BV(ALL^EDGES[d])
    return {'L':lambda:z3.LShR(v,1),'R':lambda:v<<1,'U':lambda:z3.LShR(v,W),'D':lambda:v<<W}[d]()
INV={'L':'R','R':'L','U':'D','D':'U'}
def area(b):
    result=Z
    for dx in range(-2,3):
        for dy in range(-2,3):
            if dx==0 and dy==0: continue
            q=b
            for _ in range(abs(dx)): q=shift(q,'R' if dx>0 else 'L')
            for _ in range(abs(dy)): q=shift(q,'D' if dy>0 else 'U')
            result=result|q
    return result

def initial():
    return (BV(mask('#')),Z,BV(mask('5')),BV(mask('D')),z3.BoolVal(False),Z,z3.BoolVal(False))
# wall, crates, bard, druid, active bard, note, door open
# A transition cannot lose a hero; those branches cannot win the two goals.
def trans(state, key):
    wall,cr,b,d,active,note,opened=state
    door=z3.If(opened,Z,BV(DOOR))
    occupied=wall|cr|b|d|door
    def move_dir(dr):
        target=shift(d,dr)
        # Druid cannot transmute the inactive Bard in any winning execution.
        survives=(target & b)==Z
        free=(target & occupied)==Z
        dw=z3.If((target & wall)!=Z,wall & ~target, z3.If((target & cr)!=Z,wall|target,wall))
        dc=z3.If((target & wall)!=Z,cr|target,z3.If((target & cr)!=Z,cr & ~target,cr))
        dd=z3.If(free & (target!=Z),target,d)
        # Bard fixed point: pending objects can move iff the chain ahead reaches an empty square.
        pending=b | note
        empty=~occupied & FULL
        movable=pending & shift(empty,INV[dr])
        span=pending
        for jump in (1,2,4,8):
            shifted_movable=movable; shifted_span=span
            for _ in range(jump):
                shifted_movable=shift(shifted_movable,INV[dr])
                shifted_span=shift(shifted_span,INV[dr])
            movable=movable | (span & shifted_movable)
            span=span & shifted_span
        bm=(movable & b)!=Z
        mb=z3.If(bm,shift(b,dr),b)
        mc=z3.If(bm,(cr & ~movable)|shift(cr & movable,dr),cr)
        md=z3.If(bm,(d & ~movable)|shift(d & movable,dr),d)
        return (z3.If(active,wall,dw), z3.If(active,mc,dc),z3.If(active,mb,b),z3.If(active,md,dd), z3.If(active,z3.BoolVal(True),survives))
    if key=='A':
        nw,nc,nb,nd=wall,cr,b,d; na=z3.Not(active); legal=z3.BoolVal(True)
        # Action recomputes notes before the late door phase.
        cancelled=z3.BoolVal(False)
    else:
        nw,nc,nb,nd,legal=move_dir(key); na=active
        # Blocked Bard cancels the entire turn, including Late.
        cancelled=z3.And(active,nb==b)
    notes=z3.If(na,area(nb)&(nc|nd),Z)
    newopen=((nw|nc|nb|nd)&BV(SW))==BV(SW)
    closing=z3.And(opened,z3.Not(newopen))
    legal=z3.And(legal,z3.Or(z3.Not(closing),((nb|nd)&BV(DOOR))==Z))
    nw=z3.If(closing,nw & ~BV(DOOR),nw)
    nc=z3.If(closing,nc & ~BV(DOOR),nc)
    notes=z3.If(closing,notes & ~BV(DOOR),notes)
    ns=(nw,nc,nb,nd,na,notes,newopen)
    return tuple(z3.If(cancelled,old,new) for old,new in zip(state,ns)), z3.Or(cancelled,legal)

def oracle_state(o):
    def objs(chars): return sum(1<<(y*W+x) for y in range(H) for x in range(W) if o.obj[y][x] is not None and o.obj[y][x] in chars)
    return (objs('#'),objs('*'),objs('B5'),objs('D6'),o.find_active()[2]=='B',sum(1<<(y*W+x) for x,y in o.notes),any(o.floor[y][x]=='PO' for y in range(H) for x in range(W)))
def eval_state(s):
    q=[z3.simplify(x) for x in s]
    return tuple(z3.is_true(x) if z3.is_bool(x) else x.as_long() for x in q)
def validate(route):
    o=PuzzleScriptOracle(3,ROWS); s=initial()
    assert oracle_state(o)==eval_state(s),(oracle_state(o),eval_state(s))
    for i,k in enumerate(route):
        s,legal=trans(s,k); s=tuple(z3.simplify(x) for x in s)
        ok,win=o.step(k)
        if not ok or not z3.is_true(z3.simplify(legal)): return False
        if oracle_state(o)!=eval_state(s):
            raise AssertionError((i,k,route[:i+1],oracle_state(o),eval_state(s),o.render_ascii()))
    return True

def build(n, prefix='', guide='', distance=None, timeout=60000, construct_only=False, milestone=False, onehot=False):
    if len(prefix)>n or len(guide)>n: raise ValueError('prefix/guide longer than horizon')
    if distance is not None and not guide: raise ValueError('distance requires guide')
    t=time.monotonic(); solver=z3.Solver(); solver.set(timeout=timeout)
    def vars(i): return (z3.BitVec(f'w{i}',N),z3.BitVec(f'c{i}',N),z3.BitVec(f'b{i}',N),z3.BitVec(f'd{i}',N),z3.Bool(f'a{i}'),z3.BitVec(f'n{i}',N),z3.Bool(f'o{i}'))
    states=[vars(i) for i in range(n+1)]; actions=[[z3.Bool(f'action_{i}_{ch}') for ch in 'UDLRA'] for i in range(n)]
    solver.add(*[a==b for a,b in zip(states[0],initial())]); keys='UDLRA'
    if onehot:
        for frame in states:
            for hero in frame[2:4]:
                solver.add(z3.PbEq([(z3.Extract(i,i,hero)==1,1) for i in range(N)],1))
    oracle=PuzzleScriptOracle(3,ROWS)
    for i,ch in enumerate(prefix):
        ok,won=oracle.step(ch)
        if not ok or (won and i != len(prefix)-1): raise ValueError('prefix loses or wins before its final input')
        vals=oracle_state(oracle)
        solver.add(*[var==val for var,val in zip(states[i+1],vals)])
    for i,k in enumerate(actions):
        solver.add(z3.PbEq([(a,1) for a in k],1))
        if i<len(prefix): solver.add(k[keys.index(prefix[i])])
        for j,ch in enumerate(keys):
            if i < len(prefix) and ch != prefix[i]: continue
            st,legal=trans(states[i],ch)
            solver.add(z3.Implies(z3.And(k[j], z3.Not((states[i][2]|states[i][3])==BV(GOAL))),z3.And(legal,*[a==b for a,b in zip(states[i+1],st)])))
        # Once won, absorb the state, so n means at most n actual inputs.
        goal=(states[i][2]|states[i][3])==BV(GOAL)
        solver.add(z3.Implies(goal,z3.And(*[a==b for a,b in zip(states[i+1],states[i])])))
    if milestone:
        mw=(1<<(3*W+6))|(1<<(4*W+6))
        solver.add(states[n][0]&BV(SW)==BV(mw), states[n][1]&BV(SW)==BV(SW^mw), states[n][2]==BV(1<<(5*W+6)), states[n][3]==BV(1<<(5*W+8)), states[n][4], states[n][6])
    else:
        solver.add((states[n][2]|states[n][3])==BV(GOAL))
    if guide and distance is not None:
        solver.add(z3.PbLe([(z3.Not(actions[i][keys.index(c)]),1) for i,c in enumerate(guide[:n])],distance))
    print(f'build n={n} seconds={time.monotonic()-t:.2f} assertions={len(solver.assertions())} frame_variables={7*(n+1)} action_booleans={5*n} timeout_ms={timeout}',flush=True)
    if construct_only: return solver,actions,states
    t=time.monotonic(); result=solver.check(); print(f'result={result} solve_seconds={time.monotonic()-t:.2f}',flush=True)
    if result==z3.sat:
        model=solver.model(); route=''.join(next(keys[j] for j,a in enumerate(row) if z3.is_true(model.eval(a))) for row in actions); o=PuzzleScriptOracle(3,ROWS); end=n
        for i,ch in enumerate(route):
            ok,won=o.step(ch)
            if won: end=i+1; break
        route=route[:end];
        if milestone: route += 'RRRUU'
        print('route',route,flush=True); assert validate(route)
        verifier=PuzzleScriptOracle(3,ROWS)
        for j,ch in enumerate(route):
            ok,won=verifier.step(ch)
            assert ok and (not won or j==len(route)-1)
        assert won
    elif result==z3.unknown: print('reason',solver.reason_unknown(),flush=True)

def main():
    p=argparse.ArgumentParser(); p.add_argument('--validate',action='store_true'); p.add_argument('--validate-near',action='store_true'); p.add_argument('--milestone',action='store_true'); p.add_argument('--onehot',action='store_true'); p.add_argument('--n',type=int,default=48); p.add_argument('--prefix',default=''); p.add_argument('--guide',default=''); p.add_argument('--distance',type=int); p.add_argument('--timeout',type=int,default=60000); args=p.parse_args()
    if args.validate:
        assert validate(ROUTE); rng=random.Random(7314); count=0
        for _ in range(500):
            route=''.join(rng.choice('UDLRA') for _ in range(rng.randrange(1,31)))
            count+=validate(route)
        print(f'validated reference and {count} surviving random traces',flush=True)
    elif args.validate_near:
        rng=random.Random(149314); count=0
        for _ in range(100):
            n=rng.randrange(20,47)
            route=ROUTE[:n]+''.join(rng.choice('UDLRA') for _ in range(rng.randrange(1,16)))
            count+=validate(route)
        print(f'validated {count} surviving baseline-prefix random-suffix traces',flush=True)
    else: build(args.n,args.prefix,args.guide,args.distance,args.timeout,milestone=args.milestone,onehot=args.onehot)
if __name__=='__main__': main()
