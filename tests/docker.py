import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

import docker
from golem_task_api import constants, TaskApiService


def is_docker_available():
    try:
        docker.from_env().ping()
    except Exception:  # pylint: disable=broad-except
        return False
    return True


def run_docker_container(
        image: str,
        work_dir: Path,
        command: str,
        port: int
):
    if sys.platform == 'linux':
        ports = {}
    else:
        ports = {port: port}

    docker_client = docker.from_env()
    return docker_client.containers.run(
        image=image,
        command=command,
        volumes={
            str(work_dir): {
                'bind': f'/{constants.WORK_DIR}',
                'mode': 'rw',
            }
        },
        user=os.getuid(),
        ports=ports,
        detach=True,
    )


def get_docker_container_port_mapping(
        container_id: str,
        port: int,
        vm_name: str = 'default',
) -> Tuple[str, int]:
    api_client = docker.APIClient()
    container_config = api_client.inspect_container(container_id)
    net_config = container_config['NetworkSettings']

    if sys.platform == 'darwin':
        ip_address = '127.0.0.1'
    elif sys.platform == "win32":
        vm_ip = subprocess.check_output(['docker-machine', 'ip', vm_name])
        ip_address = vm_ip.decode('utf-8').strip()
    else:
        ip_address = net_config['Networks']['bridge']['IPAddress']

    assert ip_address, "Unable to read the IP address"
    port = int(net_config['Ports'][f'{port}/tcp'][0]['HostPort'])
    return ip_address, port


class DockerTaskApiService(TaskApiService):

    def __init__(
            self,
            image: str,
            work_dir: Path
    ) -> None:
        self._image = image
        self._work_dir = work_dir
        self._container = None

    async def start(
            self,
            command: str,
            port: int
    ) -> Tuple[str, int]:
        self._container = run_docker_container(
            self._image,
            self._work_dir,
            command,
            port)

        return get_docker_container_port_mapping(self._container.id, port)

    async def stop(self) -> None:
        if not self.running():
            return
        self._container.stop()

    def running(self) -> bool:
        try:
            self._container.reload()
        except docker.errors.NotFound:
            return False
        return self._container.status not in ['exited', 'error']

    async def wait_until_shutdown_complete(self) -> None:
        if not self.running():
            return

        logs = self._container.logs().decode('utf-8')
        try:
            self._container.remove(force=True)
        finally:
            print(logs)
