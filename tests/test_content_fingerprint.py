"""Content integrity tests for raw and independently serialized chart inputs."""

from __future__ import annotations

import unittest
from types import SimpleNamespace as NS

from model_claim_replay.content_fingerprint import sample_content_sha256

IMAGE = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/"
    "AAX+Av4N70a4AAAAAElFTkSuQmCC"
)


def sample(*, image: str = IMAGE, prompt: str = "private question", answer: str = "private answer") -> NS:
    return NS(
        input=[NS(role="user", content=[NS(type="text", text=prompt),
                                       NS(type="image", image=image)])],
        target=answer,
    )


class ContentFingerprints(unittest.TestCase):
    def test_same_logged_content_has_same_digest(self):
        value = sample_content_sha256(sample())
        self.assertIsNotNone(value)
        self.assertEqual(len(value), 64)
        self.assertEqual(value, sample_content_sha256(sample()))

    def test_text_change_changes_digest(self):
        self.assertNotEqual(sample_content_sha256(sample()),
                            sample_content_sha256(sample(prompt="changed private question")))

    def test_target_change_changes_digest(self):
        self.assertNotEqual(sample_content_sha256(sample()),
                            sample_content_sha256(sample(answer="different answer")))

    def test_chart_change_changes_digest(self):
        another_image = "data:image/png;base64,aGVsbG8="
        self.assertNotEqual(sample_content_sha256(sample()),
                            sample_content_sha256(sample(image=another_image)))

    def test_local_and_network_image_references_are_unpinned(self):
        for image in ("/tmp/chart.png", "file:///tmp/chart.png", "https://example.com/chart.png"):
            with self.subTest(image=image):
                self.assertIsNone(sample_content_sha256(sample(image=image)))

    def test_unreadable_base64_is_unpinned(self):
        self.assertIsNone(sample_content_sha256(sample(image="data:image/png;base64,INVALID***")))

    def test_text_only_and_missing_reference_are_unpinned(self):
        self.assertIsNone(sample_content_sha256(NS(input="question", target="answer")))
        self.assertIsNone(sample_content_sha256(NS(input=sample().input, target=None)))

    def test_json_dict_pydantic_style_equivalent_to_namespace(self):
        value = sample()
        raw = NS(input=[{
            "role": "user",
            "content": [{"type": "text", "text": "private question"},
                        {"type": "image", "image": IMAGE}],
        }], target=value.target)
        self.assertEqual(sample_content_sha256(raw), sample_content_sha256(value))

    def test_no_sensitive_input_or_target_in_output(self):
        digest = sample_content_sha256(sample())
        self.assertNotIn("private", digest)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
