import collections
import os
import re
import unittest

import pytrec_eval

TREC_EVAL_TEST_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), '..', 'trec_eval', 'test')


def prefix_match(needle, haystack):
    match = max(haystack, key=lambda x: len(os.path.commonprefix([x, needle])))

    if not os.path.commonprefix([needle, match]):
        return None

    return match


def parse_trec_eval(f):
    measure_re = re.compile(r'^([A-Za-z0-9_\-]+)\s+(.*)\s+([0-9\.e\-]+)$')

    trec_eval = collections.defaultdict(dict)

    for line in f:
        result = measure_re.match(line)

        if result:
            measure, topic, value = \
                result.group(1), result.group(2), result.group(3)

            if measure in trec_eval[topic]:
                raise RuntimeError()

            trec_eval[topic][measure] = float(value)

    return trec_eval


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

    def test_nicknames(self):
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
        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'all_trec'})
        all_trec_metrics = {'11pt_avg','binG','bpref','G','gm_bpref','gm_map','infAP','iprec_at_recall_0.00','iprec_at_recall_0.10','iprec_at_recall_0.20','iprec_at_recall_0.30','iprec_at_recall_0.40','iprec_at_recall_0.50','iprec_at_recall_0.60','iprec_at_recall_0.70','iprec_at_recall_0.80','iprec_at_recall_0.90','iprec_at_recall_1.00','map','map_cut_10','map_cut_100','map_cut_1000','map_cut_15','map_cut_20','map_cut_200','map_cut_30','map_cut_5','map_cut_500','ndcg','ndcg_cut_10','ndcg_cut_100','ndcg_cut_1000','ndcg_cut_15','ndcg_cut_20','ndcg_cut_200','ndcg_cut_30','ndcg_cut_5','ndcg_cut_500','ndcg_rel','num_nonrel_judged_ret','num_q','num_rel','num_rel_ret','num_ret','P_10','P_100','P_1000','P_15','P_20','P_200','P_30','P_5','P_500','recall_10','recall_100','recall_1000','recall_15','recall_20','recall_200','recall_30','recall_5','recall_500','recip_rank','relative_P_10','relative_P_100','relative_P_1000','relative_P_15','relative_P_20','relative_P_200','relative_P_30','relative_P_5','relative_P_500','relstring','Rndcg','Rprec','Rprec_mult_0.20','Rprec_mult_0.40','Rprec_mult_0.60','Rprec_mult_0.80','Rprec_mult_1.00','Rprec_mult_1.20','Rprec_mult_1.40','Rprec_mult_1.60','Rprec_mult_1.80','Rprec_mult_2.00','runid','set_F','set_map','set_P','set_recall','set_relative_P','success_1','success_10','success_5','utility'}
        self.assertEqual(
            set(evaluator.evaluate({
                'q1': {},
                'q2': {}
            })['q1'].keys()),
            all_trec_metrics)

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'set'})
        set_metrics = {'num_q','num_rel','num_rel_ret','num_ret','runid','set_F','set_map','set_P','set_recall','set_relative_P','utility'}
        self.assertEqual(
            set(evaluator.evaluate({
                'q1': {},
                'q2': {}
            })['q1'].keys()),
            set_metrics)

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'official'})
        official_metrics = {'iprec_at_recall_0.80', 'P_500', 'num_q', 'iprec_at_recall_0.20', 'iprec_at_recall_0.50', 'map', 'iprec_at_recall_0.70', 'iprec_at_recall_1.00', 'iprec_at_recall_0.40', 'iprec_at_recall_0.60', 'num_rel', 'iprec_at_recall_0.90', 'bpref', 'P_200', 'gm_map', 'P_30', 'iprec_at_recall_0.30', 'P_100', 'P_10', 'P_20', 'Rprec', 'iprec_at_recall_0.10', 'P_1000', 'num_ret', 'P_5', 'num_rel_ret', 'recip_rank', 'P_15', 'runid', 'iprec_at_recall_0.00'}
        self.assertEqual(
            set(evaluator.evaluate({
                'q1': {},
                'q2': {}
            })['q1'].keys()),
            official_metrics)

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'official', 'set', 'ndcg'})
        self.assertEqual(
            set(evaluator.evaluate({
                'q1': {},
                'q2': {}
            })['q1'].keys()),
            official_metrics | set_metrics | {'ndcg'})

    def test_ndcg_cut(self):
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

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'ndcg_cut.3'})

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 0.0,  # rank 3
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg_cut_3'],
            0.5)

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'ndcg_cut.1'})

        self.assertAlmostEqual(
            evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 2.0,  # rank 3
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']['ndcg_cut_1'],
            1.0)

        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'ndcg_cut.1,2,3,1000'})
        result = evaluator.evaluate({
                'q1': {
                    'd1': 1.0,
                    'd2': 0.0,  # rank 3
                    'd3': 1.5,
                },
                'q2': {},
            })['q1']
        self.assertAlmostEqual(result['ndcg_cut_3'], 0.5)
        self.assertAlmostEqual(result['ndcg_cut_2'], 0.0)
        self.assertAlmostEqual(result['ndcg_cut_1'], 0.0)
        self.assertAlmostEqual(result['ndcg_cut_1000'], 0.5)

    def test_empty(self):
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
        run = {
            'q1': {
                'd1': 1.0,
                'd2': 0.0,
                'd3': 1.5,
            },
            'q2': {},
        }

        # empty run
        evaluator = pytrec_eval.RelevanceEvaluator(qrel, {'map', 'ndcg'})
        self.assertEqual(evaluator.evaluate({}), {})

        # empty metrics
        evaluator = pytrec_eval.RelevanceEvaluator(qrel, set())
        self.assertEqual(evaluator.evaluate(run), {'q1': {}, 'q2': {}})

        # empty qrels
        evaluator = pytrec_eval.RelevanceEvaluator({}, {'map', 'ndcg'})
        self.assertEqual(evaluator.evaluate(run), {})

        # empty qrels and run
        evaluator = pytrec_eval.RelevanceEvaluator({}, {'map', 'ndcg'})
        self.assertEqual(evaluator.evaluate({}), {})

        # empty metrics and run
        evaluator = pytrec_eval.RelevanceEvaluator(qrel, set())
        self.assertEqual(evaluator.evaluate({}), {})

        # empty qrels and metrics
        evaluator = pytrec_eval.RelevanceEvaluator({}, set())
        self.assertEqual(evaluator.evaluate(run), {})

        # empty everything
        evaluator = pytrec_eval.RelevanceEvaluator({}, {})
        self.assertEqual(evaluator.evaluate({}), {})

    def test_measure_params(self):
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
        run = {
            'q1': {
                'd1': 1.0,
                'd2': 0.0,
                'd3': 1.5,
            },
            'q2': {},
        }

        # empty run
        evaluator = pytrec_eval.RelevanceEvaluator(qrel, ['ndcg_cut', 'ndcg_cut.1,4', 'ndcg_cut_20,4', 'ndcg_cut_15', 'recall.1000', 'P'])
        self.assertEqual(set(evaluator.evaluate(run)['q1'].keys()), {'ndcg_cut_1', 'ndcg_cut_4', 'ndcg_cut_15', 'ndcg_cut_20', 'recall_1000', 'P_200', 'P_15', 'P_10', 'P_5', 'P_30', 'P_100', 'P_20', 'P_500', 'P_1000'})

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
