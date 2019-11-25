import shutil
import uuid
import zipfile

from pathlib import Path
from typing import List, Optional, Tuple

import golem_task_api as api
from golem_task_api.apputils.task import SubtaskStatus
from golem_task_api.dirutils import RequestorTaskDir, ProviderTaskDir
from golem_task_api.enums import VerifyResult
from golem_task_api.envs import DOCKER_CPU_ENV_ID
from golem_task_api.structs import Infrastructure, Task

from . import proof_of_work
from .task_manager import TaskManager, PREREQUISITES


def _read_zip_contents(path: Path) -> str:
    with zipfile.ZipFile(path, 'r') as file:
        input_file = file.namelist()[0]
        with file.open(input_file) as inner_file:
            return inner_file.read().decode('utf-8')


async def create_task(
        work_dir: RequestorTaskDir,
        max_part_count: int,
        task_params: dict,
) -> Task:
    # validate the 'difficulty' parameter
    difficulty = int(task_params['difficulty'])
    if difficulty < 0:
        raise ValueError(f"difficulty={difficulty}")
    # check whether resources were provided
    resources = task_params.get('resources')
    if not resources:
        raise ValueError(f"resources={resources}")
    # read the input file
    try:
        task_input_file = work_dir.task_inputs_dir / resources[0]
        input_data = task_input_file.read_text('utf-8')
    except (IOError, StopIteration) as exc:
        raise ValueError(f"Invalid resource file: {resources} ({exc})")
    # create the task
    task_manager = TaskManager(work_dir)
    task_manager.create_task(max_part_count)
    # update the parts with input data
    for num in range(max_part_count):
        part = task_manager.get_part(num)
        part.input_data = input_data + str(uuid.uuid4())
        part.difficulty = difficulty + (difficulty % 2)
        part.save()

    return Task(
        env_id=DOCKER_CPU_ENV_ID,
        prerequisites=PREREQUISITES,
        inf_requirements=Infrastructure(min_memory_mib=50.))


async def abort_task(
        work_dir: RequestorTaskDir,
) -> None:
    task_manager = TaskManager(work_dir)
    task_manager.abort_task()


async def abort_subtask(
        work_dir: RequestorTaskDir,
        subtask_id: str
) -> None:
    task_manager = TaskManager(work_dir)
    task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)


async def next_subtask(
        work_dir: RequestorTaskDir,
        subtask_id: str,
) -> Optional[api.structs.Subtask]:
    task_manager = TaskManager(work_dir)

    part_num = task_manager.get_next_computable_part_num()
    if part_num is None:
        return None
    part = task_manager.get_part(part_num)

    # write subtask input file
    subtask_input_file = work_dir.subtask_inputs_dir / f'{subtask_id}.zip'
    with zipfile.ZipFile(subtask_input_file, 'w') as file:
        file.writestr(subtask_id, part.input_data)

    resources = [subtask_input_file.name]
    task_manager.start_subtask(part_num, subtask_id)

    return api.structs.Subtask(
        params={
            'difficulty': part.difficulty,
            'resources': resources,
        },
        resources=resources,
    )


async def verify_subtask(
        work_dir: RequestorTaskDir,
        subtask_id: str,
) -> Tuple[VerifyResult, Optional[str]]:

    subtask_outputs_dir = work_dir.subtask_outputs_dir(subtask_id)
    output_data = _read_zip_contents(subtask_outputs_dir / f'{subtask_id}.zip')

    provider_result, provider_nonce_str = output_data.rsplit(' ', maxsplit=1)
    provider_nonce = int(provider_nonce_str)

    # verify hash
    task_manager = TaskManager(work_dir)
    task_manager.update_subtask_status(subtask_id, SubtaskStatus.VERIFYING)

    try:
        part_num = task_manager.get_part_num(subtask_id)
        part = task_manager.get_part(part_num)

        proof_of_work.verify(
            part.input_data,
            difficulty=part.difficulty,
            against_result=provider_result,
            against_nonce=provider_nonce)

        shutil.copy(
            subtask_outputs_dir / f'{subtask_id}.zip',
            work_dir.task_outputs_dir / f'{subtask_id}.zip')
    except (AttributeError, ValueError) as err:
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.FAILURE)
        return VerifyResult.FAILURE, str(err)

    task_manager.update_subtask_status(subtask_id, SubtaskStatus.SUCCESS)
    return VerifyResult.SUCCESS, None


async def discard_subtasks(
        work_dir: RequestorTaskDir,
        subtask_ids: List[str],
) -> List[str]:
    task_manager = TaskManager(work_dir)
    for subtask_id in subtask_ids:
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)
    return subtask_ids


async def has_pending_subtasks(
        work_dir: RequestorTaskDir,
) -> bool:
    task_manager = TaskManager(work_dir)
    return task_manager.get_next_computable_part_num() is not None


async def run_benchmark() -> float:
    return await api.threading.Executor.run(proof_of_work.benchmark)


async def compute_subtask(
        work_dir: ProviderTaskDir,
        subtask_id: str,
        subtask_params: dict,
) -> Path:
    # validate params
    resources = subtask_params['resources']
    if not resources:
        raise ValueError(f"resources={resources}")
    difficulty = int(subtask_params['difficulty'])
    if difficulty < 0:
        raise ValueError(f"difficulty={difficulty}")

    # read input data
    subtask_input_file = work_dir.subtask_inputs_dir / resources[0]
    subtask_input = _read_zip_contents(subtask_input_file)

    # execute computation
    hash_result, nonce = await api.threading.Executor.run(
        proof_of_work.compute,
        input_data=subtask_input,
        difficulty=difficulty)

    # bundle computation output
    subtask_output_file = work_dir / f'{subtask_id}.zip'
    with zipfile.ZipFile(subtask_output_file, 'w') as file:
        file.writestr(subtask_id, f'{hash_result} {nonce}')

    return subtask_output_file.name
