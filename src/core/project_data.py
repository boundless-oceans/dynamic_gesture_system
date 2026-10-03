"""非遗项目 / 传承人数据加载

两份 JSON 的读取都收在这里 —— 首页（两排卡片）和传承人页都要用，
不该两个模块各读一遍同一个文件。
"""

import json

from src import paths


def _load(name: str):
    path = paths.resource_path("assets", name)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


PROJECTS = _load("projects.json")


def _load_inheritors():
    """传承人数据。

    读失败返回空列表（沿用传承人页原来的行为）：**首页第二排会因此消失**，
    但整个程序还能起来、用鼠标操作其余部分 —— 比因为一个数据文件崩掉强。
    """
    try:
        return _load("inheritors.json")
    except Exception as e:
        print("[Data] 读取 inheritors.json 失败，传承人列表为空: %s" % e, flush=True)
        return []


# 传承人条目字段：name / project / video / photo / bio
INHERITORS = _load_inheritors()


def get_names():
    return [p["name"] for p in PROJECTS]


def get_sections(index: int):
    p = PROJECTS[index]
    return [(s["title"], s["body"]) for s in p["sections"]]


def get_inheritor_count() -> int:
    return len(INHERITORS)


def get_inheritor(index: int):
    """按下标取传承人；越界返回 None（调用方自己兜底）"""
    if 0 <= index < len(INHERITORS):
        return INHERITORS[index]
    return None
