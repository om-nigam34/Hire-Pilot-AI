"""
similarity.py
-------------
Computes a semantic similarity score between a resume and a job description.

This is intentionally just ONE signal in the pipeline, not the final verdict -
app.py combines this with the LLM's structured gap analysis. Two resumes that
describe the same skill in different words ("led a team" vs "managed
engineers") should still score as close, which is why we use sentence
embeddings instead of raw keyword overlap.

The model downloads once (from Hugging Face) the first time this runs, then
caches locally under ~/.cache/torch/sentence_transformers. That means the
FIRST run on your machine needs internet access; after that it works offline.
"""

import threading
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_model_lock = threading.Lock()


class ModelUnavailableError(Exception):
    """Raised when the embedding model can't be loaded (e.g. no internet
    access on first run, so the weights can't be downloaded)."""
    pass


def _get_model() -> SentenceTransformer:
    """Lazily load the model once per process, thread-safe."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                try:
                    _model = SentenceTransformer(_MODEL_NAME)
                except Exception as exc:
                    raise ModelUnavailableError(
                        f"Couldn't load the embedding model '{_MODEL_NAME}'. "
                        "This usually means there's no internet access for "
                        "the first-time model download. Check your "
                        "connection and try again."
                    ) from exc
    return _model


def compute_similarity(resume_text: str, jd_text: str) -> float:
    """
    Returns a 0-100 similarity score between resume and job description text.

    100 = near-identical semantic content, 0 = completely unrelated.
    In practice, real resume/JD pairs for a relevant role usually land
    somewhere in the 40-75 range - this is a directional signal, not a
    pass/fail grade.
    """
    model = _get_model()
    embeddings = model.encode([resume_text, jd_text], convert_to_tensor=True)
    raw_score = cos_sim(embeddings[0], embeddings[1]).item()  # -1.0 to 1.0

    # Cosine similarity for this model rarely goes negative in practice for
    # two real documents, but we clamp defensively before rescaling to 0-100.
    clamped = max(0.0, min(1.0, raw_score))
    return round(clamped * 100, 1)