"""Module pytrec_eval."""

import collections
import numpy as np

from pytrec_eval_ext import RelevanceEvaluator, supported_measures

__all__ = [
    'parse_run',
    'parse_qrel',
    'supported_measures',
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
