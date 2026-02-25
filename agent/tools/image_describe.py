
import os
import base64
import requests
from agent.tools import BaseTool, ToolManifest, ToolResult
from agent.config.prompts import get_labels

_FALLBACK = {
    "en": {
        "description": "Describe image content, recognize objects, scenes, and text",
        "parameters": {"file_path": "Image file path", "question": "Specific question about the image (optional)"},
        "examples": ["What is this image", "What's in this picture", "Describe this screenshot"],
        "default_question": "Please describe the content of this image.",
    },
    "zh": {
        "description": "描述图片内容，识别图片中的物体、场景、文字等",
        "parameters": {"file_path": "图片文件路径", "question": "关于图片的具体问题（可选）"},
        "examples": ["这张图片是什么", "图片里有什么花", "帮我看看这张截图"],
        "default_question": "请描述这张图片的内容。",
    },
    "ja": {
        "description": "画像の内容を説明し、物体・シーン・テキストを認識する",
        "parameters": {"file_path": "画像ファイルパス", "question": "画像に関する具体的な質問（任意）"},
        "examples": ["この画像は何", "写真に何が写っている", "このスクリーンショットを見て"],
        "default_question": "この画像の内容を説明してください。",
    },
}

class ImageDescribeTool(BaseTool):

    def __init__(self, config: dict):
        self.config = config
        tools_cfg = config.get("tools", {})
        img_cfg = tools_cfg.get("image_describe", {})

        self.provider = img_cfg.get("provider", "openai")
        self.model = img_cfg.get("model", "")

        llm_cfg = config.get("llm", {})
        if self.provider == "openai":
            self.api_base = img_cfg.get("api_base", "https://api.openai.com")
            self.api_key = img_cfg.get("api_key", llm_cfg.get("api_key", ""))
        else:
            self.api_base = img_cfg.get("api_base", "http://localhost:11434")
            self.api_key = ""

    def manifest(self) -> ToolManifest:
        lang = self.config.get("language", "zh")
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        m = get_labels("tools.manifests", lang).get("image_describe", {})
        return ToolManifest(
            name="image_describe",
            description=m.get("description", fb["description"]),
            parameters=m.get("parameters", fb["parameters"]),
            examples=m.get("examples", fb["examples"]),
        )

    def is_available(self) -> bool:
        if self.provider == "openai":
            return bool(self.api_key)
        return True

    def execute(self, params: dict) -> ToolResult:
        file_path = params.get("file_path", "")
        lang = self.config.get("language", "zh")
        m = get_labels("tools.manifests", lang).get("image_describe", {})
        EL = get_labels("errors.tools", lang)
        fb = _FALLBACK.get(lang, _FALLBACK["en"])
        question = params.get("question", m.get("default_question", fb["default_question"]))

        if not file_path:
            return ToolResult(success=False, data="", error=EL["missing_image_path"])
        if not os.path.exists(file_path):
            return ToolResult(success=False, data="", error=EL["image_not_found"].format(path=file_path))

        if self.provider == "openai":
            return self._describe_openai(file_path, question)
        else:
            return self._describe_local(file_path, question)

    def _describe_openai(self, file_path: str, question: str) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "zh"))
        try:
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["image_read_failed"].format(error=e))

        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
        mime_type = mime_map.get(ext, "image/jpeg")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = [
            {"role": "user", "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {
                    "url": f"data:{mime_type};base64,{image_data}",
                }},
            ]},
        ]

        try:
            resp = requests.post(
                f"{self.api_base}/v1/chat/completions",
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 1024,
                },
                timeout=60,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            return ToolResult(success=True, data=text)
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["image_describe_failed"].format(error=e))

    def _describe_local(self, file_path: str, question: str) -> ToolResult:
        EL = get_labels("errors.tools", self.config.get("language", "zh"))
        try:
            with open(file_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["image_read_failed"].format(error=e))

        try:
            resp = requests.post(
                f"{self.api_base}/api/generate",
                json={
                    "model": self.model,
                    "prompt": question,
                    "images": [image_data],
                    "stream": False,
                },
                timeout=120,
            )
            resp.raise_for_status()
            text = resp.json().get("response", "")
            if not text:
                return ToolResult(success=False, data="", error=EL["image_describe_empty"])
            return ToolResult(success=True, data=text)
        except Exception as e:
            return ToolResult(success=False, data="", error=EL["image_describe_failed"].format(error=e))
