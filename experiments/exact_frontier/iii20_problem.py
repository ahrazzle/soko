#!/usr/bin/env python3
"""Reusable unrestricted III-20 bounded winning-plan problem.

Contract: build_problem(horizon) returns (z3.Solver, actions, states).
actions[t] contains native Bool U,D,L,R,A flags named action_t_KEY.
states[t] contains 8 whole-board bitvectors and a 3-bit active-role index.
No route, guide, switch schedule, prefix, or heuristic limits the problem.
The goal is absorbing, so horizon means at most horizon original input keys.
"""
from __future__ import annotations
import random
import z3

try:
    from . import iii20_bitvector as core
except ImportError:
    import iii20_bitvector as core
from soko_mcp.oracle import PuzzleScriptOracle

MODEL_CONTRACT={
    'version':1,'room':'III-20','board':'original 15x9',
    'objective':'first win at or before horizon inputs',
    'state':['fighter','thief','wizard','priest','druid','goblins','crates','walls','active_role'],
    'state_encoding':'Eight 135-bit object masks and one 3-bit active-role index (0..4)',
    'actions':['U','D','L','R','A'],
    'action_encoding':'native one-hot Boolean aliases action_{zero_based_step}_{action}',
    'goal_absorbing':True,'all_board_cells_modeled':True,
    'noops':'actual blocked directional inputs are permitted',
    'hero_loss_pruned':False,
    'druid_behavior':'Druid transforms inactive heroes into walls; switching skips vanished roles',
    'external_lower_bound_assumed':False,'prefix_or_neighborhood_restriction':False,
    'solver_result_semantics':{'sat':'candidate requiring independent original-game replay','unsat':'no modeled win at or before horizon, subject to model correctness','unknown':'inconclusive'},
    'calibration_limits':'sampled oracle agreement is evidence, not a proof of model equivalence',
}

def _canonical_instance():
    # Use the shipped room catalog rather than an experimental captured route.
    from soko_mcp.catalog import get_room
    return get_room('III-20')

def build_problem(horizon):
    """Construct, but never solve, the complete canonical <=horizon problem."""
    if isinstance(horizon,bool) or not isinstance(horizon,int) or horizon<0: raise ValueError('horizon must be a nonnegative integer')
    instance=_canonical_instance(); sim=core.FlatBitmaskOracle(3,instance['grid'])
    solver=z3.Solver()
    states=[core.state(f'frame_{t}') for t in range(horizon+1)]
    actions=[[z3.Bool(f'action_{t}_{ch}') for ch in core.KEYS] for t in range(horizon)]
    solver.add(*[x==y for x,y in zip(states[0],core.constants(sim))])
    goals=core.bv(sim.goals_mask)
    for t,flags in enumerate(actions):
        key=z3.BitVec(f'action_code_{t}',3)
        solver.add(z3.ULE(key,4),*[flag==(key==j) for j,flag in enumerate(flags)])
        out,legal=core.transition(states[t],key,allow_noops=True,allow_sacrifices=True)
        won=core.bor(states[t][:5])==goals
        solver.add(z3.Implies(z3.Not(won),z3.And(legal,*[x==y for x,y in zip(states[t+1],out)])))
        solver.add(z3.Implies(won,z3.And(*[x==y for x,y in zip(states[t+1],states[t])])) )
        # Redundant range constraints make the public state contract explicit.
        solver.add(z3.ULE(states[t][8],4))
    solver.add(z3.ULE(states[-1][8],4),core.bor(states[-1][:5])==goals)
    return solver,actions,states

def _oracle_constants(sim):
    masks=[0]*8; active=-1
    for y,row in enumerate(sim.obj):
        for x,ch in enumerate(row):
            if ch is not None and ch in 'FTWPD12346':
                role={'F':0,'T':1,'W':2,'P':3,'D':4,'1':0,'2':1,'3':2,'4':3,'6':4}[ch]
                masks[role]|=1<<(y*core.W+x)
                if ch in 'FTWPD': active=role
            elif ch in ('O','*','#'): masks[{'O':5,'*':6,'#':7}[ch]]|=1<<(y*core.W+x)
    return [core.bv(mask) for mask in masks]+[z3.BitVecVal(active,3)]

