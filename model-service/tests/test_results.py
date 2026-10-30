"""The results a tool gives, checked before they are kept."""
import pytest

from results import check_results


def test_keeps_valid_results_and_drops_empty_fields():
    assert check_results([{"about": "ARO:0000020", "call": "not_detected", "evidence": []},
                          {"about": "ARO:0000013", "score": 0}]) == [
        {"about": "ARO:0000020", "call": "not_detected"}, {"about": "ARO:0000013", "score": 0}]


@pytest.mark.parametrize("results", [
    {"about": "ARO:0000020", "call": "R"},                  # not a list
    [{"about": "amikacin", "call": "R"}],                   # not an ARO term
    [{"about": "ARO:0000020"}],                             # neither call nor score
    [{"about": "ARO:0000020", "call": "resistant"}],        # unknown call
    [{"about": "ARO:0000020", "score": 1.5}],               # score above 1
    [{"about": "ARO:0000020", "score": "high"}],            # score not a number
    [{"about": "ARO:0000020", "call": "R", "evidence": "blaKPC"}],  # evidence not a list of dicts
    [{"about": "ARO:0000020", "call": "R", "gene": "blaKPC"}],      # unknown key
])
def test_rejects_invalid_results(results):
    with pytest.raises(ValueError):
        check_results(results)
