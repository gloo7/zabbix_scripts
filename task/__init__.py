import atexit
import os
import signal
import sys
from typing import Callable, List, NoReturn, Optional, Union

from logger import logger
from settings import COMMAND_DIR

from .collector.collector import init_collector
from .config import Config
from .const import D
from .handler.handler import init_handlers
from .parser.parser import init_parser
from .rewriter.rewriter import init_rewrites


class Task:
    collector: Callable[[], D]
    parser: Callable[[D], Union[D, List[D]]]
    rewrites: Optional[List[Callable[[D], D]]] = None
    handlers: List[Callable[[D], NoReturn]]

    @classmethod
    def daemonize(cls, pidfile: str, stdin: str = '/dev/null', stdout: str = '/dev/null', stderr: str = '/dev/null') -> None:
        if os.path.exists(pidfile):
            logger.error('Already running')
            sys.exit(1)

        # First fork (detaches from parent)
        try:
            if os.fork() > 0:
                sys.exit(1)
        except OSError as e:
            logger.error('fork #1 failed.')
            sys.exit(1)

        os.chdir('/')
        os.umask(0)
        os.setsid()
        # Second fork (relinquish session leadership)
        try:
            if os.fork() > 0:
                raise SystemExit(0)
        except OSError as e:
            logger.error('fork #2 failed.')
            sys.exit(1)

        sys.stdout.flush()
        sys.stderr.flush()

        with open(stdin, 'rb', 0) as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open(stdout, 'ab', 0) as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
        with open(stderr, 'ab', 0) as f:
            os.dup2(f.fileno(), sys.stderr.fileno())

        # Write the PID file
        with open(pidfile, 'w') as f:
            print(os.getpid(), file=f)

        # Arrange to have the PID file removed on exit/signal
        atexit.register(lambda: os.remove(pidfile))

        # Signal handler for termination (required)
        def sigterm_handler(signo, frame):
            sys.exit(1)

        signal.signal(signal.SIGTERM, sigterm_handler)

    @classmethod
    def start(cls, command: str) -> None:
        commands = os.listdir(COMMAND_DIR)
        command_file = f'{command}.json'
        if command_file not in commands:
            logger.error(
                f'Failed to start {command}: Unit {command} not found.')
            sys.exit(1)

        pidfile = f'/tmp/{command}'
        # cls.daemonize(pidfile)

        path = os.path.join(COMMAND_DIR, command_file)
        # try:
        _config = Config.parse_file(path)
        # except Exception as e:
            # logger.error(e)
            # sys.exit(1)

        cls.collector = init_collector(_config.collector)
        cls.parser = init_parser(_config.parser)
        if _config.rewrites is not None:
            cls.rewrites = init_rewrites(_config.rewrites)
        cls.handlers = init_handlers(_config.handlers)

        cls.run()

    @classmethod
    def run(cls):
        data = cls.collector()
        data = cls.parser(data)

        def _run(d: D) -> None:
            if cls.rewrites is not None:
                for rewrite in cls.rewrites:
                    d = rewrite(d)
            for handler in cls.handlers:
                handler(d)

        if isinstance(data, list):
            for item in data:
                _run(item)
        else:
            _run(data)

    @classmethod
    def stop(cls, command: str) -> None:
        pidfile = f'/tmp/{command}'
        if not os.path.exists(pidfile):
            logger.error(
                f'Failed to stop {command}: Unit {command} not loaded.')
            sys.exit(1)

        with open(pidfile, 'r') as f:
            pid = f.read()

        os.kill(pid)
        os.remove(pidfile)

    @classmethod
    def restart(cls, command: str) -> None:
        try:
            cls.stop(command)
        except SystemError as e:
            pass
        cls.start(command)

    @classmethod
    def get_action(cls, option: str) -> Callable[[str], None]:
        return {
            'start': cls.start,
            'stop': cls.stop,
            'restart': cls.restart
        }[option]