oracle_state = _oracle_constants

def calibrate(initial_samples=500,near_samples=100):
    """Compare the full transition model with every pinned baseline frame.

    This routine performs concrete differential checks, not record search.
    Random checks include blocked keys and hero destruction, with exact masks.
    """
    if initial_samples<0 or near_samples<0: raise ValueError('sample counts must be nonnegative')
    instance=_canonical_instance(); route=instance['reference_route']; sim=PuzzleScriptOracle(3,instance['grid'])
    snapshots=[sim.clone()]; compared=0
    def check_step(sim,ch,label):
        before=_oracle_constants(sim)
        out,legal=core.transition(before,z3.BitVecVal(core.KEYS.index(ch),3),True,True)
        alive,won=sim.step(ch); after=_oracle_constants(sim)
        model_alive=z3.is_true(z3.simplify(legal))
        if model_alive!=alive or (alive and any(not z3.is_true(z3.simplify(x==y)) for x,y in zip(out,after))):
            raise AssertionError(f'transition mismatch at {label}/{ch}')
        return alive,won,any(z3.is_true(z3.simplify(h==core.ZERO)) for h in after[:5])
    for step,ch in enumerate(route,1):
        alive,won,_=check_step(sim,ch,f'baseline {step}')
        if not alive or won!=(step==len(route)): raise AssertionError('baseline must first win on its final key')
        compared+=1; snapshots.append(sim.clone())
    rng=random.Random(20261112); initial_alive=0; near_alive=0; hero_loss=0
    sim=snapshots[0].clone()
    for case in range(initial_samples):
        alive,won,lost=check_step(sim,rng.choice(core.KEYS),f'initial walk {case}')
        initial_alive+=int(alive); hero_loss+=int(alive and lost)
        if not alive or won or case%30==29: sim=snapshots[0].clone()
    for case in range(near_samples):
        sim=rng.choice(snapshots[:-1]).clone()
        alive,won,lost=check_step(sim,rng.choice(core.KEYS),f'baseline branch {case}')
        near_alive+=int(alive); hero_loss+=int(alive and lost)
        if alive and lost:
            for j in range(5): check_step(sim,'A',f'switch after hero loss {case}/{j}')
    # A deterministic reachable baseline branch petrifies the inactive Wizard.
    sacrifice=snapshots[77].clone()
    alive,_,lost=check_step(sacrifice,'R','deterministic Wizard petrification')
    if not alive or not lost: raise AssertionError('petrification control did not lose the Wizard')
    for j in range(5): check_step(sacrifice,'A',f'deterministic missing-role switch {j}')
    # Small rule unit control: Fighter pushes Priest and a goblin; that goblin
    # becomes adjacent to another goblin, so both die while Priest shields F.
    rows=[[ch if ch in '#G' else '.' for ch in row] for row in instance['grid']]
    for x,y,ch in [(5,4,'F'),(6,4,'4'),(7,4,'O'),(8,3,'O'),(9,2,'2'),(5,6,'3'),(9,6,'6')]: rows[y][x]=ch
    combat=PuzzleScriptOracle(3,[''.join(row) for row in rows])
    alive,_,_=check_step(combat,'R','simultaneous goblin collision with Priest')
    if not alive or any(ch=='O' for row in combat.obj for ch in row): raise AssertionError('goblin combat control failed')
    for ch in 'AUL': check_step(combat,ch,'post-combat stateful control')
    return {'status':'passed','baseline':{'route':route,'length':len(route),'first_win':len(route),'compared_steps':compared},
            'initial_random':{'seed':20261112,'attempted':initial_samples,'surviving_and_matched':initial_alive,'meaning':'seeded random walk steps, reset at death/win or every thirty keys'},
            'baseline_prefix_random':{'attempted':near_samples,'surviving_and_matched':near_alive,'meaning':'seeded one-step random branches from baseline frames'},
            'hero_loss_cases':hero_loss,
            'mechanic_controls':{'baseline_Wizard_petrification':True,'switches_after_missing_role':5,'simultaneous_goblin_deaths':2,'post_combat_inputs':3},
            'oracle':'soko_mcp.oracle.PuzzleScriptOracle','original_game_replay_required_for_witness':True}
