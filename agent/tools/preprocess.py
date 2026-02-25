
from agent.config.prompts import get_labels

def preprocess_input(raw_input: dict, registry, language: str = "zh") -> tuple[str, dict]:
    L = get_labels("context.labels", language)

    input_type = raw_input.get("type", "text")
    text = raw_input.get("text", "")
    file_path = raw_input.get("file_path", "")

    metadata = {
        "type": input_type,
        "file_path": file_path,
        "original_text": text,
    }

    if input_type == "text":
        return text, metadata

    if input_type == "voice":
        transcribed = _transcribe_voice(file_path, registry)
        if transcribed:
            return transcribed, metadata
        return L["voice_failed"], metadata

    if input_type == "image":
        placeholder = L["image_placeholder"]
        if text:
            return f"{placeholder} {text}", metadata
        return placeholder, metadata

    if input_type == "file":
        placeholder = L["file_sent"].format(file_path=file_path)
        if text:
            return f"{placeholder} {text}", metadata
        return placeholder, metadata

    return text or L["unknown_input"], metadata

def _transcribe_voice(file_path: str, registry) -> str | None:
    if not file_path:
        return None

    tool = registry.get_tool("voice_transcribe")
    if not tool:
        return None

    result = registry.execute("voice_transcribe", {"file_path": file_path})
    if result.success:
        return result.data
    else:
        return None
