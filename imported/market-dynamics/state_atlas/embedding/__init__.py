"""Embeddings (OOS-projectable only). β-VAE in vae.py — see DECISIONS.md."""

from state_atlas.embedding.base import Embedder

__all__ = ["Embedder", "BetaVAEEmbedder"]


def __getattr__(name: str):
    # Lazy import so users without [embed] extra (no torch) can still
    # import state_atlas.embedding for the Protocol type.
    if name == "BetaVAEEmbedder":
        from state_atlas.embedding.vae import BetaVAEEmbedder

        return BetaVAEEmbedder
    raise AttributeError(name)
