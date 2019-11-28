# pylint: disable=unused-import, redefined-outer-name
import shlex
import subprocess
from pathlib import Path

from golem_task_api import TaskApiService
from golem_task_api.testutils.dockertaskapiservice import DockerTaskApiService

from tutorial_app import constants

from .base import (
    SimulationBase,
    task_lifecycle_util,
)


class TestDocker(SimulationBase):
    IMAGE = f"{constants.DOCKER_IMAGE}:test"

    @classmethod
    def setup_class(cls):
        path = Path(__file__).parent.parent / 'image'
        subprocess.check_call(shlex.split(
            f'docker build -t {cls.IMAGE} -f {path / "Dockerfile"} {path}'
        ))

    def _get_task_api_service(
            self,
            work_dir: Path,
    ) -> TaskApiService:
        return DockerTaskApiService(
            image=self.IMAGE,
            work_dir=work_dir)
