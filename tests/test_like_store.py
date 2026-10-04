"""点赞计数存档（src/core/like_store.py）

这一层要守的都是**坏了不会报错**的坏法：

  * **键必须是 slug，不是序号** —— 序号会在项目增减/调序时全体错位，
    点赞数就悄悄串到别的项目上，界面看着完全正常
  * **存档文件的任何毛病都不能把程序搞崩** —— 它是运行时数据，用户/杀毒/
    断电都可能把它弄坏。读坏了就当空的重来，只记一行日志
  * **写盘要原子** —— 写到一半断电不能留下半个 JSON（那样下次直接读不出来）
  * **空 slug 不能写进去** —— 否则存档里会多出键为空的垃圾条目

全在临时目录里跑，不碰仓库里真正的 likes.json。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.like_store import MAX_COUNT, LikeStore


class _Base(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="likes-test-")
        self.path = os.path.join(self.dir, "likes.json")

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def store(self):
        return LikeStore(self.path)

    def write_raw(self, text):
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def read_raw(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()


class TestBasicCounting(_Base):

    def test_新档是空的(self):
        s = self.store()
        self.assertEqual(s.count("baogong"), 0)
        self.assertEqual(s.all_counts(), {})

    def test_add返回加完之后的数(self):
        s = self.store()
        self.assertEqual(s.add("baogong"), 1)
        self.assertEqual(s.add("baogong"), 2)
        self.assertEqual(s.count("baogong"), 2)

    def test_按项目分开记(self):
        s = self.store()
        s.add("baogong", 3)
        s.add("hulu")
        self.assertEqual(s.count("baogong"), 3)
        self.assertEqual(s.count("hulu"), 1)
        self.assertEqual(s.count("luju"), 0)

    def test_all_counts是副本(self):
        """改返回的字典不能影响到存档 —— 否则调用方顺手一改数据就错了"""
        s = self.store()
        s.add("baogong")
        d = s.all_counts()
        d["baogong"] = 999
        self.assertEqual(s.count("baogong"), 1)


class TestPersistence(_Base):

    def test_存盘之后重新打开还在(self):
        self.store().add("baogong", 4)
        self.assertEqual(self.store().count("baogong"), 4)

    def test_add当场落盘(self):
        """点赞是低频动作，不值得为省一次写盘去冒"断电丢数据"的险。"""
        s = self.store()
        s.add("hulu")
        with open(self.path, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"hulu": 1})

    def test_写完的文件是完整合法的json(self):
        """走的是"临时文件 + replace"，不该出现写了一半的中间态"""
        s = self.store()
        for slug in ("hulu", "baogong", "luju"):
            s.add(slug, 2)
        data = json.loads(self.read_raw())
        self.assertEqual(data, {"hulu": 2, "baogong": 2, "luju": 2})

    def test_不留临时文件(self):
        s = self.store()
        s.add("hulu")
        leftovers = [n for n in os.listdir(self.dir) if n != "likes.json"]
        self.assertEqual(leftovers, [], "写盘之后不该留下临时文件")

    def test_写盘失败时旧档必须完好(self):
        """⚠ **走"临时文件 + os.replace"的全部意义就在这一条上。**

        直接 `open(path, "w")` 去写的话，json.dump 中途抛异常时文件**已经被截断**了
        —— 旧档没了，新档又没写全，下次启动直接读不出来。
        （所以"写完是合法 JSON"那条其实验不出区别：直接覆写也能过。）

        这里塞一个不可 JSON 序列化的值（集合）去逼 dump 中途抛异常。
        """
        s = self.store()
        s.add("hulu", 3)
        before = self.read_raw()

        s._counts["坏值"] = {1, 2}      # set 不可序列化 → dump 中途抛
        s.save()

        self.assertEqual(self.read_raw(), before, "写盘失败把旧档毁掉了")
        self.assertEqual(self.store().count("hulu"), 3, "旧档应该还能原样读出来")
        leftovers = [n for n in os.listdir(self.dir) if n != "likes.json"]
        self.assertEqual(leftovers, [], "写失败的临时文件没被清掉")

    def test_目录不存在时add不抛且内存仍然对(self):
        """写不进去只该是"这次没落盘"，不该把点赞这个动作本身弄失败。"""
        s = LikeStore(os.path.join(self.dir, "不存在的目录", "likes.json"))
        self.assertEqual(s.add("baogong"), 1, "落盘失败也要照常返回新值")
        self.assertEqual(s.count("baogong"), 1)


class TestCorruptedFile(_Base):
    """存档文件的任何毛病都只能退化成"当空的算"，绝不能抛"""

    def test_文件不存在(self):
        self.assertEqual(self.store().all_counts(), {})

    def test_不是json(self):
        self.write_raw("{这不是 json")
        self.assertEqual(self.store().all_counts(), {})

    def test_是json但不是字典(self):
        self.write_raw("[1, 2, 3]")
        self.assertEqual(self.store().all_counts(), {})

    def test_空文件(self):
        self.write_raw("")
        self.assertEqual(self.store().all_counts(), {})

    def test_值不是数字就当0(self):
        self.write_raw(json.dumps({"baogong": "很多", "hulu": None}))
        s = self.store()
        self.assertEqual(s.count("baogong"), 0)
        self.assertEqual(s.count("hulu"), 0)

    def test_值能当数字用就留下(self):
        self.write_raw(json.dumps({"baogong": "7"}))
        self.assertEqual(self.store().count("baogong"), 7)

    def test_负数夹到0(self):
        self.write_raw(json.dumps({"baogong": -5}))
        self.assertEqual(self.store().count("baogong"), 0)

    def test_超上限夹到上限(self):
        self.write_raw(json.dumps({"baogong": MAX_COUNT + 10000}))
        self.assertEqual(self.store().count("baogong"), MAX_COUNT)

    def test_坏掉之后还能正常继续记(self):
        """读坏了不该让它变成只读的 —— 后面照样能加。"""
        self.write_raw("{坏的")
        s = self.store()
        self.assertEqual(s.add("hulu"), 1)
        self.assertEqual(self.store().count("hulu"), 1)


class TestGuards(_Base):

    def test_空slug不写盘(self):
        """⚠ 它表示"此刻没有对应的项目"（比如在传承人页上点赞）。

        不挡住的话，存档里会多出一个键为空的垃圾条目，而且**没人会发现**。
        """
        s = self.store()
        self.assertEqual(s.add(""), 0)
        self.assertEqual(s.add(None), 0)
        self.assertFalse(os.path.exists(self.path), "空 slug 不该产生存档文件")
        self.assertEqual(s.all_counts(), {})

    def test_到了上限就不再涨(self):
        """防"某个项目被误触刷到离谱数字"。到了上限不再涨，但**不报错、不牵连别的项目**。"""
        self.write_raw(json.dumps({"baogong": MAX_COUNT}))
        s = self.store()
        self.assertEqual(s.add("baogong"), MAX_COUNT)
        self.assertEqual(s.add("hulu"), 1, "别的项目不该受影响")

    def test_加0不改变计数(self):
        s = self.store()
        s.add("hulu", 5)
        self.assertEqual(s.add("hulu", 0), 5)

    def test_负数增量不倒退(self):
        s = self.store()
        s.add("hulu", 5)
        self.assertEqual(s.add("hulu", -3), 5)


class TestReset(_Base):

    def test_清零并删掉文件(self):
        s = self.store()
        s.add("hulu", 3)
        s.reset()
        self.assertEqual(s.all_counts(), {})
        self.assertFalse(os.path.exists(self.path))
        self.assertEqual(self.store().all_counts(), {}, "重开也不该把旧的读回来")

    def test_没有文件时清零不抛(self):
        self.store().reset()


if __name__ == "__main__":
    unittest.main(verbosity=2)
