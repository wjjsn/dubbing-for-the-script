import os
import queue
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Literal
import yaml
import jsonschema
from src.common import *
from src.tts_client import tts_client_mimo,tts_client_CosyVoice3
# ── 配置 ────────────────────────────────────────────────────

SCHEMA_PATH = "schema.jsonc"
MAX_RETRIES = 10
MAX_TEXT_LEN = 10

# client_id → 独立配置
CLIENT_CONFIGS: dict[int, dict] = {
    #所有密钥都是失效的，无需担心
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

# 角色 → {voice_path, model}
VOICE_MAP: dict[str, dict] = {
    "旁白":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "爱蜜莉雅":   {"voice_path": "asset/爱蜜莉雅.wav", "model": "mimo-v2.5-tts", "prompt_text": "どうしたのスバル君 ホームルームのチャイムはなりましたよ"},
    "雷姆":       {"voice_path": "asset/雷姆.wav", "model": "mimo-v2.5-tts", "prompt_text": "カララギに到着して、まず宿を借ります 生活の基盤は、家とお仕事があればなんとかなるでしょう 幸い、レムはロズバール様のあからいで教育を受けていますから カララギでもいくらか仕事を見つけるのは良いだと思います スバル君は肉体労働を探してもらうか、レムの身の回りの汗は押してもらうことになるかもしれませんね"},
    "碧翠丝":     {"voice_path": "asset/碧翠丝.wav", "model": "mimo-v2.5-tts", "prompt_text": "なんて心の底から腹立たしいやつなのかしら お前に見せる笑顔なんで長少で十分なのよ ビティの処庫県新室県を支出かしら"},
    "罗兹瓦尔":   {"voice_path": "asset/罗兹瓦尔.wav", "model": "mimo-v2.5-tts", "prompt_text": "これはこれは珍しいとりあわせだーね スバルくん それは私から聞いたのかね うん そうか そうか残念だ シラを着ることもできるが 君らもそれなりの根拠を持ってここへ来たんだ 私もそれに敬意を払おうじゃないか"},
    "拉姆":       {"voice_path": "asset/拉姆.wav", "model": "mimo-v2.5-tts", "prompt_text": "アラバルスの子のことラムたちの超芸術性に誘われて現れたようね レムたちが屋敷の外で雪と騙むれているのに ラムだけベッドでダミンを塗さぼっているとでも"},
    "奥托":       {"voice_path": "asset/奥托.wav", "model": "mimo-v2.5-tts", "prompt_text": "何か言いましたかあなつきさん どうしたんですか急に出れるじゃないですか これからメイザーするよまでもう夜ですし危険では僕たちは今夜ここで夜へするつもり なのでよければご視聴されませんか"},
    # "爱蜜莉雅":   {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    # "雷姆":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts-voiceclone"},
    # "碧翠丝":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts-voiceclone"},
    # "罗兹瓦尔":   {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts-voiceclone"},
    # "拉姆":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts-voiceclone"},
    # "奥托":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts-voiceclone"},
    "弗雷德莉卡": {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "加菲尔":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "佩特拉":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "库珥修":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "菲莉丝":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "威尔海姆":   {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "普莉希拉":   {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "阿尔":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "菲鲁特":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "莱茵哈鲁特": {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "安娜塔西亚": {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "由里乌斯":   {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "里卡多":     {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "蜜蜜":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "缇碧":       {"voice_path": "src/CosyVoice/asset/zero_shot_prompt.wav", "model": "mimo-v2.5-tts", "prompt_text": "希望你以后能够做的比我还好呦。"},
    "凑粉毛":       {"voice_path": "asset/凑粉毛.wav", "model": "mimo-v2.5-tts-voiceclone", "prompt_text": "不过新的插件堂堂复活！四个小版本不见，插件带来了若干新功能，包括但不限于：一、对话分岔：你现在可以和ChatGPT一样在任何对话节点展开一个新的对话"},
}





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





# ── 生产者-消费者引擎 ──────────────────────────────────────

def _produce(title: str, script: list[dict]) -> list[TtsTask]:
    tasks = []
    for i, item in enumerate(script):
        character = item.get("character", "旁白")
        text = item.get("text", "").strip()
        if not text :
            continue

        safe_title = _sanitize(title, 50)
        filename = f"{i:04d}-{character}-{_sanitize(text)}.wav"

        tasks.append(TtsTask(
            index=i,
            character=character,
            text=text,
            emotion=item.get("emotion", ""),
            prompt=item.get("prompt", ""),
            voice_path=VOICE_MAP.get(character, {}).get("voice_path", ""),
            character_voice_prompt_text=VOICE_MAP.get(character, {}).get("prompt_text", ""),
            model=VOICE_MAP.get(character, {}).get("model"),
            output_path=os.path.join("voice", safe_title, filename),
        ))
    return tasks


def _consume(task_queue: queue.Queue, stats: dict, results: list, backend: Literal["mimo", "CosyVoice3"]):
    def worker(cid: int):
        client = None
        match backend:
            case "mimo":
                cfg = CLIENT_CONFIGS[cid]
                client = tts_client_mimo(cid, cfg["api_key"], cfg["base_url"])
            case "CosyVoice3":
                client = tts_client_CosyVoice3(cid)
        if client == None:
            exit(-1)

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

def generate_tts(yaml_path: str, backend: Literal["mimo", "CosyVoice3"]) -> dict:
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

    _consume(q, stats, results, backend)

    for r in results:
        if not r.success:
            print(f"  ❌ [{r.task.index:04d}] {r.task.character}: {r.task.text[:30]}  →  {r.error}")

    return stats
