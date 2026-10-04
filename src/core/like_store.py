"""点赞计数（**按非遗项目分记**）

「点赞」静态手势给**当前这个项目** +1，数最后画在首页卡片角标上 ——
访客一眼能看出哪个展项最受欢迎，文化馆也顺带拿到一份真实的使用分布。

**为什么按 slug 记、不按序号记**
    序号（`project_assets.slug_of` 的入参）会在文化馆往 `projects.json` 里
    插一个项目、或调一下顺序时**全体错位**。那样点赞数会**悄悄串到别的项目上**，
    而且不报任何错 —— 正是这个项目最讨厌的那类坏法。slug 是稳定标识。

**存盘**：`config.LIKE_COUNT_PATH`（铺在 exe 旁边，已 gitignore）。
    * 读坏了就当空的重来，只打一行日志 —— **绝不因为一个计数文件让展台起不来**
    * 写盘走"写临时文件 → `os.replace`"，避免写到一半断电留下半个 JSON
    * 写不进去（目录只读等）不抛异常：内存里照样记，只是这次没落盘
"""
import json
import os
import tempfile

from src import config

# 上限。防的是"某个项目被误触刷到离谱数字"——到了上限就不再涨，
# 但**不报错、不影响别的项目**。选 999999 是因为它在卡片角标上还放得下。
MAX_COUNT = 999999


def _coerce(v) -> int:
    """把存档里的一个值弄成合法的计数。弄不出来就是 0，不抛异常。"""
    try:
        n = int(v)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_COUNT, n))


class LikeStore:
    """按项目 slug 记点赞数。**一个实例即可**（MainWindow 持有）。

    构造时读盘；`add()` 加完立刻落盘 —— 点赞是低频动作，不值得为省一次写盘
    去冒"断电丢数据"的险。
    """

    def __init__(self, path: str | None = None):
        self.path = path if path is not None else config.LIKE_COUNT_PATH
        self._counts: dict[str, int] = {}
        self.load()

    # ---------------- 读 ----------------
    def load(self):
        """从磁盘读。任何异常都退化成"空档"，不让计数文件搞垮程序。"""
        self._counts = {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return                      # 第一次跑，正常
        except Exception as e:
            print(f"[Likes] 读取 {os.path.basename(self.path)} 失败，先按空的算: {e}",
                  flush=True)
            return
        if not isinstance(data, dict):
            print(f"[Likes] {os.path.basename(self.path)} 不是一个字典，先按空的算",
                  flush=True)
            return
        for slug, v in data.items():
            self._counts[str(slug)] = _coerce(v)

    # ---------------- 写 ----------------
    def save(self):
        """原子写盘。失败只记一行日志 —— 计数不该是能把程序弄崩的东西。"""
        tmp = None
        try:
            d = os.path.dirname(os.path.abspath(self.path))
            fd, tmp = tempfile.mkstemp(prefix=".likes-", suffix=".tmp", dir=d)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self._counts, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)      # 同目录 rename，原子
        except Exception as e:
            print(f"[Likes] 保存失败（本次只在内存里记着）: {e}", flush=True)
            if tmp:
                try:
                    os.remove(tmp)
                except OSError:
                    pass

    # ---------------- 用 ----------------
    def count(self, slug: str) -> int:
        return self._counts.get(slug, 0)

    def add(self, slug: str, n: int = 1) -> int:
        """给某个项目 +n，返回**加完之后**的数。

        ⚠ **空 slug 直接返回 0、不写盘** —— 它表示"此刻没有对应的项目"
        （比如在传承人页上点赞：那一位传承人不一定属于首页那几个项目）。
        不挡住的话，存档里会多出一个键为空的垃圾条目。
        """
        if not slug:
            return 0
        cur = self._counts.get(slug, 0)
        # 夹在 [0, MAX_COUNT]：上限防"被误触刷到离谱数字"，
        # 下限防调用方传个负数把计数弄倒退
        self._counts[slug] = min(MAX_COUNT, cur + max(0, n))
        self.save()
        return self._counts[slug]

    def all_counts(self) -> dict:
        """当前全部计数（副本，改它不影响存档）"""
        return dict(self._counts)

    def reset(self):
        """清零并删掉存档文件（操作员用）"""
        self._counts = {}
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass
        except OSError as e:
            print(f"[Likes] 删不掉 {os.path.basename(self.path)}: {e}", flush=True)
            return
        print("[Likes] 点赞计数已清零", flush=True)
