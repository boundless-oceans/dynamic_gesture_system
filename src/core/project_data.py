"""非遗项目数据加载"""

import json
import os


def _load():
    path = os.path.join(os.path.dirname(__file__), "../../assets/projects.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


PROJECTS = _load()


def get_names():
    return [p["name"] for p in PROJECTS]


def get_sections(index: int):
    p = PROJECTS[index]
    return [(s["title"], s["body"]) for s in p["sections"]]
