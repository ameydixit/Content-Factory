import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from main import ContentAgency, build_parser, slugify


class FakeClient:
    def __init__(self):
        self.responses = self
        self.images = self
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        prompt = kwargs["input"]
        if "APPROVED:" in prompt:
            text = "APPROVED: yes"
        elif "The complete article" in prompt or "Write the complete article" in prompt:
            text = "# Future\n\nAn article."
        elif "image prompt" in prompt.lower():
            text = "A cinematic local shop at sunrise."
        elif "only HTML" in prompt:
            text = "<!doctype html><html><body><h1>Future</h1></body></html>"
        elif "Topic:" in prompt:
            text = "Audience: Local business owners"
        else:
            text = "Clear, sourced notes."
        return type("Response", (), {"output_text": text})()

    def generate(self, **kwargs):
        return type(
            "Result",
            (),
            {"data": [type("Item", (), {"b64_json": "aGVsbG8="})()]},
        )()


class ContentAgencyTests(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("The Future! of Small Businesses"), "the-future-of-small-businesses")

    def test_open_html_option(self):
        args = build_parser().parse_args(["--topic", "Gardening", "--open-html"])
        self.assertEqual(args.topic, "Gardening")
        self.assertTrue(args.open_html)

    def test_run_writes_expected_files(self):
        with TemporaryDirectory() as temp:
            client = FakeClient()
            agency = ContentAgency(
                client=client,
                text_model="test-text",
                text_fallbacks=[],
                image_model="test-image",
                image_fallbacks=[],
                output_root=Path(temp),
            )
            run_dir = agency.run("Local businesses", "", 3)
            for name in (
                "brief.md",
                "notes.md",
                "article.md",
                "editor-feedback.md",
                "image-prompt.txt",
                "image.png",
                "page.html",
                "run-details.txt",
            ):
                self.assertTrue((run_dir / name).is_file())


if __name__ == "__main__":
    unittest.main()
