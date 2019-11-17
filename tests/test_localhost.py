from pathlib import Path

import pytest
from golem_task_api import TaskApiService
from golem_task_api.testutils import InlineTaskApiService

from tutorial_app.entrypoint import (
    ProviderHandler,
    RequestorHandler,
)

from .base import (
    SimulationBase,
    task_lifecycle_util,
)


class TestLocalhost(SimulationBase):

    def _get_task_api_service(
            self,
            work_dir: Path,
    ) -> TaskApiService:
        return InlineTaskApiService(
            work_dir,
            requestor_handler=RequestorHandler(),
            provider_handler=ProviderHandler(),
        )

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
