# Tools

Each folder here is a prediction tool of the model service, named as the model it runs:

```
tools/<name>/
├── environment.yml   # its conda environment (the tool and its dependencies, with pinned versions)
└── tool.py           # INPUTS, run() and software(), as registry.py describes
```

The image builds one conda environment per tool, `tool_<name>`, so tools with conflicting
dependencies can live together; `run_in_env` in `registry.py` runs a command in it.
