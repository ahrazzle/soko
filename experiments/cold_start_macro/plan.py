"""Interactive plan builder for III-21 on top of the spec oracle.
Script lines: 'F: RRRD' (switch to Fighter then keys), 'F>12,3' (walk Fighter to cell by
shortest pure walk), 'P~F' (walk Priest to nearest cell adjacent to Fighter), '#' comments."""
import sys, json, subprocess
from collections import deque
sys.path.insert(0, '/home/user/soko')
from soko_mcp.oracle import PuzzleScriptOracle
GRID = json.loads(subprocess.check_output([sys.executable,'-m','soko_mcp','get-room','--room','III-21'],cwd='/home/user/soko'))['grid']
ACT = {'F':'F','T':'T','W':'W','P':'P','B':'B','D':'D'}
INACT = {'F':'1','T':'2','W':'3','P':'4','B':'5','D':'6'}
ORDER = 'FTWPBD'
DIRS = {'U':(0,-1),'D':(0,1),'L':(-1,0),'R':(1,0)}

class Plan:
    def __init__(self):
        self.o = PuzzleScriptOracle(3, GRID); self.route = ''; self.log = []
    def active(self):
        a = self.o.find_active(); return a[2], (a[0], a[1])
    def pos(self, h):
        for y in range(self.o.h):
            for x in range(self.o.w):
                if self.o.obj[y][x] in (ACT[h], INACT[h]): return (x, y)
    def press(self, k):
        alive, win = self.o.step(k); self.route += k
        if not alive: raise RuntimeError(f'death at key {len(self.route)} ({k})\n' + self.o.render_ascii())
        return win
    def switch(self, h):
        n = 0
        while self.active()[0] != h:
            self.press('A'); n += 1
            if n > 6: raise RuntimeError('cannot switch to ' + h)
        return n
    def snap(self):
        return [r[:] for r in self.o.obj]
    def pure_walk_moves(self, h):
        """BFS over single steps that move only hero h; returns dict cell->keys."""
        start = self.pos(h); base = self.o.clone()
        def others(o):
            return [(x,y,o.obj[y][x]) for y in range(o.h) for x in range(o.w) if o.obj[y][x] not in (None, ACT[h])]
        ref = sorted(others(base))
        seen = {start: ''}; q = deque([(start, base)])
        while q:
            p, st = q.popleft()
            for k in 'UDLR':
                c = st.clone(); alive, _ = c.step(k)
                if not alive: continue
                a = c.find_active()
                if a is None or a[2] != ACT[h]: continue
                np_ = (a[0], a[1])
                if abs(np_[0]-p[0]) + abs(np_[1]-p[1]) != 1: continue
                if sorted(others(c)) != ref: continue
                if np_ not in seen:
                    seen[np_] = seen[p] + k; q.append((np_, c))
        return seen
    def walk(self, h, target):
        self.switch(h)
        paths = self.pure_walk_moves(h)
        if target not in paths: raise RuntimeError(f'{h} cannot walk to {target}; reachable={sorted(paths)}')
        for k in paths[target]: self.press(k)
        return paths[target]
    def run(self, script):
        for line in script.strip().splitlines():
            line = line.split('#')[0].strip()
            if not line: continue
            h, rest = line[0], line[1:].strip()
            before = len(self.route)
            if rest.startswith(':'):
                self.switch(h)
                for k in rest[1:].strip(): self.press(k)
            elif rest.startswith('>'):
                x, y = map(int, rest[1:].split(',')); self.walk(h, (x, y))
            self.log.append((line, self.route[before:]))
        return self
    def report(self, verbose=False):
        if verbose:
            for line, keys in self.log: print(f'{len(keys):3d} {line:30s} {keys}')
        print(self.o.render_ascii()); print('len', len(self.route), 'A', self.route.count('A'), 'win', self.o.check_win())

if __name__ == '__main__':
    p = Plan().run(open(sys.argv[1]).read()); p.report(verbose=True); print(p.route)
