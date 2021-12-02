import functools
import json
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Union, List, TypeVar, ParamSpec

from .logger import get_logger
from .utils import int2bytes

log = get_logger()


@dataclass
class RoundConfig:
    state: int
    time: int
    length: int


@dataclass
class RoundInfo:
    state: int
    listen: List[int]
    player: List[int]
    content: List[str]


class AiErrorType(Enum):
    RunError = (0, "runError")
    TimeOutError = (1, "timeOutError")
    OutputLimitError = (2, "outputLimitError")


EndInfo = List[int]

ValueAccessor = Union[Callable[[str], any], Callable[[str, bool], any]]

T = TypeVar('T')


def json_object_receiver(desc):
    def inner(func: Callable[[ValueAccessor], T]) -> Callable[[bytes], T]:
        @functools.wraps(func)
        def wrapper(data: bytes) -> T:
            json_obj = json.loads(data.decode("utf-8"))

            def value(key: str, required: bool = True) -> any:
                v = json_obj.get(key)
                if required and v is None:
                    log.error("Missing [%s] in %s", key, desc)
                    raise ValueError
                return v

            return func(value)

        return wrapper

    return inner


P = ParamSpec('P')


def json_object_sender(func: Callable[P, any]) -> Callable[P, bytes]:
    def wrapper(*args: P.args) -> bytes:
        obj = func(*args)
        json_str: str = json.dumps(obj)
        json_bytes: bytes = json_str.encode("utf-8")
        return int2bytes(len(json_bytes)) + json_bytes

    return wrapper


class Protocol:
    """
    Current Saiblo judger protocol implement
    to_xxx methods will append the package size information
    from_xxx methods should accept data without the size information
    In fact you can directly pass away the bytes across current designed classes
    """

    @staticmethod
    @json_object_receiver("logic data")
    def from_logic_data(value: ValueAccessor) -> Union[RoundConfig, RoundInfo, EndInfo]:
        if value("state") == -1:
            end_info: str = value("end_info")
            end_info_obj = json.loads(end_info)
            scores: EndInfo = []
            for i in range(10):
                score = end_info_obj.get(str(i))
                if score is None:
                    break
                scores.append(score)
            return scores
        elif value("time", False) is None:
            return RoundInfo(value("state"), value("listen"), value("player"), value("content"))
        else:
            return RoundConfig(value("state"), value("time"), value("length"))

    @staticmethod
    @json_object_sender
    def to_logic_init_info(player_list: List[int], config: object, replay_path: str) -> any:
        return {
            "player_list": player_list,
            "player_num": len(player_list),
            "config": config,
            "replay": replay_path
        }

    @staticmethod
    @json_object_sender
    def to_logic_ai_normal_message(ai_id: int, content: str, time: int):
        return {
            "player": ai_id,
            "content": content,
            "time": time
        }

    @staticmethod
    @json_object_sender
    def to_logic_ai_error(error_ai: int, state: int, error_type: AiErrorType):
        return {
            "player": -1,
            "content": json.dumps({
                "player": error_ai,
                "state": state,
                "error": error_type.value[0],
                "error_log": error_type.value[1]
            })
        }
