"""A fake tool for the tests that gives invalid results."""
INPUTS = ("assembly", "proteins")


def run(inputs, organism, workdir):
    return [{"about": "amikacin", "call": "resistant"}], None


def software():
    return []
