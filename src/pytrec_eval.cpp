#include <Python.h>
#include "structmember.h"

// trec_Eval includes.
#include "common.h"
#include "sysfunc.h"
#include "trec_eval.h"
#include "trec_format.h"

extern "C" int te_print_single_meas_a_cut (
    const EPI *epi, const TREC_MEAS *tm,
    const TREC_EVAL *eval);

#include "functions.h"

// Standard library.
#include <map>
#include <set>
#include <string>

extern int te_num_trec_measures;
extern TREC_MEAS* te_trec_measures[];
extern int te_num_trec_measure_nicknames;
extern TREC_MEASURE_NICKNAMES te_trec_measure_nicknames[];
extern int te_num_rel_info_format;
extern REL_INFO_FILE_FORMAT te_rel_info_format[];
extern int te_num_results_format;
extern RESULTS_FILE_FORMAT te_results_format[];
extern int te_num_form_inter_procs;
extern RESULTS_FILE_FORMAT te_form_inter_procs[];

#define CHECK(condition) assert(condition)
#define CHECK_EQ(first, second) assert(first == second)
#define CHECK_GT(first, second) assert(first > second)
#define CHECK_GE(first, second) assert(first >= second)
#define CHECK_NOTNULL(condition) assert(condition != 0)

#define int32 long
#define int64 long long

#define __DEVELOPMENT false

// Helpers.
int PyDict_SetItemAndSteal(PyObject* p, PyObject* key, PyObject* val) {
    CHECK(key != Py_None);
    CHECK(val != Py_None);

    int ret = PyDict_SetItem(p, key, val);

    Py_XDECREF(key);
    Py_XDECREF(val);

    return ret;
}

static PyTypeObject RelevanceEvaluatorType;

// RelevanceEvaluator

typedef struct {
    PyObject_HEAD

    // Original dictionary with relevance information.
    PyObject* object_relevance_per_qid_;

    // trec_eval session structure.
    EPI epi_;

    // trec_eval relevance structure.
    ALL_REL_INFO all_rel_info_;

    // Mapping from query identifier to internal idx.
    std::map<std::string, size_t>* query_id_to_idx_;
    std::set<size_t>* measures_;
} RelevanceEvaluator;

static PyObject* RelevanceEvaluator_new(PyTypeObject* type, PyObject* args, PyObject* kwds) {
    RelevanceEvaluator* self;

    self = (RelevanceEvaluator*) type->tp_alloc(type, 0);
    if (self != NULL) {
        self->object_relevance_per_qid_ = NULL;
        self->query_id_to_idx_ = new std::map<std::string, size_t>;
        self->measures_ = new std::set<size_t>;
        self->all_rel_info_.num_q_rels = -1;
    }

    return (PyObject*) self;
}

template <typename QueryT, typename ListOfPairsT, typename PairT>
class RankingBuilder {
 public:
    typedef QueryT QueryType;
    typedef PairT QueryDocumentPairType;

