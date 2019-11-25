# pylint: disable=unused-import, redefined-outer-name
from pathlib import Path

import docker
import pytest

from golem_task_api import TaskApiService

from tutorial_app import constants

from .base import (
    SimulationBase,
    task_lifecycle_util,
)
from .docker import (
    is_docker_available,
    DockerTaskApiService,
)


@pytest.mark.skipif(not is_docker_available(), reason='docker not available')
class TestDocker(SimulationBase):
    IMAGE = f"{constants.DOCKER_IMAGE}:test"

    @classmethod
    def setup_class(cls):
        docker.from_env().images.build(
            path=str(Path(__file__).parent.parent / 'image'),
            tag=cls.IMAGE,
        )

    def _get_task_api_service(
            self,
            work_dir: Path,
    ) -> TaskApiService:
        return DockerTaskApiService(
            image=self.IMAGE,
            work_dir=work_dir)
