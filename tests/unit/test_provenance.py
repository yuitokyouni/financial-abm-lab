"""Tests for provenance tracking."""

from prism.provenance import ProvenanceRecord, ProvenanceTracker, hash_bytes


class TestHashBytes:
    def test_deterministic(self):
        h1 = hash_bytes(b"hello")
        h2 = hash_bytes(b"hello")
        assert h1 == h2

    def test_different_input(self):
        h1 = hash_bytes(b"hello")
        h2 = hash_bytes(b"world")
        assert h1 != h2

    def test_length(self):
        h = hash_bytes(b"test")
        assert len(h) == 16


class TestProvenanceTracker:
    def test_seal_produces_record(self):
        tracker = ProvenanceTracker(run_id="test_run_001")
        tracker.record_data_hash("pre_data", "abc123")
        tracker.record_seed("simulation", 42)
        tracker.record_estimator_version("leverage_effect", "0.1.0")
        tracker.record_parameter("adapter", "sg")

        record = tracker.seal()
        assert isinstance(record, ProvenanceRecord)
        assert record.run_id == "test_run_001"
        assert record.data_hashes["pre_data"] == "abc123"
        assert record.rng_seeds["simulation"] == 42
        assert record.estimator_versions["leverage_effect"] == "0.1.0"
        assert record.parameters["adapter"] == "sg"

    def test_to_dict(self):
        tracker = ProvenanceTracker(run_id="test_run_002")
        tracker.record_data_hash("pre", "hash1")
        record = tracker.seal()
        d = record.to_dict()
        assert d["prov:type"] == "prism:EvaluationRun"
        assert d["run_id"] == "test_run_002"
        assert d["data_hashes"]["pre"] == "hash1"

    def test_auto_run_id(self):
        tracker = ProvenanceTracker()
        record = tracker.seal()
        assert record.run_id.startswith("run_")
