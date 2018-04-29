#!/bin/env python

import argparse
import math
import matplotlib
import numpy as np
import os
import sys
import time

import pytrec_eval

font = {
    'family': 'sans-serif',
    'sans-serif': ['Helvetica'],
    'size': 18
}

matplotlib.rc('font', **font)
import matplotlib.pyplot as plt


"""
Adapted from https://gist.github.com/bwhite/3726239#file-rank_metrics-py-L152.
"""


def native_dcg(r):
    return r[0] + sum(
        rel / math.log2(rank + 2) for rank, rel in enumerate(r[1:]))


def native_ndcg(document_scores, document_relevances):
    r = [document_relevances.get(document_id, 0)
         for document_id in sorted(
             document_scores.keys(),
             key=lambda document_id: document_scores[document_id],
             reverse=True)]

    dcg_max = native_dcg(sorted(r, reverse=True))
    if not dcg_max:
        return 0.
    return native_dcg(r) / dcg_max


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--num_documents_per_query', type=int, nargs='+',
                        default=[1, 3, 5, 10, 20, 30, 40, 50,
                                 100, 1000, 10000, 100000])

    parser.add_argument('--num_repeats', type=int, default=20)

    parser.add_argument('--plot_out', type=str, required=True)

    args = parser.parse_args()

    assert not os.path.exists(args.plot_out)

    plt.style.use('bmh')

    speedups_mean = []
    speedups_std = []

    for num_documents_per_query in args.num_documents_per_query:
        document_scores = {
            '{}'.format(document_idx): float(document_idx)
            for document_idx in range(num_documents_per_query)}

        document_relevances = {
            '{}'.format(document_idx): 1
            for document_idx in range(num_documents_per_query)}

        native_durations = []
        pytrec_eval_durations = []

        for _ in range(args.num_repeats):
            native_start_time = time.time()

            ndcg = native_ndcg(
                document_scores, document_relevances)

            native_end_time = time.time()

            pytrec_eval_start_time = time.time()

            evaluator = pytrec_eval.RelevanceEvaluator(
                {'0': document_relevances}, {'ndcg'})

            pytrec_eval_ndcg = evaluator.evaluate(
                {'0': document_scores})['0']['ndcg']

            pytrec_eval_end_time = time.time()

            assert ndcg == pytrec_eval_ndcg

            native_duration = native_end_time - native_start_time
            pytrec_eval_duration = \
                pytrec_eval_end_time - pytrec_eval_start_time

            native_durations.append(native_duration)
            pytrec_eval_durations.append(pytrec_eval_duration)

        native_durations = np.array(native_durations)
        pytrec_eval_durations = np.array(pytrec_eval_durations)

        speedups = native_durations / pytrec_eval_durations

        speedup_mean = np.mean(speedups)
        speedups_mean.append(speedup_mean)

        speedup_std = np.std(speedups)
        speedups_std.append(speedup_std)

    x = np.arange(len(args.num_documents_per_query))

    fig = plt.gcf()
    fig.set_figheight(fig.get_figheight() * 0.65)

    plt.plot([0, len(args.num_documents_per_query) - 1], [1.0, 1.0],
             '--', color='r')

    plt.errorbar(x, speedups_mean, speedups_std, linestyle='-', marker='^')

    plt.xlabel('Number of documents', fontsize=14)
    plt.ylabel('Speedup', fontsize=14)

    plt.ylim(ymin=0.0, ymax=3.0)

    plt.gca().set_xticks(x)
    plt.gca().set_xticklabels([
        r'$10^{{{}}}$'.format(int(np.log10(num_documents)))
        if num_documents >= 100 else r'${}$'.format(int(num_documents))
        for num_documents in args.num_documents_per_query])

    plt.tight_layout()

    plt.savefig(args.plot_out,
                bbox_inches='tight',
                transparent=True,
                pad_inches=0.1)

if __name__ == '__main__':
    sys.exit(main())
