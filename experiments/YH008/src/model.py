"""model.py -- backend-neutral probing/intervention API.

Exposes a small surface the rest of the pipeline depends on, so the backend
(TransformerLens now, nnsight fallback later) can be swapped without rewriting
downstream code (addendum: backend-neutral API):

    m = ProbeModel.load(cfg)
    out = m.p_sell(prompt_str)                  # group-normalized P(sell) + masses
    resid = m.cache(prompts, layers)            # {layer: (B, d_model)} at decision slot
    m.apply_direction_hook(layer, direction, mode, alpha)  # KO/Rescue/Amp (Stage 3)

Decision-token convention (fixed research decision #2 + addendum 0.2/§5):
  P(sell) = mass(False group) / (mass(True group) + mass(False group)), where each
  group's mass is the softmax probability summed over its spelling-variant tokens
  (computed via logsumexp over group logits). Out-of-group mass is reported; if it
  exceeds `out_of_group_mass_flag` the probe is flagged as failed for that state.
"""
from __future__ import annotations
from dataclasses import dataclass
from contextlib import contextmanager
from typing import Iterable
import math
import torch


@dataclass
class ProbeResult:
    p_sell: float
    mass_true: float
    mass_false: float
    in_group_mass: float       # mass_true + mass_false
    out_group_mass: float      # 1 - in_group_mass
    flagged: bool              # out_group_mass > threshold


