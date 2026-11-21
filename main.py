import argparse
import base64
import os
import re
import webbrowser
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


DEFAULT_TOPIC = "The future of local small businesses"
MAX_EDIT_ROUNDS = 3


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value[:60] or "content-run"


def split_fallbacks(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class ContentAgency:
    def __init__(self, client: OpenAI, text_model: str, text_fallbacks: list[str],
                 image_model: str, image_fallbacks: list[str], output_root: Path):
        self.client = client
        self.text_model = text_model
        self.text_fallbacks = text_fallbacks
        self.image_model = image_model
        self.image_fallbacks = image_fallbacks
        self.output_root = output_root

    def call_text(self, role: str, system: str, user: str) -> str:
        models = [self.text_model, *self.text_fallbacks]
        last_error = None
        for model in dict.fromkeys(models):
            try:
                response = self.client.responses.create(
                    model=model,
                    instructions=system,
                    input=user,
                )
                return response.output_text
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"{role} failed with all configured text models: {last_error}")

    def call_image(self, prompt: str) -> tuple[bytes, str]:
        models = [self.image_model, *self.image_fallbacks]
        last_error = None
        for model in dict.fromkeys(models):
            try:
                result = self.client.images.generate(
                    model=model,
                    prompt=prompt,
                    size="1536x1024",
                    quality="medium",
                    output_format="png",
                )
                image_base64 = result.data[0].b64_json
                if not image_base64:
                    raise RuntimeError("The image API returned no base64 image.")
                return base64.b64decode(image_base64), model
            except Exception as exc:
                last_error = exc
        raise RuntimeError(f"Image generation failed with all configured image models: {last_error}")

    def run(self, topic: str, brief: str, max_edit_rounds: int) -> Path:
        run_dir = self.output_root / slugify(topic)
        run_dir.mkdir(parents=True, exist_ok=True)

        source_brief = brief.strip() or f"Create an informative article about: {topic}"
        (run_dir / "brief.md").write_text(
            f"# Brief\n\n**Topic:** {topic}\n\n{source_brief}\n", encoding="utf-8"
        )

        clarified = self.call_text(
            "Clarifier",
            "You are a senior editorial clarifier. Turn a topic and supplied brief into a concise creative brief.",
            f"Topic: {topic}\n\nSupplied brief:\n{source_brief}\n\n"
            "Return: audience, goal, angle, required themes, tone, and suggested article length.",
        )
        (run_dir / "brief.md").write_text(
            f"# Editorial Brief\n\n**Topic:** {topic}\n\n{clarified}\n", encoding="utf-8"
        )

        notes = self.call_text(
            "Researcher",
            "You are a careful researcher. Separate established facts from uncertain claims.",
            f"Research the topic using the following editorial brief. Do not invent citations.\n\n"
            f"{clarified}\n\nProduce 6-10 useful notes, themes, risks, and questions. "
            "Mark claims that need live-source verification.",
        )
        (run_dir / "notes.md").write_text(notes, encoding="utf-8")

        draft = self.call_text(
            "Writer",
            "You are a publication-quality writer. Use the brief and notes, but never present uncertain claims as facts.",
            f"Editorial brief:\n{clarified}\n\nResearch notes:\n{notes}\n\n"
            "Write the complete article in Markdown. Include a headline, short introduction, "
            "clear sections, practical examples, and a conclusion.",
        )

        feedback_history = []
        for round_number in range(1, max_edit_rounds + 1):
            review = self.call_text(
                "Editor",
                "You are an exacting editor. Correct factual overreach and reward clarity.",
                f"Editorial brief:\n{clarified}\n\nArticle draft:\n{draft}\n\n"
                "Reply with 'APPROVED: yes' or 'APPROVED: no' on the first line, then a concise "
                "copy-edit and completeness review.",
            )
            feedback_history.append(f"## Round {round_number}\n\n{review}")
            approved = bool(re.search(r"(?im)^APPROVED:\s*yes\b", review))
            if approved:
                break
            draft = self.call_text(
                "Writer",
                "You are a publication-quality writer revising a draft.",
                f"Editorial brief:\n{clarified}\n\nCurrent draft:\n{draft}\n\n"
                f"Editorial feedback:\n{review}\n\nRevise the draft while preserving the publication style.",
            )

        (run_dir / "article.md").write_text(draft, encoding="utf-8")
        (run_dir / "editor-feedback.md").write_text(
            "\n\n".join(feedback_history), encoding="utf-8"
        )

        image_prompt = self.call_text(
            "Image Designer",
            "You are a visual art director. Write one detailed, original image-generation prompt.",
            f"Article:\n{draft}\n\nCreate a single hero image prompt that is relevant to the topic, "
            "contains no article text, and specifies composition, style, lighting, and palette.",
        )
        (run_dir / "image-prompt.txt").write_text(image_prompt, encoding="utf-8")
        image_bytes, image_model = self.call_image(image_prompt)
        (run_dir / "image.png").write_bytes(image_bytes)

        html = self.call_text(
            "HTML Developer",
            "You are a front-end developer. Produce a polished, responsive standalone HTML page.",
            f"Article in Markdown:\n{draft}\n\nThe hero image is 'image.png'. "
            "Return only HTML. Include embedded CSS, semantic sections, no external dependencies.",
        )
        html = re.sub(r"^```(?:html)?\s*|\s*```$", "", html.strip(), flags=re.I)
        (run_dir / "page.html").write_text(html, encoding="utf-8")
        (run_dir / "run-details.txt").write_text(
            f"Text model: {self.text_model}\nImage model: {image_model}\n"
            f"Edit rounds: {len(feedback_history)}\n",
            encoding="utf-8",
        )
        return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a prompt-chained content agency.")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--brief", default="")
    parser.add_argument("--output", default="output")
    parser.add_argument("--rounds", type=int, default=MAX_EDIT_ROUNDS)
    parser.add_argument(
        "--open-html",
        action="store_true",
        help="Open the generated HTML page in your default browser",
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()
    if not 1 <= args.rounds <= MAX_EDIT_ROUNDS:
        raise SystemExit(f"--rounds must be between 1 and {MAX_EDIT_ROUNDS}")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("Set OPENAI_API_KEY before running the content factory.")

    client = OpenAI()
    agency = ContentAgency(
        client=client,
        text_model=os.getenv("TEXT_MODEL", "gpt-6-luna"),
        text_fallbacks=split_fallbacks(
            os.getenv("TEXT_FALLBACK_MODELS", "gpt-6.2-sol,gpt-6.1-terra")
        ),
        image_model=os.getenv("IMAGE_MODEL", "gpt-image-2.6-flare"),
        image_fallbacks=split_fallbacks(
            os.getenv("IMAGE_FALLBACK_MODELS", "gpt-image-2.5-flare")
        ),
        output_root=Path(args.output),
    )
    run_dir = agency.run(args.topic, args.brief, args.rounds)
    print(f"Content factory complete: {run_dir.resolve()}")
    if args.open_html:
        page = (run_dir / "page.html").resolve()
        if not webbrowser.open(page.as_uri()):
            raise SystemExit(f"Could not open the generated HTML page: {page}")
        print(f"Opened HTML page: {page}")


if __name__ == "__main__":
    main()
