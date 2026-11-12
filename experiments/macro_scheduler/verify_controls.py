#!/usr/bin/env python3
"""Rebuild and verify portable controls, without launching an optimization query."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from soko_mcp.oracle import PuzzleScriptOracle
from soko_mcp.original import SOURCES, replay

def verify(original_html=None):
    evidence=HERE/'evidence'
    manifest=evidence/'manifest.json'
    if manifest.exists():
        for relative,expected in json.loads(manifest.read_text()).items():
            path=(HERE/relative).resolve()
            assert path.is_relative_to(HERE)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected,relative
    instance=json.loads((evidence/'instance.json').read_text())
    route=instance['reference_route']; inputs=(evidence/'fixed/input.txt').read_text()
    with tempfile.TemporaryDirectory(prefix='macro-controls-') as temporary:
        binary=Path(temporary)/'macro_scheduler'
        subprocess.run(['g++','-std=c++20','-O3',str(HERE/'macro_scheduler.cpp'),'-o',str(binary)],check=True)
        def native(*args):
            result=subprocess.run([str(binary),*args],input=inputs,text=True,capture_output=True,check=True,timeout=30)
            return [json.loads(line) for line in result.stdout.splitlines()]
        frames=native('--calibrate')
        assert frames==[json.loads(line) for line in (evidence/'baseline-frames.jsonl').read_text().splitlines()]
        oracle=PuzzleScriptOracle(3,instance['grid'])
        digest=oracle.fold_canonical_digest(14695981039346656037)
        assert frames[0]['digest']==digest
        for step,key in enumerate(route,1):
            alive,won=oracle.step(key); digest=oracle.fold_canonical_digest(digest)
            assert alive and won==(step==len(route))
            assert (frames[step]['alive'],frames[step]['won'],frames[step]['digest'])==(alive,won,digest)
        control=native('--omit-noops','--action-cap','75','--control-only')[0]
        assert control['status']=='baseline_control_passed' and control['identical_to_reference']
        assert control['route']==route and control['length']==316
        priority=native('--omit-noops','--action-cap','75','--goal-directed','--priority-self-test')[0]
        assert priority['status']=='priority_unit_passed'
        assert priority['score_above_bound_retained'] and priority['lower_g_reopens'] and priority['stale_higher_g_discarded']
    certificate=json.loads((evidence/'baseline-original-replay.json').read_text())
    assert certificate['valid_winning_route'] and certificate['route']==route
    assert certificate['first_win']==316 and certificate['first_death'] is None
    assert certificate['html_sha256']==SOURCES[3][1]
    assert certificate['puzzlescript_source_sha256']==SOURCES[3][2]
    fresh=False
    if original_html:
        certificate=replay(3,21,route,html=Path(original_html))
        assert certificate['valid_winning_route'] and certificate['first_win']==316
        fresh=True
    return {'status':'passed','optimization_queries_run':0,'compiled_native':True,
            'native_python_exact_frames':len(frames),'baseline_inputs':len(route),
            'baseline_normalization_identical':True,'priority_unit':'passed',
            'stored_pinned_original_certificate':'passed','fresh_original_replay':fresh}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-html',type=Path,help='Optionally rerun the original baseline control in the pinned HTML')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args(); result=verify(args.original_html)
    text=json.dumps(result,indent=2)+'\n';print(text,end='')
    if args.report: args.report.write_text(text)
