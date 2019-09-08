import asyncio
import json
import random
import uuid

from enum import Enum
from pathlib import Path
from typing import Dict, NewType, List, Optional, Tuple

from dataclasses import asdict, dataclass, field

try:
    from contextlib import asynccontextmanager
except ImportError:
    from async_generator import asynccontextmanager

SubtaskId = NewType('SubtaskId', str)
SubtaskParams = NewType('SubtaskParams', Dict[str, str])

_locks: Dict[Path, asyncio.Lock] = dict()


def create_subtask_id(
        subtask_num: int,
        uuid_str: Optional[str] = None
) -> SubtaskId:
    return f'{subtask_num}_{uuid_str or uuid.uuid4()}'


def parse_subtask_id(subtask_id: SubtaskId) -> Tuple[int, str]:
    subtask_num_str, uuid_str = subtask_id.split('_')
    return int(subtask_num_str), uuid_str


@dataclass
class TaskBase:
    difficulty: int
    subtasks_pending: List[int]
    subtasks_in_progress: Dict[int, SubtaskParams] = field(
        default_factory=dict)
    subtasks_successful: Dict[int, SubtaskParams] = field(
        default_factory=dict)
    subtasks_discarded: Dict[int, List[SubtaskParams]] = field(
        default_factory=dict)

    @classmethod
    def _load(cls, task_work_dir: Path) -> 'TaskBase':
        file_path = task_work_dir / 'task.json'
        with open(file_path, 'r') as f:
            state_dict = json.load(f)
        return cls(**state_dict)

    def _save(self, task_work_dir: Path) -> None:
        file_path = task_work_dir / 'task.json'
        with open(file_path, 'w') as f:
            json.dump(asdict(self), f)


@dataclass
class Task(TaskBase):
    @classmethod
    def create(
            cls,
            directory: Path,
            difficulty: int,
            subtasks_count: int
    ) -> None:
        Task(
            difficulty=difficulty,
            subtasks_pending=list(range(subtasks_count)),
        )._save(directory)

    @classmethod
    @asynccontextmanager
    async def lock(cls, directory: Path) -> 'Task':
        if directory not in _locks:
            _locks[directory] = asyncio.Lock()
        async with _locks[directory]:
            task = cls._load(directory)
            yield task
            task._save(directory)

    def next_subtask_num(self) -> int:
        return random.choice(tuple(self.subtasks_pending))

    def subtask_in_progress(self, subtask_id: int) -> SubtaskParams:
        subtask_num, _ = parse_subtask_id(subtask_id)
        subtask_params = dict(
            id=subtask_id,
            difficulty=self.difficulty,
            # TODO: provider node identifier
            node='TBD')

        self.subtasks_pending.remove(subtask_num)
        self.subtasks_in_progress[subtask_id] = subtask_params
        return subtask_params

    def subtask_successful(self, subtask_id: SubtaskId) -> None:
        subtask_params = self.subtasks_in_progress[subtask_id]
        self.subtasks_successful[subtask_id] = subtask_params

    def subtask_discarded(self, subtask_id: SubtaskId) -> None:
        subtask_params = self.subtasks_in_progress[subtask_id]
        subtask_num, _ = parse_subtask_id(subtask_id)

        if subtask_num not in self.subtasks_discarded:
            self.subtasks_discarded[subtask_num] = list()

        self.subtasks_discarded[subtask_num].append(subtask_params)
        self.subtasks_pending.append(subtask_num)
