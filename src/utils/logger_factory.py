import logging
import sys
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Generator

from rich.console import Console
from rich.logging import RichHandler
from rich.status import Status

from src.config.settings import settings

# 使用同一个 Console，保证 status 与 logging 不冲突
SHARED_CONSOLE = Console()


class StreamingHandler(logging.Handler):
    """
    自定义Handler，用于处理流式输出（如大模型的流式返回）
    支持实时打印内容，不自动换行
    """

    def __init__(self, console: Optional[Console] = None):
        super().__init__()
        self.console = console or SHARED_CONSOLE
        self._current_stream = []
        self.style = "bold blue"

    def emit(self, record: logging.LogRecord) -> None:
        """处理普通的 logger.info"""
        try:
            msg = self.format(record)
            self.console.print(msg, style=self.style)
        except Exception:
            self.handleError(record)

    def stream_chunk(self, chunk: str) -> None:
        """流式打印文本块，不换行"""
        self.console.print(chunk, style=self.style, end="", highlight=False)
        self._current_stream.append(chunk)

    def end_stream(self) -> str:
        """结束流式输出，返回完整内容并换行"""
        self.console.print()
        full_content = "".join(self._current_stream)
        self._current_stream.clear()
        return full_content


class LoggerFactory:
    """
    日志工厂类，提供基于RICH的彩色日志输出
    支持普通日志和流式日志两种模式
    """

    _loggers: dict[str, logging.Logger] = {}
    _streaming_handlers: dict[str, StreamingHandler] = {}

    @staticmethod
    def get_logger(
        name: str,
        use_rich: bool = True,
        show_time: bool = True,
        show_path: bool = False,
        enable_file_output: bool = True,
        log_file_name: Optional[str] = None,
    ) -> logging.Logger:
        """
        获取或创建一个 logger 实例

        Args:
            name: logger名称
            use_rich: 是否使用 RICH 进行彩色输出，默认为 True
            show_time: 是否显示时间，默认为 True
            show_path: 是否显示文件路径，默认为 False
            enable_file_output: 是否启用文件输出，默认为 True
            log_file_name: 日志文件名，默认为 None（自动生成）

        Returns:
            配置好的 logger 实例
        """
        logger_key = f"{name}_{use_rich}_{show_time}_{show_path}_{enable_file_output}"

        if logger_key not in LoggerFactory._loggers:
            logger = logging.getLogger(name)
            logger.setLevel(logging.getLevelName(settings.LOG_LEVEL))
            logger.propagate = False

            logger.handlers.clear()

            if use_rich:
                console_handler = RichHandler(
                    console=SHARED_CONSOLE,
                    show_time=show_time,
                    show_path=show_path,
                    rich_tracebacks=True,
                    tracebacks_show_locals=True,
                    markup=True,
                )
            else:
                console_handler = logging.StreamHandler(sys.stderr)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)

            logger.addHandler(console_handler)

            if enable_file_output:
                file_handler = LoggerFactory._create_file_handler(log_file_name)
                logger.addHandler(file_handler)

            LoggerFactory._loggers[logger_key] = logger

        return LoggerFactory._loggers[logger_key]

    @staticmethod
    def _create_file_handler(
        log_file_name: Optional[str] = "paper_pilot.log",
    ) -> RotatingFileHandler:
        """
        创建文件输出 handler

        Args:
            log_file_name: 日志文件名，如果为 None 则使用默认值

        Returns:
            配置好的 RotatingFileHandler
        """
        if log_file_name is None:
            log_file_name = "paper_pilot.log"

        log_dir = Path(settings.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file_path = log_dir / log_file_name

        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.getLevelName(settings.LOG_LEVEL))

        file_formatter = logging.Formatter(
            "%(asctime)s - [%(name)s] - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_formatter)

        return file_handler

    @staticmethod
    def get_streaming_handler(name: str = "streaming") -> StreamingHandler:
        """
        获取或创建一个流式处理器，用于大模型流式输出

        Args:
            name: 处理器名称

        Returns:
            StreamingHandler实例
        """
        if name not in LoggerFactory._streaming_handlers:
            LoggerFactory._streaming_handlers[name] = StreamingHandler()

        return LoggerFactory._streaming_handlers[name]

    @staticmethod
    def get_streaming_logger(
        name: str,
        logging_level: Optional[int] = None,
        enable_file_output: bool = True,
        log_file_name: Optional[str] = None,
    ) -> tuple[logging.Logger, StreamingHandler]:
        """
        获取一个配置了流式处理器的logger

        Args:
            name: logger名称
            logging_level: 日志级别，默认使用 settings.LOG_LEVEL
            enable_file_output: 是否启用文件输出，默认为 True
            log_file_name: 日志文件名，默认为 None（自动生成）

        Returns:
            (logger实例, StreamingHandler实例)的元组
        """
        logger_key = f"{name}_streaming_{enable_file_output}"

        if logger_key not in LoggerFactory._loggers:
            logger = logging.getLogger(name)
            effective_level = (
                logging_level
                if logging_level is not None
                else logging.getLevelName(settings.LOG_LEVEL)
            )
            logger.setLevel(effective_level)
            logger.propagate = False

            logger.handlers.clear()

            streaming_handler = LoggerFactory.get_streaming_handler(name)
            logger.addHandler(streaming_handler)

            if enable_file_output:
                file_handler = LoggerFactory._create_file_handler(log_file_name)
                logger.addHandler(file_handler)

            LoggerFactory._loggers[logger_key] = logger

        logger = LoggerFactory._loggers[logger_key]
        streaming_handler = LoggerFactory.get_streaming_handler(name)

        return logger, streaming_handler

    @staticmethod
    @contextmanager
    def status_task(
        status_msg: str,
        logger: Optional[logging.Logger] = None,
        level: int = logging.INFO,
    ) -> Generator[Status, None, None]:
        """
        用于处理长时间运行任务的上下文管理器。
        UI 显示转圈，同时向文件写入日志。

        Args:
            status_msg: UI显示的文本
            logger: 如果提供，会记录开始和结束的日志
            level: 日志级别
        """
        if logger:
            logger.log(level, f"开始: {status_msg}")

        with SHARED_CONSOLE.status(
            f"[bold green]{status_msg}...", spinner="dots"
        ) as status:
            try:
                yield status
            finally:
                if logger:
                    logger.log(level, f"结束: {status_msg}")