    bool operator()(PyObject* const dict, int64& num_queries, QueryT*& queries) {
        num_queries = PyDict_Size(dict);

        queries = Malloc(num_queries, QueryT);
        ListOfPairsT* const query_pair_list = Malloc(num_queries, ListOfPairsT);

        CHECK_NOTNULL(queries);
        CHECK_NOTNULL(query_pair_list);

        PyObject* key = NULL;
        PyObject* value = NULL;

        Py_ssize_t pos = 0;

        size_t query_idx = 0;

        while (PyDict_Next(dict, &pos, &key, &value)) {
            if (!PyUnicode_Check(key)) {
                PyErr_SetString(PyExc_TypeError, "Expected string as key.");

                return false;
            }

            if (!PyDict_Check(value)) {
                PyErr_SetString(PyExc_TypeError, "Expected dictionary as value.");

                return false;
            }

            Py_INCREF(key);

            queries[query_idx].qid = PyUnicode_AsUTF8(key);
            CHECK_NOTNULL(queries[query_idx].qid);

            PairT* const query_document_pairs = Malloc(PyDict_Size(value), PairT);

            PyObject* inner_key = NULL;
            PyObject* inner_value = NULL;

            Py_ssize_t inner_pos = 0;

            size_t pair_idx = 0;

            while (PyDict_Next(value, &inner_pos, &inner_key, &inner_value)) {
                if (!PyUnicode_Check(inner_key)) {
                    PyErr_SetString(PyExc_TypeError, "Expected mapping of document id to query relevance or matching score.");

                    return false;  // TODO(cvangysel): need to clean up here!
                }

                query_document_pairs[pair_idx].docno = PyUnicode_AsUTF8(inner_key);
                CHECK_NOTNULL(query_document_pairs[pair_idx].docno);

                if (!ProcessQueryDocumentPair(&query_document_pairs[pair_idx],
                                              inner_value)) {
                    return false;
                }

                ++pair_idx;
            }

            if (!ProcessListOfQueryDocumentPairs(&query_pair_list[query_idx],
                                                 PyDict_Size(value),
                                                 query_document_pairs)) {
                return false;
            }

            if (!ProcessQuery(&queries[query_idx], &query_pair_list[query_idx])) {
                return false;
            }

            ++query_idx;
        }

        return true;
    }

    virtual void cleanup(const int64 num_queries, QueryT* queries) const = 0;

 protected:
    virtual bool ProcessQuery(QueryT* const query,
                              ListOfPairsT* query_pair_list) const = 0;

    virtual bool ProcessListOfQueryDocumentPairs(
        ListOfPairsT* const query_pair_list,
        const size_t num_pairs,
        PairT* const query_document_pairs) const = 0;

    virtual bool ProcessQueryDocumentPair(
        PairT* const pair,
        PyObject* const inner_value) const = 0;
};

class QrelRankingBuilder : public RankingBuilder<REL_INFO, TEXT_QRELS_INFO, TEXT_QRELS> {
 public:
    virtual void cleanup(const int64 num_queries, REL_INFO* queries) const {
        for (size_t idx = 0; idx < num_queries; ++idx) {
            Free(((TEXT_QRELS_INFO*) queries[idx].q_rel_info)->text_qrels);
        }

        Free(queries->q_rel_info);
        Free(queries);
    }

 protected:
    virtual bool ProcessQuery(REL_INFO* const query,
                              TEXT_QRELS_INFO* const query_pair_list) const {
        query->rel_format = "qrels";
        query->q_rel_info = query_pair_list;

        return true;
    }

    virtual bool ProcessListOfQueryDocumentPairs(
            TEXT_QRELS_INFO* const query_pair_list,
            const size_t num_pairs,
            TEXT_QRELS* const query_document_pairs) const {
        query_pair_list->num_text_qrels = num_pairs;
        query_pair_list->text_qrels = query_document_pairs;

        return true;
    }

    virtual bool ProcessQueryDocumentPair(TEXT_QRELS* const pair,
                                          PyObject* const inner_value) const {
        if (!PyLong_Check(inner_value)) {
            PyErr_SetString(PyExc_TypeError, "Expected relevance to be integer.");

            return false;
        }

        pair->rel = PyLong_AsLong(inner_value);

        return true;
    }
};

class ResultRankingBuilder : public RankingBuilder<RESULTS, TEXT_RESULTS_INFO, TEXT_RESULTS> {
 public:
    virtual void cleanup(const int64 num_queries, RESULTS* queries) const {
        for (size_t idx = 0; idx < num_queries; ++idx) {
            Free(((TEXT_RESULTS_INFO*) queries[idx].q_results)->text_results);
        }

        Free(queries->q_results);
        Free(queries);
    }

