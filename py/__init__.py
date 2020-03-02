"""Module pytrec_eval."""

import re
import collections
import numpy as np

from pytrec_eval_ext import RelevanceEvaluator as _RelevanceEvaluator
from pytrec_eval_ext import supported_measures, supported_nicknames

__all__ = [
    'parse_run',
    'parse_qrel',
    'supported_measures',
    'supported_nicknames',
    'RelevanceEvaluator',
]


def parse_run(f_run):
    run = collections.defaultdict(dict)

    for line in f_run:
        query_id, _, object_id, ranking, score, _ = line.strip().split()

        assert object_id not in run[query_id]
        run[query_id][object_id] = float(score)

    return run


def parse_qrel(f_qrel):
    qrel = collections.defaultdict(dict)

    for line in f_qrel:
        query_id, _, object_id, relevance = line.strip().split()

        assert object_id not in qrel[query_id]
        qrel[query_id][object_id] = int(relevance)

    return qrel


def compute_aggregated_measure(measure, values):
    if measure.startswith('num_'):
        agg_fun = np.sum
    elif measure.startswith('gm_'):
        def agg_fun(values):
            return np.exp(np.sum(values) / len(values))
    else:
        agg_fun = np.mean

    return agg_fun(values)


class RelevanceEvaluator(_RelevanceEvaluator):
    def __init__(self, query_relevance, measures, relevance_level=1):
        measures = self._expand_nicknames(measures)
        measures = self._combine_measures(measures)
        super().__init__(query_relevance=query_relevance, measures=measures, relevance_level=relevance_level)

    def evaluate(self, scores):
        if not scores:
            return {}
        return super().evaluate(scores)

    def _expand_nicknames(self, measures):
        # Expand nicknames (e.g., official, all_trec)
        result = set()
        for measure in measures:
            if measure in supported_nicknames:
                result.update(supported_nicknames[measure])
            else:
                result.add(measure)
        return result

    def _combine_measures(self, measures):
        RE_BASE = r'{}[\._]([0-9]+(\.[0-9]+)?(,[0-9]+(\.[0-9]+)?)*)'

        # break apart measures in any of the following formats and combine
        #  1) meas          -> {meas: {}}  # either non-parameterized measure or use default params
        #  2) meas.p1       -> {meas: {p1}}
        #  3) meas_p1       -> {meas: {p1}}
        #  4) meas.p1,p2,p3 -> {meas: {p1, p2, p3}}
        #  5) meas_p1,p2,p3 -> {meas: {p1, p2, p3}}
        param_meas = collections.defaultdict(set)
        for measure in measures:
            if measure not in supported_measures and measure not in supported_nicknames:
                matches = ((m, re.match(RE_BASE.format(re.escape(m)), measure)) for m in supported_measures)
                match = next(filter(lambda x: x[1] is not None, matches), None)
                if match is None:
                    raise ValueError('unsupported measure {}'.format(measure))
                base_meas, meas_args = match[0], match[1].group(1)
                param_meas[base_meas].update(meas_args.split(','))
            elif measure not in param_meas:
                param_meas[measure] = set()

        # re-construct in meas.p1,p2,p3 format for trec_eval
        fmt_meas = set()
        for meas, meas_args in param_meas.items():
            if meas_args:
                meas = '{}.{}'.format(meas, ','.join(sorted(meas_args)))
            fmt_meas.add(meas)

        return fmt_meas
