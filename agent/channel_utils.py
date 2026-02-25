
import os
import logging

logger = logging.getLogger(__name__)

def split_message(text: str, max_length: int = 4096) -> list[str]:
    if len(text) <= max_length:
        return [text]

    chunks = []
    while text:
        if len(text) <= max_length:
            chunks.append(text)
            break

        cut = text.rfind("\n\n", 0, max_length)
        if cut == -1:
            cut = text.rfind("\n", 0, max_length)
        if cut == -1:
            for sep in ("。", "？", "！", ".", "?", "!"):
                cut = text.rfind(sep, 0, max_length)
                if cut != -1:
                    cut += len(sep)
                    break
        if cut <= 0:
            cut = max_length

        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")

    return chunks

def safe_remove(path: str):
    try:
        os.remove(path)
        logger.debug("已删除临时文件: %s", path)
    except OSError:
        pass
