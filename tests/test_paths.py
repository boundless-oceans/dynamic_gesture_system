"""运行期路径：开发时指向仓库根、打包后指向 exe 目录

这里守的是"**打包之后才会暴露**"的那条路径。`sys.frozen` 是 PyInstaller 注入的，
开发环境永远是 `False`，所以本机跑测试永远走不到打包那一支——只能靠打桩盖住。

要防的具体事故：所有路径都从 `__file__` 往上推算时，打包后 `__file__` 指向
**只读的 `_internal/`**，于是
  * `logs/` 与 `config_local.json` 写进 bundle（onefile 下退出即删，日志整个丢掉）
  * 内容文件（assets/ weights/ pages/）在 bundle 里找不到，因为它们铺在 exe 旁边
"""
import contextlib
import importlib
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import paths
from src import logger

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@contextlib.contextmanager
def _frozen_to(exe_path: str):
    """打桩成"打包后"：`sys.frozen = True`，`sys.executable` 指向那个 exe"""
    had_frozen = hasattr(sys, "frozen")
    saved_frozen = getattr(sys, "frozen", None)
    saved_exe = sys.executable
    sys.frozen = True
    sys.executable = exe_path
    try:
        yield
    finally:
        if had_frozen:
            sys.frozen = saved_frozen
        else:
            del sys.frozen
        sys.executable = saved_exe


@contextlib.contextmanager
def _patched_data_dir(value: str):
    saved = paths.data_dir
    paths.data_dir = lambda: value
    try:
        yield
    finally:
        paths.data_dir = saved


@contextlib.contextmanager
def _temp_dir():
    d = tempfile.mkdtemp(prefix="dsg-paths-")
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


class TestDevMode(unittest.TestCase):
    """开发时行为必须和以前**完全一样**——否则现有 150+ 个测试的路径假设会崩"""

    def test_开发时不是_frozen(self):
        self.assertFalse(paths.is_frozen())

    def test_程序目录就是仓库根(self):
        self.assertEqual(paths.app_dir(), REPO_ROOT)

    def test_数据目录等于程序目录(self):
        """单台展台 + zip 解压到 D 盘，程序目录一定可写，不做 %LOCALAPPDATA% 退化"""
        self.assertEqual(paths.data_dir(), paths.app_dir())

    def test_开发时内容文件都在(self):
        for rel in (("assets", "projects.json"), ("assets", "inheritors.json"),
                    ("assets", "gestures.json"),
                    ("pages", "map.html"), ("pages", "viewer.html")):
            self.assertTrue(os.path.exists(paths.resource_path(*rel)), rel)


class TestFrozenMode(unittest.TestCase):

    def test_打包后指向_exe_所在目录(self):
        with _temp_dir() as exe_dir:
            with _frozen_to(os.path.join(exe_dir, "非遗展示系统.exe")):
                self.assertTrue(paths.is_frozen())
                self.assertEqual(paths.app_dir(), exe_dir)
                self.assertEqual(paths.data_dir(), exe_dir)
                self.assertEqual(paths.resource_path("assets", "projects.json"),
                                 os.path.join(exe_dir, "assets", "projects.json"))

    def test_打包后不再指向代码所在目录(self):
        """这才是真正要防的事：曾经一切从 __file__ 往上推算，
        打包后 __file__ 指向只读的 _internal/"""
        code_dir = os.path.dirname(os.path.dirname(os.path.abspath(paths.__file__)))
        with _temp_dir() as exe_dir:
            with _frozen_to(os.path.join(exe_dir, "app.exe")):
                self.assertNotEqual(paths.app_dir(), code_dir)
                self.assertEqual(paths.app_dir(), exe_dir)


class TestCallSitesFollowPaths(unittest.TestCase):
    """防"改一半"：各处路径常量必须真的从 paths 来。

    逐个断言**取值**，而不是去源码里找有没有写对——后者是 lint，不是测试。
    """

    def test_config_的根目录与权重路径(self):
        from src import config
        self.assertEqual(config.ROOT_DIR, paths.app_dir())
        self.assertEqual(os.path.dirname(config.MODEL_WEIGHTS_PATH),
                         os.path.join(paths.app_dir(), "weights"))

    def test_config_的本地调参文件落在数据目录(self):
        from src import config
        self.assertEqual(os.path.dirname(config.LOCAL_CONFIG_PATH), paths.data_dir())

    def test_素材三个目录都在程序目录下(self):
        from src.core import project_assets as PA
        self.assertEqual(PA.ROOT, paths.app_dir())
        for d in (PA.IMAGES_DIR, PA.MODELS_DIR, PA.VIDEOS_DIR):
            self.assertTrue(d.startswith(paths.app_dir()), d)

    def test_日志目录走数据目录而不是代码目录(self):
        from src import logger
        self.assertEqual(logger.LOG_DIR, os.path.join(paths.data_dir(), "logs"))

    def test_项目数据真的从新路径读到了(self):
        """读不到的话 PROJECTS 会直接抛异常；但如果有人加个 try/except 静默兜底，
        这条能兜住"""
        from src.core.project_data import PROJECTS
        self.assertTrue(PROJECTS)
        self.assertTrue(all(p.get("name") for p in PROJECTS))


