"""idea_plan + scaffold — judgment → implementation plan → code/proposal.

Stage B of the idea pipeline. Given a judged idea, the LLM proposes ONE of
three implementation strategies, depending on how novel the idea is:

  param_sweep      : extend an existing REGISTRY model with new params.
                     Scaffold = a row in the `proposals` table that the
                     existing propose_cli execute path can run as-is.
  mechanism_combo  : combine two existing mechanisms into a hybrid ABM.
                     Scaffold = a Python file under packages/abm_models/
                     abm_models/<new_name>/model.py implementing the
                     ABMModel protocol.
  new_method       : a genuinely-new mechanism not derivable from existing.
                     Scaffold = a skeleton Python file with TODO markers
                     for the human to fill in.

The LLM-generated Python for mechanism_combo is best-effort: it imports the
two base ABMs from abm_models and stitches their step() methods together.
Quality varies; on syntax error / import error / non-ABMModel-conformance,
the scaffold is saved anyway and the failure is logged on the idea's row.
"""
from __future__ import annotations

import json
import os
import re
import sys
import textwrap
from typing import Any

from .db import (
    ensure_proposals_schema, insert_proposal, load_proposals, load_runs,
)
from .fingerprint import FEATURE_NAMES
from .idea_judge import _call_groq
from .adapters import MODEL_BOUNDS, PRICELESS_MODELS


DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


PLAN_SYSTEM_PROMPT = """\
Given a financial-ABM idea + a novelty judgment, propose ONE concrete
implementation plan. Output ONE JSON object with this exact shape:

{
  "implementation_type": "param_sweep" | "mechanism_combo" | "new_method",
  "based_on_method": "<name from candidate methods, or null for new_method>",

  // populated when implementation_type == "param_sweep"
  "param_sweep": {
      "target_model": "<one of REGISTRY: speculation_game, cont_bouchaud, ...>",
      "params": {<full dict of every key in parameter_bounds[target_model]>},
      "predicted_fingerprint": {<all 9 features>},
      "predicted_novelty_distance": <float>,
      "rationale": "<2-4 Japanese sentences naming the target fingerprint
                    region, why these params push there, and which paper
                    inspired the move>"
  },

  // populated when implementation_type == "mechanism_combo"
  "mechanism_combo": {
      "base_method_a": "<existing method name>",
      "base_method_b": "<existing method name (or 'none' for solo extension)>",
      "combination_strategy": "<1-3 sentence Japanese description>",
      "new_class_name": "<CamelCase Python class name>",
      "expected_behavior": "<1-2 sentence Japanese summary>"
  },

  // populated when implementation_type == "new_method"
  "new_method": {
      "mechanism_description": "<3-6 sentence Japanese mechanism spec>",
      "agent_types": [<list>],
      "key_state_variables": [<list>],
      "new_class_name": "<CamelCase Python class name>"
  },

  "knowhow_techniques_to_apply": [<list of technique names from
                                   `candidate_techniques` that the user
                                   should keep in mind, e.g. SBI / Sobol
                                   pre-screen / out-of-sample testing>],
  "calibration_strategy": "<1 sentence in Japanese>",
  "validation_strategy": "<1 sentence in Japanese>",
  "references": [<arxiv_ids from candidate_literature only>]
}

Hard constraints:
  1. If the judgment category is 'trivial_variant' or 'incremental_novelty',
     pick implementation_type='param_sweep'.
  2. If the judgment category is 'novel_combination',
     pick implementation_type='mechanism_combo'.
  3. If the judgment category is 'genuinely_novel',
     pick implementation_type='new_method'.
  4. For param_sweep, params MUST include every key in
     parameter_bounds[target_model] and stay within ±30% of the bounds.
  5. Cite only arxiv_ids that appeared in `candidate_literature`. Do not
     fabricate references.
"""


