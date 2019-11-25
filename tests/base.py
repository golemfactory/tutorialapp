# pylint: disable=unused-import, redefined-outer-name
import abc
import asyncio

from pathlib import Path
from typing import List

import pytest

from golem_task_api import TaskApiService
from golem_task_api.testutils import TaskLifecycleUtil


@pytest.fixture
def task_lifecycle_util(tmpdir):
    return TaskLifecycleUtil(Path(tmpdir))


class SimulationBase(abc.ABC):

    @abc.abstractmethod
    def _get_task_api_service(
            self,
            work_dir: Path,
    ) -> TaskApiService:
        pass

    @staticmethod
    def _get_app_params(
            difficulty: int = 10,
    ):
        return {
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
        assert list(req_task_outputs_dir.iterdir())

    async def _simulate_task(
            self,
            max_subtasks_count: int,
            task_params: dict,
            task_lifecycle_util: TaskLifecycleUtil,
    ):
        task_dir = await task_lifecycle_util.simulate_task(
            self._get_task_api_service,
            max_subtasks_count,
            task_params,
            self._get_task_resources(),
        )
        self._check_results(task_dir.task_outputs_dir)

    @pytest.mark.asyncio
    async def test_discard(
            self,
            task_lifecycle_util: TaskLifecycleUtil,
    ):
        max_subtasks_count = 4
        app_params = self._get_app_params()

        async with task_lifecycle_util.init_requestor(
                self._get_task_api_service) as requestor_client:

            task_id = '0xf00f'
            opaque_node_id = '0xd00d'

            await task_lifecycle_util.create_task(
                task_id,
                max_subtasks_count,
                self._get_task_resources(),
                app_params)

            task_lifecycle_util.init_provider(
                self._get_task_api_service,
                task_id)
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id,
                opaque_node_id)
            task_dir = task_lifecycle_util.req_dir.task_dir(task_id)
            self._check_results(task_dir.task_outputs_dir)

            # Discard all
            discarded_subtask_ids = await requestor_client.discard_subtasks(
                task_id,
                subtask_ids)
            assert discarded_subtask_ids == subtask_ids
            assert await requestor_client.has_pending_subtasks(task_id)
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id,
                opaque_node_id)
            self._check_results(task_dir.task_outputs_dir)

            # Discard single
            discarded_subtask_ids = await requestor_client.discard_subtasks(
                task_id,
                subtask_ids[:1],
            )
            assert discarded_subtask_ids == subtask_ids[:1]
            assert await requestor_client.has_pending_subtasks(task_id)
            subtask_ids = await task_lifecycle_util.compute_remaining_subtasks(
                task_id,
                opaque_node_id)
            assert len(subtask_ids) == 1
            self._check_results(task_dir.task_outputs_dir)

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
            self._get_app_params(difficulty=256),
            task_lifecycle_util
        ))
        shutdown_defer = asyncio.ensure_future(_shutdown())

        await asyncio.wait(
            [shutdown_defer, benchmark_defer],
            return_when=asyncio.ALL_COMPLETED,
            timeout=5.)

    @pytest.mark.asyncio
    async def test_requestor_benchmark(self, task_lifecycle_util):
        async with task_lifecycle_util.init_requestor(
                self._get_task_api_service):
            score = await task_lifecycle_util.requestor_client.run_benchmark()
            assert score > 0

    @pytest.mark.asyncio
    async def test_provider_benchmark(self, task_lifecycle_util):
        task_id = '0xf00f'
        task_lifecycle_util.init_provider(self._get_task_api_service, task_id)
        await task_lifecycle_util.start_provider()
        score = await task_lifecycle_util.provider_client.run_benchmark()
        assert score > 0
