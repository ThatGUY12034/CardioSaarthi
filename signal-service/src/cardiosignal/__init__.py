"""CardioSaarthi Layer 1 — deterministic ECG measurement engine and renderer.

Design principle for the whole platform: clinical facts are computed, never
generated. Every value this package produces is closed-form arithmetic over the
raw waveform. Diagnoses are inherited from the dataset's cardiologist
annotations. No model is consulted anywhere in this package.
"""

from cardiosignal.config import SCHEMA_VERSION

__version__ = "0.1.0"
__all__ = ["SCHEMA_VERSION", "__version__"]
