import hashlib
import time
from typing import Tuple

import golem_task_api as api

_MAX_NONCE: int = 2 ** 256


def compute(
        input_data: str,
        difficulty: int,
) -> Tuple[str, int]:
    target = 2 ** (256 - difficulty)
    for nonce in range(_MAX_NONCE):
        if api.threading.Executor.is_shutting_down():
            raise RuntimeError("Interrupted")
        hash_result = _sha256(input_data + str(nonce))
        if int(hash_result, 16) < target:
            return hash_result, nonce
    raise RuntimeError("Solution not found")


def verify(
        input_data: str,
        difficulty: int,
        against_result: str,
        against_nonce: int,
) -> None:
    target = 2 ** (256 - difficulty)
    result = _sha256(input_data + str(against_nonce))
    if against_result != result:
        raise ValueError(f"Invalid result hash: {against_result} != {result}")
    if int(result, 16) >= target:
        raise ValueError(f"Invalid result hash difficulty")


def benchmark(
        iterations: int = 2 ** 8,
) -> float:
    started = time.time()
    for nonce in range(iterations):
        if api.threading.Executor.is_shutting_down():
            raise RuntimeError("Interrupted")
        hash_result = _sha256('benchmark' + str(nonce))
    elapsed = time.time() - started
    if elapsed:
        return 1000. / elapsed
    return 1000.


def _sha256(input_data: str) -> str:
    input_bytes = input_data.encode('utf-8')
    return hashlib.sha256(input_bytes).hexdigest()