 protected:
    virtual bool ProcessQuery(RESULTS* const query,
                              TEXT_RESULTS_INFO* const query_pair_list) const {
        query->run_id = "my_little_test_run";
        query->ret_format = "trec_results";
        query->q_results = query_pair_list;

        return true;
    }

    virtual bool ProcessListOfQueryDocumentPairs(
            TEXT_RESULTS_INFO* const query_pair_list,
            const size_t num_pairs,
            TEXT_RESULTS* const query_document_pairs) const {
        query_pair_list->num_text_results = num_pairs;
        query_pair_list->text_results = query_document_pairs;

        return true;
    }

    virtual bool ProcessQueryDocumentPair(TEXT_RESULTS* const pair,
                                          PyObject* const inner_value) const {
        if (!PyFloat_Check(inner_value)) {
            PyErr_SetString(PyExc_TypeError, "Expected matching score to be float.");

            return false;
        }

        pair->sim = PyFloat_AsDouble(inner_value);

        return true;
    }
};

int qrel_docno_compare(
        const void* raw_a, const void* raw_b) {
    const QrelRankingBuilder::QueryDocumentPairType* a =
        (QrelRankingBuilder::QueryDocumentPairType*) raw_a;
    const QrelRankingBuilder::QueryDocumentPairType* b =
        (QrelRankingBuilder::QueryDocumentPairType*) raw_b;

    return std::string(a->docno).compare(b->docno);
}

static int RelevanceEvaluator_init(RelevanceEvaluator* self, PyObject* args, PyObject* kwds) {
    PyObject* object_relevance_per_qid = NULL;
    PyObject* measures = NULL;

    int32 relevance_level = 1;

    static char* kwlist[] = {
        "query_relevance", "measures", "relevance_level",
        NULL};

    if (!PyArg_ParseTupleAndKeywords(
            args, kwds, "OO|i", kwlist,
            &object_relevance_per_qid,
            &measures,
            &relevance_level)) {
        PyErr_SetString(
            PyExc_TypeError,
            "Expected object_relevance_per_qid dictionary "
            "and measures set.");

        return -1;
    }

    if (!PyDict_Check(object_relevance_per_qid)) {
        PyErr_SetString(PyExc_TypeError,
                        "Argument query_relevance should be of type dictionary.");

        return -1;
    }

    if (!PySet_Check(measures)) {
        PyErr_SetString(PyExc_TypeError,
                        "Argument measures should be of type set.");

        return -1;
    }

    if (relevance_level < 1) {
        PyErr_SetString(PyExc_TypeError,
                        "Argument relevance_level should be positive.");

        return -1;
    }

    // Configure trec_eval session.
    self->epi_.query_flag = 0;
    self->epi_.average_complete_flag = 0;
    self->epi_.judged_docs_only_flag = 0;
    self->epi_.summary_flag = 0;
    self->epi_.relation_flag = 1;
    self->epi_.debug_level = 0;
    self->epi_.debug_query = NULL;
    self->epi_.num_docs_in_coll = 0;
    self->epi_.relevance_level = relevance_level;
    self->epi_.max_num_docs_per_topic = MAXLONG;
    self->epi_.rel_info_format = "qrels";
    self->epi_.results_format = "trec_results";
    self->epi_.zscore_flag = 0;
    self->epi_.meas_arg = NULL;

    // Resolve requested measures.
    Py_INCREF(measures);

    for (size_t measure_idx = 0;
         measure_idx < te_num_trec_measures;
         ++measure_idx) {
        PyObject* const measure_name = PyUnicode_FromFormat(
            "%s", te_trec_measures[measure_idx]->name);

        if (1 == PySet_Contains(measures, measure_name)) {
            self->measures_->insert(measure_idx);
        }

        Py_DECREF(measure_name);
    }

    const bool invalid_measures = self->measures_->size() != PySet_Size(measures);

    Py_DECREF(measures);

    if (invalid_measures) {
        PyErr_SetString(
            PyExc_TypeError,
            "Unable to resolve all measures.");

        return -1;
    }

    // Save reference to object_relevance_per_qid.
    Py_INCREF(object_relevance_per_qid);

    self->object_relevance_per_qid_ = object_relevance_per_qid;
    CHECK_NOTNULL(self->object_relevance_per_qid_);

    // Build internal trec_eval data structures.
    QrelRankingBuilder builder;

    int64 num_queries = 0;
    QrelRankingBuilder::QueryType* queries = NULL;

    if (!builder(self->object_relevance_per_qid_, num_queries, queries)) {
        Py_DECREF(self->object_relevance_per_qid_);

        return -1;
    }

    CHECK_NOTNULL(queries);

    for (size_t query_idx = 0; query_idx < num_queries; ++query_idx) {
        qsort(((TEXT_QRELS_INFO*) queries[query_idx].q_rel_info)->text_qrels,
              ((TEXT_QRELS_INFO*) queries[query_idx].q_rel_info)->num_text_qrels,
              sizeof(QrelRankingBuilder::QueryDocumentPairType),
              qrel_docno_compare);
    }

    self->all_rel_info_.num_q_rels = num_queries;
    self->all_rel_info_.rel_info = queries;

    for (size_t query_idx = 0; query_idx < num_queries; ++query_idx) {
        const std::string& qid = queries[query_idx].qid;
        CHECK_EQ(self->query_id_to_idx_->find(qid), self->query_id_to_idx_->end());

        self->query_id_to_idx_->insert({qid, query_idx});
    }

    return NULL;
}

