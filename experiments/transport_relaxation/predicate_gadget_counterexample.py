"""Enumerate a counterexample to the proposed arbitrary-pair predicate gadget.

This checks the represented objective for a fixed original partition, not
the soundness of an independently checked capacity cut. Additional structural
restrictions may make the gadget exact on particular contracted instances.
"""
import itertools
import json


def counterexample():
    pairs = [('u1', 'v1'), ('u2', 'v2')]
    source_side = {'s', 'u1', 'v1'}
    predicate_weight, large_weight = 10, 1000
    original = predicate_weight * any(u in source_side and v not in source_side
                                      for u, v in pairs)
    arcs = [(u, 'pred_in', large_weight) for u, _ in pairs]
    arcs += [('pred_in', 'pred_out', predicate_weight)]
    arcs += [('pred_out', v, large_weight) for _, v in pairs]
    placements = []
    for left, right in itertools.product((False, True), repeat=2):
        side = source_side | ({'pred_in'} if left else set()) | ({'pred_out'} if right else set())
        cost = sum(weight for u, v, weight in arcs if u in side and v not in side)
        placements.append({'pred_in_in_source': left, 'pred_out_in_source': right, 'cost': cost})
    represented = min(row['cost'] for row in placements)
    if original != 0 or represented != predicate_weight:
        raise AssertionError('counterexample failed')
    return {'pairs': pairs, 'source_side': sorted(source_side),
            'predicate_weight': predicate_weight, 'large_weight': large_weight,
            'original_predicate_cost': original, 'auxiliary_placements': placements,
            'minimum_gadget_cost': represented,
            'scope': 'The arbitrary-pair gadget charges cross pairs; this does not invalidate independently checked original cut capacities.'}


if __name__ == '__main__':
    print(json.dumps(counterexample(), indent=2))
