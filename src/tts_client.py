from openai import OpenAI
import base64
from src.common import *
import os

import time
import requests
class tts_client_mimo:
    def _build_messages(task: TtsTask) -> list[dict]:
        return [
            {"role": "user", "content": "请说中文。"},
            {"role": "assistant", "content": task.text},
        ]

    def __init__(self, client_id: int, api_key: str, base_url: str):
        self.client_id = client_id
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def synthesize(self, task: TtsTask, max_retries=10) -> TaskResult:
        # 已有产物：跳过 API，直接返回成功
        if task.output_path and os.path.isfile(task.output_path):
            print(f"  ⏭️  [{task.index:04d}] {task.character}: 复用 {task.output_path}")
            return TaskResult(task=task, success=True)

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                kwargs = {"model": task.model, "messages": self._build_messages(task),"seed": 42,"temperature": 0.1}
                # print(f"角色`{task.character}`正在使用`{task.model}`模型，声音是：`{task.voice_path}`")
                print(task,end='\n--------\n')
                if task.voice_path and os.path.isfile(task.voice_path):
                    if task.model == "mimo-v2.5-tts-voiceclone":
                        with open(task.voice_path, "rb") as f:
                            voice_b64 = base64.b64encode(f.read()).decode("utf-8")
                        kwargs["audio"] = {
                            "format": "wav",
                            "voice": f"data:audio/mpeg;base64,{voice_b64}",
                        }
                    elif task.model == "mimo-v2.5-tts":
                        kwargs["audio"] = {
                            "format": "wav",
                            "voice": "白桦",
                        }
                    else:
                        return TaskResult(task=task, success=False)

                resp = self.client.chat.completions.create(**kwargs)
                audio_bytes = base64.b64decode(resp.choices[0].message.audio.data)

                os.makedirs(os.path.dirname(task.output_path), exist_ok=True)
                with open(task.output_path, "wb") as f:
                    f.write(audio_bytes)

                return TaskResult(task=task, success=True)

            except Exception as e:
                last_error = str(e)
                task.retries = attempt + 1
                if attempt < max_retries:
                    time.sleep(2 * attempt)

        return TaskResult(task=task, success=False, error=last_error)
    def close(self):
        """显式关闭客户端，释放底层连接池"""
        self.client.close()

class tts_client_CosyVoice3:
    """
    调用本地 CosyVoice3 FastAPI 服务。
    服务返回完整 WAV 文件，客户端直接落盘即可。
    """

    def __init__(self, client_id: int = 0, base_url: str = "http://127.0.0.1:50000", **_kwargs):
        self.client_id = client_id
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        # 没有专属音色时用的默认 prompt wav（CosyVoice 自带）
        self._default_prompt_wav = os.path.join(
            os.path.dirname(__file__), "CosyVoice", "asset", "zero_shot_prompt.wav"
        )

    def close(self):
        """显式关闭 HTTP 连接池"""
        self.session.close()

    def synthesize(self, task: TtsTask, max_retries=3) -> TaskResult:
        # 已有产物：跳过
        if task.output_path and os.path.isfile(task.output_path):
            print(f"  ⏭️  [{task.index:04d}] {task.character}: 复用 {task.output_path}")
            return TaskResult(task=task, success=True)
        
        url = None
        data = None
        # prompt_wav 必须传，没有专属音色就用默认
        prompt_wav_path = task.voice_path if (task.voice_path and os.path.isfile(task.voice_path)) else self._default_prompt_wav
        match task.model:
            case "mimo-v2.5-tts":
                url = f"{self.base_url}/inference_cross_lingual"
                data = {
                    "tts_text": f'You are a helpful assistant.请用稍快一丝的语速朗读。<|endofprompt|>{task.text}',
                }
            case "mimo-v2.5-tts-voiceclone":
                url = f"{self.base_url}/inference_zero_shot"
                data = {
                    "tts_text": f'{task.text}',
                    "prompt_text": f'You are a helpful assistant.<|endofprompt|>{task.character_voice_prompt_text}'
                }


        last_error = None
        with open(prompt_wav_path, "rb") as f:
            file_content = f.read()
        for attempt in range(max_retries + 1):
            try:
                resp = self.session.post(url, data=data,
                    files={"prompt_wav": (os.path.basename(prompt_wav_path), file_content, "application/octet-stream")},
                    timeout=600)
                resp.raise_for_status()
                wav_bytes = resp.content
                break
            except Exception as e:
                last_error = str(e)
                task.retries = attempt + 1
                print(f"  ⚠️  [{task.index:04d}] {task.character} 第 {attempt+1} 次重试: {e}")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                wav_bytes = b""

        if not wav_bytes:
            return TaskResult(task=task, success=False, error=f"all retries failed: {last_error}")

        os.makedirs(os.path.dirname(task.output_path), exist_ok=True)
        with open(task.output_path, "wb") as f:
            f.write(wav_bytes)
        print(f"文件已保存在： {task.output_path}")
        return TaskResult(task=task, success=True)
