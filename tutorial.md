Quick links

- [`Tutorial-App` github repository](https://github.com/golemfactory/tutorialapp)
- [Task API documentation](https://github.com/golemfactory/task-api/README.md)
- [Bootstrapping](#bootstrapping-the-application)
- [Implementation](#implementation)
- [Bundling](#bundling-the-application)
- [Testing](#testing-the-application)
- [Publishing](#publishing-the-application)

# Introduction

This tutorial will guide you through the process of creating a sample Golem application. We will work with the `Golem-Task-Api` library to quickly bootstrap and test our app.

> Note: the `Golem-Task-Api` helper library is currently written in Python (3.6) and serves as a foundation for apps built in that language. The Rust and static binary versions of that library are currently on the roadmap.

The `Tutorial-App` is a simple Proof of Work application. Golem tasks are initialized with a PoW difficulty parameter, set by the application user (requestor). After publishing the task in the network, Golem finds providers that are willing to participate in the computation. Each provider then computes a PoW with the set input difficulty and for different chunks of input data. The results will be sent back to the requestor and verified. For a more detailed description of task's lifecycle in the network, please refer to [this section](#application-lifecycle).

The `github` repository for the `Tutorial-App` can be found [here](https://github.com/golemfactory/tutorialapp).

# Scope of the tutorial

The guide for creating `Tutorial-App` will cover the following aspects of Task API app development:

1. Bootstrapping the application with the `Golem-Task-Api` library.
2. Implementing requestor-side logic:
   - creating a new task
   - splitting a task into parts
   - creating subtasks for each of the parts
   - verifying subtask computation results
3. Implementing provider-side logic:
   - computing subtasks
   - benchmarking the application
4. Bundling the application inside a Docker image.
5. Testing.
6. Publishing the application.

# Building the `Tutorial-App`

The Task API library provides an out-of-the-box [gRPC](https://grpc.io) server compliant with the [API specification](https://github.com/golemfactory/task-api/README.md). The messages used for the API calls are specified in the [Protocol Buffers](https://developers.google.com/protocol-buffers) format. The Task API library hides these details from developers and provides a convenient way to implement application's logic.

> The protocol and message definition files can be found [here](https://github.com/golemfactory/task-api/tree/master/golem_task_api/proto).

Currently, the Task API apps are required to be built as Docker images. [This section](#bundling-the-application) provides more details on the subject.

## Development tools

For the purposes of developing the tutorial app you will need:

- Python 3.6
- Docker

[Golem docs](https://docs.golem.network) will guide you through installing these tools for your operating system.

## Prerequisites

This tutorial assumes that you possess the knowledge of:

- Python 3.6+ language and features
- `asyncio` asynchronous programming module
- basic Docker usage

## Structuring the project

On your disk, create the following directory structure:
```
Tutorial-App
├── image/
│   └── tutorial_app/
└── tests/
```

- `image` is the main project directory, containing the application code and the Docker image definition
- `image/tutorial_app` is the root directory for the app's Python module
- `tests` is the place for the `pytest` test suite

## Bootstrapping the application

[Source code on github](https://github.com/golemfactory/tutorialapp)

Let's switch to `Tutorial-App/image/tutorial_app` as our main working directory. To define the Python package, create the following:

```python
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

The `parse_requirements` function converts the contents of a `pip` requirements file to a format understood by the `setup` function. This eliminates a need to double the work by specifying the requirements manually. `parse_requirements` is implemented as follows:

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
    version=VERSION,  # defined in constants.py
    packages=['tutorial_app'],
    python_requires='>=3.6',
    install_requires=parse_requirements(),
)
```

### `requirements.txt`

[`requirements.txt` on github](image/tutorial_app/requirements.txt)

Our requirements file will use an extra PIP package repository to fetch the `golem_task_api` package.

```bash
--extra-index-url https://builds.golem.network
# peewee ORM for database-backed persistence
peewee==3.11.2
golem_task_api==0.24.1
dataclasses==0.6; python_version < '3.7'
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
- `entrypoint.py` will start the application server

### `entrypoint.py`

[`entrypoint.py` on github](image/tutorial_app/tutorial_app/entrypoint.py)

The code in `entrypoint.py` source file is responsible for starting the gRPC server and executing requestor or provider logic. All server initialization code and message handling is done by the `Golem-Task-Api` library (here referred to by `api`).

The role that the server will be executed in is determined by command line arguments:

- `python entrypoint.py requestor [port]` starts the requestor app server on the specified port
- `python entrypoint.py provider [port]` analogically, starts the provider app server on the specified port

The initialization logic itself is defined in the `main` function:

```python
async def main():
    await api.entrypoint(
        work_dir=Path(f'/{api.constants.WORK_DIR}'),
        argv=sys.argv[1:],
        requestor_handler=RequestorHandler(),
        provider_handler=ProviderHandler(),
    )
```

- `work_dir` is the application's working directory, as seen from inside the Docker container. A real file system location is mounted on that directory
- `argv` is a list / tuple of command line arguments
- `requestor_handler` is an instance of requestor's app logic handler
- `provider_handler` is an instance of provider's app logic handler

The entrypoint is run directly via the `__main__` execution entry point. The following code initializes the `asyncio` event loop and executes the `main` function within it:

```python
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```

The actual logic for `RequestorHandler` and `ProviderHandler` will be defined elsewhere as these classes are here to satisfy the implementation of the interfaces. By writing our code this way, we isolate the implementation from the bootstrapping code.

The `RequestorHandler` is derived from the Task API's `RequestorAppHandler` and defined as follows:

```python
class RequestorHandler(api.RequestorAppHandler):
    async def create_task(
            self,
            task_work_dir: RequestorTaskDir,
            max_subtasks_count: int,
            task_params: dict,
    ) -> Task:
        return await create_task(task_work_dir, max_subtasks_count, task_params)

    async def next_subtask(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str,
            opaque_node_id: str,
    ) -> Optional[Subtask]:
        return await next_subtask(task_work_dir, subtask_id)

    async def verify(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> Tuple[VerifyResult, Optional[str]]:
        return await verify_subtask(task_work_dir, subtask_id)

    async def discard_subtasks(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_ids: List[str],
    ) -> List[str]:
        return await discard_subtasks(task_work_dir, subtask_ids)

    async def has_pending_subtasks(
            self,
            task_work_dir: RequestorTaskDir,
    ) -> bool:
        return await has_pending_subtasks(task_work_dir)

    async def run_benchmark(
            self,
            task_work_dir: RequestorTaskDir,
    ) -> float:
        return await run_benchmark()

    async def abort_task(
            self,
            task_work_dir: RequestorTaskDir,
    ) -> None:
        return await abort_task(task_work_dir)

    async def abort_subtask(
            self,
            task_work_dir: RequestorTaskDir,
            subtask_id: str
    ) -> None:
        return await abort_subtask(task_work_dir, subtask_id)
```

Next, the `ProviderHandler` (Task API's `ProviderAppHandler` [LINK]):

```python
class ProviderHandler(api.ProviderAppHandler):
    async def compute(
            self,
            task_work_dir: ProviderTaskDir,
            subtask_id: str,
            subtask_params: dict,
    ) -> Path:
        return await compute_subtask(task_work_dir, subtask_id, subtask_params)

    async def run_benchmark(
            self,
            task_work_dir: Path,
    ) -> float:
        return await run_benchmark()
```

We will go back to actual command implementations in the next sections. For now, let's focus on the core logic of the application - Proof of Work.

## Implementation

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

The PoW used in the `Tutorial-App` is literal - providers execute a computationally expensive function, whose result can be easily verified by the requestor.

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

In order not to block the event loop thread, we're going to execute  `compute` in a dedicated thread. `Executor.is_shutting_down` will signal whether we should stop the iteration, since the result is going to be discarded anyway.

For verification purposes, a hash is computed from the same `input_data` and compared with the received hash. Then, we perform a sanity check on the hash difficulty:

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

To satisfy the Task API interface, we need to provide a benchmarking function. It will measure the execution time of an arbitrary number of iterations. The result will be converted to a fixed score range.

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

### `constants.py`
[`constants.py` on github](image/tutorial_app/tutorial_app/constants.py)

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            ├── proof_of_work.py
            └── constants.py
```

This file contains the Docker image name and the application version.

```python
DOCKER_IMAGE = 'golemfactory/tutorialapp'
VERSION = '1.0.0'
```

### `task_manager.py`

[`task_manager.py` on github](image/tutorial_app/tutorial_app/task_manager.py)

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            ├── proof_of_work.py
            └── task_manager.py
```

The Task API library is equipped with an out-of-the-box task manager. It is based on the following concepts:

- part

    An outcome of splitting a task into separate units of work. There
    usually exists a constant number of parts.

- subtask

    A clone of a chosen task part that will be assigned to a
    computing node.

    Each subtask is given a unique identifier in order to distinguish
    computation attempts of the same part, which may fail due to
    unexpected errors or simply time out.

    A successful subtask computation concludes the computation of the
    corresponding part.

The included task manager will help you in the following areas:

- splitting the task into parts
- creating and managing subtasks bound to task parts
- updating the status of each subtask
- persisting the state to disk

The default `TaskManager` class is built on the `peewee` library and uses an SQLite database by default.

`SubtaskStatus` is defined in `golem_task_api.apputils.task` as:

```python
class SubtaskStatus(enum.Enum):
    WAITING = None
    COMPUTING = 'computing'
    VERIFYING = 'verifying'
    SUCCESS = 'success'
    FAILURE = 'failure'
    ABORTED = 'aborted'
```

For the purpose of this project, we're going to extend the task part model with additional fields.

```python
from golem_task_api.apputils.task import database


class Part(database.Part):
    input_data = peewee.CharField(null=True)
    difficulty = peewee.FloatField(null=True)


class TaskManager(database.DBTaskManager):
    def __init__(self, work_dir: Path) -> None:
        super().__init__(work_dir, part_model=Part)
```

We've added two fields to the `Part` model:

- `input_data`, which will be the source data for our PoW compute function
- `difficulty`, representing the PoW function difficulty threshold

Now we want the `DBTaskManager` to use our `Part` model. We can do that by calling `super().__init__(work_dir, part_model=Part)`.

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

In the tutorial app, we're going to assume that each resource (be it subtask input data or subtask computation result) is a ZIP file containing a single file. To simplify read operations on files inside of those archives, we will define the following helper function:

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
    ```

2. `abort_task`

    ```python
    async def abort_task(
            work_dir: RequestorTaskDir,
    ) -> None:
        task_manager = TaskManager(work_dir)
        task_manager.abort_task()
    ```

3. `abort_subtask`

   ```python
    async def abort_subtask(
            work_dir: RequestorTaskDir,
            subtask_id: str
    ) -> None:
        task_manager = TaskManager(work_dir)
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)
   ```

4. `next_subtask`

    ```python
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
        with zipfile.ZipFile(subtask_input_file, 'w') as zf:
            zf.writestr(subtask_id, part.input_data)

        resources = [subtask_input_file.name]
        task_manager.start_subtask(part_num, subtask_id)

        return api.structs.Subtask(
            params={
                'difficulty': part.difficulty,
                'resources': resources,
            },
            resources=resources,
        )
    ```

5. `verify_subtask`

    ```python
    async def verify_subtask(
            work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> Tuple[VerifyResult, Optional[str]]:

        subtask_outputs_dir = work_dir.subtask_outputs_dir(subtask_id)
        output_data = _read_zip_contents(subtask_outputs_dir / f'{subtask_id}.zip')

        provider_result, provider_nonce = output_data.rsplit(' ', maxsplit=1)
        provider_nonce = int(provider_nonce)

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
            return VerifyResult.FAILURE, err.message

        task_manager.update_subtask_status(subtask_id, SubtaskStatus.SUCCESS)
        return VerifyResult.SUCCESS, None
    ```

6. `discard_subtasks`

    ```python
    async def discard_subtasks(
            work_dir: RequestorTaskDir,
            subtask_ids: List[str],
    ) -> List[str]:
        task_manager = TaskManager(work_dir)
        for subtask_id in subtask_ids:
            task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)
        return subtask_ids
    ```

7. `has_pending_subtasks`

    ```python
    async def has_pending_subtasks(
            work_dir: RequestorTaskDir,
    ) -> bool:
        task_manager = TaskManager(work_dir)
        return task_manager.get_next_computable_part_num() is not None
    ```

8. `run_benchmark`

    ```python
    async def run_benchmark() -> float:
        return await api.threading.Executor.run(proof_of_work.benchmark)
    ```

9. `compute_subtask`

    ```python
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
        with zipfile.ZipFile(subtask_output_file, 'w') as zf:
            zf.writestr(subtask_id, f'{hash_result} {nonce}')

        return subtask_output_file.name
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

3. Copy application code.

    ```dockerfile
    COPY tutorial_app /golem/tutorial_app
    ```

4. Install required packages and the app itself.

    ```dockerfile
    RUN python3 -m pip install --no-cache-dir --upgrade pip
    RUN python3 -m pip install --no-cache-dir -r /golem/tutorial_app/requirements.txt
    RUN python3 -m pip install --no-cache-dir /golem/tutorial_app
    ```

5. Clean up the no longer needed packages.

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

In order to make your app available to others, you will need to:

1. Upload the app image to Docker Hub

    This short [tutorial](https://docs.docker.com/docker-hub/) will guide you through the process.

2. Create an app descriptor file and make it publicly available. The file has the following format:

    ```json
    {
        "name": "repository/image_name",
        "description": "My app",
        "version": "1.0.0",
        "author": "Me <me@company.org>, Others <others@company.org>",
        "license": "GPLv3",
        "requestor_env": "docker_cpu",
        "requestor_prereq": {
            "image": "repository/image_name",
            "tag": "1.0.0"
        },
        "market_strategy": "brass",
        "max_benchmark_score": 10000.0
    }
    ```

    The app descriptor file is needed by requesting nodes and should be placed under `<golem_data_dir>/apps` directory.

    `golem_data_dir` can be found at the following locations:

    - macOS

        `~/Library/Application Support/golem/default/<mainnet|rinkeby>`

    - Linux

        `~/.local/share/golem/default/<mainnet|rinkeby>`

    - Windows

        `%LOCALAPPDATA%\golem\golem\default\<mainnet|rinkeby>`

3. Have both requestors and providers whitelist your image repository within Golem.

    In order to manage a repository whitelist use the following CLI commands:

    - `golemcli debug rpc env.docker.repos.whitelist`

    To display all whitelisted repositories.

    - `golemcli debug rpc env.docker.repos.whitelist.add <repository_name>`

    Whitelist `<repository_name>`.

    - `golemcli debug rpc env.docker.repos.whitelist.remove <repository_name>`

    Remove the `<repository_name>` from your whitelist.

    - `golemcli debug rpc env.docker.images.discovered`

    List all app images seen by your node on the network.
