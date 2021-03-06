from enum import Enum, EnumMeta
from typing import Iterable
import requests


class FileMatchChoice(str, Enum):
    strict = 'strict'
    glob = 'glob'


class MethodChoice(str, Enum):
    get = 'get'
    post = 'post'
    put = 'put'
    delete = 'delete'
    options = 'options'


from .collector.map import collector_mapping
from .handler.map import handler_mapping
from .parser.map import parser_mapping
from .rewriter.map import rewriter_mapping


def get_enum_meta(keys: Iterable):
    class _EnumMeta(EnumMeta):
        def __new__(metacls, cls, bases, classdict, **kwds):
            for key in keys:
                classdict[key] = key
            cls = super().__new__(metacls, cls, bases, classdict, **kwds)
            return cls
    return _EnumMeta


class CollectorChoice(str, Enum, metaclass=get_enum_meta(collector_mapping)):
    pass


class ParserChoice(str, Enum, metaclass=get_enum_meta(parser_mapping)):
    pass


class RewriterChoice(str, Enum, metaclass=get_enum_meta(rewriter_mapping)):
    pass


class HandlerChoice(str, Enum, metaclass=get_enum_meta(handler_mapping)):
    pass
