"""literature_map — 2D embedding of the literature_methods corpus.

Project each paper into a 2D plane using TF-IDF over (mechanism_tags +
OpenAlex concepts + title), then take the first two components of a SVD.
Render with matplotlib: color by primary tag, size by citation count,
label the K most-cited papers.

Numpy-only — no sklearn dep. Hand-rolled because the corpus is small
(~100-200 papers, ~200 vocab tokens) and a project-wide "numpy is the
ML stack" rule is already in place.

Outputs:
  - PNG scatter plot (the visual)
  - CSV of (arxiv_id, x, y, primary_tag, cited_by_count) for downstream
    cross-references (coverage.py reuses the primary_tag clustering)
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import numpy as np


_STOPWORDS = frozenset({
    "the", "a", "an", "of", "and", "in", "for", "with", "to", "on", "as",
    "by", "from", "is", "are", "be", "this", "that", "we", "our", "they",
    "their", "it", "its", "or", "but", "not", "into", "via", "based",
    "using", "approach", "approaches", "method", "methods", "model",
    "models", "study", "studies", "paper", "papers", "results", "result",
    "show", "shows", "shown", "such", "more", "less", "first", "new",
    "well", "between", "without", "within", "can", "may", "two", "one",
    "three", "given", "use", "used", "uses",
})

# Generic over-frequent words; useful in domain but kill them as features
# so the SVD focuses on what differentiates papers, not what they share.
_BORING_DOMAIN = frozenset({
    "computer", "science", "economics", "business", "mathematics",
    "physics", "psychology", "engineering",
})


def _tokenize(text: str) -> list[str]:
    if not text:
        return []
    text = text.lower()
    raw = re.findall(r"[a-z][a-z\-]+", text)
    return [t for t in raw
            if len(t) >= 3 and t not in _STOPWORDS and t not in _BORING_DOMAIN]


def _row_tokens(row: dict[str, Any]) -> list[str]:
    """Build the token bag for one paper: tags + concepts + title."""
    tokens: list[str] = []
    for tag in (row.get("mechanism_tags") or []):
        tokens.extend(_tokenize(tag))
    for concept in (row.get("oa_concepts") or "").split(","):
        tokens.extend(_tokenize(concept))
    tokens.extend(_tokenize(row.get("title") or ""))
    return tokens


def build_corpus(rows: list[dict]) -> tuple[list[list[str]], list[dict]]:
    """Tokenise each paper. Drop papers that produce zero tokens."""
    docs: list[list[str]] = []
    kept: list[dict] = []
    for r in rows:
        toks = _row_tokens(r)
        if toks:
            docs.append(toks)
            kept.append(r)
    return docs, kept


def tfidf_matrix(docs: list[list[str]], *, max_features: int = 300
                  ) -> tuple[np.ndarray, list[str]]:
    """Dense TF-IDF over the top-`max_features` tokens by document frequency.

    Each row is L2-normalised so cosine similarity reduces to a dot product
    — gives the SVD a uniform scale to work with."""
    doc_counts = [Counter(d) for d in docs]
    df = Counter()
    for c in doc_counts:
        for term in c:
            df[term] += 1
    vocab = [t for t, _ in df.most_common(max_features)]
    vocab_idx = {t: i for i, t in enumerate(vocab)}
    n_docs = len(docs)
    if n_docs == 0 or not vocab:
        return np.zeros((n_docs, 0)), []
    X = np.zeros((n_docs, len(vocab)))
    for i, c in enumerate(doc_counts):
        for term, tf in c.items():
            j = vocab_idx.get(term)
            if j is not None:
                X[i, j] = tf
    idf = np.array([math.log((n_docs + 1) / (df[t] + 1)) + 1.0 for t in vocab])
    X = X * idf[np.newaxis, :]
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return X / norms, vocab


def project_2d(X: np.ndarray) -> np.ndarray:
    """Centered SVD to 2D coordinates (the first 2 PCA components)."""
    if X.shape[0] < 2 or X.shape[1] < 1:
        return np.zeros((X.shape[0], 2))
    Xc = X - X.mean(axis=0, keepdims=True)
    U, S, _ = np.linalg.svd(Xc, full_matrices=False)
    return U[:, :2] * S[:2]


def primary_tag(row: dict) -> str:
    """Pick one tag-like label for color-coding. mechanism_tags wins, then
    the first OpenAlex concept, then 'other'."""
    tags = row.get("mechanism_tags") or []
    if tags:
        return tags[0]
    concepts = (row.get("oa_concepts") or "").split(",")
    first = concepts[0].strip() if concepts else ""
    return first or "other"


def _citation_count(row: dict) -> int:
    """Pull whichever citation count is present, prefer OpenAlex."""
    for k in ("oa_cited_by_count", "s2_influential_citation_count"):
        v = row.get(k)
        if v is not None:
            try:
                return int(v)
            except (TypeError, ValueError):
                pass
    return 0


def render_literature_map(rows: list[dict], png_path: str, *,
                            csv_path: str | None = None,
                            top_labels: int = 12,
                            figsize: tuple[float, float] = (14.0, 10.0),
                            dpi: int = 120) -> dict:
    """Render the 2D map to PNG (+ optional CSV of point coords).

    Returns a summary dict for the caller (n_papers, n_tags, vocab_size).
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    docs, kept = build_corpus(rows)
    if not docs:
        raise ValueError("no papers with any tokens to embed")
    X, vocab = tfidf_matrix(docs)
    coords = project_2d(X)

    tags = [primary_tag(r) for r in kept]
    unique_tags = sorted(set(tags))
    tag_idx = {t: i for i, t in enumerate(unique_tags)}
    cmap = plt.cm.tab20
    colors = [cmap(tag_idx[t] % 20) for t in tags]
    sizes = [20 + 6 * math.log(1 + _citation_count(r)) for r in kept]

    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(coords[:, 0], coords[:, 1], c=colors, s=sizes, alpha=0.75,
                edgecolors="black", linewidths=0.3)

    # Label the K most-cited papers (sparingly — labels overlap fast)
    cit_sorted = sorted(range(len(kept)),
                         key=lambda i: -_citation_count(kept[i]))
    for i in cit_sorted[:top_labels]:
        ax.annotate(kept[i]["arxiv_id"],
                     coords[i], fontsize=7, alpha=0.85,
                     xytext=(3, 3), textcoords="offset points")

    # Legend: top tags by count
    tag_counts = Counter(tags)
    for tag, n in tag_counts.most_common(15):
        ax.scatter([], [], c=[cmap(tag_idx[tag] % 20)],
                    label=f"{tag} ({n})", s=40, edgecolors="black",
                    linewidths=0.3)
    ax.legend(loc="best", fontsize=7, framealpha=0.92,
               title="primary mechanism tag")

    ax.set_title(f"Literature map — {len(kept)} papers "
                  f"(TF-IDF over tags+concepts+title, SVD-2D)")
    ax.set_xlabel("SVD component 1")
    ax.set_ylabel("SVD component 2")
    ax.grid(True, alpha=0.2)
    plt.tight_layout()
    plt.savefig(png_path, dpi=dpi)
    plt.close()

    if csv_path:
        import csv
        with open(csv_path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["arxiv_id", "x", "y", "primary_tag",
                        "cited_by_count", "title"])
            for i, r in enumerate(kept):
                w.writerow([r["arxiv_id"], f"{coords[i,0]:.4f}",
                             f"{coords[i,1]:.4f}", tags[i],
                             _citation_count(r),
                             (r.get("title") or "")[:120]])

    return {
        "n_papers": len(kept),
        "n_dropped_no_tokens": len(rows) - len(kept),
        "n_unique_tags": len(unique_tags),
        "vocab_size": len(vocab),
    }
