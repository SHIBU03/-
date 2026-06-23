"""card2vec: card embeddings learned from decklists (co-occurrence -> PPMI -> SVD).

Pure numpy (no gensim). Cards that appear together in good decks end up close in
embedding space, which seeds combo discovery and synergy-guided mutation. The
corpus grows as the QD archive fills, so embeddings are retrained periodically.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import numpy as np


class CardEmbeddings:
    def __init__(self, vocab, vectors):
        self.vocab = list(vocab)
        self.index = {c: i for i, c in enumerate(self.vocab)}
        norm = np.linalg.norm(vectors, axis=1, keepdims=True)
        norm[norm == 0] = 1.0
        self.V = (vectors / norm).astype(np.float32)

    def has(self, card) -> bool:
        return card in self.index

    def vec(self, card):
        i = self.index.get(card)
        return self.V[i] if i is not None else None

    def nearest(self, card, k=5):
        i = self.index.get(card)
        if i is None:
            return []
        sims = self.V @ self.V[i]
        order = np.argsort(-sims)
        return [(self.vocab[j], float(sims[j])) for j in order if j != i][:k]

    def sim_to_set(self, card, cards) -> float:
        i = self.index.get(card)
        if i is None:
            return 0.0
        idxs = [self.index[d] for d in cards if d in self.index]
        if not idxs:
            return 0.0
        return float((self.V[idxs] @ self.V[i]).mean())


def train_card2vec(corpus, *, dim=32, min_count=1, max_vocab=800):
    """corpus: iterable of decks (each a list of card IDs). Returns CardEmbeddings
    or None if there is not enough data."""
    corpus = [list(d) for d in corpus]
    counts = Counter()
    for deck in corpus:
        counts.update(set(deck))
    vocab = [c for c, k in counts.most_common(max_vocab) if k >= min_count]
    if len(vocab) < 4 or len(corpus) < 3:
        return None
    idx = {c: i for i, c in enumerate(vocab)}
    n = len(vocab)
    co = np.zeros((n, n), dtype=np.float64)
    uni = np.zeros(n, dtype=np.float64)
    for deck in corpus:
        present = [c for c in set(deck) if c in idx]
        for c in present:
            uni[idx[c]] += 1.0
        for a, b in combinations(present, 2):
            ia, ib = idx[a], idx[b]
            co[ia, ib] += 1.0
            co[ib, ia] += 1.0
    total = co.sum()
    if total <= 0 or uni.sum() <= 0:
        return None
    pij = co / total
    pi = uni / uni.sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log((pij / (np.outer(pi, pi) + 1e-12)) + 1e-12)
    ppmi = np.maximum(pmi, 0.0)
    d = min(dim, n - 1)
    try:
        U, S, _ = np.linalg.svd(ppmi)
    except np.linalg.LinAlgError:
        return None
    emb = U[:, :d] * np.sqrt(S[:d])
    return CardEmbeddings(vocab, emb.astype(np.float32))