def make_plan(db_path: str, idea_text: str, judgment_payload: dict, *,
              groq_model: str = DEFAULT_GROQ_MODEL,
              dry_run_response: dict | None = None) -> dict:
    """Run the LLM to propose an implementation plan from a judged idea."""
    from .knowhow_techniques import load_techniques

    aspects = judgment_payload["aspects"]
    matches = judgment_payload["matches"]
    verdict = judgment_payload["verdict"]
    payload = {
        "idea": idea_text,
        "aspects": aspects,
        "judgment": verdict,
        "candidate_methods": matches["methods"],
        "candidate_literature": matches["literature"],
        "candidate_techniques": load_techniques(db_path),
        "parameter_bounds": {k: {p: list(b) for p, b in v.items()}
                             for k, v in MODEL_BOUNDS.items()},
        "priceless_models": sorted(PRICELESS_MODELS),
        "feature_names": FEATURE_NAMES,
    }
    if dry_run_response is not None:
        return dry_run_response
    return _call_groq(PLAN_SYSTEM_PROMPT, payload, groq_model)


# ----- Scaffold paths -----------------------------------------------------

def scaffold_param_sweep(db_path: str, plan: dict, idea_id: int,
                          *, llm_model: str) -> dict:
    """Insert the param_sweep plan as a row in the `proposals` table so the
    existing `propose_cli execute` path can run it."""
    ensure_proposals_schema(db_path)
    ps = plan.get("param_sweep") or {}
    target_model = ps.get("target_model")
    if not target_model or target_model not in MODEL_BOUNDS:
        raise ValueError(
            f"param_sweep plan has invalid target_model {target_model!r}; "
            f"expected one of {list(MODEL_BOUNDS)}"
        )
    params = ps.get("params") or {}
    missing = set(MODEL_BOUNDS[target_model].keys()) - set(params.keys())
    if missing:
        raise ValueError(
            f"param_sweep plan missing required keys: {sorted(missing)}"
        )
    rationale = (ps.get("rationale") or "").strip()
    if len(rationale) < 20:
        rationale = (rationale + "  (idea #{}, plan-generated, see ideas.id={})"
                     .format(idea_id, idea_id))
    proposal_id = insert_proposal(
        db_path,
        proposal_type="param_sweep",
        target_model=target_model,
        params=params,
        rationale=rationale,
        predicted_fingerprint=ps.get("predicted_fingerprint"),
        predicted_novelty_distance=ps.get("predicted_novelty_distance"),
        references=plan.get("references") or [],
        llm_model=llm_model,
    )
    return {
        "type": "param_sweep",
        "proposal_id": proposal_id,
        "target_model": target_model,
        "params": params,
    }


def scaffold_mechanism_combo(plan: dict, idea_id: int,
                              packages_root: str) -> dict:
    """Write a Python file under packages_root for a hybrid ABM. Returns
    {paths: [...], class_name: ..., import_path: ...}. The file is best-
    effort code generation; the human is expected to review."""
    mc = plan.get("mechanism_combo") or {}
    name = mc.get("new_class_name") or f"IdeaCombo{idea_id}"
    snake = _camel_to_snake(name)
    base_a = mc.get("base_method_a") or "speculation_game"
    base_b = mc.get("base_method_b") or "none"
    desc = (mc.get("combination_strategy") or "").strip()
    behaviour = (mc.get("expected_behavior") or "").strip()

    module_dir = os.path.join(packages_root, "abm_models", "abm_models",
                              f"_idea_{snake}")
    os.makedirs(module_dir, exist_ok=True)
    init_path = os.path.join(module_dir, "__init__.py")
    model_path = os.path.join(module_dir, "model.py")

    init_body = (
        f'"""auto-scaffold for idea #{idea_id}: combo({base_a} + {base_b}).\n'
        f"REVIEW BEFORE RUNNING — this code is best-effort LLM scaffolding.\n"
        f'"""\n'
        f"from .model import {name}\n\n"
        f'__all__ = ["{name}"]\n'
    )
    model_body = textwrap.dedent(f'''\
        """auto-scaffold for idea #{idea_id} ({name}).

        combination_strategy:
        {textwrap.fill(desc, width=72, initial_indent="          ",
                       subsequent_indent="          ")}

        expected_behavior:
        {textwrap.fill(behaviour, width=72, initial_indent="          ",
                       subsequent_indent="          ")}

        TODO(human): fill in the actual step logic. The scaffold below
        instantiates the two base ABMs and returns the first one's result —
        replace with the real combination.
        """
        from __future__ import annotations
        from dataclasses import dataclass, field
        from typing import Any

        from abm_models import REGISTRY


        @dataclass(slots=True)
        class {name}:
            """Auto-scaffolded combo of `{base_a}` and `{base_b}`."""
            base_a_params: dict = field(default_factory=dict)
            base_b_params: dict = field(default_factory=dict)
            name: str = field(default="_idea_{snake}", init=False)

            def run(self, *, seed: int) -> dict[str, Any]:
                # TODO(human): combine the two base ABMs here.
                # The scaffold just runs base_a as a placeholder.
                BaseA = REGISTRY["{base_a}"]
                model_a = BaseA(**self.base_a_params)
                return model_a.run(seed=seed)
        ''')

    with open(init_path, "w") as fh:
        fh.write(init_body)
    with open(model_path, "w") as fh:
        fh.write(model_body)

    return {
        "type": "mechanism_combo",
        "paths": [init_path, model_path],
        "class_name": name,
        "module": f"abm_models._idea_{snake}",
    }


