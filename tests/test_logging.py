"""日志落盘：print 重定向、幂等、无控制台不崩、未捕获异常留痕、体积有上限

这里钉的是"**打包之后才会暴露**"的失效模式：PyInstaller 的 `--windowed` 包不带
控制台，`sys.stdout` 是 `None`。那条路径在本机跑测试时永远走不到，不写用例就没人守。

同时守住"静默失效"：日志这东西坏了不会报错，只是**一条记录都没有**——
等真出事的时候才发现，就晚了。
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import logger

_AUTO = object()        # 表示"用默认的 StringIO"，与显式传 None（模拟无控制台）区分


class _LoggingTestCase(unittest.TestCase):
    """把日志导向临时目录，用例结束后把全局状态原样还回去。

    `setup_logging()` 改的是全局（`sys.stdout` / `sys.excepthook` / logger 的 handler），
    不还原会污染后面所有用例。
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="dsg-log-")
        self._saved = (sys.stdout, sys.stderr, sys.excepthook,
                       logger.LOG_DIR, logger.LOG_PATH,
                       logger.MAX_BYTES, logger.BACKUP_COUNT)
        logger.LOG_DIR = self.tmp
        logger.LOG_PATH = os.path.join(self.tmp, "app.log")
        logger.MAX_BYTES = 1024 * 1024
        logger.BACKUP_COUNT = 3
        self._reset()

    def tearDown(self):
        (sys.stdout, sys.stderr, sys.excepthook,
         logger.LOG_DIR, logger.LOG_PATH,
         logger.MAX_BYTES, logger.BACKUP_COUNT) = self._saved
        self._reset()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _reset(self):
        """清掉 handler 与 _installed 标志，让下一次 setup_logging() 真的会重装"""
        for h in list(logger.get_logger().handlers):
            logger.get_logger().removeHandler(h)
            try:
                h.close()
            except Exception:
                pass
        logger._installed = False       # 测试要模拟"从没装过"，只能碰这个私有标志

    def _install(self, stdout=_AUTO, stderr=_AUTO):
        """装上日志。原始终端流默认换成 StringIO，免得测试输出被刷屏。"""
        sys.stdout = io.StringIO() if stdout is _AUTO else stdout
        sys.stderr = io.StringIO() if stderr is _AUTO else stderr
        return logger.setup_logging()

    def _read(self, name="app.log"):
        for h in logger.get_logger().handlers:
            try:
                h.flush()
            except Exception:
                pass
        path = os.path.join(self.tmp, name)
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            return f.read()