class ProbeModel:
    def __init__(self, model, tokenizer, true_ids, false_ids,
                 out_of_group_mass_flag: float, device: str = "cuda"):
        self.model = model
        self.tokenizer = tokenizer
        self.true_ids = sorted(set(true_ids))
        self.false_ids = sorted(set(false_ids))
        self.group_ids = self.true_ids + self.false_ids
        self.out_flag = out_of_group_mass_flag
        self.device = device
        self.backend = "transformer_lens"

    # ---- construction -------------------------------------------------------
    @classmethod
    def load(cls, cfg, true_ids=None, false_ids=None):
        import os
        os.environ.setdefault("HF_HOME", cfg["paths"]["hf_home"])
        os.environ.setdefault("HF_HUB_CACHE", cfg["paths"]["hf_home"] + "/hub")
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        from transformer_lens import HookedTransformer
        from transformers import AutoTokenizer, AutoModelForCausalLM
        name = cfg["model"]["name"]
        rev = cfg["model"]["revision"]
        dtype = getattr(torch, cfg["model"]["dtype"])
        tok = AutoTokenizer.from_pretrained(name, revision=rev)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        tok.padding_side = "left"   # decision slot is always position -1
        hf = AutoModelForCausalLM.from_pretrained(name, revision=rev, torch_dtype=dtype)
        model = HookedTransformer.from_pretrained(
            name, hf_model=hf, tokenizer=tok, dtype=dtype,
            fold_ln=True, center_writing_weights=True, center_unembed=True,
        )
        del hf
        model.eval()
        device = str(model.cfg.device)
        if true_ids is None or false_ids is None:
            raise ValueError("true_ids/false_ids must be frozen by Stage 0.2 before load()")
        return cls(model, tok, true_ids, false_ids,
                   cfg["probe"]["out_of_group_mass_flag"], device=device)

    # ---- tokenization -------------------------------------------------------
    def _to_tokens(self, prompts):
        """Left-padded input_ids + attention_mask via the HF tokenizer. The chat
        template already includes BOS, so add_special_tokens=False. Returns
        (input_ids, attention_mask) on the model device."""
        if isinstance(prompts, str):
            prompts = [prompts]
        enc = self.tokenizer(list(prompts), return_tensors="pt", padding=True,
                             add_special_tokens=False)
        dev = self.model.cfg.device
        return enc["input_ids"].to(dev), enc["attention_mask"].to(dev)

    # ---- P(sell) from decision logits ---------------------------------------
    def _p_sell_from_logp(self, logp_row: torch.Tensor) -> ProbeResult:
        lt = torch.logsumexp(logp_row[self.true_ids], dim=0)
        lf = torch.logsumexp(logp_row[self.false_ids], dim=0)
        m_true = math.exp(lt.item()); m_false = math.exp(lf.item())
        in_group = m_true + m_false
        out_group = max(0.0, 1.0 - in_group)
        p_sell = m_false / in_group if in_group > 0 else float("nan")
        return ProbeResult(p_sell=p_sell, mass_true=m_true, mass_false=m_false,
                           in_group_mass=in_group, out_group_mass=out_group,
                           flagged=out_group > self.out_flag)

    @torch.no_grad()
    def p_sell(self, prompts) -> "ProbeResult | list[ProbeResult]":
        single = isinstance(prompts, str)
        toks, mask = self._to_tokens(prompts)
        logits = self.model(toks, attention_mask=mask)   # (B, S, V)
        logp = torch.log_softmax(logits[:, -1, :].float(), dim=-1)  # decision slot = -1 (left-padded)
        res = [self._p_sell_from_logp(logp[i]) for i in range(logp.shape[0])]
        return res[0] if single else res

    @torch.no_grad()
    def p_sell_batched(self, prompts, batch_size=16) -> list[ProbeResult]:
        out = []
        for i in range(0, len(prompts), batch_size):
            out.extend(self.p_sell(list(prompts[i:i + batch_size])))
        return out

    # ---- residual cache at the decision slot --------------------------------
    @torch.no_grad()
    def cache(self, prompts, layers: Iterable[int]) -> dict:
        """Return {layer: (B, d_model)} resid_post at the decision slot (pos -1).
        Selective cache: only the named layers' decision-slot vector is kept."""
        if isinstance(prompts, str):
            prompts = [prompts]
        layers = list(layers)
        names = [f"blocks.{L}.hook_resid_post" for L in layers]
        toks, mask = self._to_tokens(prompts)
        _, cache = self.model.run_with_cache(
            toks, attention_mask=mask, names_filter=lambda n: n in names, return_type=None)
        return {L: cache[f"blocks.{L}.hook_resid_post"][:, -1, :].clone().cpu()
                for L in layers}

    @torch.no_grad()
    def cache_batched(self, prompts, layers, batch_size=16) -> dict:
        layers = list(layers)
        acc = {L: [] for L in layers}
        for i in range(0, len(prompts), batch_size):
            c = self.cache(list(prompts[i:i + batch_size]), layers)
            for L in layers:
                acc[L].append(c[L])
        return {L: torch.cat(acc[L], dim=0) for L in layers}

    # ---- activation-level intervention (Stage 3; built for backend-neutrality) --
    @contextmanager
    def apply_direction_hook(self, layer: int, direction: torch.Tensor, mode: str,
                             alpha: float = 1.0):
        """Context manager adding a resid_post hook at `layer`.
          mode='ko'     : project OUT the unit direction  h' = h - (h.s_hat) s_hat
          mode='add'    : h' = h + alpha * s_hat            (Amp)
          mode='rescue' : project out then re-add          h' = h - (h.s_hat)s_hat + alpha*s_hat
        Unit-normalizes `direction`. Operates on every position (decision-slot read
        still taken at -1)."""
        s = direction.to(self.model.cfg.device, dtype=self.model.W_E.dtype)
        s = s / (s.norm() + 1e-8)
        name = f"blocks.{layer}.hook_resid_post"

        def hook(act, hook):  # act: (B, S, d_model)
            proj = (act @ s).unsqueeze(-1) * s  # (B,S,d)
            if mode == "ko":
                return act - proj
            if mode == "add":
                return act + alpha * s
            if mode == "rescue":
                return act - proj + alpha * s
            raise ValueError(f"unknown mode {mode}")

        self.model.add_hook(name, hook)
        try:
            yield
        finally:
            self.model.reset_hooks()

    # ---- behavioral generation (faithfulness only) --------------------------
    @torch.no_grad()
    def generate(self, prompt: str, max_new_tokens=256, temperature=0.0) -> str:
        toks = self.model.to_tokens(prompt, prepend_bos=False)
        out = self.model.generate(
            toks, max_new_tokens=max_new_tokens, do_sample=temperature > 0,
            temperature=max(temperature, 1e-4), verbose=False)
        return self.model.to_string(out[0, toks.shape[1]:])
