"""
The result of a prediction, the same for every tool (and as Cocos stores it, in prediction/results.py).

A job gives a list of results, one for each thing the tool says something about:

    {"about": "ARO:0000020",           # an ARO term: an antibiotic, or a class of antibiotics
     "call": "R",                      # a verdict: one of CALLS (optional)
     "score": 0.83,                    # the probability of resistance, from 0 to 1 (optional)
     "evidence": [{...}, ...]}         # what the verdict rests on, e.g. the genes found (optional)

A result has a call, a score or both. The calls are R (resistant), I (susceptible, increased
exposure) and S (susceptible), as clinical categories; "possible" (a determinant of a class of
antibiotics was found, which does not always make a strain resistant to all of them); and
"not_detected" (no known determinant was found, which is not the same as susceptible).
"""
CALLS = ("R", "I", "S", "possible", "not_detected")


def check_results(results):
    """The results, if they are valid; raise ValueError otherwise."""
    if not isinstance(results, list):
        raise ValueError("The results must be a list.")
    return [_check(result) for result in results]


def _check(result):
    if not isinstance(result, dict):
        raise ValueError(f"A result must be a dict, not {result!r}.")
    unknown = set(result) - {"about", "call", "score", "evidence"}
    if unknown:
        raise ValueError(f"Unknown keys in a result: {', '.join(sorted(unknown))}.")
    about = result.get("about")
    if not isinstance(about, str) or not about.startswith("ARO:"):
        raise ValueError(f"A result must be about an ARO term (ARO:...), not {about!r}.")
    call, score = result.get("call"), result.get("score")
    if call is None and score is None:
        raise ValueError(f"The result about {about} needs a call or a score.")
    if call is not None and call not in CALLS:
        raise ValueError(f"Unknown call {call!r} about {about}; expected one of {', '.join(CALLS)}.")
    if score is not None and not (isinstance(score, (int, float)) and 0 <= score <= 1):
        raise ValueError(f"The score about {about} must be a number between 0 and 1, not {score!r}.")
    evidence = result.get("evidence", [])
    if not isinstance(evidence, list) or not all(isinstance(item, dict) for item in evidence):
        raise ValueError(f"The evidence about {about} must be a list of dicts.")
    return {key: value for key, value in result.items() if value is not None and value != []}
