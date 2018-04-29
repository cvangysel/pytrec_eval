#!/bin/env python

import argparse
import collections
import json
import subprocess
import sys
import tempfile
import time

import pytrec_eval


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument('--tmp_dir', type=str, default=None)
    parser.add_argument('--num_repeats', type=int, default=20)

    parser.add_argument('--measurements_out', type=str, required=True)

    args = parser.parse_args()

    print(args)

    def write_qrel(qrel, f_qrel_out):
        for query_id, document_ids_and_relevance in qrel.items():
            for document_id, document_relevance in \
                    document_ids_and_relevance.items():
                f_qrel_out.write(
                    '{query_id} 0 {document_id} {document_relevance:d}\n'
                    .format(
                        query_id=query_id,
                        document_id=document_id,
                        document_relevance=document_relevance).encode('utf8'))

    def write_run(run, f_run_out):
        for query_id, document_ids_and_scores in run.items():
            for document_id, document_score in document_ids_and_scores.items():
                f_run_out.write(
                    '{query_id} 0 {document_id} {rank:d} '
                    '{document_score:.3f} {run_name}\n'
                    .format(
                        query_id=query_id,
                        document_id=document_id,
                        rank=0,  # Rank is ignored by trec_eval.
                        document_score=document_score,
                        run_name='test').encode('utf8'))

    all_measurements = []

    for num_queries in (1, 10, 50, 250, 1000, 5000, 10000):
        for num_documents_per_query in (1, 5, 10, 20, 50, 100, 500, 1000):
            qrel = {
                'query_{}'.format(query_idx): {
                    'document_{}'.format(document_idx): 0
                    for document_idx in range(num_documents_per_query)}
                for query_idx in range(num_queries)}

            f_qrel = tempfile.NamedTemporaryFile(dir=args.tmp_dir)
            write_qrel(qrel, f_qrel)
            f_qrel.flush()

            qrel_path = f_qrel.name

            run = {
                'query_{}'.format(query_idx): {
                    'document_{}'.format(document_idx): float(document_idx)
                    for document_idx in range(num_documents_per_query)}
                for query_idx in range(num_queries)}

            #
            # pytrec_eval.
            #

            evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'ndcg'})

            start_time = time.time()

            for _ in range(args.num_repeats):
                evaluator.evaluate(run)

            end_time = time.time()

            elapsed = end_time - start_time

            pytrec_eval_time = elapsed / args.num_repeats

            #
            # OS invocation.
            #

            start_time = time.time()

            for _ in range(args.num_repeats):
                f_run = tempfile.NamedTemporaryFile(dir=args.tmp_dir)
                write_run(run, f_run)
                f_run.flush()

                run_path = f_run.name

                subprocess.check_output(
                    ['trec_eval', '-mndcg', '-q', qrel_path, run_path])

            end_time = time.time()

            elapsed = end_time - start_time

            os_trec_eval_time = elapsed / args.num_repeats

            measurement = collections.OrderedDict([
                ('num_queries', num_queries),
                ('num_documents_per_query', num_documents_per_query),
                ('pytrec_eval_time', pytrec_eval_time),
                ('os_trec_eval_time', os_trec_eval_time),
                ('speedup', os_trec_eval_time / pytrec_eval_time),
            ])

            all_measurements.append(measurement)

    if all_measurements:
        with open(args.measurements_out, 'w') as f_measurements_out:
            for measurement in all_measurements:
                f_measurements_out.write(json.dumps(measurement))
                f_measurements_out.write('\n')

if __name__ == '__main__':
    sys.exit(main())
