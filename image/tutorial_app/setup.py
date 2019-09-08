from pathlib import Path
from setuptools import setup
from typing import List


def parse_requirements(file_name: str = 'requirements.txt') -> List[str]:
    file_path = Path(__file__).parent / file_name
    with open(file_path, 'r') as requirements_file:
        return [
            line for line in requirements_file
            if line and not line.strip().startswith(('-', '#'))
        ]


setup(
    name='Tutorial-App',
    version='0.1.0',
    packages=['tutorial_app'],
    python_requires='>=3.6',
    install_requires=parse_requirements(),
)
