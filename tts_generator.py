import base64
import json
import os
import queue
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional

import yaml
import jsonschema
from openai import OpenAI

# ── 配置 ────────────────────────────────────────────────────

MODEL = "mimo-v2.5-tts-voiceclone"
SCHEMA_PATH = "schema.jsonc"
MAX_RETRIES = 50
MAX_TEXT_LEN = 10

# client_id → 独立配置
CLIENT_CONFIGS: dict[int, dict] = {
    0: {
        "api_key": "sk-cawpv749024o67kun1n8csga03yzugzv4y3pvllpty9pjbph",
        "base_url": "https://api.xiaomimimo.com/v1",
    },
    1: {
        "api_key": "sk-c6mws0teq8sjj9aygzq1adp8xkr4qml2lirkamhrodl3fms4",
        "base_url": "https://api.xiaomimimo.com/v1",
    },
    2: {
        "api_key": "tp-cbqaign8waw5q0v3g97vnl4k2wqb33uxm9xzxz7ri1h53zqa",
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
    },
}

# 角色 → 音色文件路径
VOICE_MAP: dict[str, str] = {
    "旁白": "asset/aimiliya.wav",
    "爱蜜莉雅": "asset/aimiliya.wav",
    "雷姆": "asset/aimiliya.wav",
    "碧翠丝": "asset/aimiliya.wav",
    "罗兹瓦尔": "asset/aimiliya.wav",
    "拉姆": "asset/aimiliya.wav",
    "奥托": "asset/aimiliya.wav",
    "弗雷德莉卡": "asset/aimiliya.wav",
    "加菲尔": "asset/aimiliya.wav",
    "佩特拉": "asset/aimiliya.wav",
    "库珥修": "asset/aimiliya.wav",
    "菲莉丝": "asset/aimiliya.wav",
    "威尔海姆": "asset/aimiliya.wav",
    "普莉希拉": "asset/aimiliya.wav",
    "阿尔": "asset/aimiliya.wav",
    "菲鲁特": "asset/aimiliya.wav",
    "莱茵哈鲁特": "asset/aimiliya.wav",
    "安娜塔西亚": "asset/aimiliya.wav",
    "由里乌斯": "asset/aimiliya.wav",
    "里卡多": "asset/aimiliya.wav",
    "蜜蜜": "asset/aimiliya.wav",
    "缇碧": "asset/aimiliya.wav",
}


# ── 数据结构 ────────────────────────────────────────────────

@dataclass
class TtsTask:
    index: int
    character: str
    text: str
    emotion: str = ""
    prompt: str = ""
    voice_path: str = ""
    output_path: str = ""
    retries: int = 0


@dataclass
class TaskResult:
    task: TtsTask
    success: bool
    error: Optional[str] = None


# ── 工具 ────────────────────────────────────────────────────

def _sanitize(s: str, max_len: int = MAX_TEXT_LEN) -> str:
    s = re.sub(r'\s+', '', s)[:max_len]
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    return s or "empty"


def _load_jsonc(path: str) -> dict:
    """读取 JSONC 文件（跳过注释和逗号尾随）"""
    import commentjson
    with open(path, 'r', encoding='utf-8') as f:
        return commentjson.load(f)


def _build_messages(task: TtsTask) -> list[dict]:
    return [
        {"role": "user", "content": ""},
        {"role": "assistant", "content": task.text},
    ]


# ── TTS 客户端（单个 worker） ──────────────────────────────

class TtsClient:
    def __init__(self, client_id: int, api_key: str, base_url: str):
        self.client_id = client_id
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def synthesize(self, task: TtsTask) -> TaskResult:
        last_error = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                kwargs = {"model": MODEL, "messages": _build_messages(task),"seed": 42,"temperature": 0.1}
                if task.voice_path and os.path.isfile(task.voice_path):
                    with open(task.voice_path, "rb") as f:
                        voice_b64 = base64.b64encode(f.read()).decode("utf-8")
                    kwargs["audio"] = {
                        "format": "wav",
                        "voice": f"data:audio/mpeg;base64,{voice_b64}",
                    }

                resp = self.client.chat.completions.create(**kwargs)
                audio_bytes = base64.b64decode(resp.choices[0].message.audio.data)

                os.makedirs(os.path.dirname(task.output_path), exist_ok=True)
                with open(task.output_path, "wb") as f:
                    f.write(audio_bytes)

                return TaskResult(task=task, success=True)

            except Exception as e:
                last_error = str(e)
                task.retries = attempt + 1
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)

        return TaskResult(task=task, success=False, error=last_error)
    def close(self):
        """显式关闭客户端，释放底层连接池"""
        self.client.close()


# ── 生产者-消费者引擎 ──────────────────────────────────────

def _produce(title: str, script: list[dict]) -> list[TtsTask]:
    tasks = []
    for i, item in enumerate(script):
        character = item.get("character", "旁白")
        text = item.get("text", "").strip()
        if not text or character == "视频内容":
            continue

        safe_title = _sanitize(title, 50)
        filename = f"{i:04d}-{character}-{_sanitize(text)}.wav"

        tasks.append(TtsTask(
            index=i,
            character=character,
            text=text,
            emotion=item.get("emotion", ""),
            prompt=item.get("prompt", ""),
            voice_path=VOICE_MAP.get(character, ""),
            output_path=os.path.join("voice", safe_title, filename),
        ))
    return tasks


def _consume(task_queue: queue.Queue, stats: dict, results: list):
    def worker(cid: int):
        cfg = CLIENT_CONFIGS[cid]
        client = TtsClient(cid, cfg["api_key"], cfg["base_url"])
        while True:
            try:
                task = task_queue.get_nowait()
            except queue.Empty:
                break
            result = client.synthesize(task)
            results.append(result)
            stats["success" if result.success else "failed"] += 1
            task_queue.task_done()
        client.close()

    with ThreadPoolExecutor(max_workers=len(CLIENT_CONFIGS)) as pool:
        futs = [pool.submit(worker, i) for i in range(len(CLIENT_CONFIGS))]
        for f in as_completed(futs):
            f.result()


# ── 对外函数 ────────────────────────────────────────────────

def generate_tts(yaml_path: str) -> dict:
    """
    读取 YAML 剧本，校验 schema，生成 TTS 语音。

    Returns: {"total": N, "success": N, "failed": N}
    """
    with open(yaml_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    schema = _load_jsonc(SCHEMA_PATH)
    jsonschema.validate(instance=data, schema=schema)

    title = data.get("title", "untitled")
    tasks = _produce(title, data.get("script", []))
    stats = {"total": len(tasks), "success": 0, "failed": 0}
    results: list[TaskResult] = []

    if not tasks:
        return stats

    q = queue.Queue()
    for t in tasks:
        q.put(t)

    _consume(q, stats, results)

    for r in results:
        if not r.success:
            print(f"  ❌ [{r.task.index:04d}] {r.task.character}: {r.task.text[:30]}  →  {r.error}")

    return stats