class TestPrintRedirection(_LoggingTestCase):

    def test_print_落盘(self):
        self._install()
        print("[Camera] 测试消息")
        self.assertIn("测试消息", self._read())

    def test_同时仍然输出到原始终端(self):
        """本机开发时终端体验不能变差"""
        out = io.StringIO()
        self._install(stdout=out)
        print("[Camera] 两头都要有")
        self.assertIn("两头都要有", out.getvalue())
        self.assertIn("两头都要有", self._read())

    def test_没有控制台时不抛异常且照样落盘(self):
        """打包成 --windowed 后的真实情形

        未装日志时 `sys.stdout is None`，`print()` 会直接抛 AttributeError；
        装完之后 sys.stdout 是 tee，原始终端流为 None 只是"少写一份"。
        """
        self._install(stdout=None, stderr=None)
        self.assertIsNone(sys.stdout._original, "tee 没有正确记录'无控制台'")
        print("[Main] 无控制台也要留下")          # 这行不能抛
        self.assertIn("无控制台也要留下", self._read())

    def test_纯空行不进日志(self):
        self._install()
        print()
        print("  ")
        self.assertEqual(self._read().count("\n"), 1, "空行被记进日志了")

    def test_每条都带日期和时刻(self):
        """轮转能留十来天，只有时分秒的话跨天就分不清（翻日志时踩到过）"""
        self._install()
        print("[Main] 要带时间")
        line = [l for l in self._read().splitlines() if "要带时间" in l][0]
        self.assertRegex(line, r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_多参数_print_只记一条(self):
        """`print("a:", b)` 会分多次 write —— 不能拆成几条，更不能丢前缀。

        这是实际踩到的：只有时分秒的那版日志里出现过
            [19:17:25] INFO    is_frozen:
            [19:17:25] INFO    False
        """
        self._install()
        print("[Camera] 索引", 2)
        log = self._read()
        self.assertIn("[Camera] 索引 2", log, "被拆行或丢了前缀")
        self.assertEqual(log.count("索引"), 1, "一行被记成了多条")

    def test_不带换行的残句在_flush_时不丢(self):
        """`print(x, end="")` 的内容不能一直卡在缓冲里"""
        self._install()
        sys.stdout.write("没有换行的残句")
        sys.stdout.flush()
        self.assertIn("没有换行的残句", self._read())


class TestInstallIsIdempotent(_LoggingTestCase):

    def test_只有一个handler(self):
        self._install()
        self.assertEqual(len(logger.get_logger().handlers), 1)

    def test_重复调用不会套娃(self):
        self._install()
        first = sys.stdout
        logger.setup_logging()
        self.assertIs(sys.stdout, first, "重复调用把 stdout 又包了一层 tee")
        self.assertEqual(len(logger.get_logger().handlers), 1)

    def test_不往root冒泡(self):
        """Qt / torch 会给 root 挂 handler，冒泡会让同一条被输出两遍"""
        self._install()
        self.assertFalse(logger.get_logger().propagate)


class TestRotation(_LoggingTestCase):

    def test_超过上限会切分且总量有界(self):
        """原先的 FileHandler 是无上限的，24/7 跑下去能把磁盘写满"""
        logger.MAX_BYTES = 1024
        logger.BACKUP_COUNT = 2
        self._install()
        for _ in range(200):
            print("[Main] " + "x" * 120)

        names = sorted(f for f in os.listdir(self.tmp) if f.startswith("app.log"))
        self.assertIn("app.log.1", names, "没有发生轮转")
        self.assertLessEqual(len(names), logger.BACKUP_COUNT + 1, f"备份数量超了: {names}")

        total = sum(os.path.getsize(os.path.join(self.tmp, f)) for f in names)
        limit = logger.MAX_BYTES * (logger.BACKUP_COUNT + 1) + 2048
        self.assertLess(total, limit, f"日志总量失控: {total} 字节")


class TestUncaughtException(_LoggingTestCase):

    def _raise_and_handle(self, msg="模拟崩溃"):
        try:
            raise ValueError(msg)
        except ValueError:
            logger._handle_uncaught(*sys.exc_info())

    def test_未捕获异常留下记录(self):
        self._install()
        self._raise_and_handle()
        log = self._read()
        self.assertIn("未捕获异常", log)
        self.assertIn("模拟崩溃", log)

    def test_摘要只记一条_traceback不重复(self):
        """摘要由我们记，traceback 由原处理器写 stderr（已是 tee）——各一遍，不重复"""
        self._install()
        self._raise_and_handle()
        log = self._read()
        self.assertEqual(log.count("未捕获异常"), 1, "摘要被记了多遍")
        self.assertIn("Traceback", log, "traceback 没进日志")
        self.assertIn("ValueError", log)

    def test_KeyboardInterrupt不记为崩溃(self):
        """Ctrl+C 是正常退出，不该在日志里留下一条 CRITICAL"""
        self._install()
        try:
            raise KeyboardInterrupt()
        except KeyboardInterrupt:
            logger._handle_uncaught(*sys.exc_info())
        self.assertNotIn("未捕获异常", self._read())


class TestSingleSink(_LoggingTestCase):

    def test_结构化日志与print同落一处(self):
        self._install()
        logger.get_logger().warning("结构化警告")
        print("[Main] 普通输出")
        log = self._read()
        self.assertIn("结构化警告", log)
        self.assertIn("普通输出", log)

    def test_启动时就把日志文件建出来(self):
        """handler 是 delay=True，靠启动那条 info 把文件真正创建出来——
        否则"程序起来了但没有日志文件"这件事本身就无法与"程序没起来"区分"""
        self._install()
        self.assertTrue(os.path.exists(logger.LOG_PATH))


if __name__ == "__main__":
    unittest.main()
