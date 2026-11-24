"""Metadata endpoint constants for explicit historical Gemini investigations."""
from model_claim_replay.graphwalks_runtime import MODEL as GEMINI_CLAIM_MODEL
from provider_readiness import ProviderProbeError, _metadata_get

_GEMINI_HOST = "generativelanguage.googleapis.com"
_GEMINI_PATH = "/v1beta/models/" + GEMINI_CLAIM_MODEL
