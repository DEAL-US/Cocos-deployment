"""The contract of the service, with the fake tools of tests/tools."""
import pytest
from fastapi.testclient import TestClient

FASTA = b">contig_1\nACGT\n"


@pytest.fixture
def client(service):
    return TestClient(service.app)


def test_lists_the_tools_with_their_inputs_and_software(client):
    models = client.get("/models").json()

    assert models["fake"] == {"inputs": ["assembly"], "software": [{"name": "Fake", "version": "1.0", "type": "tool"}]}
    assert models["broken"]["inputs"] == ["assembly", "proteins"]


def test_a_job_gives_its_results_raw_output_and_software(client):
    response = client.post("/predict/fake", files={"assembly": ("sample.fasta", FASTA)},
                           data={"organism": "NCBITaxon:562"})
    assert response.status_code == 200
    job_id = response.json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert job["status"] == "completed"
    assert job["model"] == "fake"
    assert job["organism"] == "NCBITaxon:562"
    assert job["software"] == [{"name": "Fake", "version": "1.0", "type": "tool"}]

    assert client.get(f"/jobs/{job_id}/result").json() == {"model": "fake", "results": [
        {"about": "ARO:0000020", "call": "R", "evidence": [{"gene": "blaFAKE-1", "identity": 99.5}]},
        {"about": "ARO:0000013", "score": 0.25},
    ]}
    raw = client.get(f"/jobs/{job_id}/raw")
    assert raw.status_code == 200
    assert "blaFAKE-1\tNCBITaxon:562" in raw.text


def test_a_tool_that_fails_on_its_input_fails_for_good(client):
    job_id = client.post("/predict/fake", files={"assembly": ("sample.fasta", b"not a fasta")}).json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert (job["status"], job["error_kind"], job["message"]) == ("failed", "input", "The assembly is not a FASTA file")
    assert client.get(f"/jobs/{job_id}/result").status_code == 409


def test_invalid_results_fail_the_job(client):
    job_id = client.post("/predict/broken", files={"assembly": ("a.fasta", FASTA), "proteins": ("p.faa", FASTA)}).json()["job_id"]

    job = client.get(f"/jobs/{job_id}").json()
    assert (job["status"], job["error_kind"]) == ("failed", "internal")
    assert "ARO term" in job["message"]


def test_rejects_unknown_models_and_missing_inputs(client):
    assert client.post("/predict/nothing", files={"assembly": ("a.fasta", FASTA)}).status_code == 404
    response = client.post("/predict/broken", files={"assembly": ("a.fasta", FASTA)})
    assert response.status_code == 400
    assert "proteins" in response.json()["detail"]


def test_unknown_jobs_are_not_found(client):
    for path in ("/jobs/nothing", "/jobs/nothing/result", "/jobs/nothing/raw"):
        assert client.get(path).status_code == 404


def test_busy_when_too_many_jobs_are_active(client, service, monkeypatch):
    monkeypatch.setattr(service, "MAX_ACTIVE_JOBS", 1)
    service.create_job("fake", {})  # pending

    response = client.post("/predict/fake", files={"assembly": ("a.fasta", FASTA)})
    assert response.status_code == 503
    assert response.json()["status"] == "busy"
