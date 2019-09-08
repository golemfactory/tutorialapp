Quick links

- [`Tutorial-App` github repository](https://github.com/golemfactory/tutorialapp)
- [Task API documentation]()
- [Bootstrapping](#bootstrapping-the-application)
- [Implementation]()
- [Bundling](#bundling-the-application)
- [Testing](#testing-the-application)
- [Publishing](#publishing-the-application)

# Introduction

This section will guide you through the process of creating a sample Golem application. We will work with the `Golem-Task-Api` library to quickly bootstrap the app and implement the required logic.

> Note: the `Golem-Task-Api` helper library is currently written in Python (3.6) and serves as a foundation for apps built in that language. The Rust and static binary versions of that library are currently on the roadmap.

The `Tutorial-App` is a simple Proof of Work application. Golem tasks [LINK] are initialized with a PoW difficulty parameter, set by the application user (requestor [LINK]). After publishing the task in the network, Golem finds providers that are willing to participate in the computation. Each provider then computes a PoW with the set input difficulty and for different chunks of input data. The results will be sent back to the requestor and verified. For a more detailed description of task's lifecycle in the network, please refer to this section [LINK].

The `github` repository for the `Tutorial-App` can be found here [LINK].

# Scope of the tutorial

The guide for creating `Tutorial-App` will cover the following aspects of Task API app development:

1. Bootstrapping the application with the `Golem-Task-Api` library.
2. Implementing requestor logic:
   - creating new tasks
   - creating subtasks within a task, preparing subtask input data
   - verifying subtask computation results
   - managing subtask state
3. Implementing provider logic:
   - computing subtasks
   - benchmarking the application
4. Bundling the application inside a Docker image.
5. Testing.
6. Publishing the application.

# Building the `Tutorial-App`

The heart of a Task API application is a gRPC [LINK] server which responds to a set of predefined function calls. Each call is accompanied by a message containing the input call data and interpreted by the app server. Depending on the domain logic, the app may respond to the call with a well-defined message or raise an exception to be handled by Golem.

> The Task API protocols and services are defined using the Google's Protocol Buffers language. The definition files can be found here [LINK].

Currently (and by default) Golem requires apps to be built for the Docker environment [LINK]. At the end of the tutorial, we're going to bundle the `Tutorial-App` within a Docker image.

## Development tools

For the purposes of developing the tutorial app you will need:

- Python 3.6
- Docker

Golem docs [LINK] will guide you through installing the required tools for your operating system.

## Required knowledge

This tutorial requires from you to possess the knowledge of:

- Python 3.6+ language and features
- `asyncio` asynchronous programming module
- `threading` module
- basic Docker usage

## Structuring the project

Create the following directory structure somewhere on your disk:
```
Tutorial-App
├── image/
│   └── tutorial_app/
└── tests/
```

- `image` is the main directory for the project, containing Python code and Docker image definition
- `image/tutorial_app` is the root directory for the app's Python module
- `tests` is the place for the `pytest` test suite

## Bootstrapping the application

[source code on github](.)

Let's switch to `Tutorial-App/image/tutorial_app` as our main working directory. To define the Python package, create the following:

```
Tutorial-App
└── image/
    └── tutorial_app/
        ├── tutorial_app/
        ├── setup.py
        └── requirements.txt
```

- `tutorial_app` will contain the Python module source code
- `setup.py` is the `setuptools` project definition file
- `requirements.txt` defines project's requirements used by `pip`

### `setup.py`

[`setup.py` on github](image/tutorial_app/setup.py)

This file is composed of 2 parts:

- parsing the `requirements.txt` file
- calling the `setuptools.setup` function

The result of former will be passed to the `setup` function as an `install_requires` argument. The `parse_requirements` is implemented as follows:

```python
def parse_requirements(file_name: str = 'requirements.txt') -> List[str]:
    file_path = Path(__file__).parent / file_name
    with open(file_path, 'r') as requirements_file:
        return [
            line for line in requirements_file
            if line and not line.strip().startswith(('-', '#'))
        ]
```

Now, to call the `setup` function:

```python
setup(
    name='Tutorial-App',
    version='0.1.0',
    packages=['tutorial_app'],
    python_requires='>=3.6',
    install_requires=parse_requirements(),
)
```

This way there is no need to separately specify the requirements inside the `setup` function call.

### `requirements.txt`

[`requirements.txt` on github](image/tutorial_app/requirements.txt)

Our requirements file will use an extra PIP package repository to fetch the `golem_task_api` package.

```bash
--extra-index-url https://builds.golem.network
golem_task_api==0.15.2
dataclasses; python_version < '3.7'
async_generator; python_version < '3.7'
```

Note that the project also requires two features backported from Python 3.7 - `dataclasses` and `async_generator`.

### `tutorial_app/`

[`tutorial_app/` on github](image/tutorial_app/tutorial_app/tutorial_app)

Now, let's define our Python module.

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            └── entrypoint.py
```

- `__init__.py` is an empty module init file
- `entrypoint.py` contains the function starting the app server

### `entrypoint.py`

[`entrypoint.py` on github](image/tutorial_app/tutorial_app/entrypoint.py)

The code in `entrypoint.py` source file is responsible for starting the gRPC server, fulfilling requestor or provider logic. All server initialization code and message handling is done by the `Golem-Task-Api` library (here referred to by `api`).

The role that the server will be executed in is defined by script's command line arguments:

- `python entrypoint.py requestor [port]` starts the requestor app server on the specified port
- `python entrypoint.py provider [port]` executes the provider part of the application

The initialization itself logic is defined in the `main` function:

```python
async def main():
    await api.entrypoint(
        work_dir=Path(f'/{api.constants.WORK_DIR}'),
        argv=sys.argv[1:],
        requestor_handler=RequestorHandler(),
        provider_handler=ProviderHandler(),
    )
```

- `work_dir` is the application's working directory, as seen from inside the Docker container. A real file system location is mounted under that directory
- `argv` is a list / tuple of command line arguments
- `requestor_handler` is an instance of requestor's app logic handler
- `provider_handler` is an instance of provider's app logic handler

The entrypoint is run directly via the `__main__` execution entry point. The following code initializes the `asyncio` event loop and executes the `main` function within it:

```python
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

The actual logic for `RequestorHandler` and `ProviderHandler` will be defined elsewhere. These classes are here to satisfy the implementation of the interfaces. This way app implementation may be isolated from the bootstrapping code.

The `RequestorHandler` is derived from the Task API's `RequestorAppHandler` [LINK] and defined as follows:

```python
class RequestorHandler(api.RequestorAppHandler):
    async def create_task(
            self,
            task_work_dir: Path,
            max_subtasks_count: int,
            task_params: dict,
    ) -> None:
        return await create_task(task_work_dir, max_subtasks_count, task_params)

    async def next_subtask(
            self,
            task_work_dir: Path,
    ) -> api.structs.Subtask:
        return await next_subtask(task_work_dir)

    async def verify(
            self,
            task_work_dir: Path,
            subtask_id: str,
    ) -> Tuple[bool, Optional[str]]:
        return await verify_subtask(task_work_dir, subtask_id)

    async def discard_subtasks(
            self,
            task_work_dir: Path,
            subtask_ids: List[str],
    ) -> List[str]:
        return await discard_subtasks(task_work_dir, subtask_ids)

    async def has_pending_subtasks(
            self,
            task_work_dir: Path,
    ) -> bool:
        return await has_pending_subtasks(task_work_dir)

    async def run_benchmark(self, work_dir: Path) -> float:
        return await run_benchmark(work_dir)
```

Next, the `ProviderHandler` (Task API's `ProviderAppHandler` [LINK]):

```python
class ProviderHandler(api.ProviderAppHandler):
    async def compute(
            self,
            task_work_dir: Path,
            subtask_id: str,
            subtask_params: dict,
    ) -> Path:
        return await compute_subtask(task_work_dir, subtask_id, subtask_params)

    async def run_benchmark(self, work_dir: Path) -> float:
        return await run_benchmark(work_dir)
```

We will go back to actual command implementations in the next sections. For now, let's focus on the core logic of the application - Proof of Work.

### `proof_of_work.py`

[`proof_of_work.py` on github](image/tutorial_app/tutorial_app/proof_of_work.py)

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            └── proof_of_work.py
```

According to Wikipedia:
> A Proof-of-Work (PoW) system (or protocol, or function) is a consensus mechanism. It allows to deter denial of service attacks and other service abuses such as spam on a network by requiring some work from the service requester, usually meaning processing time by a computer.

The PoW used in the `Tutorial-App` is literal - providers compute an expensive function (that serves no real purpose) and which is later easily verified by the requestor.

To implement a PoW system we need at least 2 functions - `compute` and `verify`. With PoW computation, we try to find a digest that satisfies a certain difficulty threshold. We define the `compute` function as follows:

```python
_MAX_NONCE: int = 2 ** 256


def compute(
        input_data: str,
        difficulty: int,
) -> Tuple[str, int]:
    target = 2 ** (256 - difficulty)
    for nonce in range(_MAX_NONCE):
        if api.threading.Executor.is_shutting_down():
            raise RuntimeError("Interrupted")
        hash_result = _sha256(input_data + str(nonce))
        if int(hash_result, 16) < target:
            return hash_result, nonce
    raise RuntimeError("Solution not found")
```

Please note the `is_shutting_down()` call. In order not to block the event loop thread, we're going to execute the `compute` function in a separate thread. `is_shutting_down` will signal whether we should stop the iteration, since the result will be discarded.

For verification purposes, a hash is computed from the same `input_data` and compared with the resulting hash. Besides that, we check the difficulty threshold:

```python
def verify(
        input_data: str,
        difficulty: int,
        against_result: str,
        against_nonce: int,
) -> None:
    target = 2 ** (256 - difficulty)
    result = _sha256(input_data + str(against_nonce))
    if against_result != result:
        raise ValueError(f"Invalid result hash: {against_result} != {result}")
    if int(result, 16) >= target:
        raise ValueError(f"Invalid result hash difficulty")
```

To satisfy the Task API interface, we need to provide a benchmarking function. It will measure the execution time of an arbitrary number of iterations. The result will be converted to a certain score range.

```python
def benchmark(
        iterations: int = 2 ** 8,
) -> float:
    started = time.time()
    for nonce in range(iterations):
        if api.threading.Executor.is_shutting_down():
            raise RuntimeError("Interrupted")
        hash_result = _sha256('benchmark' + str(nonce))
    elapsed = time.time() - started
    if elapsed:
        return 1000. / elapsed
    return 1000.
```

Here is the remaining `_sha256` function, which converts the input data to `bytes` and returns a hex-encoded digest of that data:

```python
def _sha256(input_data: str) -> str:
    input_bytes = input_data.encode('utf-8')
    return hashlib.sha256(input_bytes).hexdigest()
```

### `task.py`

[`task.py` on github](image/tutorial_app/tutorial_app/task.py)

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            ├── proof_of_work.py
            └── task.py
```

This section describes subtask management and persistence within the scope of the app.

For the purpose of this tutorial, the persistence part will be simplified - any task information we want to store will be saved in a single JSON file. File operations on that data will be synchronized with a mutex, per working task directory.

The following data class defines the structure of persisted data:

- `difficulty` - the the Proof of Work function parameter, set by the user
- `subtasks_pending` - a list of subtasks (their numbers) to be computed
- `subtasks_in_progress` - a collection of currently computed subtasks
- `subtasks_successful` - a collection of successfully computed subtasks
- `subtasks_discarded` - a collection of subtasks that timed out / failed the verification

```python
SubtaskParams = NewType('SubtaskParams', Dict[str, str])

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
```

Additionally, the base class defines a `_load` and `_save` method, which accordingly de-serialize and serialize the object from and to a JSON file.

Each subtasks object created within a task needs to be uniquely identified. The subtask number does not fulfil that requirement, since it may have been assigned to 2 different providers due to (e.g.) verification failure. The following functions generate and parse a semi-random identifier containing a subtask number.

```python
SubtaskId = NewType('SubtaskId', str)

def create_subtask_id(
        subtask_num: int
) -> SubtaskId:
    return f'{subtask_num}_{uuid.uuid4()}'

def parse_subtask_id(subtask_id: SubtaskId) -> Tuple[int, str]:
    subtask_num_str, uuid_str = subtask_id.split('_')
    return int(subtask_num_str), uuid_str
```

Next, let's take care of the persistence and synchronization issue. Since our code is asynchronous and may be interrupted, we don't want for our data to be a subject of a race condition.

The main `Task` class defines a context manager that allows to read, modify and save changes made to the task object using a mutex, per task directory.

```python
_locks: Dict[Path, asyncio.Lock] = dict()

@dataclass
class Task(TaskBase):
    ...

    @classmethod
    @asynccontextmanager
    async def lock(cls, directory: Path) -> 'Task':
        if directory not in _locks:
            _locks[directory] = asyncio.Lock()
        async with _locks[directory]:
            task = cls._load(directory)
            yield task
            task._save(directory)
    ...
```

The task creation function simply creates a `Task` object and serializes it to the working directory:

```python
@dataclass
class Task(TaskBase):
    ...

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
    ...
```

The remaining methods take care of juggling the subtask state between the collections defined in `TaskBase`:

```python
@dataclass
class Task(TaskBase):
    ...

    def next_subtask_num(self) -> int:
        return random.choice(tuple(self.subtasks_pending))

    def subtask_in_progress(self, subtask_id: int) -> SubtaskParams:
        ...

    def subtask_successful(self, subtask_id: SubtaskId) -> None:
        ...

    def subtask_discarded(self, subtask_id: SubtaskId) -> None:
        ...
```

With this knowledge, we may move to defining commands used in requestor and provider app handlers.


### `commands.py`

[`commands.py` on github](image/tutorial_app/tutorial_app/commands.py)

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            ├── proof_of_work.py
            ├── task.py
            └── commands.py
```

In the tutorial app, we're going to assume that each resource (be it subtask input data or subtask computation result) is a ZIP file containing a single file. To simplify read operations on files inside of those archives, we will define a following helper function:

```python
def _read_zip_contents(path: Path) -> str:
    with zipfile.ZipFile(path, 'r') as f:  # open the archive
        input_file = f.namelist()[0]  # assume there's a single file inside
        with f.open(input_file) as zf:  # open the archived file
            return zf.read().decode('utf-8')  # read the contents as a string
```

Let's go through the commands, one by one.

1. `create_task`

    ```python
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
    ```

2. `next_subtask`

    ```python
    async def next_subtask(
            task_work_dir: Path,
    ) -> api.structs.Subtask:
        task_inputs_dir = task_work_dir / api.constants.TASK_INPUTS_DIR
        subtask_inputs_dir = task_work_dir / api.constants.SUBTASK_INPUTS_DIR
        # the task input file is a single resource file provided in create_task
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
            # mark subtask as "in progress"
            task.subtask_in_progress(subtask_id)
            # create a subtask definition object
            return api.structs.Subtask(
                subtask_id=subtask_id,
                params={'difficulty': task.difficulty},
                resources=[subtask_input_zip]
            )
    ```

3. `verify_subtask`

    ```python
    async def verify_subtask(
            task_work_dir: Path,
            subtask_id: str,
    ) -> Tuple[bool, Optional[str]]:
        subtask_inputs_dir = task_work_dir / api.constants.SUBTASK_INPUTS_DIR
        subtask_outputs_dir = task_work_dir / api.constants.SUBTASK_OUTPUTS_DIR
        task_outputs_dir = task_work_dir / api.constants.TASK_OUTPUTS_DIR
        # read subtask input
        input_data = _read_zip_contents(subtask_inputs_dir / f'{subtask_id}.zip')
        # read subtask (computation) output
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
    ```

4. `discard_subtasks`

    ```python
    async def discard_subtasks(
            task_work_dir: Path,
            subtask_ids: List[str],
    ) -> List[str]:
        async with Task.lock(task_work_dir) as task:
            for subtask_id in subtask_ids:
                task.subtask_discarded(subtask_id)
        return subtask_ids
    ```

5. `has_pending_subtasks`

    ```python
    async def has_pending_subtasks(
            task_work_dir: Path,
    ) -> bool:
        async with Task.lock(task_work_dir) as task:
            return len(task.subtasks_pending)
    ```

6. `run_benchmark`

    ```python
    async def run_benchmark(
            task_work_dir: Path
    ) -> float:
        return await api.threading.Executor.run(proof_of_work.benchmark)
    ```

7. `compute_subtask`

    ```python
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
    ```

## Bundling the application

[`Dockerfile` on github](image/Dockerfile)

```
Tutorial-App
└── image/
    ├── tutorial_app/
    └── Dockerfile
```

In this section we're going to build a Docker image with our application. Please create an empty `Dockerfile` in the `Tutorial-App/image/` directory. Then, add the following lines:

1. The image is going to be derived from a base Golem image.

    ```dockerfile
    FROM golemfactory/base:1.5
    ```

2. Install prerequisites.

    ```dockerfile
    RUN apt update
    RUN apt install -y python3-pip
    ```

3. Copy the application.

    ```dockerfile
    COPY tutorial_app /golem/tutorial_app
    ```

4. Install the required packages and app itself.

    ```dockerfile
    RUN python3 -m pip install --no-cache-dir --upgrade pip
    RUN python3 -m pip install --no-cache-dir -r /golem/tutorial_app/requirements.txt
    RUN python3 -m pip install --no-cache-dir /golem/tutorial_app
    ```

5. Clean up unnecessary packages.

    ```dockerfile
    RUN apt remove -y python3-pip
    RUN apt clean
    ```

6. Set up the working directory inside the image and the entrypoint.

    ```dockerfile
    WORKDIR /golem/work
    ENTRYPOINT ["python3", "-m", "tutorial_app.entrypoint"]
    ```

In order to build the image, execute the following command in the `image` directory:

```bash
docker build -t tutorial_app -f Dockerfile .
```

That's it!

## Testing the application

[`tests` on github](tests)

TBD

## Publishing the application

TBD

# `Golem-Task-Api` helper library features

## Application lifecycle

TBD
