"""β-VAE embedder (torch, CPU).

Architecture (CPU < 5 min constraint, see DECISIONS.md):

    encoder:  in → 64 → 32 → (μ, logσ²)   (GELU between layers)
    decoder:  z  → 32 → 64 → in           (mirror, identity head)

Loss = MSE_per_sample(sum over dims)  +  β · KL_per_sample(sum over dims)

β is annealed linearly from 0 to ``cfg.beta`` over ``cfg.kl_anneal_epochs``
epochs. This delays the regularization pressure until the encoder has
something to compress, which is the standard mitigation for posterior
collapse.

Posterior collapse is a *diagnostic*, not a bug (DECISIONS.md): the per-dim
KL is reported via ``kl_per_dim`` so the caller can decide whether the
embedding actually uses ``latent_dim`` axes or has folded onto fewer.

Inputs are expected already causally z-scored (Phase 2). The decoder
therefore reconstructs in the same scale; no internal normalization.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from state_atlas.config import EmbeddingConfig

log = logging.getLogger(__name__)


class _BetaVAEModule(nn.Module):
    def __init__(self, in_dim: int, latent_dim: int, hidden_dims: list[int]):
        super().__init__()
        # encoder
        enc_layers: list[nn.Module] = []
        prev = in_dim
        for h in hidden_dims:
            enc_layers.append(nn.Linear(prev, h))
            enc_layers.append(nn.GELU())
            prev = h
        self.encoder_body = nn.Sequential(*enc_layers)
        self.head_mu = nn.Linear(prev, latent_dim)
        self.head_logvar = nn.Linear(prev, latent_dim)

        # decoder (mirror)
        dec_layers: list[nn.Module] = []
        prev = latent_dim
        for h in reversed(hidden_dims):
            dec_layers.append(nn.Linear(prev, h))
            dec_layers.append(nn.GELU())
            prev = h
        dec_layers.append(nn.Linear(prev, in_dim))
        self.decoder = nn.Sequential(*dec_layers)

    def encode(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = self.encoder_body(x)
        return self.head_mu(h), self.head_logvar(h)

    def reparameterize(self, mu: torch.Tensor, logvar: torch.Tensor) -> torch.Tensor:
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        mu, logvar = self.encode(x)
        z = self.reparameterize(mu, logvar)
        x_hat = self.decoder(z)
        return x_hat, mu, logvar


class BetaVAEEmbedder:
    """Trainable β-VAE conforming to the Embedder Protocol."""

    def __init__(self, in_dim: int, cfg: EmbeddingConfig):
        self.in_dim = in_dim
        self.cfg = cfg
        # Reproducibility: torch + numpy seeded together so train order matches.
        torch.manual_seed(cfg.seed)
        np.random.seed(cfg.seed)
        self.device = torch.device("cpu")
        self.model = _BetaVAEModule(
            in_dim=in_dim,
            latent_dim=cfg.latent_dim,
            hidden_dims=list(cfg.hidden_dims),
        ).to(self.device)
        self._kl_per_dim: np.ndarray | None = None
        self._recon_mse: float | None = None

    # ------------------------------------------------------------------
    # Embedder Protocol
    # ------------------------------------------------------------------

    def fit(
        self,
        X: np.ndarray,
        val_frac: float = 0.1,
        verbose: bool = False,
    ) -> BetaVAEEmbedder:
        X = np.ascontiguousarray(X, dtype=np.float32)
        if X.ndim != 2 or X.shape[1] != self.in_dim:
            raise ValueError(f"X must be (N, {self.in_dim}), got {X.shape}")
        n = len(X)
        if n < 32:
            raise ValueError(f"need ≥32 rows to fit, got {n}")

        # Causal train/val split: last val_frac is held out (no shuffling across the boundary).
        n_val = max(8, int(n * val_frac))
        X_train, X_val = X[:-n_val], X[-n_val:]

        train_ds = TensorDataset(torch.from_numpy(X_train))
        # Generator pins the shuffle for reproducibility.
        g = torch.Generator().manual_seed(self.cfg.seed)
        train_loader = DataLoader(
            train_ds,
            batch_size=min(self.cfg.batch_size, len(X_train)),
            shuffle=True,
            generator=g,
            drop_last=False,
        )
        opt = torch.optim.Adam(self.model.parameters(), lr=self.cfg.lr)

        anneal_steps = max(1, self.cfg.kl_anneal_epochs)
        for epoch in range(self.cfg.epochs):
            beta = float(self.cfg.beta) * min(1.0, (epoch + 1) / anneal_steps)
            self.model.train()
            running = 0.0
            for (xb,) in train_loader:
                xb = xb.to(self.device)
                x_hat, mu, logvar = self.model(xb)
                # per-sample sums over dims, then mean over batch
                recon = ((x_hat - xb) ** 2).sum(dim=1).mean()
                kl = (-0.5 * (1 + logvar - mu**2 - logvar.exp())).sum(dim=1).mean()
                loss = recon + beta * kl
                opt.zero_grad()
                loss.backward()
                opt.step()
                running += float(loss.item())
            if verbose and (epoch % 20 == 0 or epoch == self.cfg.epochs - 1):
                log.info(
                    "epoch %3d  beta=%.3f  loss=%.4f", epoch, beta, running / len(train_loader)
                )

        # Diagnostics on the held-out tail.
        self.model.eval()
        with torch.no_grad():
            x_val = torch.from_numpy(X_val).to(self.device)
            x_hat, mu, logvar = self.model(x_val)
            self._kl_per_dim = (
                (-0.5 * (1 + logvar - mu**2 - logvar.exp())).mean(dim=0).cpu().numpy()
            )
            self._recon_mse = float(((x_hat - x_val) ** 2).mean().item())
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """Deterministic OOS projection: returns μ (no sampling)."""
        X = np.ascontiguousarray(X, dtype=np.float32)
        if X.ndim != 2 or X.shape[1] != self.in_dim:
            raise ValueError(f"X must be (N, {self.in_dim}), got {X.shape}")
        self.model.eval()
        with torch.no_grad():
            x = torch.from_numpy(X).to(self.device)
            mu, _ = self.model.encode(x)
        return mu.cpu().numpy()

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": self.model.state_dict(),
                "in_dim": self.in_dim,
                "cfg": self.cfg.model_dump(),
                "kl_per_dim": self._kl_per_dim,
                "recon_mse": self._recon_mse,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> BetaVAEEmbedder:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
        cfg = EmbeddingConfig(**ckpt["cfg"])
        emb = cls(in_dim=ckpt["in_dim"], cfg=cfg)
        emb.model.load_state_dict(ckpt["state_dict"])
        emb._kl_per_dim = ckpt["kl_per_dim"]
        emb._recon_mse = ckpt["recon_mse"]
        return emb

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    @property
    def kl_per_dim(self) -> np.ndarray:
        if self._kl_per_dim is None:
            raise RuntimeError("call fit() before reading kl_per_dim")
        return self._kl_per_dim.copy()

    @property
    def recon_mse(self) -> float:
        if self._recon_mse is None:
            raise RuntimeError("call fit() before reading recon_mse")
        return self._recon_mse

    def effective_dim(self, tau: float = 0.1) -> int:
        """# of latent dims with KL_i > τ. See DECISIONS.md Phase 4.5."""
        return int((self.kl_per_dim > tau).sum())