static void RelevanceEvaluator_dealloc(RelevanceEvaluator* self) {
    if (self->object_relevance_per_qid_ != NULL) {
        Py_DECREF(self->object_relevance_per_qid_);

        self->object_relevance_per_qid_ = NULL;
    }

    if (self->all_rel_info_.num_q_rels >= 0) {
        // Clean up internal trec_eval data structures.
        QrelRankingBuilder builder;
        builder.cleanup(self->all_rel_info_.num_q_rels, self->all_rel_info_.rel_info);

        self->all_rel_info_.num_q_rels = -1;
    }

    delete self->query_id_to_idx_;
    delete self->measures_;
}

int query_document_pair_compare(
        const void* raw_a, const void* raw_b) {
    const ResultRankingBuilder::QueryDocumentPairType* a =
        (ResultRankingBuilder::QueryDocumentPairType*) raw_a;
    const ResultRankingBuilder::QueryDocumentPairType* b =
        (ResultRankingBuilder::QueryDocumentPairType*) raw_b;

    if (a->sim < b->sim) return 1;
    if (a->sim > b->sim) return -1;
    return std::string(a->docno).compare(b->docno);
}

static PyObject* RelevanceEvaluator_evaluate(RelevanceEvaluator* self, PyObject* args) {
    PyObject* object_scores = NULL;

    if (!PyArg_ParseTuple(args, "O", &object_scores) ||
        !PyDict_Check(object_scores)) {
        PyErr_SetString(
            PyExc_TypeError,
            "Argument object scores should be of type dictionary.");

        return NULL;
    }

    ResultRankingBuilder builder;

    int64 num_queries = 0;
    ResultRankingBuilder::QueryType* queries = NULL;

    if (!builder(object_scores, num_queries, queries)) {
        PyErr_SetString(
            PyExc_TypeError,
            "Unable to extract query/object scores.");

        return NULL;
    }

    CHECK_NOTNULL(queries);

    for (size_t query_idx = 0; query_idx < num_queries; ++query_idx) {
        qsort(((TEXT_RESULTS_INFO*) queries[query_idx].q_results)->text_results,
              ((TEXT_RESULTS_INFO*) queries[query_idx].q_results)->num_text_results,
              sizeof(ResultRankingBuilder::QueryDocumentPairType),
              query_document_pair_compare);
    }

    ALL_RESULTS all_results;
    TREC_EVAL q_eval;

    all_results.num_q_results = num_queries;
    all_results.results = queries;

    TREC_EVAL accum_eval;
    accum_eval = (TREC_EVAL) {"all", 0, NULL, 0, 0};

    for (std::set<size_t>::iterator it = self->measures_->begin();
         it != self->measures_->end(); ++it) {
        const size_t measure_idx = *it;

        te_trec_measures[measure_idx]->init_meas(
            &self->epi_,
            te_trec_measures[measure_idx],
            &accum_eval);
    }

    /* Reserve space and initialize q_eval to be copy of accum_eval */
    q_eval.values = Malloc(
        accum_eval.num_values, TREC_EVAL_VALUE);
    CHECK_NOTNULL(q_eval.values);

    memcpy(q_eval.values, accum_eval.values,
           accum_eval.num_values * sizeof (TREC_EVAL_VALUE));

    q_eval.num_values = accum_eval.num_values;
    q_eval.num_queries = 0;

    // Holds the result.
    PyObject* const result = PyDict_New();

    for (size_t result_query_idx = 0;
         result_query_idx < num_queries;
         ++result_query_idx) {
        const std::string qid = all_results.results[result_query_idx].qid;
        std::map<std::string, size_t>::iterator it = self->query_id_to_idx_->find(qid);

        if (it == self->query_id_to_idx_->end()) {
            // Query not found in relevance judgments; skipping.
            continue;
        }

        const size_t eval_query_idx = it->second;
        q_eval.qid = all_results.results[result_query_idx].qid;

        PyObject* const query_measures = PyDict_New();

        for (std::set<size_t>::iterator it = self->measures_->begin();
             it != self->measures_->end(); ++it) {
            const size_t measure_idx = *it;

            // Empty buffer.
            for (int32 value_idx = 0; value_idx < q_eval.num_values; ++value_idx) {
                q_eval.values[value_idx].value = 0;
            }

            // Compute measure.
            te_trec_measures[measure_idx]->calc_meas(
                &self->epi_,
                &self->all_rel_info_.rel_info[eval_query_idx],
                &all_results.results[result_query_idx],
                te_trec_measures[measure_idx],
                &q_eval);

            CHECK_GE(te_trec_measures[measure_idx]->eval_index, 0);

            if (te_trec_measures[measure_idx]->print_single_meas == &te_print_single_meas_a_cut) {
                for (int32 param_idx = 0;
                     param_idx < te_trec_measures[measure_idx]->meas_params->num_params;
                     ++param_idx) {
                    PyDict_SetItemAndSteal(
                        query_measures,
                        PyUnicode_FromString(
                            q_eval.values[te_trec_measures[measure_idx]->eval_index + param_idx].name),
                        PyFloat_FromDouble(
                            q_eval.values[te_trec_measures[measure_idx]->eval_index + param_idx].value));
                }
            } else {
                PyDict_SetItemAndSteal(
                    query_measures,
                    PyUnicode_FromString(te_trec_measures[measure_idx]->name),
                    PyFloat_FromDouble(
                        q_eval.values[te_trec_measures[measure_idx]->eval_index].value));
            }

            // Add the measure value to the aggregate.
            // This call is probably unnecessary as we don't rely on trec_eval's averaging mechanism.
            te_trec_measures[measure_idx]->acc_meas(
                &self->epi_,
                te_trec_measures[measure_idx],
                &q_eval,
                &accum_eval);

            if (__DEVELOPMENT) {
                // Print.
                te_trec_measures[measure_idx]->print_single_meas(
                    &self->epi_,
                    te_trec_measures[measure_idx],
                    &q_eval);
            }

            accum_eval.num_queries++;
        }

        PyDict_SetItemAndSteal(
            result,
            PyUnicode_FromString(qid.c_str()),
            query_measures);
    }

    for (std::set<size_t>::iterator it = self->measures_->begin();
         it != self->measures_->end(); ++it) {
        const size_t measure_idx = *it;

        // Cleanup; nothing gets printed as self->epi_.summary_flag == 0.
        te_trec_measures[measure_idx]->print_final_and_cleanup_meas 
            (&self->epi_, te_trec_measures[measure_idx],  &accum_eval);
    }

    // Clean.
    builder.cleanup(num_queries, queries);

    Free(q_eval.values);
    Free(accum_eval.values);

    return result;
}

