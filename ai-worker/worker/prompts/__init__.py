from pathlib import Path

PROMPT_VERSION = "phase3-scaffold-v1"
_PROMPTS_DIR = Path(__file__).parent


def load_classification_prompt() -> str:
    return (_PROMPTS_DIR / "classification_prompt.txt").read_text(encoding="utf-8")


def load_suggestion_prompt() -> str:
    return (_PROMPTS_DIR / "suggestion_prompt.txt").read_text(encoding="utf-8")
