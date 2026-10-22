"""The Renascitur History Engine."""

import os
import sys

# Determinism: BLAS must run single-threaded, and the limits only work if set before NumPy loads.
THREAD_VARS = ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS")
NUMPY_LOADED_FIRST = "numpy" in sys.modules and any(os.environ.get(v) != "1" for v in THREAD_VARS)
for _var in THREAD_VARS:
    os.environ.setdefault(_var, "1")

__version__ = "0.1.0"
