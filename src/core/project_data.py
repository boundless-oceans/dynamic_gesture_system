"""非遗项目数据加载"""

import json

from src import paths


def _load():
    path = paths.resource_path("assets", "projects.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["items"]


PROJECTS = _load()


def get_names():
    return [p["name"] for p in PROJECTS]


def get_sections(index: int):
    p = PROJECTS[index]
    return [(s["title"], s["body"]) for s in p["sections"]]