class TestConfigFollowsPathsWhenFrozen(unittest.TestCase):
    """config 的三个路径常量，打包后也要落在 exe 旁边。

    **为什么不能只靠上面那条常量断言**：开发环境下
    `os.path.dirname(os.path.dirname(config.__file__))` 和 `paths.app_dir()`
    **恰好结果相同**（都是仓库根），所以把 ROOT_DIR 改回从 `__file__` 推算，
    那道断言照样通过 —— 变异验证实测发现的。只有把环境桩成 frozen 才区分得出来。
    """

    def test_打包后权重与本地调参落在_exe_旁边(self):
        from src import config
        with _temp_dir() as exe_dir:
            try:
                with _frozen_to(os.path.join(exe_dir, "app.exe")):
                    reloaded = importlib.reload(config)
                    self.assertEqual(reloaded.ROOT_DIR, exe_dir)
                    self.assertEqual(os.path.dirname(reloaded.MODEL_WEIGHTS_PATH),
                                     os.path.join(exe_dir, "weights"))
                    self.assertEqual(os.path.dirname(reloaded.LOCAL_CONFIG_PATH),
                                     exe_dir)
            finally:
                importlib.reload(config)      # 用真实环境重载回去


class TestFrozenLoaderReadsFromExeDir(unittest.TestCase):
    """端到端：在"打包后"的桩下，**真的**从 exe 旁边的 `assets/` 读数据。

    上面那些常量断言只能覆盖模块级常量（`ROOT`、`LOG_DIR`）。而 `project_data`
    这类模块是**调用时才拼路径**的，没有常量可断言 —— 只能在冻结环境里重载它，
    看它读出来的是哪份文件。
    """

    def test_project_data_从_exe_旁边的_assets_读(self):
        with _temp_dir() as exe_dir:
            fake_assets = os.path.join(exe_dir, "assets")
            os.makedirs(fake_assets)
            with open(os.path.join(fake_assets, "projects.json"),
                      "w", encoding="utf-8") as f:
                json.dump({"items": [{"name": "桩项目"}]}, f, ensure_ascii=False)

            from src.core import project_data
            try:
                with _frozen_to(os.path.join(exe_dir, "app.exe")):
                    reloaded = importlib.reload(project_data)
                    self.assertEqual([p["name"] for p in reloaded.PROJECTS],
                                     ["桩项目"],
                                     "打包后没有读 exe 旁边那份，而是读了别处")
            finally:
                importlib.reload(project_data)     # 用真实路径重载回去，别污染其它用例


class TestLoggerFollowsDataDir(unittest.TestCase):
    """防回归：logger 曾经自己用 `__file__` 推算日志目录。

    打包后那是只读的 `_internal/`，日志会整个丢掉——而且丢掉这件事**不会报错**。

    LOG_DIR 是模块级常量，所以只能重载模块来看它在冻结环境下的取值。
    """

    def test_打包后日志落到_exe_旁边(self):
        with _temp_dir() as exe_dir:
            try:
                with _frozen_to(os.path.join(exe_dir, "app.exe")):
                    reloaded = importlib.reload(logger)
                    self.assertEqual(reloaded.LOG_DIR, os.path.join(exe_dir, "logs"))
                    self.assertTrue(reloaded.LOG_PATH.startswith(exe_dir))
            finally:
                importlib.reload(logger)     # 用真实环境重载，别污染其它用例


class TestWritableCheck(unittest.TestCase):

    def test_可写时返回_None(self):
        self.assertIsNone(paths.check_writable())

    def test_探测过的不留残留文件(self):
        paths.check_writable()
        self.assertFalse(os.path.exists(os.path.join(paths.data_dir(), ".write_probe")))

    def test_不可写时给出说明而不是静默失败(self):
        """拿一个"已存在的普通文件"当目录用，makedirs 必然失败。

        这条要紧：写不进去的后果是日志一条没有、现场调参存不下来，**都不报错**。
        而且那种情况下日志本身也建不出来，弹窗是唯一的告知途径。
        """
        with _temp_dir() as tmp:
            blocker = os.path.join(tmp, "这是文件不是目录")
            with open(blocker, "w", encoding="utf-8") as f:
                f.write("x")
            with _patched_data_dir(blocker):
                msg = paths.check_writable()
            self.assertIsNotNone(msg, "不可写却返回了 None —— 那就是静默失效")
            self.assertIn(blocker, msg)


class TestNoPathComputedFromFile(unittest.TestCase):
    """不变量：`src/` 下除 `paths.py` 之外，**不许**再从 `__file__` 推算路径。

    打包后 `__file__` 指向只读的 `_internal/`，从它算出来的路径全是错的。

    这是结构性守卫，比"逐个断言取值"更根本 —— `map_page` / `viewer_page` 这些是在
    `__init__` 里才拼路径的，没有模块级常量可以断言，只能从源头禁掉这种写法。
    """

    def test_没有模块自己从_file_推算路径(self):
        offenders = []
        src_root = os.path.join(REPO_ROOT, "src")
        for dirpath, dirs, files in os.walk(src_root):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if not name.endswith(".py") or name == "paths.py":
                    continue
                full = os.path.join(dirpath, name)
                with open(full, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        if "__file__" in line and "os.path" in line:
                            offenders.append(f"{os.path.relpath(full, REPO_ROOT)}:{lineno}")
        self.assertEqual(
            offenders, [],
            "这些地方仍从 __file__ 推算路径，打包后会指向只读的 _internal/：\n  "
            + "\n  ".join(offenders) + "\n\n请改走 src/paths.py")


if __name__ == "__main__":
    unittest.main()
