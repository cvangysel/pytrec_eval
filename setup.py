"""Sets up pytrec_eval."""

from setuptools import setup, Extension
import os
import sys
import tempfile

REMOTE_TREC_EVAL_URI = 'https://github.com/usnistgov/trec_eval/archive/v9.0.8.tar.gz'

REMOTE_TREC_EVAL_TLD_NAME = 'trec_eval-9.0.8'

LOCAL_TREC_EVAL_DIR = os.path.realpath(
    os.path.join(__file__, '..', 'trec_eval'))

TREC_EVAL_SRC = []

with tempfile.TemporaryDirectory() as tmp_dir:
    if os.path.isfile(os.path.join(LOCAL_TREC_EVAL_DIR, 'trec_eval.h')):
        # Use local version.
        trec_eval_dir = LOCAL_TREC_EVAL_DIR
    else:  # Fetch remote version.
        print('Fetching trec_eval from {}.'.format(REMOTE_TREC_EVAL_URI))

        import io
        import urllib.request

        response = urllib.request.urlopen(REMOTE_TREC_EVAL_URI)
        mmap_f = io.BytesIO(response.read())

        if REMOTE_TREC_EVAL_URI.endswith('.zip'):
            import zipfile

            trec_eval_archive = zipfile.ZipFile(mmap_f)
        elif REMOTE_TREC_EVAL_URI.endswith('.tar.gz'):
            import tarfile

            trec_eval_archive = tarfile.open(fileobj=mmap_f)

        trec_eval_archive.extractall(tmp_dir)

        trec_eval_dir = os.path.join(tmp_dir, REMOTE_TREC_EVAL_TLD_NAME)

    for filename in os.listdir(trec_eval_dir):
        if filename.endswith('.c') and not filename == "trec_eval.c":
            TREC_EVAL_SRC.append(os.path.join(trec_eval_dir, filename))
    #include the windows/ subdirectory on windows machines
    if sys.platform == 'win32':
        for filename in os.listdir(os.path.join(trec_eval_dir, "windows")):
            if filename.endswith('.c') and not filename == "trec_eval.c":
                TREC_EVAL_SRC.append(os.path.join(trec_eval_dir, "windows", filename))

    pytrec_eval_ext = Extension(
        'pytrec_eval_ext',
        sources=['src/pytrec_eval.cpp'] + TREC_EVAL_SRC,
        #windows doesnt need libm
        libraries=[] if sys.platform == 'win32' else ['m', 'stdc++'],
        include_dirs=[trec_eval_dir, os.path.join(trec_eval_dir, "windows")] if sys.platform == 'win32' else [trec_eval_dir],
        undef_macros=['NDEBUG'],
        extra_compile_args=['-g', '-Wall', '-O3'],
        define_macros=[('VERSIONID', '\"pytrec_eval\"'),
                       ('_GLIBCXX_USE_CXX11_ABI', '0'),
                       ('P_NEEDS_GNU_CXX_NAMESPACE', '1')])

    setup(name='pytrec_eval',
          version='0.5',
          description='Provides Python bindings for popular '
                      'Information Retrieval measures implemented '
                      'within trec_eval.',
          author='Christophe Van Gysel',
          author_email='cvangysel@uva.nl',
          ext_modules=[pytrec_eval_ext],
          packages=['pytrec_eval'],
          package_dir={'pytrec_eval': 'py'},
          python_requires='>=3',
          url='https://github.com/cvangysel/pytrec_eval',
          download_url='https://github.com/cvangysel/pytrec_eval/tarball/0.5',
          keywords=[
              'trec_eval',
              'information retrieval',
              'evaluation',
              'ranking',
          ],
          classifiers=[
              'Development Status :: 3 - Alpha',
              'License :: OSI Approved :: MIT License',
              'Programming Language :: Python',
              'Programming Language :: C++',
              'Intended Audience :: Science/Research',
              'Operating System :: POSIX :: Linux',
              'Topic :: Text Processing :: General',
          ])
