"""现场调参（config_local.json）的载入、夹紧与还原

展台上这个文件是"能被改坏的东西"：被观众或误操作写成越界值/错类型时，
不能让参数顶到离谱值而让展台失控，也不能让程序起不来。
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config


class TestTunableSpec(unittest.TestCase):

    def test_每个可调项都指向真实存在的配置项(self):
        for spec in config.TUNABLE:
            self.assertTrue(hasattr(config, spec["key"]),
                            f"{spec['key']} 在 config 里不存在")

    def test_每项都有区间和说明(self):
        for spec in config.TUNABLE:
            for field in ("label", "min", "max", "decimals", "hint"):
                self.assertIn(field, spec, f"{spec['key']} 缺字段 {field}")
            self.assertLess(spec["min"], spec["max"], f"{spec['key']} 区间不合法")
            v = getattr(config, spec["key"])
            self.assertTrue(spec["min"] <= v <= spec["max"],
                            f"{spec['key']} 当前默认值 {v} 落在区间外")

    def test_键不重复(self):
        keys = [s["key"] for s in config.TUNABLE]
        self.assertEqual(len(keys), len(set(keys)), "可调项有重复")

    def test_平滑帧数不在可调列表(self):
        """SMOOTH_FRAMES 决定 deque 容量，构造时固定，改了不生效 → 不应暴露出来"""
        self.assertNotIn("SMOOTH_FRAMES", [s["key"] for s in config.TUNABLE])


class TestLocalOverride(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dgs_cfg_")
        self.path = os.path.join(self.tmp, "config_local.json")
        self._saved_path = config.LOCAL_CONFIG_PATH
        self._saved_vals = {k: getattr(config, k) for k in config.DEFAULTS}
        config.LOCAL_CONFIG_PATH = self.path

    def tearDown(self):
        config.LOCAL_CONFIG_PATH = self._saved_path
        for k, v in self._saved_vals.items():
            setattr(config, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, data):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def _restore_defaults(self):
        for k, v in config.DEFAULTS.items():
            setattr(config, k, v)

    def test_文件不存在时用代码默认值(self):
        self._restore_defaults()
        config._apply_local_overrides()
        for k, v in config.DEFAULTS.items():
            self.assertEqual(getattr(config, k), v)

    def test_保存后能重新载入(self):
        config.CONFIDENCE_THRESHOLD = 0.75
        config.ACTION_COOLDOWN_MS = 1500
        config.save_local_overrides()
        self.assertTrue(os.path.exists(self.path))

        self._restore_defaults()
        config._apply_local_overrides()
        self.assertEqual(config.CONFIDENCE_THRESHOLD, 0.75)
        self.assertEqual(config.ACTION_COOLDOWN_MS, 1500)

    def test_越界值被夹到区间内(self):
        self._write({"CONFIDENCE_THRESHOLD": 9.9, "CONSISTENCY_COUNT": -5})
        config._apply_local_overrides()
        spec = {s["key"]: s for s in config.TUNABLE}
        self.assertEqual(config.CONFIDENCE_THRESHOLD, spec["CONFIDENCE_THRESHOLD"]["max"])
        self.assertEqual(config.CONSISTENCY_COUNT, spec["CONSISTENCY_COUNT"]["min"])

    def test_类型不符被忽略(self):
        self._restore_defaults()
        self._write({"DISPLAY_CONFIDENCE": "垃圾", "MAX_LOCK_MS": None})
        config._apply_local_overrides()
        self.assertEqual(config.DISPLAY_CONFIDENCE, config.DEFAULTS["DISPLAY_CONFIDENCE"])
        self.assertEqual(config.MAX_LOCK_MS, config.DEFAULTS["MAX_LOCK_MS"])

    def test_文件损坏不影响启动(self):
        self._restore_defaults()
        with open(self.path, "w", encoding="utf-8") as f:
            f.write("{ 这不是合法 JSON ")
        config._apply_local_overrides()          # 不应抛异常
        for k, v in config.DEFAULTS.items():
            self.assertEqual(getattr(config, k), v)

    def test_只写部分键时其余保持默认(self):
        self._restore_defaults()
        self._write({"CONSISTENCY_COUNT": 4})
        config._apply_local_overrides()
        self.assertEqual(config.CONSISTENCY_COUNT, 4)
        self.assertEqual(config.CONFIDENCE_THRESHOLD, config.DEFAULTS["CONFIDENCE_THRESHOLD"])

    def test_整数项载入后仍是整数(self):
        """滑条按 int 比较，浮点数会让 max/min 判断出现意外"""
        self._write({"CONSISTENCY_COUNT": 3.7, "ACTION_COOLDOWN_MS": 1200.0})
        config._apply_local_overrides()
        self.assertIsInstance(config.CONSISTENCY_COUNT, int)
        self.assertIsInstance(config.ACTION_COOLDOWN_MS, int)

    def test_恢复默认会删除本地文件(self):
        config.CONSISTENCY_COUNT = 5
        config.save_local_overrides()
        self.assertTrue(os.path.exists(self.path))
        config.reset_to_defaults()
        self.assertFalse(os.path.exists(self.path), "恢复默认应删掉本地调参文件")
        self.assertEqual(config.CONSISTENCY_COUNT, config.DEFAULTS["CONSISTENCY_COUNT"])

    def test_恢复默认在文件不存在时也不报错(self):
        config.reset_to_defaults()               # 不应抛 FileNotFoundError
        self.assertEqual(config.CONSISTENCY_COUNT, config.DEFAULTS["CONSISTENCY_COUNT"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
