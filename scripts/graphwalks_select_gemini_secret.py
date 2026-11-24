"""Select a repository Gemini credential for the pinned model metadata.

Only fixed-host, non-generative model metadata GET requests are issued.
No secret material is logged, included in receipts or returned to stdout.
The selected credential is handed to a later GitHub Actions step via the
runner's private GITHUB_ENV file in the legacy live scan. Manual workflows
use --alias-only to emit a nonsecret allowlisted name to GITHUB_OUTPUT and
inject the corresponding secret only into provider-facing steps.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Callable, Mapping

from provider_readiness import (
    GEMINI_CLAIM_MODEL,
    ProviderProbeError,
    _GEMINI_HOST,
    _GEMINI_PATH,
    _metadata_get,
    probe_providers,
)

_METADATA = Callable[[str, str, Mapping[str, str]], tuple[int, Any]]
_ALIASES = ("GEMINI_API_KEY", "GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY")


def select_gemini_secret(
    environ: Mapping[str, str],
    *,
    request: _METADATA | None = None,
) -> tuple[str, str] | None:
    """Return the first working *alias and value*, keeping both private.

    Unlike blindly preferring the first nonempty variable, this checks every
    explicitly supported candidate. A metadata success is not a guarantee
    that token-counting, generation or billing is enabled for the account.
    """
    request = request or _metadata_get
    checked_values: set[str] = set()
    for name in _ALIASES:
        key = environ.get(name)
        if (not isinstance(key, str) or not key or key in checked_values
                or any(char in key for char in ("\n", "\r", "\0"))):
            continue
        checked_values.add(key)
        try:
            status, payload = request(
                _GEMINI_HOST,
                _GEMINI_PATH,
                {"x-goog-api-key": key, "Accept": "application/json"},
            )
        except ProviderProbeError:
            continue
        if (status == 200 and isinstance(payload, dict)
                and payload.get("name") == "models/" + GEMINI_CLAIM_MODEL):
            return name, key
    return None


def main(argv: list[str] | None = None) -> int:
    """Select the credential; optionally return only its allowlisted alias."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--alias-only", action="store_true",
                        help="Emit only the selected secret name to GITHUB_OUTPUT")
    args = parser.parse_args(argv)
    target_name = "GITHUB_OUTPUT" if args.alias_only else "GITHUB_ENV"
    env_file = os.environ.get(target_name)
    if not env_file:
        print("Missing private GitHub Actions " + target_name + " file", file=sys.stderr)
        return 2
    candidate = select_gemini_secret(os.environ)
    if candidate is None:
        # Different-provider metadata is useful for triage, never a substitute
        # for the pinned Gemini model in this GraphWalks claim.
        fallback = probe_providers(os.environ)
        print(
            "No Gemini claim-model credential passed metadata validation. "
            "OpenAI metadata fallback: " + fallback["openai"]["status"],
            file=sys.stderr,
        )
        print(
            "Cannot count Gemini source tokens with a different provider.",
            file=sys.stderr,
        )
        return 2

    alias, secret = candidate
    if alias not in _ALIASES:
        print("Unexpected credential alias", file=sys.stderr)
        return 2
    if args.alias_only:
        # The workflow uses this fixed allowlisted name to inject a secret
        # only into the specific steps that need it. Never emit secret bytes.
        with Path(env_file).open("a", encoding="utf-8") as stream:
            stream.write("alias=" + alias + "\n")
        print("Pinned Gemini model metadata authenticated using " + alias)
        return 0
    # Secrets must be one-line keys. GITHUB_ENV lives on the ephemeral runner
    # and is intentionally omitted from all public artifacts.
    with Path(env_file).open("a", encoding="utf-8") as stream:
        stream.write("GEMINI_API_KEY=" + secret + "\n")
    print("Pinned Gemini model metadata authenticated using " + alias)
    print("Credential written to the ephemeral GitHub Actions environment only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
