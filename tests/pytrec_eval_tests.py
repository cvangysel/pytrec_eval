from cvangysel.trec_utils import parse_trec_eval
import os
import unittest

import pytrec_eval

TREC_EVAL_TEST_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..', 'trec_eval', 'test')


def prefix_match(needle, haystack):
    match = max(haystack, key=lambda x: len(os.path.commonprefix([x, needle])))

    if not os.path.commonprefix([needle, match]):
        return None

    return match


class PyTrecEvalUnitTest(unittest.TestCase):

    def test_ndcg(self):
        qrel = {
            'q1': {
                'd1': 0,
                'd2': 1,
                'd3': 0,
            },
            'q2': {
                'd2': 1,
                'd3': 1,
            },
        }

        evaluator = pytrec_eval.RelevanceEvaluator(
            qrel, {'map', 'ndcg'})

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 0.0,  # rank 3
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg'],
            0.5)

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 2.0,  # rank 1
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg'],
            1.0)

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 2.0,  # rank 1
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg'],
            1.0)

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 4.0,
                    'd2': 2.0,  # rank 2
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg'],
            0.6309297535714575)

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 2.0,  # rank 1
                    'd3': 1.5,
                },
            })['q1']['ndcg'],
            1.0)

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 4.0,
                    'd2': 2.0,  # rank 2
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg'],
            0.6309297535714575)


# TODO(cvangysel): add tests to detect memory leaks.
class PyTrecEvalIntegrationTest(unittest.TestCase):

    pass


TRADITIONAL_TREC_EVAL_TEST_CASES = [
    ('results.test', 'qrels.test', 'out.test', {}),
    ('results.test', 'qrels.rel_level', 'out.test.aql',
     {'relevance_level': 2}),
]


def generate_traditional_test(run_filename,
                              qrel_filename,
                              ground_truth_filename,
                              **kwargs):
    def __test(self):
        with open(os.path.join(TREC_EVAL_TEST_DIR, ground_truth_filename)) as \
                f_trec_eval:
            trec_eval_output = parse_trec_eval(f_trec_eval)

        measures = set(
            measure
            if measure in pytrec_eval.supported_measures
            else prefix_match(measure, pytrec_eval.supported_measures)
            for measure in trec_eval_output['all'].keys())

        with open(os.path.join(TREC_EVAL_TEST_DIR, qrel_filename)) as f_qrel:
            qrel = pytrec_eval.parse_qrel(f_qrel)

        with open(os.path.join(TREC_EVAL_TEST_DIR, run_filename)) as f_run:
            run = pytrec_eval.parse_run(f_run)

        evaluator = pytrec_eval.RelevanceEvaluator(
            qrel, measures, **kwargs)

        results = evaluator.evaluate(run)

        expected_measures = trec_eval_output['all']

        for measure in expected_measures:
            agg_measure_value = pytrec_eval.compute_aggregated_measure(
                measure,
                [query_measure_values[measure]
                 for query_measure_values in
                 results.values()])

            ground_truth_agg_measure_value = \
                trec_eval_output['all'][measure]

            self.assertAlmostEqual(agg_measure_value,
                                   ground_truth_agg_measure_value,
                                   places=3,
                                   msg=measure)

    return __test

if __name__ == '__main__':
    assert os.path.isdir(TREC_EVAL_TEST_DIR), \
        'Make sure the trec_eval source has been checked out.'

    for test_case in TRADITIONAL_TREC_EVAL_TEST_CASES:
        test_name = 'test_{}'.format('-'.join(test_case[:3]))

        if test_case[3]:
            test_name = '{}-{}'.format(
                test_name, '-'.join(
                    '{}={}'.format(key, value)
                    for key, value in test_case[3].items()))

        test_fn = generate_traditional_test(*test_case[:3], **test_case[3])
        setattr(PyTrecEvalIntegrationTest, test_name, test_fn)

    unittest.main()
