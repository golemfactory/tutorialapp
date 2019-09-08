import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import golem_task_api as api

from tutorial_app.commands import (
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
            task_work_dir: Path,
            max_subtasks_count: int,
            task_params: dict,
    ) -> None:
        return await create_task(task_work_dir, max_subtasks_count, task_params)

    async def next_subtask(
            self,
            task_work_dir: Path,
    ) -> api.structs.Subtask:
        return await next_subtask(task_work_dir)

    async def verify(
            self,
            task_work_dir: Path,
            subtask_id: str,
    ) -> Tuple[bool, Optional[str]]:
        return await verify_subtask(task_work_dir, subtask_id)

    async def discard_subtasks(
            self,
            task_work_dir: Path,
            subtask_ids: List[str],
    ) -> List[str]:
        return await discard_subtasks(task_work_dir, subtask_ids)

    async def has_pending_subtasks(
            self,
            task_work_dir: Path,
    ) -> bool:
        return await has_pending_subtasks(task_work_dir)

    async def run_benchmark(self, work_dir: Path) -> float:
        return await run_benchmark(work_dir)


class ProviderHandler(api.ProviderAppHandler):
    async def compute(
            self,
            task_work_dir: Path,
            subtask_id: str,
            subtask_params: dict,
    ) -> Path:
        return await compute_subtask(task_work_dir, subtask_id, subtask_params)

    async def run_benchmark(self, work_dir: Path) -> float:
        return await run_benchmark(work_dir)


async def main():
    await api.entrypoint(
        work_dir=Path(f'/{api.constants.WORK_DIR}'),
        argv=sys.argv[1:],
        requestor_handler=RequestorHandler(),
        provider_handler=ProviderHandler(),
    )


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
