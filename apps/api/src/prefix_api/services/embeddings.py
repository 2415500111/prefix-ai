"""Text embeddings for retrieving protocol steps (used by the AI Prep Assistant).

Only clinician-approved protocol text is ever embedded; patient data never is.
"""

import hashlib
import itertools
import math
import re
from typing import Protocol

from prefix_api.db.models.protocol import EMBEDDING_DIMENSIONS

_TOKEN = re.compile(r"\w+", re.UNICODE)


class EmbeddingProvider(Protocol):
    name: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class LocalHashingEmbedder:
    """Deterministic, offline embedder: hashed unigrams and bigrams, L2-normalised.

    No network or model download, so it works in development, CI and air-gapped
    deployments. Retrieval quality is lexical rather than semantic; a hosted provider can
    replace it behind the same interface.
    """

    name = "local-hashing-v1"
    dimensions = EMBEDDING_DIMENSIONS

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        tokens = [token.lower() for token in _TOKEN.findall(text)]
        features = tokens + [f"{a} {b}" for a, b in itertools.pairwise(tokens)]
        vector = [0.0] * self.dimensions
        for feature in features:
            digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return vector if norm == 0 else [value / norm for value in vector]


def get_embedding_provider(name: str) -> EmbeddingProvider:
    if name == "local":
        return LocalHashingEmbedder()
    raise ValueError(f"Unknown embedding provider '{name}'")
