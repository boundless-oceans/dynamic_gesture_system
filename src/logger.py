"""日志系统

**为什么需要这个模块**

整个项目的诊断输出都走 `print()`（33 处，都带 `[Camera]` 这类标签、都带 `flush=True`），
而 `main.py` 不重定向 stdout。本机开发时这没问题，但打成 PyInstaller 的 `--windowed`
包之后就全没了：

  * windowed 模式不挂控制台，`sys.stdout` 是 `None` —— 这时 `print()` 不是
    "输出没人看"，而是**直接抛 AttributeError**
  * 就算不抛，输出也无处可去

结果是：展台在文化馆出问题时，**手上一条记录都没有**。

**做法**

不改那 33 个调用点，只在 `main.py` 开头调一次 `setup_logging()`，把 stdout/stderr
接到一个 tee 上：

    本机开发：终端照常显示，同一条也落盘
    打包之后：控制台不存在就只落盘，不报错

这样避免了去动 6 个文件、33 个调用点——那些 print 本来就带标签、本来就 flush，
语义上**已经就是日志**，缺的只是时间戳。

再加上 `sys.excepthook`：未捕获异常也留一条记录。不然程序崩了事后什么都不剩，
"崩溃自拉起"也就无从查起。
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_PATH = os.path.join(LOG_DIR, "app.log")

# 单个文件 1MB、留 3 份备份，总量封顶约 4MB。
# 必须设上限：展台 24/7 跑下去，原先那个 FileHandler 是**无上限增长**的。
MAX_BYTES = 1 * 1024 * 1024
BACKUP_COUNT = 3

_FORMAT = "[%(asctime)s] %(levelname)-7s %(message)s"
_formatter = logging.Formatter(_FORMAT, datefmt="%H:%M:%S")

_logger = logging.getLogger("gesture")
_logger.setLevel(logging.DEBUG)
# 不往 root logger 冒泡：否则第三方库（Qt / torch）挂的 root handler 会把同一条再输出一遍
_logger.propagate = False

_sys_excepthook = sys.excepthook
_installed = False


class _Tee:
    """把 write() 同时送到日志文件和原始终端流。

    两个 print 兼容点，都是为了"打包后也能正常跑"：

      * **原流可能是 None** —— windowed 包没有控制台，`sys.stdout` 就是 None。
        这时只写文件，绝不能让 print 抛异常。
      * **防重入** —— 日志本身出错时 `logging` 会往 stderr 写错误信息，而 stderr
        又指向本对象，会无限递归。用标志位挡掉。
    """

    def __init__(self, original, level: int):
        self._original = original
        self._level = level
        self._busy = False

    def write(self, text: str) -> int:
        if self._busy:
            return len(text)
        self._busy = True
        try:
            # rstrip：print 自带换行，日志里每条自己成行；纯空行不记
            msg = text.rstrip()
            if msg:
                _logger.log(self._level, msg)
            if self._original is not None:
                self._original.write(text)
                if text.endswith("\n"):
                    self._original.flush()
        except Exception:
            pass        # 写日志失败绝不能反过来把程序搞崩
        finally:
            self._busy = False
        return len(text)

    def writelines(self, lines) -> None:
        for line in lines:
            self.write(line)

    def flush(self) -> None:
        if self._original is not None:
            try:
                self._original.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        return bool(self._original is not None and self._original.isatty())

    def fileno(self):
        # 有些库拿它判断能不能上色/分页。没有终端时如实报错，别返回假 fd
        if self._original is None:
            raise OSError("no console")
        return self._original.fileno()

    @property
    def encoding(self) -> str:
        return getattr(self._original, "encoding", None) or "utf-8"


def _handle_uncaught(exc_type, exc_value, exc_tb):
    """未捕获异常：先在日志里落一条醒目的，再把原处理器放行。

    只记一行摘要、不自己打 traceback —— 原处理器会往 stderr 写完整 traceback，
    而 stderr 已经是 tee 了，那些行同样会进日志。自己再打一遍就是重复。
    """
    if issubclass(exc_type, KeyboardInterrupt):
        _sys_excepthook(exc_type, exc_value, exc_tb)
        return
    try:
        _logger.critical("未捕获异常，程序即将退出: %s: %s",
                         exc_type.__name__, exc_value)
    except Exception:
        pass
    _sys_excepthook(exc_type, exc_value, exc_tb)


def setup_logging() -> str:
    """安装日志文件 + stdout/stderr 重定向 + 未捕获异常钩子。返回日志文件路径。

    幂等：重复调用只生效一次。

    **只在 `main.py` 里调用**——测试与 tools 脚本不调，保持它们的输出干净
    （测试要断言输出时，被重定向会很麻烦）。
    """
    global _installed
    if _installed:
        return LOG_PATH

    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        handler = RotatingFileHandler(
            LOG_PATH, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT,
            encoding="utf-8", delay=True)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(_formatter)
        _logger.addHandler(handler)
    except Exception as e:
        # 日志建不起来也必须让程序跑起来（只读目录、磁盘满、权限……）。
        # 这里要护一手：此刻 sys.stdout 还是**原始**的，windowed 包下它就是 None，
        # 直接 print 会反过来把启动搞崩
        try:
            print("[Log] 无法创建日志文件 %s: %s" % (LOG_PATH, e), flush=True)
        except Exception:
            pass

    # stderr 被接进了 logging，而 logging 出错时又要往 stderr 写 —— 关掉 raiseExceptions
    # 才是稳的（tee 自己还有一道重入保护，这里是第二道）
    logging.raiseExceptions = False

    sys.stdout = _Tee(sys.stdout, logging.INFO)
    sys.stderr = _Tee(sys.stderr, logging.ERROR)
    sys.excepthook = _handle_uncaught

    _installed = True
    # 这一条同时把日志文件真正创建出来（handler 是 delay=True）
    _logger.info("---- 日志启动，写入 %s ----", LOG_PATH)
    return LOG_PATH


def get_logger():
    """需要级别 / exc_info 等结构化能力时用它。

    它和 `print()` 走的是**同一个 handler**，所以不会出现两个句柄写同一个文件。
    """
    return _logger
