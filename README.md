pytrec_eval
===========

pytrec\_eval is a Python interface to TREC's evaluation tool, [trec\_eval](https://github.com/usnistgov/trec_eval). It is an attempt to stop the cultivation of custom implementations of Information Retrieval evaluation measures for the Python programming language.

Requirements
------------

The module was developed using Python 3.5. You need a Python distribution that comes with development headers. In addition to the default Python modules, [numpy](http://www.numpy.org) and [scipy](https://www.scipy.org) are required.

Installation
------------

Installation is simple and should be relatively painless if your Python environment is functioning correctly (see below for FAQs).

	pip install pytrec_eval
	
Examples
--------

Check out the examples that simulate the standard [trec\_eval front-end](examples/trec_eval.py) and that compute [statistical significance](examples/statistical_significance.py) between two runs.

To get a grasp of how simple the module is to use, check this out:

	import pytrec_eval
	import json
	
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
	    'q2': {
	        'd1': 1.5,
	        'd2': 0.2,
	        'd3': 0.5,
	    }
	}
	
	evaluator = pytrec_eval.RelevanceEvaluator(
	    qrel, {'map', 'ndcg'})
	
	print(json.dumps(evaluator.evaluate(run), indent=1))
	
The above snippet will return a data structure that contains the requested evaluation measures for queries `q1` and `q2`:

	{
	    'q1': {
	        'ndcg': 0.5,
	        'map': 0.3333333333333333
	    },
	    'q2': {
	        'ndcg': 0.6934264036172708,
	        'map': 0.5833333333333333
	    }
	}
	
For more like this, see the example that uses [parametrized evaluation measures](examples/simple_cut.py).

Frequently Asked Questions
--------------------------

Since the module's initial release, no questions have been asked so frequently that they deserve a spot in this section.

Citation
--------

If you use pytrec\_eval to produce results for your scientific publication, please refer to our SIGIR paper:

```
@inproceedings{VanGysel2018pytreceval,
  title={Pytrec\_eval: An Extremely Fast Python Interface to trec\_eval},
  author={Van Gysel, Christophe and de Rijke, Maarten},
  publisher={ACM},
  booktitle={SIGIR},
  year={2018},
}
```

License
-------

pytrec\_eval is licensed under the [MIT license](LICENSE). Please note that [trec\_eval](https://github.com/usnistgov/trec_eval) is licensed separately. If you modify pytrec\_eval in any way, please link back to this repository.