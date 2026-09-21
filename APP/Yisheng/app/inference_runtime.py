"""Process-local defaults for the bundled Windows inference runtime."""
from __future__ import annotations

import os
import sys


def configure_inference_runtime() -> None:
    """Keep a short worker spin for inference, then yield CPU to foreground apps.

    Called by app.__init__ before importing NumPy, CTranslate2 or faster-whisper.
    Intel OpenMP otherwise spins for 200 ms after a parallel region, even while
    we wait for the next utterance. 1 ms preserves fast repeated operations but
    stops long idle spins. Fully passive/0 ms slowed inference in local tests.

    Do not change machine/user environment settings, thread counts, models, or
    any explicit OpenMP wait policy supplied by the caller.
    """
    if sys.platform != "win32":
        return
    if any(name in os.environ for name in ('KMP_BLOCKTIME', 'OMP_WAIT_POLICY', 'KMP_LIBRARY')):
        return
    os.environ.setdefault('KMP_BLOCKTIME', '1')
