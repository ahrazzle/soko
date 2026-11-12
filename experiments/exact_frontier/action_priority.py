"""Optional CaDiCaL IPASIR-UP action decisions; imposes no extra constraints.

Connect this propagator before solving and call solver.observe(abs(literal))
for every preferred literal. Observation also prevents elimination of these
variables. The callback never propagates or contributes a clause.
"""

from pysat.engines import Propagator

class ActionPriority(Propagator):
    """Suggest preferred literals while tracking observed solver assignments."""
    def __init__(self, preferred):
        super().__init__()
        self.preferred = list(preferred)
        self.values = {}
        self.fixed = set()
        self.level = 0
        self.trail = [[]]
        self.decisions = 0
        self.backtracks = 0
    def on_assignment(self, lit, fixed=False):
        var = abs(lit)
        if fixed:
            self.fixed.add(var)
        if var in self.values:
            if self.values[var] != lit:
                raise RuntimeError('conflicting observed assignment')
            return
        self.values[var] = lit
        self.trail[self.level].append(var)
    def on_new_level(self):
        self.level += 1
        self.trail.append([])
    def on_backtrack(self, to):
        self.backtracks += 1
        while self.level > to:
            for var in self.trail.pop():
                if var not in self.fixed:
                    self.values.pop(var, None)
            self.level -= 1
    def check_model(self, model):
        return True
    def decide(self):
        for lit in self.preferred:
            if abs(lit) not in self.values:
                self.decisions += 1
                return lit
        return 0
    def propagate(self):
        return []
    def has_clause(self):
        return False
    def add_clause(self):
        raise RuntimeError('unexpected external clause request')
    def provide_reason(self, lit):
        raise RuntimeError('unexpected propagation reason request')


def action_preferences(aliases, hint):
    """Return chronological preferred decision literals, without clauses.

    Each hint character selects the positive action literal at that frame;
    the other action literals receive negative polarity. One-hot CNF constraints
    remain responsible for defining the actual legal action choices.
    """
    result = []
    for index, key in enumerate(hint):
        if key not in 'UDLRA':
            raise ValueError(f'invalid action at frame {index}')
        choices = [aliases[f'action_{index}_{choice}'] for choice in 'UDLRA']
        if any(type(var) is not int or var <= 0 for var in choices):
            raise ValueError('action aliases must be positive integer variables')
        result.append(aliases[f'action_{index}_{key}'])
        result.extend(-aliases[f'action_{index}_{choice}'] for choice in 'UDLRA' if choice != key)
    if len(set(map(abs, result))) != len(result):
        raise ValueError('action aliases must be distinct')
    return result
