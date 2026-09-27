"""Shared fixtures.

Synthetic signals are built from `neurokit2.ecg_simulate` with a fixed seed, so
the unit tests are deterministic and need no downloaded data. Tests that do need
a dataset are marked and skip cleanly when it is absent.
"""

from __future__ import annotations

import numpy as np
import pytest

from cardiosignal import config
from cardiosignal.types import Recording

SIM_SEED = 11
# Per-lead gains, including two negative ones so aVR-style inverted complexes
# are exercised rather than only upright ones.
LEAD_GAINS = np.array([0.9, 1.2, 0.35, -1.05, 0.5, 0.85, -0.55, 0.75, 1.15, 1.35, 1.05, 0.7])


@pytest.fixture(scope="session")
def simulate():
    import neurokit2 as nk

    def _simulate(heart_rate: int = 72, duration: float = 10.0, seed: int = SIM_SEED) -> np.ndarray:
        return nk.ecg_simulate(
            duration=duration,
            sampling_rate=config.FS,
            heart_rate=heart_rate,
            random_state=seed,
        )

    return _simulate


@pytest.fixture(scope="session")
def single_lead(simulate) -> np.ndarray:
    return simulate()


@pytest.fixture(scope="session")
def twelve_lead(simulate) -> np.ndarray:
    return simulate()[:, None] * LEAD_GAINS[None, :]


@pytest.fixture(scope="session")
def recording(twelve_lead) -> Recording:
    return Recording(
        ecg_id=900001, source="synthetic", signal=twelve_lead, age=57, sex="male"
    )


@pytest.fixture(scope="session")
def measured(recording):
    from cardiosignal.engine import measure_record

    return measure_record(recording)


def _dataset_or_skip(module) -> None:
    if not module.is_available():
        pytest.skip(f"{module.__name__} data not downloaded")


@pytest.fixture()
def ludb_records():
    from cardiosignal.io import ludb

    _dataset_or_skip(ludb)
    return ludb.list_records()


@pytest.fixture()
def qtdb_records():
    from cardiosignal.io import qtdb

    _dataset_or_skip(qtdb)
    return qtdb.list_records()
