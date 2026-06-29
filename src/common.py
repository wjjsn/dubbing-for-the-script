

from dataclasses import dataclass
from typing import Optional
# ── 数据结构 ────────────────────────────────────────────────

@dataclass
class TtsTask:
    index: int
    character: str
    text: str
    emotion: str = ""
    prompt: str = ""
    voice_path: str = ""
    character_voice_prompt_text: str = ""
    model: str = ""
    output_path: str = ""
    retries: int = 0


@dataclass
class TaskResult:
    task: TtsTask
    success: bool
    error: Optional[str] = None