# Content Factory

A CLI implementation of the prompt chain shown in the supplied diagrams. Each role's output becomes the next role's input:

1. Clarifier: expands the topic and brief
2. Researcher: creates a notes document
3. Writer: creates a Markdown draft
4. Editor: approves or returns feedback for up to three rounds
5. Image Designer: creates an image prompt
6. HTML Developer: creates a standalone HTML page

## Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e .
Copy-Item .env.example .env
```

Set `OPENAI_API_KEY` in `.env`. Text and image model IDs can also be changed there.

## Run

Use the demo topic and open the generated page in your default browser:

```powershell
python main.py --open-html
```

Choose a different topic and add a brief describing the audience, angle, or details
you want the content to cover:

```powershell
python main.py --topic "A beginner's guide to balcony gardening" --brief "Write for apartment renters. Focus on low-cost containers, easy herbs, and getting started in a small space." --open-html
```

The generated page is saved as `output/<topic-slug>/page.html` and opens in your
default browser when you include `--open-html`. Omit that option to generate files
without opening a browser. Each run is written to `output/<topic-slug>/` as
`brief.md`, `notes.md`, `article.md`, `editor-feedback.md`, `image-prompt.txt`,
`image.png`, `page.html`, and `run-details.txt`. To use another output folder,
pass `--output "path\to\folder"`.
