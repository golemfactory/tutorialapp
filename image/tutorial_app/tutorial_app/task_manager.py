from pathlib import Path

import peewee
from golem_task_api.apputils.task import database

from .constants import DOCKER_IMAGE, VERSION


PREREQUISITES = {
    "image": DOCKER_IMAGE,
    "tag": VERSION,
}


class Part(database.Part):
    input_data = peewee.CharField(null=True)
    difficulty = peewee.FloatField(null=True)


class TaskManager(database.DBTaskManager):
    def __init__(self, work_dir: Path) -> None:
        super().__init__(work_dir, part_model=Part)
