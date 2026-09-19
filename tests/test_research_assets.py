from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import urllib.error

import pytest

from tools import research_assets as a

PDF = b"%PDF-1.7\nfixture\n"
HASH = hashlib.sha256(PDF).hexdigest()


class Response(io.BytesIO):
    def __init__(self, content=PDF, headers=None):
        super().__init__(content)
        self.headers = headers or {}


def test_catalog_load_and_find(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "references": [{"id": "paper", "sha256": HASH}]}))
    assert a.find_ref(a.load_catalog(path), "paper")["sha256"] == HASH


@pytest.mark.parametrize("refs", [[{"id": "../escape"}], [{"id": "x"}, {"id": "x"}], [{"id": "x", "sha256": "bad"}], [None]])
def test_catalog_rejects_bad_records(tmp_path, refs):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "references": refs}))
    with pytest.raises(a.AssetError):
        a.load_catalog(path)


def test_catalog_rejects_unknown_schema(tmp_path):
    path = tmp_path / "catalog.json"
    path.write_text('{"schema_version": 99, "references": []}')
    with pytest.raises(a.AssetError):
        a.load_catalog(path)


def test_sha256(tmp_path):
    path = tmp_path / "a.pdf"; path.write_bytes(PDF)
    assert a.sha256(path) == HASH


def test_find_ref_unknown():
    with pytest.raises(a.AssetError):
        a.find_ref({"references": []}, "missing")


def test_download_stages_verifies_and_reuses_cache(tmp_path, monkeypatch):
    calls = []
    def fake(*args):
        calls.append(args)
        return Response(headers={"Content-Length": str(len(PDF))})
    monkeypatch.setattr(a, "_open", fake)
    target = tmp_path / "a.pdf"
    assert a.download("url", {}, target, HASH, 100, pdf=True)["cache_hit"] is False
    assert a.download("url", {}, target, HASH, 100, pdf=True)["cache_hit"] is True
    assert len(calls) == 1
    assert target.read_bytes() == PDF
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.parametrize("content,expected,cap,pdf,headers", [
    (PDF, "0" * 64, 100, True, {}),
    (PDF, HASH, 2, True, {}),
    (PDF, HASH, 2, True, {"Content-Length": "100"}),
    (PDF, HASH, 100, True, {"Content-Length": "90"}),
    (b"html", hashlib.sha256(b"html").hexdigest(), 100, True, {}),
])
def test_failed_download_leaves_no_output(tmp_path, monkeypatch, content, expected, cap, pdf, headers):
    monkeypatch.setattr(a, "_open", lambda *_: Response(content, headers))
    with pytest.raises(a.AssetError):
        a.download("url", {}, tmp_path / "a.pdf", expected, cap, pdf=pdf)
    assert list(tmp_path.iterdir()) == []


def test_existing_file_never_overwritten(tmp_path, monkeypatch):
    path = tmp_path / "original.pdf"; path.write_bytes(b"keep")
    def forbidden(*_):
        pytest.fail("network must not be called")
    monkeypatch.setattr(a, "_open", forbidden)
    with pytest.raises(a.AssetError):
        a.download("url", {}, path, HASH, 100)
    assert path.read_bytes() == b"keep"


def test_symlink_refused(tmp_path):
    original = tmp_path / "original"; original.write_bytes(PDF)
    link = tmp_path / "link"; link.symlink_to(original)
    with pytest.raises(a.AssetError):
        a.download("url", {}, link, HASH, 100)
    assert original.read_bytes() == PDF


def test_hash_required_before_network(tmp_path, monkeypatch):
    with pytest.raises(a.AssetError):
        a.drive_download("id", tmp_path / "a.pdf", None)
    with pytest.raises(a.AssetError):
        a.gcs_download("gs://bucket/a", tmp_path / "a", "bad")


