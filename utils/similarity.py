import threading
from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_model_lock = threading.Lock()


class ModelUnavailableError(Exception):
    # Raised when the embedding model can't be loaded.
    pass


def _get_model() -> SentenceTransformer:
    # Load the model once per process, thread-safe.
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:  # re-check inside the lock
                try:
                    _model = SentenceTransformer(_MODEL_NAME)
                except Exception as exc:
                    raise ModelUnavailableError(
                        f"Couldn't load the embedding model '{_MODEL_NAME}'. "
                        "Check your connection and try again."
                    ) from exc
    return _model


def compute_similarity(resume_text: str, jd_text: str) -> float:
    # Returns a 0-100 similarity score between resume and job description text.
    # 100 = near-identical semantic content, 
    # 0 = completely unrelated.
    # Real resume/JD pairs for a relevant role usually land
    # somewhere in the 40-75 range - this is a directional signal, not a
    # pass/fail grade.

    model = _get_model()
    embeddings = model.encode([resume_text, jd_text], convert_to_tensor=True)
    raw_score = cos_sim(embeddings[0], embeddings[1]).item()  # -1.0 to 1.0

    # Cosine similarity for this model rarely goes negative in practice for
    # two real documents, but we clamp defensively before rescaling to 0-100.
    clamped = max(0.0, min(1.0, raw_score))
    return round(clamped * 100, 1)