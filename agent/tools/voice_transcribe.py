
import os
import requests
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

_FALLBACK = {
    "en": {
        "description": "Transcribe voice/audio files to text",
        "parameters": {"file_path": "Audio file path (mp3/wav/ogg/m4a etc.)"},
        "examples": ["Transcribe voice message", "Convert recording to text"],
    },
    "zh": {
        "description": "将语音/音频文件转为文字",
        "parameters": {"file_path": "音频文件路径（支持 mp3/wav/ogg/m4a 等）"},
        "examples": ["转写语音消息", "将录音转为文字"],
    },
    "ja": {
        "description": "音声・オーディオファイルをテキストに変換する",
        "parameters": {"file_path": "音声ファイルパス（mp3/wav/ogg/m4a 等）"},
        "examples": ["音声メッセージを文字起こし", "録音をテキストに変換"],
    },
}

class VoiceTranscribeTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        tools_cfg = config.get("tools", {})
        voice_cfg = tools_cfg.get("voice_transcribe", {})

        llm_cfg = config.get("llm", {})
        self.api_base = voice_cfg.get("api_base", llm_cfg.get("api_base", "https://api.openai.com"))
        self.api_key = voice_cfg.get("api_key", llm_cfg.get("api_key", ""))
        self.model = voice_cfg.get("model", "")
        self.language = voice_cfg.get("language", "zh")

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "zh")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("voice_transcribe", {})
        return ToolManifest(
            name="voice_transcribe",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def is_available(self) -> bool:
        return bool(self.api_key)

    def execute(self, params: dict) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "zh"))
        file_path = params.get("file_path", "")
        if not file_path:
            return ToolResult(success=False, data="", error=EL["missing_file_path"])
        if not os.path.exists(file_path):
            return ToolResult(success=False, data="", error=EL["voice_file_not_found"].format(path=file_path))

        headers = {"Authorization": f"Bearer {self.api_key}"}

        try:
            with open(file_path, "rb") as f:
                resp = requests.post(
                    f"{self.api_base}/v1/audio/transcriptions",
                    headers=headers,
                    files={"file": (os.path.basename(file_path), f)},
                    data={
                        "model": self.model,
                        "language": self.language,
                    },
                    timeout=60,
                )
            resp.raise_for_status()
            text = resp.json().get("text", "")
            if not text:
                return ToolResult(success=False, data="", error=EL["voice_transcribe_empty"])
            return ToolResult(success=True, data=text)
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["voice_transcribe_failed"].format(error=e))
