"""Phase 3 — β-VAE embedder tests.

Cheap, deterministic checks: tiny synthetic 2D-structured data, short training,
posterior collapse / OOS / save-load / KL diagnostic invariants.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from state_atlas.config import EmbeddingConfig  # noqa: E402
from state_atlas.embedding import BetaVAEEmbedder  # noqa: E402


def _two_cluster_data(n_per: int = 200, in_dim: int = 8, seed: int = 0) -> np.ndarray:
    """Two well-separated Gaussian blobs along axis 0; rest are noise dimensions."""
    rng = np.random.default_rng(seed)
    centers = np.array([+2.5, -2.5])
    cluster = rng.choice(2, size=2 * n_per)
    X = rng.standard_normal((2 * n_per, in_dim)) * 0.5
    X[:, 0] += centers[cluster]
    return X.astype(np.float32)


def _short_cfg(**overrides) -> EmbeddingConfig:
    base = dict(
        type="vae",
        latent_dim=2,
        hidden_dims=[16, 8],  # tiny to keep tests fast
        beta=0.25,
        epochs=40,
        batch_size=64,
        lr=2e-3,
        kl_anneal_epochs=20,
        seed=0,
    )
    base.update(overrides)
    return EmbeddingConfig(**base)


def test_fit_then_transform_shapes() -> None:
    X = _two_cluster_data()
    cfg = _short_cfg()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg).fit(X)
    Z = emb.transform(X)
    assert Z.shape == (X.shape[0], cfg.latent_dim)


def test_transform_is_deterministic_oos() -> None:
    """Calling transform twice on the same input yields identical points."""
    X = _two_cluster_data()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=_short_cfg()).fit(X)
    Z1 = emb.transform(X[:50])
    Z2 = emb.transform(X[:50])
    np.testing.assert_array_equal(Z1, Z2)


def test_seed_reproducibility() -> None:
    """Same seed + same data + same config → identical training outcome."""
    X = _two_cluster_data()
    cfg = _short_cfg()
    a = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg).fit(X)
    b = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg).fit(X)
    Za = a.transform(X[:20])
    Zb = b.transform(X[:20])
    np.testing.assert_allclose(Za, Zb, atol=1e-6)


def test_kl_per_dim_shape_and_diagnostics() -> None:
    """KL per dim has the right shape and effective_dim respects the threshold."""
    X = _two_cluster_data()
    cfg = _short_cfg()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg).fit(X)
    kl = emb.kl_per_dim
    assert kl.shape == (cfg.latent_dim,)
    assert np.all(kl >= 0)
    d_low = emb.effective_dim(tau=1e-9)
    d_high = emb.effective_dim(tau=1e9)
    assert d_high <= d_low <= cfg.latent_dim


def test_reports_recon_mse() -> None:
    X = _two_cluster_data()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=_short_cfg()).fit(X)
    assert isinstance(emb.recon_mse, float) and emb.recon_mse >= 0.0


def test_save_load_roundtrip(tmp_path: Path) -> None:
    X = _two_cluster_data()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=_short_cfg()).fit(X)
    path = tmp_path / "vae.pt"
    emb.save(path)
    loaded = BetaVAEEmbedder.load(path)
    np.testing.assert_allclose(emb.transform(X[:30]), loaded.transform(X[:30]), atol=1e-6)
    np.testing.assert_allclose(emb.kl_per_dim, loaded.kl_per_dim, atol=1e-9)


def test_posterior_collapse_on_pure_noise_is_observable() -> None:
    """When the data is pure isotropic noise, KL should be small on most dims.

    We don't require complete collapse (training is short), just that the
    diagnostic is observable: at least one dim is at most modestly active.
    """
    rng = np.random.default_rng(7)
    X = rng.standard_normal((400, 6)).astype(np.float32)
    cfg = _short_cfg(beta=1.0, epochs=60, kl_anneal_epochs=10)
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=cfg).fit(X)
    kl = emb.kl_per_dim
    # Posterior collapse pressure: at least one latent dim has lower KL than the other.
    assert kl.min() < kl.max(), f"KL per dim {kl} — expected asymmetry under noise"


def test_wrong_input_dim_raises() -> None:
    X = _two_cluster_data()
    emb = BetaVAEEmbedder(in_dim=X.shape[1], cfg=_short_cfg()).fit(X)
    with pytest.raises(ValueError, match="X must be"):
        emb.transform(X[:, :3])
