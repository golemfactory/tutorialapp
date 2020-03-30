
# tutorialapp in depth

## Introduction
This tutorial will guide you through the process of creating a sample Golem application. We will work with the `Golem-Task-Api` library to quickly bootstrap and test our app.

> Note: the `Golem-Task-Api` helper library is currently written in Python (3.6) and serves as a foundation for apps built in that language. The Rust and static binary versions of that library are currently on the roadmap.

The `Tutorial-App` is a simple Proof of Work application. Golem tasks are initialized with a PoW difficulty parameter, set by the application user (requestor). After publishing the task in the network, Golem finds providers that are willing to participate in the computation. Each provider then computes a PoW with the set input difficulty and for different chunks of input data. The results will be sent back to the requestor and verified. For a more detailed description of the task's lifecycle in the network, please refer to [this section](#application-lifecycle).

The `github` repository for the `Tutorial-App` can be found [here](https://github.com/golemfactory/tutorialapp).

#### Scope of the tutorial

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

---

## Preparation

The Task API library provides an out-of-the-box [gRPC](https://grpc.io) server compliant with the [API specification](https://github.com/golemfactory/task-api/README.md). The messages used for the API calls are specified in the [Protocol Buffers](https://developers.google.com/protocol-buffers) format. The Task API library hides these details from developers and provides a convenient way to implement the application's logic.

> The protocol and message definition files can be found [here](https://github.com/golemfactory/task-api/tree/master/golem_task_api/proto).

Currently, the Task API apps are required to be built as Docker images. [This section](#bundling-the-application) provides more details on the subject.

#### Development tools

To develop the tutorial app you will need:

- Python 3.6
- Docker

[Golem docs](https://docs.golem.network) will guide you through installing these tools for your operating system.

#### Prerequisites

This tutorial assumes that you possess the knowledge of:

- Python 3.6+ language and features
- `asyncio` asynchronous programming module
- basic Docker usage

## Step by step walkthrough

### Structuring the project

```
Tutorial-App
├── image/
│   └── tutorial_app/
└── tests/
```
On your disk, create the following directory structure:

- `image` is the main project directory, containing the application code and the Docker image definition
- `image/tutorial_app` is the root directory for the app's Python module
- `tests` is the place for the `pytest` test suite

### Bootstrapping the application

```python
Tutorial-App
└── image/
    └── tutorial_app/
        ├── tutorial_app/
        ├── setup.py
        └── bash.txt
```
[Source code on github](https://github.com/golemfactory/tutorialapp)

Let's switch to `Tutorial-App/image/tutorial_app` as our main working directory. To define the Python package, create the following:

- `tutorial_app` will contain the Python module source code
- `setup.py` is the `setuptools` project definition file
- `requirements.txt` defines the project's requirements used by `pip`

### setup.py

```python
def parse_requirements(file_name: str = 'requirements.txt') -> List[str]:
    file_path = Path(__file__).parent / file_name
    with open(file_path, 'r') as requirements_file:
        return [
            line for line in requirements_file
            if line and not line.strip().startswith(('-', '#'))
        ]
```
[`setup.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/setup.py)

This file is composed of 2 parts:

- parsing the `requirements.txt` file
- calling the `setuptools.setup` function

The `parse_requirements` function converts the contents of a `pip` requirements file to a format understood by the `setup` function. This eliminates a need to double the work by specifying the requirements manually. `parse_requirements` is implemented as follows

```python
setup(
    name='Tutorial-App',
    version=VERSION,  # defined in constants.py
    packages=['tutorial_app'],
    python_requires='>=3.6',
    install_requires=parse_requirements(),
)
```
#### Now, to call the `setup` function:


### requirements.txt

```
--extra-index-url https://builds.golem.network
# peewee ORM for database-backed persistence
peewee==3.11.2
golem_task_api==0.24.1
dataclasses==0.6; python_version < '3.7'
async_generator; python_version < '3.7'
```
[`requirements.txt` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/requirements.txt)

Our requirements file will use an extra PIP package repository to fetch the `golem_task_api` package.

Note that the project also requires two features backported from Python 3.7 - `dataclasses` and `async_generator`.

### tutorial_app/
```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            └── entrypoint.py
```
[`tutorial_app/` on github](https://github.com/golemfactory/tutorialapp/tree/master/image/tutorial_app/tutorial_app)

Now, let's define our Python module.

- `__init__.py` is an empty module init file
- `entrypoint.py` will start the application server

### entrypoint.py

[`entrypoint.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/tutorial_app/entrypoint.py)

The code in `entrypoint.py` source file is responsible for starting the gRPC server and executing requestor or provider logic. All server initialization code and message handling is done by the `Golem-Task-Api` library (here referred to by `api`).

### executing server

The role that the server will be executed in is determined by command line arguments:

```python
async def main():
    await api.entrypoint(
        work_dir=Path(f'/{api.constants.WORK_DIR}'),
        argv=sys.argv[1:],
        requestor_handler=RequestorHandler(),
        provider_handler=ProviderHandler(),
    )
```
- `python entrypoint.py requestor [port]` starts the requestor app server on the specified port
- `python entrypoint.py provider [port]` analogically, starts the provider app server on the specified port

The initialization logic itself is defined in the `main` function

- `work_dir` is the application's working directory, as seen from inside the Docker container. A real file system location is mounted on that directory
- `argv` is a list / tuple of command line arguments
- `requestor_handler` is an instance of requestor's app logic handler
- `provider_handler` is an instance of provider's app logic handler

### entrypoint

```python
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
```
The entrypoint is run directly via the `__main__` execution entry point. The following code initializes the `asyncio` event loop and executes the `main` function within it:



The actual logic for `RequestorHandler` and `ProviderHandler` will be defined elsewhere as these classes are here to satisfy the implementation of the interfaces. By writing our code this way, we isolate the implementation from the bootstrapping code.

### RequestorHandler

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

### ProviderHandler

Next, the `ProviderHandler` (Task API's `ProviderAppHandler`):

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

> According to Wikipedia:
> A Proof-of-Work (PoW) system (or protocol, or function) is a consensus mechanism. It allows to deter denial of service attacks and other service abuses such as spam on a network by requiring some work from the service requester, usually meaning processing time by a computer.

The PoW used in the `Tutorial-App` is literal - providers execute a computationally expensive function, whose result can be easily verified by the requestor.

### proof_of_work.py

```
Tutorial-App
└── image/
    └── tutorial_app/
        └── tutorial_app/
            ├── __init__.py
            ├── entrypoint.py
            └── proof_of_work.py
```

[`proof_of_work.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/tutorial_app/proof_of_work.py)

To implement a PoW system we need at least 2 functions - `compute` and `verify`. With PoW computation, we try to find a digest that satisfies a certain difficulty threshold.

### `compute` function

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

### `verify` function

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

For verification purposes, a hash is computed from the same `input_data` and compared with the received hash. Then, we perform a sanity check on the hash difficulty

### benchmarking

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

To satisfy the Task API interface, we need to provide a benchmarking function. It will measure the execution time of an arbitrary number of iterations. The result will be converted to a fixed score range.

```python
def _sha256(input_data: str) -> str:
    input_bytes = input_data.encode('utf-8')
    return hashlib.sha256(input_bytes).hexdigest()
```

Here is the remaining `_sha256` function, which converts the input data to `bytes` and returns a hex-encoded digest of that data:

### constants.py

[`constants.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/tutorial_app/constants.py)

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

### task_manager.py

[`task_manager.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/tutorial_app/task_manager.py)

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

### SubtaskStatus

```python
class SubtaskStatus(enum.Enum):
    WAITING = None
    COMPUTING = 'computing'
    VERIFYING = 'verifying'
    SUCCESS = 'success'
    FAILURE = 'failure'
    ABORTED = 'aborted'
```
`SubtaskStatus` is defined in `golem_task_api.apputils.task` as


### Extending the task part model

```python
from golem_task_api.apputils.task import database


class Part(database.Part):
    input_data = peewee.CharField(null=True)
    difficulty = peewee.FloatField(null=True)


class TaskManager(database.DBTaskManager):
    def __init__(self, work_dir: Path) -> None:
        super().__init__(work_dir, part_model=Part)
```

For the purpose of this project, we're going to extend the task part model with additional fields.

We've added two fields to the `Part` model:

- `input_data`, which will be the source data for our PoW compute function
- `difficulty`, representing the PoW function difficulty threshold

Now we want the `DBTaskManager` to use our `Part` model. We can do that by calling `super().__init__(work_dir, part_model=Part)`.

### commands.py

[`commands.py` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/tutorial_app/tutorial_app/commands.py)

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

### Helper function

```python
def _read_zip_contents(path: Path) -> str:
    with zipfile.ZipFile(path, 'r') as f:
        input_file = f.namelist()[0]
        with f.open(input_file) as zf:
            return zf.read().decode('utf-8')
```
- open the archive
- assume there's a single file inside
- open the archived file
- read the contents as a string
In the tutorial app, we're going to assume that each resource (be it subtask input data or subtask computation result) is a ZIP file containing a single file. To simplify read operations on files inside of those archives, we will define the following helper function:



Let's go through the commands, one by one.

### 1. `create_task`

```python
    async def create_task(
            work_dir: RequestorTaskDir,
            max_part_count: int,
            task_params: dict,
    ) -> Task:

```

> validate the 'difficulty' parameter

```python
        difficulty = int(task_params['difficulty'])
        if difficulty < 0:
            raise ValueError(f"difficulty={difficulty}")
```

> check whether resources were provided

```python
        resources = task_params.get('resources')
        if not resources:
            raise ValueError(f"resources={resources}")
```

> read the input resource file, provided by the user (requestor)

```python
        try:
            task_input_file = work_dir.task_inputs_dir / resources[0]
            input_data = task_input_file.read_text('utf-8')
        except (IOError, StopIteration) as exc:
            raise ValueError(f"Invalid resource file: {resources} ({exc})")
```

> create the task within the task manager

```python
        task_manager = TaskManager(work_dir)
        task_manager.create_task(max_part_count)
```

> update the parts in the database with our input data

```python
        for num in range(max_part_count):
            part = task_manager.get_part(num)
            part.input_data = input_data + str(uuid.uuid4())
            part.difficulty = difficulty + (difficulty % 2)
            part.save()
```

> return task's definition. We need to specify:
> - the execution environment ID. Here: Docker CPU-only compute
> - specify the Docker CPU environment prerequisites
> - a minimum memory requirement in MiB

```python
        return Task(
            env_id=DOCKER_CPU_ENV_ID,  # 'docker_cpu'
            prerequisites=PREREQUISITES,
            inf_requirements=Infrastructure(min_memory_mib=50.))
```

Returns a computation environment ID and prerequisites JSON, specifying the parameters needed to execute task computation.



    Where `PREREQUISITES` tell us which Docker image providers should pull and execute:

	```python
        PREREQUISITES = {
            "image": 'golemfactory/tutorialapp',
            "tag": "1.0",
        }
	```

### 2. `abort_task`

```python
    async def abort_task(
            work_dir: RequestorTaskDir,
    ) -> None:
        task_manager = TaskManager(work_dir)
```

> abort the task and currently running subtasks

```python
        task_manager.abort_task()
```
Will be called when the subtask is aborted by the user or timed out. Should stop verification of the subtask (if it's running) and perform any other necessary cleanup.



### 3. `abort_subtask`

```python
    async def abort_subtask(
            work_dir: RequestorTaskDir,
            subtask_id: str
    ) -> None:
        task_manager = TaskManager(work_dir)
```

> abort a single subtask by changing its status to 'ABORTED';
> task manager will automatically handle the new status

```python
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)
```
Will be called when the subtask is aborted by the user or timed out.



### 4. `next_subtask`

```python
    async def next_subtask(
            work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> Optional[api.structs.Subtask]:
        task_manager = TaskManager(work_dir)
```

> check whether we have any parts left for computation

```python
        part_num = task_manager.get_next_computable_part_num()
        if part_num is None:
            return None
```

> get the part model from the database

```python
        part = task_manager.get_part(part_num)
```

> write subtask input data file under a predefined directory

```python
        subtask_input_file = work_dir.subtask_inputs_dir / f'{subtask_id}.zip'
        with zipfile.ZipFile(subtask_input_file, 'w') as zf:
            zf.writestr(subtask_id, part.input_data)
        resources = [subtask_input_file.name]
```

> bind the subtask to the part number and mark it as started

```python
        task_manager.start_subtask(part_num, subtask_id)
```

> create subtask's definition. We need to specify:
>   - subtask parameters, which will be passed to providers as input
>     computation parameters
>   - a list of resources (file names) for providers to download and
>     use for the computation. Resource transfers are handled
>     automatically by Golem

```python
        return api.structs.Subtask(
            params={
                'difficulty': part.difficulty,
                'resources': resources,
            },
            resources=resources,
        )
```
Returns subtask_params_json which is the JSON string containing subtask specific parameters.
Also returns resources which is a list of names of files required for computing the subtask. Files with these names are required to be present in `{task_id}/{constants.SUBTASK_INPUTS_DIR}` directory.

Can return an empty message meaning that the app refuses to assign a subtask to the provider node (for whatever reason).



### 5. `verify_subtask`


```python
    async def verify_subtask(
            work_dir: RequestorTaskDir,
            subtask_id: str,
    ) -> Tuple[VerifyResult, Optional[str]]:

        subtask_outputs_dir = work_dir.subtask_outputs_dir(subtask_id)
```

> read contents of the subtask input data file

```python
        output_data = _read_zip_contents(subtask_outputs_dir / f'{subtask_id}.zip')
```

> parse the read data as PoW computation result and nonce

```python
        provider_result, provider_nonce = output_data.rsplit(' ', maxsplit=1)
        provider_nonce = int(provider_nonce)
```

> notify the task manager that the subtask is being verified

```python
        task_manager = TaskManager(work_dir)
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.VERIFYING)

        try:
```

> retrieve current part model from the database

```python
            part_num = task_manager.get_part_num(subtask_id)
            part = task_manager.get_part(part_num)
```

> execute the verification function

```python
            proof_of_work.verify(
                part.input_data,
                difficulty=part.difficulty,
                against_result=provider_result,
                against_nonce=provider_nonce)
        except (AttributeError, ValueError) as err:
```

> verification has failed; update the status in the task manager

```python
            task_manager.update_subtask_status(subtask_id, SubtaskStatus.FAILURE)
            return VerifyResult.FAILURE, err.message
```

> verification has succeeded
> copy results to the output directory, set by the requestor

```python
        shutil.copy(
            subtask_outputs_dir / f'{subtask_id}.zip',
            work_dir.task_outputs_dir / f'{subtask_id}.zip')
```

> update the status in the task manager

```python
        task_manager.update_subtask_status(subtask_id, SubtaskStatus.SUCCESS)
        return VerifyResult.SUCCESS, None
```
Called when computation results have been downloaded by Golem. For successfully verified subtasks it can also perform merging of the partial results into the final one.



### 6. `discard_subtasks`

```python
    async def discard_subtasks(
            work_dir: RequestorTaskDir,
            subtask_ids: List[str],
    ) -> List[str]:
        task_manager = TaskManager(work_dir)
```

> the PoW app simply aborts the subtasks in this case

```python
        for subtask_id in subtask_ids:
            task_manager.update_subtask_status(subtask_id, SubtaskStatus.ABORTED)
        return subtask_ids
```
Should discard results of given subtasks and any dependent subtasks.



### 7. `has_pending_subtasks`

```python
    async def has_pending_subtasks(
            work_dir: RequestorTaskDir,
    ) -> bool:
        task_manager = TaskManager(work_dir)
        return task_manager.get_next_computable_part_num() is not None
```
Returns a boolean indicating whether there are any more pending subtasks waiting for computation at given moment.


### 8. `run_benchmark`

```python
    async def run_benchmark() -> float:
```

> execute the benchmark function in the background and wait for the result

```python
        return await api.threading.Executor.run(proof_of_work.benchmark)
```
Returns a score which indicates how efficient the machine is for this type of task.

### 9. `compute_subtask`

```python
    async def compute_subtask(
            work_dir: ProviderTaskDir,
            subtask_id: str,
            subtask_params: dict,
    ) -> Path:
```

> validate subtask input parameters

```python
        resources = subtask_params['resources']
        if not resources:
            raise ValueError(f"resources={resources}")
        difficulty = int(subtask_params['difficulty'])
        if difficulty < 0:
            raise ValueError(f"difficulty={difficulty}")
```

> read the subtask input data from file, saved in a predefined directory

```python
        subtask_input_file = work_dir.subtask_inputs_dir / resources[0]
        subtask_input = _read_zip_contents(subtask_input_file)
```

> execute computation in background and wait for the result

```python
        hash_result, nonce = await api.threading.Executor.run(
            proof_of_work.compute,
            input_data=subtask_input,
            difficulty=difficulty)
```

> bundle computation output and save it in a predefined directory

```python
        subtask_output_file = work_dir / f'{subtask_id}.zip'
        with zipfile.ZipFile(subtask_output_file, 'w') as zf:
            zf.writestr(subtask_id, f'{hash_result} {nonce}')
```

> return the name of our output file

```python
        return subtask_output_file.name
```

Executes the computation.

## Bundling the application

[`Dockerfile` on github](https://github.com/golemfactory/tutorialapp/blob/master/image/Dockerfile)

```
Tutorial-App
└── image/
    ├── tutorial_app/
    └── Dockerfile
```

In this section we're going to build a Docker image with our application. Please create an empty `Dockerfile` in the `Tutorial-App/image/` directory. Then, add the following lines:

```dockerfile
    FROM golemfactory/base:1.5
```

> The image is going to be derived from a base Golem image.


```dockerfile
    RUN apt update
    RUN apt install -y python3-pip
```

> Install prerequisites.


```dockerfile
    COPY tutorial_app /golem/tutorial_app
```

> Copy application code.


```dockerfile
    RUN python3 -m pip install --no-cache-dir --upgrade pip
    RUN python3 -m pip install --no-cache-dir -r /golem/tutorial_app/requirements.txt
    RUN python3 -m pip install --no-cache-dir /golem/tutorial_app
```

> Install required packages and the app itself.


```dockerfile
    RUN apt remove -y python3-pip
    RUN apt clean
```

> Clean up the no longer needed packages.

```dockerfile
    WORKDIR /golem/work
    ENTRYPOINT ["python3", "-m", "tutorial_app.entrypoint"]
```

> Set up the working directory inside the image and the entrypoint.

In order to build the image, execute the following command in the `tutorialapp` directory:

```
docker build image -t golemfactory/tutorialapp:1.0.0
```

That's it!

# tutorialapp hands on
## Preparare hands on

In this section we are going to run your application locally inside golem. Before we start make sure you have the prerequisites:

```
../
├── tutorialapp/
└── golem/
```

1. Cloned `tutorialapp` from github `git clone https://github.com/golemfactory/tutorialapp.git`
2. Working golem node from source

For this guide, the `tutorialapp` and `golem` repositories are in the same folder.

#### Build the docker image

```
$ docker image golemfactory/tutorialapp
REPOSITORY                 TAG                 IMAGE ID            CREATED             SIZE
golemfactory/tutorialapp   1.0.0               <random_id>         <some time ago>     <not so large>
```
If you have followed the in depth guide, you should have a build docker image.

To build this docker image, navigate to the `tutorialapp` folder and run:

`docker build image -t golemfactory/tutorialapp:1.0.0`

## Run the `basic_integration` test

The easiest way to test your app is to run a `basic_integration` test, provided in the golem source files.
In this example we will run the test on the `tutorialapp`.
The required input files are available in the [`examples` on github](https://github.com/golemfactory/tutorialapp/tree/master/examples). Put both source folders next to each other to copy/paste the commands below.

#### Preparation

Navigate to the golem source folder and enable your virtual env ( optional ), make sure golem is not running.

For windows users: please load your `docker-machine env golem`, by copying the last line of the output without the first characters

```
pip install -r requirements.txt
python scripts/task_api_tests/basic_integration.py task-from-app-def ../tutorialapp/examples/app_descriptor.json ../tutorialapp/examples/app_parameters.json --resources ../tutorialapp/examples/input.txt --max-subtasks=1
```
#### Testing the app

Now you are ready to test the app! Run the following commands:

## Run the app on a local golem setup

When the `basic_integration` test passes your app is ready to be ran on 2 golem nodes:

#### Add the app descriptor JSON file to your requestor's data-dir

An app descriptor file is generated by the developer to be loaded into your golem.
For this tutorial you can use `app_descriptor.json` from the `tutorialapp/examples` folder.
The app descriptor file is needed by requesting nodes and should be placed under `<golem_data_dir>/apps` directory.
`golem_data_dir` can be found at the following locations:

   - macOS

    `~/Library/Application Support/golem/default/<mainnet|rinkeby>`

   - Linux

    `~/.local/share/golem/default/<mainnet|rinkeby>`

   - Windows

    `%LOCALAPPDATA%\golem\golem\default\<mainnet|rinkeby>`

The first time you start golem the app is enabled by default, the second time you need to update the database to enable it.

To enable the app, wait for `golemapp` to start and then run:

```
golemcli debug rpc apps.update 801964d531675a235c9ddcfda00075cb 1
```

#### Build the docker image on all nodes

Check if you have [built the docker image](#prepare-the-docker-image) on all participating nodes.

```json
    {
        "golem": {
            "app_id": "801964d531675a235c9ddcfda00075cb",
            "name": "test task",
            "resources": ["/absolute/path/to/tutorialapp/examples/input.txt"],
            "max_price_per_hour": "1000000000000000000",
            "max_subtasks": 4,
            "task_timeout": 180,
            "subtask_timeout": 60,
            "output_directory": "/absolute/path/to/output/directory"
        },
        "app": {
            "difficulty": "1",
            "resources": [
                "input.txt"
            ]
        }
    }
```
#### Create a `task.json` file to request a task

Create a `task.json` file with the following contents, make sure to update the paths to your setup:

```
golemapp --protocol_id=1337
```
#### Enter a private network ( optional, recommended to not have others pick up your task )

(optional) Enter a private network by starting all golem nodes with the `protocol_id` option

```
golemapp --task-api-dev
```
#### Start golem with task-api-dev flag

To make sure your new app is whitelisted and enabled run both provider and requestor with the task-api-dev flag:


```
golemcli tasks create ./task.json
```
#### Create a task using the `golemcli`

Now you can can start the task using golemcli:


# Publishing the application

## Publish for requestor

In order to make your app available to others, you will need to:

#### Upload the app image to Docker Hub

This short [tutorial](https://docs.docker.com/docker-hub/) will guide you through the process.

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
#### Create an app descriptor file and make it publicly available. The file has the following format:


The app descriptor file is needed by requesting nodes and should be placed under `<golem_data_dir>/apps` directory.

`golem_data_dir` can be found at the following locations:

- macOS

    `~/Library/Application Support/golem/default/<mainnet|rinkeby>`

- Linux

    `~/.local/share/golem/default/<mainnet|rinkeby>`

- Windows

    `%LOCALAPPDATA%\golem\golem\default\<mainnet|rinkeby>`

#### Enable the application

Before you can run any new application in golem you need to enable it for the requestor

To list currently installed apps:
- `golemcli debug rpc apps.list`

To enable an app run:
- `golemcli debug rpc apps.update <app_id> <enabled_flag>`

#### Whitelist your image repository within Golem.

As a requestor, you also have to whitelist the "requestor prerequisite" docker hub repository

In order to manage a repository whitelist use the following CLI commands:

- `golemcli debug rpc env.docker.repos.whitelist`

To display all whitelisted repositories.

- `golemcli debug rpc env.docker.repos.whitelist.add <repository_name>`

Whitelist `<repository_name>`.

- `golemcli debug rpc env.docker.repos.whitelist.remove <repository_name>`

Remove the `<repository_name>` from your whitelist.

- `golemcli debug rpc env.docker.images.discovered`

List all app images seen by your node on the network.

## Publish for provider

<aside class="notice">Make sure you trust the developer before whitelisting their repository!</aside>
By default only apps verified and uploaded by the Golem Factory to our docker repository are whitelisted.
Before whitelisting any other repository, make sure you trust the developer. Any apps they upload in the future will compute on your machine, also when they lose control over their docker repository account.

In order to provide for other developers apps, you will need to whitelist the "provider prerequisite" docker hub repository.


#### Whitelist your image repository within Golem.

In order to manage a repository whitelist use the following CLI commands:

- `golemcli debug rpc env.docker.repos.whitelist`

To display all whitelisted repositories.

- `golemcli debug rpc env.docker.repos.whitelist.add <repository_name>`

Whitelist `<repository_name>`.

- `golemcli debug rpc env.docker.repos.whitelist.remove <repository_name>`

Remove the `<repository_name>` from your whitelist.

- `golemcli debug rpc env.docker.images.discovered`

List all app images seen by your node on the network.


# Running a task on Task-Api

Task-API has been enabled on testnet since the 0.22.0 release. For this first release there is no GUI support yet, so this guide will use the CLI only. When you create a task with CLI it will not be supported from the GUI

### Short summary:

- Create new task-api JSON file
- Run the file using the cli

### Prepare a JSON

Here is an example of a new task-api JSON file.

```JSON
{
    "golem": {
        "app_id": "daec55c08c9de7b71bf4ec3eb759c83b",
        "name": "",
        "resources": ["/absolute/path/to/resources/file.blend"],
        "max_price_per_hour": "1_000_000_000_000_000_000",
        "max_subtasks": 1,
        "task_timeout": 600,
        "subtask_timeout": 590,
        "output_directory": "/absolute/path/to/output/"
    },
    "app": {
        "resources": ["file.blend"],
        "resolution": [320, 240],
        "frames": "1",
        "format": "PNG",
        "compositing": "False"
    }
}
```

### golem

```
...
    "golem": {
        "app_id": "daec55c08c9de7b71bf4ec3eb759c83b",
        "name": "",
        "resources": ["/absolute/path/to/resources/file.blend"],
        "max_price_per_hour": "1_000_000_000_000_000_000",
        "max_subtasks": 1,
        "task_timeout": 600,
        "subtask_timeout": 590,
        "output_directory": "/absolute/path/to/output/"
    },
...
```
The golem block of the JSON is meant for the input Golem needs, these are the same for all apps


#### golem.app_id

App id is the unique identifier of the app including its version.
You can get the build in app_id's from the logs when starting golem
`daec55c08c9de7b71bf4ec3eb759c83b` is `golemfactory/blenderapp:0.7.2` the only available option at the time.

#### golem.name

Name of the task in the GUI, not related to task-api. Allowed to be empty.

#### golem.resources

List of absolute paths to the files required for running this task

#### golem.max_price_per_hour

Max price to pay for the computation per hour, always passed as string ( in "").
The golem token has 18 digits, so for 1 GNT add 18 zero's.

#### golem.max_subtasks

Amount of subtasks to split the task into.

#### golem.task_timeout

Task timeout in seconds, 600 is 10 minutes.

#### golem.subtask_timeout

Subtask timeout in seconds, 600 is 10 minutes.

### app

```
...
    "app": {
        "resources": ["file.blend"],
        "resolution": [320, 240],
        "frames": "1",
        "format": "PNG",
        "compositing": "False"
    }
...
```
The app block contains app specific input parameters, these are different per app.

#### app.resources

A relative list of the resources, currently only one level.

#### app.resolution

Resolution of the blender render in pixels

#### app.frames

Frames to select during the blender render

#### app.format

Output format for the blender render ( PNG, JPEG or EXR )

#### app.compositing

Use compositing for the blender render?

## Run a task-api task

To run a task-api task you use the same command as the old ones.

```
golemcli tasks create ./task_api_json_file.json
```

Then you can use `golemcli tasks show` to list the task
We also implemented `golemcli tasks abort`, `.. delete` and `.. restart_subtask`
Other commands are not supported yet, they will be added soon

To help debug the task-api computation there are extra logs stored in your `logs/app_name/` folder.
Please provide the generated logs next to the regular logs when creating issues.
