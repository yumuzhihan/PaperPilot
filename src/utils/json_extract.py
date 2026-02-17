import re
import json


def extract_json_from_text(text: str):
    """
    从混合文本中提取 JSON 内容。
    支持提取 list [...] 或 dict {...}
    """
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    pattern = r"(\{.*\}|\[.*\])"
    match = re.search(pattern, text, re.DOTALL)

    if match:
        json_str = match.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return None
