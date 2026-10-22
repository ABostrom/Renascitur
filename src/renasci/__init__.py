"""The Renascitur History Engine."""

import os

# Determinism: BLAS must run single-threaded, and this has to happen before NumPy loads.
for _var in ("OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "OMP_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

__version__ = "0.1.0"
