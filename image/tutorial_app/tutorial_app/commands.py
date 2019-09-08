import asyncio
import functools
import os
import random
import shutil
import string
import uuid
import zipfile

from concurrent import futures
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

import golem_task_api as api

from tutorial_app import proof_of_work
from tutorial_app.task import Task, create_subtask_id


def _read_zip_contents(path: Path) -> str:
    with zipfile.ZipFile(path, 'r') as f:
        input_file = f.namelist()[0]
        with f.open(input_file) as zf:
            return zf.read().decode('utf-8')


async def create_task(
        task_work_dir: Path,
        max_subtasks_count: int,
        task_params: dict,
) -> None:
    task_inputs_dir = task_work_dir / api.constants.TASK_INPUTS_DIR
    # read task parameters
    difficulty = int(task_params['difficulty'])
    subtasks_count = int(task_params['subtasks_count'])
    # validate the 'difficulty' parameter
    if difficulty < 0:
        raise ValueError(f"difficulty={difficulty}")
    # validate the 'subtasks_count' parameter
    if not (0 < subtasks_count <= max_subtasks_count):
        raise ValueError(f"subtasks_count={subtasks_count}")
    # copy the single resource file
    contents = os.listdir(task_inputs_dir)
    if len(contents) != 1:
        raise ValueError(f"len(resources)={contents} != 1")
    # create and save the task to the working directory
    Task.create(
        task_work_dir,
        difficulty=difficulty,
        subtasks_count=subtasks_count)


async def next_subtask(
        task_work_dir: Path,
) -> api.structs.Subtask:
    task_inputs_dir = task_work_dir / api.constants.TASK_INPUTS_DIR
    subtask_inputs_dir = task_work_dir / api.constants.SUBTASK_INPUTS_DIR
    task_input_file = os.listdir(task_inputs_dir)[0]

    async with Task.lock(task_work_dir) as task:
        subtask_num = task.next_subtask_num()
        subtask_id = create_subtask_id(subtask_num)
        subtask_input_zip = f'{subtask_id}.zip'
        # create subtask input data
        with open(task_inputs_dir / task_input_file, 'r') as f:
            input_data = f.read() + str(uuid.uuid4())
        # write subtask input file
        with zipfile.ZipFile(subtask_inputs_dir / subtask_input_zip, 'w') as zf:
            zf.writestr(subtask_id, input_data)

        task.subtask_in_progress(subtask_id)
        return api.structs.Subtask(
            subtask_id=subtask_id,
            params={'difficulty': task.difficulty},
            resources=[subtask_input_zip]
        )


async def verify_subtask(
        task_work_dir: Path,
        subtask_id: str,
) -> Tuple[bool, Optional[str]]:
    subtask_inputs_dir = task_work_dir / api.constants.SUBTASK_INPUTS_DIR
    subtask_outputs_dir = task_work_dir / api.constants.SUBTASK_OUTPUTS_DIR
    task_outputs_dir = task_work_dir / api.constants.TASK_OUTPUTS_DIR
    # read subtask input
    input_data = _read_zip_contents(subtask_inputs_dir / f'{subtask_id}.zip')
    # read subtask output
    output_data = _read_zip_contents(subtask_outputs_dir / f'{subtask_id}.zip')
    provider_result, provider_nonce = output_data.rsplit(' ', maxsplit=1)
    provider_nonce = int(provider_nonce)
    # verify hash
    async with Task.lock(task_work_dir) as task:
        try:
            proof_of_work.verify(
                input_data,
                difficulty=task.difficulty,
                against_result=provider_result,
                against_nonce=provider_nonce)
            shutil.copy(
                subtask_outputs_dir / f'{subtask_id}.zip',
                task_outputs_dir / f'{subtask_id}.zip')
        except ValueError as err:
            task.subtask_discarded(subtask_id)
            return False, err.message
        task.subtask_successful(subtask_id)
    return True, None


async def discard_subtasks(
        task_work_dir: Path,
        subtask_ids: List[str],
) -> List[str]:
    async with Task.lock(task_work_dir) as task:
        for subtask_id in subtask_ids:
            task.subtask_discarded(subtask_id)
    return subtask_ids


async def has_pending_subtasks(
        task_work_dir: Path,
) -> bool:
    async with Task.lock(task_work_dir) as task:
        return len(task.subtasks_pending)


async def run_benchmark(
        task_work_dir: Path
) -> float:
    return await api.threading.Executor.run(proof_of_work.benchmark)


async def compute_subtask(
        task_work_dir: Path,
        subtask_id: str,
        subtask_params: dict,
) -> Path:
    # validate params
    difficulty = int(subtask_params['difficulty'])
    if difficulty < 0:
        raise ValueError(f"difficulty={difficulty}")
    # set up directories
    subtask_inputs_dir = task_work_dir / api.constants.SUBTASK_INPUTS_DIR
    subtask_outputs_dir = task_work_dir
    # read input data
    # FIXME: compute should take a resource list as an argument
    subtask_input_file = subtask_inputs_dir / os.listdir(subtask_inputs_dir)[0]
    subtask_input = _read_zip_contents(subtask_input_file)
    os.remove(subtask_inputs_dir / subtask_input_file)
    # execute computation
    hash_result, nonce = await api.threading.Executor.run(
        proof_of_work.compute,
        input_data=subtask_input,
        difficulty=difficulty)
    # bundle computation output
    subtask_output_file = Path(f'{subtask_id}.zip')
    with zipfile.ZipFile(subtask_outputs_dir / subtask_output_file, 'w') as zf:
        zf.writestr(subtask_id, f'{hash_result} {nonce}')
    return subtask_output_file