static PyMemberDef RelevanceEvaluator_members[] = {
    {NULL}  /* Sentinel */
};

static PyMethodDef RelevanceEvaluator_methods[] = {
    {"evaluate", (PyCFunction) RelevanceEvaluator_evaluate, METH_VARARGS,
     "Evaluate a ranking according to query relevance."},
    {NULL}  /* Sentinel */
};

static PyModuleDef PyTrecEvalModule = {
    PyModuleDef_HEAD_INIT,
    "pytrec_eval_ext",
    "Python interface to TREC Eval.",
    -1,
    RelevanceEvaluator_methods,
    NULL, NULL, NULL, NULL
};

PyMODINIT_FUNC PyInit_pytrec_eval_ext(void) {
    RelevanceEvaluatorType = {
        PyVarObject_HEAD_INIT(NULL, 0)
        "pytrec_eval.RelevanceEvaluator",   /* tp_name */
        sizeof(RelevanceEvaluator),         /* tp_basicsize */
        0,                         /* tp_itemsize */
        (destructor) RelevanceEvaluator_dealloc, /* tp_dealloc */
        0,                         /* tp_print */
        0,                         /* tp_getattr */
        0,                         /* tp_setattr */
        0,                         /* tp_reserved */
        0,                         /* tp_repr */
        0,                         /* tp_as_number */
        0,                         /* tp_as_sequence */
        0,                         /* tp_as_mapping */
        0,                         /* tp_hash */
        0,                         /* tp_call */
        0,                         /* tp_str */
        0,                         /* tp_getattro */
        0,                         /* tp_setattro */
        0,                         /* tp_as_buffer */
        Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE, /* tp_flags */
        "RelevanceEvaluator objects",       /* tp_doc */
        0,                         /* tp_traverse */
        0,                         /* tp_clear */
        0,                         /* tp_richcompare */
        0,                         /* tp_weaklistoffset */
        0,                         /* tp_iter */
        0,                         /* tp_iternext */
        RelevanceEvaluator_methods,         /* tp_methods */
        RelevanceEvaluator_members,         /* tp_members */
        0,                         /* tp_getset */
        0,                         /* tp_base */
        0,                         /* tp_dict */
        0,                         /* tp_descr_get */
        0,                         /* tp_descr_set */
        0,                         /* tp_dictoffset */
        (initproc) RelevanceEvaluator_init, /* tp_init */
        0,                         /* tp_alloc */
        RelevanceEvaluator_new,             /* tp_new */
    };

    if (PyType_Ready(&RelevanceEvaluatorType) < 0) {
        return NULL;
    }

    PyObject* const module = PyModule_Create(&PyTrecEvalModule);

    if (module == NULL) {
        return NULL;
    }

    Py_INCREF(&RelevanceEvaluatorType);
    PyModule_AddObject(module, "RelevanceEvaluator", (PyObject*) &RelevanceEvaluatorType);

    CHECK_EQ(te_trec_measure_nicknames[2].name, "all_trec");

    // Add set of all supported relevance measures.
    PyObject* const measures = PySet_New(NULL);

    size_t measure_idx = 0;
    while (te_trec_measure_nicknames[2].name_list[measure_idx] != NULL) {
        PySet_Add(
            measures,
            PyUnicode_FromFormat(
                "%s", te_trec_measure_nicknames[2].name_list[measure_idx]));

        ++measure_idx;
    }

    PyModule_AddObject(module, "supported_measures", measures);

    return module;
}
