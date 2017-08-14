import os
from distutils.core import setup, Extension

TREC_EVAL_DIR = os.path.realpath(
    os.path.join(__file__, '..', 'trec_eval'))

TREC_EVAL_SRC = []

for filename in os.listdir(TREC_EVAL_DIR):
    if filename.endswith('.c'):
        TREC_EVAL_SRC.append(os.path.join(TREC_EVAL_DIR, filename))

pytrec_eval_ext = Extension(
    'pytrec_eval_ext',
    sources=['src/pytrec_eval.cpp'] + TREC_EVAL_SRC,
    libraries=['m', 'stdc++'],
    include_dirs=[TREC_EVAL_DIR],
    undef_macros=['NDEBUG'],
    extra_compile_args=['-g', '-Wall'],
    define_macros=[('VERSIONID', '\"pytrec_eval\"'),
                   ('_GLIBCXX_USE_CXX11_ABI', '0'),
                   ('P_NEEDS_GNU_CXX_NAMESPACE', '1')])

setup(name='pytrec_eval',
      version='alpha',
      description='Provides Python bindings for popular Information Retrieval '
                  'measures implemented within trec_eval.',
      author='Christophe Van Gysel',
      author_email='cvangysel@uva.nl',
      ext_modules=[pytrec_eval_ext],
      packages=['pytrec_eval'],
      package_dir={'pytrec_eval': 'py'},
      url='https://github.com/cvangysel/pytrec_eval',
      keywords=['trec_eval', 'information retrieval', 'evaluation', 'ranking'],
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python',
          'Programming Language :: C++',
          'Intended Audience :: Science/Research',
          'Operating System :: POSIX :: Linux',
          'Topic :: Text Processing :: General',
      ])
