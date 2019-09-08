import abc
import asyncio
import contextlib
import os
import socket
import time

from pathlib import Path
from typing import List

import pytest

from golem_task_api import TaskApiService
from golem_task_api.client import ShutdownException
from golem_task_api.testutils import TaskLifecycleUtil


@pytest.fixture
def task_lifecycle_util(tmpdir):
    print('workdir:', tmpdir)
    return TaskLifecycleUtil(Path(tmpdir))


class SimulationBase(abc.ABC):
    @abc.abstractmethod
    def _get_task_api_service(
            self,
            work_dir: Path,
    ) -> TaskApiService:
        pass

    @staticmethod
    def _get_task_params(
            subtasks_count: int = 1,
            difficulty: int = 10,
    ):
        return {
            "subtasks_count": subtasks_count,
            "difficulty": difficulty,
            "resources": [
                "task.input",
            ]
        }

    @staticmethod
    def _get_task_resources() -> List[Path]:
        return [Path(__file__).parent / 'resources' / 'task.input']

    @staticmethod
    def _check_results(
            req_task_outputs_dir: Path,
    ) -> None:
        contents = os.listdir(req_task_outputs_dir)
        assert len(contents) > 0

    async def _simulate_task(
            self,
            max_subtasks_count: int,
            task_params: dict,
            task_lifecycle_util: TaskLifecycleUtil,
            interruptible: bool = False,
    ):
        try:
            await task_lifecycle_util.simulate_task(
                self._get_task_api_service,
                max_subtasks_count,
                task_params,
                self._get_task_resources(),
            )
        except Exception as exc:
            if not interruptible:
                raise
        else:
            self._check_results(task_lifecycle_util.req_subtask_outputs_dir)

    @pytest.mark.asyncio
    async def test_discard(
            self,
            task_lifecycle_util: TaskLifecycleUtil,
    ):
        max_subtasks_count = 4
        task_params = self._get_task_params(subtasks_count=4)

        async with task_lifecycle_util.init_requestor(
                self._get_task_api_service) as requestor_client:

            task_id = 'test_discard_task_id123'
            await task_lifecycle_util.create_task(
                task_id,
                max_subtasks_count,
                self._get_task_resources(),
                task_params,
            )
            task_lifecycle_util.init_provider(
                self._get_task_api_service,
                task_id,
            )
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id)
            self._check_results(task_lifecycle_util.req_task_outputs_dir)

            # Discard all
            discarded_subtask_ids = await requestor_client.discard_subtasks(
                task_id,
                subtask_ids)
            assert discarded_subtask_ids == subtask_ids
            assert await requestor_client.has_pending_subtasks(task_id)
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id)
            self._check_results(task_lifecycle_util.req_task_outputs_dir)

            # Discard single
            discarded_subtask_ids = await requestor_client.discard_subtasks(
                task_id,
                subtask_ids[:1],
            )
            assert discarded_subtask_ids == subtask_ids[:1]
            assert await requestor_client.has_pending_subtasks(task_id)
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id)
            assert len(subtask_ids) == 1
            self._check_results(
                task_lifecycle_util.req_task_outputs_dir,
            )

    @pytest.mark.asyncio
    async def test_provider_single_shutdown(self, task_lifecycle_util):
        print("init_provider")
        task_lifecycle_util.init_provider(self._get_task_api_service, 'task123')
        print("start_provider")
        await task_lifecycle_util.start_provider()
        print("shutdown 1")
        await task_lifecycle_util.shutdown_provider()
        print("done!")

    @pytest.mark.asyncio
    async def test_provider_double_shutdown(self, task_lifecycle_util):
        print("init_provider")
        task_lifecycle_util.init_provider(self._get_task_api_service, 'task123')
        print("start_provider")
        await task_lifecycle_util.start_provider()
        print("shutdown 1")
        await task_lifecycle_util.shutdown_provider()
        print("shutdown 2")
        await task_lifecycle_util.shutdown_provider()
        print("done!")

    @pytest.mark.asyncio
    async def test_provider_shutdown_in_benchmark(self, task_lifecycle_util):

        async def _shutdown():
            await asyncio.sleep(3.)
            await task_lifecycle_util.shutdown_provider()

        benchmark_defer = asyncio.ensure_future(self._simulate_task(
            1,
            self._get_task_params(difficulty=256),
            task_lifecycle_util,
            interruptible=True
        ))
        shutdown_defer = asyncio.ensure_future(_shutdown())

        await asyncio.wait(
            [shutdown_defer, benchmark_defer],
            return_when=asyncio.ALL_COMPLETED,
            timeout=5.)