def scaffold_new_method(plan: dict, idea_id: int,
                        packages_root: str) -> dict:
    """Write a more abstract skeleton when the idea is genuinely new."""
    nm = plan.get("new_method") or {}
    name = nm.get("new_class_name") or f"IdeaNew{idea_id}"
    snake = _camel_to_snake(name)
    description = (nm.get("mechanism_description") or "").strip()
    agents = nm.get("agent_types") or []
    state_vars = nm.get("key_state_variables") or []

    module_dir = os.path.join(packages_root, "abm_models", "abm_models",
                              f"_idea_{snake}")
    os.makedirs(module_dir, exist_ok=True)
    init_path = os.path.join(module_dir, "__init__.py")
    model_path = os.path.join(module_dir, "model.py")

    init_body = (
        f'"""auto-scaffold for idea #{idea_id} (NEW METHOD: {name}).\n'
        f"REVIEW + COMPLETE BEFORE RUNNING — TODOs mark missing pieces.\n"
        f'"""\n'
        f"from .model import {name}\n\n"
        f'__all__ = ["{name}"]\n'
    )
    agent_init = "\n        ".join(
        [f"# TODO(human): initial state for agent type '{a}'" for a in agents]
    ) or "# TODO(human): initial agent state"
    state_init = "\n        ".join(
        [f"# TODO(human): self.{v} = ..." for v in state_vars]
    ) or "# TODO(human): self.state = ..."

    model_body = textwrap.dedent(f'''\
        """auto-scaffold for idea #{idea_id} ({name}).

        mechanism_description:
        {textwrap.fill(description, width=72, initial_indent="          ",
                       subsequent_indent="          ")}

        agent_types       : {agents}
        key_state_variables: {state_vars}

        TODO(human): implement the agent_step + price_step. The scaffold
        returns NaN returns and must be filled in before it's useful.
        """
        from __future__ import annotations
        from dataclasses import dataclass, field
        from typing import Any
        import numpy as np


        @dataclass(slots=True)
        class {name}:
            T: int = 2000
            seed: int = 0
            name: str = field(default="_idea_{snake}", init=False)

            def run(self, *, seed: int) -> dict[str, Any]:
                rng = np.random.default_rng(seed)
                {agent_init}
                {state_init}
                returns = np.full(self.T, np.nan)
                # TODO(human): fill in the actual step loop.
                #   for t in range(self.T):
                #       ...
                #       returns[t] = ...
                return {{"returns": returns}}
        ''')

    with open(init_path, "w") as fh:
        fh.write(init_body)
    with open(model_path, "w") as fh:
        fh.write(model_body)

    return {
        "type": "new_method",
        "paths": [init_path, model_path],
        "class_name": name,
        "module": f"abm_models._idea_{snake}",
    }


def _camel_to_snake(name: str) -> str:
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return re.sub(r"[^a-z0-9_]+", "_", s.lower()).strip("_") or "anon"


def scaffold(plan: dict, *, db_path: str, idea_id: int,
             packages_root: str, llm_model: str) -> dict:
    """Dispatcher: route to the right scaffolder by implementation_type."""
    impl = plan.get("implementation_type")
    if impl == "param_sweep":
        return scaffold_param_sweep(db_path, plan, idea_id, llm_model=llm_model)
    if impl == "mechanism_combo":
        return scaffold_mechanism_combo(plan, idea_id, packages_root)
    if impl == "new_method":
        return scaffold_new_method(plan, idea_id, packages_root)
    raise ValueError(
        f"unknown implementation_type {impl!r}; expected one of "
        f"param_sweep / mechanism_combo / new_method"
    )
