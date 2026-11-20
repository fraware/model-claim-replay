"""Conservative source-content fingerprints for Chartography Inspect samples.

Hash canonicalized inputs and reference answers without exporting them. Image
references are accepted only if the original media bytes are present as a
base64 data URI. Paths and network URLs cannot bind image content and cause the
fingerprint to be unavailable. Matching fingerprints prove only the consistency
of *logged* inputs and targets, never the identity of model execution.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
from types import SimpleNamespace
from typing import Any

MAX_IMAGE_DATA_URI_CHARS = 24 * 1024 * 1024
MAX_NESTING = 24


class _Unavailable(Exception):
    """Input media is not pinned or cannot be represented canonically."""


def _normalize(value: Any, depth: int, image_count: list[int]) -> Any:
    """Produce JSON-compatible data while committing to actual image bytes."""
    if depth > MAX_NESTING:
        raise _Unavailable
    if hasattr(value, "model_dump"):
        try:
            value = value.model_dump(mode="json", exclude_none=True)
        except (TypeError, ValueError):
            raise _Unavailable from None
    elif isinstance(value, SimpleNamespace):
        value = vars(value)
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise _Unavailable
        if value.get("type") == "image":
            image = value.get("image")
            if not isinstance(image, str) or not image.startswith("data:image/"):
                raise _Unavailable
            if len(image) > MAX_IMAGE_DATA_URI_CHARS:
                raise _Unavailable
            prefix, separator, encoded = image.partition(",")
            if not separator or not prefix.lower().endswith(";base64"):
                raise _Unavailable
            try:
                decoded = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                raise _Unavailable from None
            if not decoded:
                raise _Unavailable
            image_count[0] += 1
            value = dict(value)
            value["image"] = {
                "media_type": prefix[5:-7].lower(),
                "bytes_sha256": hashlib.sha256(decoded).hexdigest(),
            }
        return {key: _normalize(item, depth + 1, image_count) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item, depth + 1, image_count) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise _Unavailable


def sample_content_sha256(sample: Any) -> str | None:
    """Fingerprint logged Chartography input and target, or return ``None``.

    A readable chart image is mandatory. The digest is a consistency check on
    log contents; it is not a dataset signature or evidence that the image was
    actually delivered to the model. The digest may permit dictionary attacks
    on known samples, so it is a pseudonym rather than an anonymization scheme.
    """
    raw_input = getattr(sample, "input", None)
    raw_target = getattr(sample, "target", None)
    if raw_input is None or raw_target is None:
        return None
    images = [0]
    try:
        payload = {
            "input": _normalize(raw_input, 0, images),
            "target": _normalize(raw_target, 0, images),
        }
        if images[0] == 0:
            return None
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (_Unavailable, UnicodeError, ValueError, TypeError):
        return None
    return hashlib.sha256(b"mcr-chartography-content-v1\0" + serialized).hexdigest()
