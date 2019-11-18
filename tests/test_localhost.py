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
