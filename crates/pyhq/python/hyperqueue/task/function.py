import pickle
from typing import Callable, Dict

from ..ffi.protocol import TaskDescription
from ..wrapper import CloudWrapper
from .task import Task, TaskId

_CLOUDWRAPPER_CACHE = {}


def purge_cache():
    global _PICKLE_CACHE
    _PICKLE_CACHE = {}


def cloud_wrap(fn, cache=True) -> CloudWrapper:
    if isinstance(fn, CloudWrapper):
        return fn
    return CloudWrapper(fn, cache=cache)


class PythonEnv:
    def __init__(self, python_bin="python3", prologue=None, shell="bash"):
        code = (
            "import sys,pickle\n"
            "try:\n"
            " fn,a,kw=pickle.loads(sys.stdin.buffer.read())\n"
            " fn(*a, **(kw if kw is not None else {}))\n"
            "except Exception as e:\n"
            " import os, traceback\n"
            " t = traceback.format_exc()\n"
            " with open(os.environ['HQ_ERROR_FILENAME'], 'w') as f:\n"
            "  f.write(t)\n"
            " sys.exit(1)"
        )

        if prologue:
            self.args = [shell, "-c", f'{prologue}\n\n{python_bin} -c "{code}"']
        else:
            self.args = [python_bin, "-c", code]


class PythonFunction(Task):
    def __init__(
        self,
        fn: Callable,
        *,
        args=(),
        kwargs=None,
        stdout=None,
        stderr=None,
        dependencies=(),
    ):
        super().__init__(dependencies)

        fn_id = id(fn)
        wrapper = _CLOUDWRAPPER_CACHE.get(fn_id)
        if wrapper is None:
            wrapper = cloud_wrap(fn)
            _CLOUDWRAPPER_CACHE[fn_id] = wrapper

        self.fn = wrapper
        self.args = args
        self.kwargs = kwargs
        self.stdout = stdout
        self.stderr = stderr

    def _build(self, client, id_map: Dict[Task, TaskId]) -> TaskDescription:
        depends_on = [id_map[dependency] for dependency in self.dependencies]
        return TaskDescription(
            id=id_map[self],
            args=client.python_env.args,
            stdout=self.stdout,
            stderr=self.stderr,
            env={},
            stdin=pickle.dumps((self.fn, self.args, self.kwargs)),
            cwd=None,
            dependencies=depends_on,
            task_dir=True,
        )