def test_drive_cache_needs_no_credentials(tmp_path, monkeypatch):
    path = tmp_path / "a.pdf"; path.write_bytes(PDF)
    monkeypatch.delenv("GOOGLE_DRIVE_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(a, "google_token", lambda *_: pytest.fail("no auth for cache hit"))
    assert a.drive_download("abc", path, HASH)["cache_hit"] is True


def test_fixed_host_allowlist():
    for url in ("http://api.zotero.org/users/1/items", "https://example.org", "https://api.zotero.org.evil.com", "https://key@api.zotero.org"):
        with pytest.raises(a.AssetError):
            a._open(url, {})


def test_redirect_never_forwards_credentials():
    with pytest.raises(a.AssetError):
        a.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.org")


def test_gcs_pins_and_escapes():
    url = a.gcs_url("gs://my-bucket/market data/2026.parquet", "123")
    assert "market%20data%2F2026.parquet" in url
    assert "generation=123" in url


@pytest.mark.parametrize("uri", ["file:///x", "gs://bucket/", "gs://bucket/*.csv", "gs://bucket/a?x=1", "gs://bucket/a#2"])
def test_gcs_rejects_nonexact_objects(uri):
    with pytest.raises(a.AssetError):
        a.gcs_url(uri)


def test_zotero_paging(monkeypatch):
    monkeypatch.setenv("ZOTERO_USER_ID", "123")
    monkeypatch.setenv("ZOTERO_API_KEY", "secret")
    seen = []
    def fake(url, headers):
        seen.append((url, headers))
        return [{"key": "ABCDEFGH", "version": 7, "data": {"title": "X", "tags": []}}]
    monkeypatch.setattr(a, "_json_request", fake)
    assert a.zotero_search("test", 50, 100)[0]["version"] == 7
    assert "start=100" in seen[0][0]
    assert "secret" not in seen[0][0]
    assert seen[0][1]["Zotero-API-Version"] == "3"
    with pytest.raises(a.AssetError):
        a.zotero_search("x", 101)


def test_literature_snapshot_is_read_only(tmp_path):
    path = tmp_path / "snapshot.json"
    raw = json.dumps([{"arxiv_id": "1902.02040v1", "title": "Speculation Game", "mechanism_summary": "abstract-based"}])
    path.write_text(raw)
    found = a.literature_search(path, "speculation", 1)
    assert found[0]["evidence_level"] == "discovery_summary_not_verified_full_text"
    assert found[0]["arxiv_id"].endswith("v1")
    assert path.read_text() == raw


def test_http_retry_is_bounded(monkeypatch):
    attempts = []
    def failing(*args, **kwargs):
        attempts.append(1)
        raise urllib.error.HTTPError("url", 503, "error", {}, None)
    monkeypatch.setattr(a.OPENER, "open", failing)
    monkeypatch.setattr(a.time, "sleep", lambda *_: None)
    with pytest.raises(a.AssetError):
        a._open("https://api.zotero.org/users/1/items", {})
    assert len(attempts) == 3


def test_doctor_missing_is_not_success(monkeypatch, tmp_path, capsys):
    for key in ("ZOTERO_USER_ID", "ZOTERO_API_KEY", "GOOGLE_DRIVE_ACCESS_TOKEN", "GOOGLE_GCS_ACCESS_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(a.shutil, "which", lambda *_: None)
    path = tmp_path / "catalog.json"; path.write_text('{"schema_version":1,"references":[]}')
    assert a.main(["--catalog", str(path), "doctor"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["drive"] == "missing_credentials"
    assert result["live_requested"] is False


def test_credential_rejects_newlines_without_echoing_secret():
    with pytest.raises(a.AssetError) as exc:
        a._credential("secret\nvalue")
    assert "secret\nvalue" not in str(exc.value)


def test_text_fetch_selects_registered_text(tmp_path, monkeypatch, capsys):
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version":1,"references":[{"id":"x","text":{"drive_file_id":"textid","sha256":HASH}}]}))
    def fake(fid, output, expected, cap, **kwargs):
        assert fid == "textid" and output.name == "x.pages.txt"
        assert kwargs["pdf"] is False and expected == HASH
        return {"ok": True}
    monkeypatch.setattr(a, "drive_download", fake)
    assert a.main(["--catalog",str(path),"refs","fetch","x","--text"]) == 0


def test_live_doctor_probes_metadata_only(monkeypatch):
    urls = []
    monkeypatch.setattr(a, "zotero_search", lambda *_: [])
    monkeypatch.setattr(a, "google_token", lambda *_: "token")
    monkeypatch.setattr(a, "_json_request", lambda url, _: urls.append(url) or {})
    result = a.doctor(True, {"references":[{"drive_file_id":"abc"}]}, "gs://bucket/a")
    assert all(result[k] == "live_read_ok" for k in ("zotero", "drive", "gcs"))
    assert all("alt=media" not in url for url in urls)
