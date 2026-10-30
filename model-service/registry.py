"""
The tools of this service: each folder of tools/ with a tool.py is one, named after the folder.

A tool.py defines:
    INPUTS      the files the tool needs, by role, e.g. ("assembly",)
    run(inputs, organism, workdir) -> (results, raw)
                inputs is {role: Path}, organism an NCBITaxon CURIE or None, and workdir a folder
                for the files of the tool. results is a list as results.py describes, and raw the
                Path of the output of the tool itself (or None), which is kept as it is.
    software()  the tools and databases it uses, with their versions (see versions.py of the bio service)

A tool raises InputError when it fails because of its input, so running it again would fail too.
Each tool runs in its own conda environment, tool_<name>, built from its environment.yml, so that
tools with conflicting dependencies can live in the same image (see run_in_env).
"""
import importlib.util
import os
import subprocess
from functools import lru_cache
from pathlib import Path

TOOLS_DIR = Path(os.getenv("TOOLS_DIR", Path(__file__).parent / "tools"))

REQUIRED = ("INPUTS", "run", "software")


class InputError(Exception):
    """A tool failed because of its input: running it again on the same files would fail too."""


@lru_cache(maxsize=None)
def tools():
    """{name: module} of the tools in TOOLS_DIR. Raise ValueError if one lacks what a tool must define."""
    found = {}
    for path in sorted(TOOLS_DIR.glob("*/tool.py")):
        name = path.parent.name
        spec = importlib.util.spec_from_file_location(f"tools.{name}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        missing = [attribute for attribute in REQUIRED if not hasattr(module, attribute)]
        if missing:
            raise ValueError(f"The tool {name} does not define {', '.join(missing)} in {path}")
        found[name] = module
    return found


def get_tool(name):
    """The module of a tool, or None if there is no such tool."""
    return tools().get(name)


def run_in_env(tool_name, command, cwd, timeout=None):
    """Run a command in the conda environment of a tool and return its CompletedProcess (text output)."""
    return subprocess.run(
        ["conda", "run", "--no-capture-output", "-n", f"tool_{tool_name}", *command],
        cwd=cwd, capture_output=True, text=True, timeout=timeout,
    )
