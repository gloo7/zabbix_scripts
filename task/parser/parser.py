from task.config import ParserConfig
from task._typing import Process
from .map import parser_mapping


def init_parser(config: ParserConfig) -> Process:
    return parser_mapping.get(config.mode.value)(config)(**config.dict())
