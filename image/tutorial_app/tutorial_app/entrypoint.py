import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import golem_task_api as api

from golem_task_api.dirutils import ProviderTaskDir, RequestorTaskDir
from golem_task_api.enums import VerifyResult
from golem_task_api.structs import Subtask, Task

from .commands import (
    abort_task,
    abort_subtask,
    create_task,
    next_subtask,
    verify_subtask,
    discard_subtasks,
    has_pending_subtasks,
    compute_subtask,
    run_benchmark,
)


class RequestorHandler(api.RequestorAppHandler):
    async def create_task(
            self,
            task_work_dir: RequestorTaskDir,
            max_subtasks_count: int,
            task_params: dict,
    ) -> Task:
        return await create_task(task_work_dir, max_subtasks_count, task_params)

    async def next_subtask(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str,
            opaque_node_id: str,
    ) -> Optional[Subtask]:
        return await next_subtask(task_work_dir, subtask_id)

    async def verify(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> Tuple[VerifyResult, Optional[str]]:
        return await verify_subtask(task_work_dir, subtask_id)

    async def discard_subtasks(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_ids: List[str],
    ) -> List[str]:
        return await discard_subtasks(task_work_dir, subtask_ids)

    async def has_pending_subtasks(
            self,
            task_work_dir: RequestorTaskDir,
    ) -> bool:
        return await has_pending_subtasks(task_work_dir)

    async def run_benchmark(
            self,
            work_dir: RequestorTaskDir,
    ) -> float:
        return await run_benchmark()

    async def abort_task(
            self,
            task_work_dir: RequestorTaskDir,
    ) -> None:
        return await abort_task(task_work_dir)

    async def abort_subtask(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> None:
        return await abort_subtask(task_work_dir, subtask_id)


class ProviderHandler(api.ProviderAppHandler):
    async def compute(
            self,
            task_work_dir: ProviderTaskDir,
            subtask_id: str,
            subtask_params: dict,
    ) -> Path:
        return await compute_subtask(task_work_dir, subtask_id, subtask_params)

    async def run_benchmark(
            self,
            work_dir: Path,
    ) -> float:
        return await run_benchmark()


async def main():
    await api.entrypoint(
        work_dir=Path(f'/{api.constants.WORK_DIR}'),
        argv=sys.argv[1:],
        requestor_handler=RequestorHandler(),
        provider_handler=ProviderHandler(),
    )


if __name__ == '__main__':
    LOOP = asyncio.get_event_loop()
    LOOP.run_until_complete(main())
