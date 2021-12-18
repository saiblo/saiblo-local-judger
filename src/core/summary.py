import dataclasses
import time
from enum import Enum, auto
from typing import List


class JudgeEventType(Enum):
    JUDGE_START = auto()
    AI_CONNECTED = auto()
    LOGIC_BOOTED = auto()
    NEW_ROUND = auto()
    AI_RE = auto()
    AI_TLE = auto()
    AI_OLE = auto()
    LOGIC_CRASHED = auto()
    GAME_OVER = auto()
    INTERNAL_ERROR = auto()


@dataclasses.dataclass
class JudgeEvent:
    type: JudgeEventType
    time: float
    round: int
    ai_id: int  # For AI_xxx
    elapsed_time: float  # For new round
    comment: str


class JudgeState(Enum):
    GAME_OVER = auto()
    LOGIC_CRASHED = auto()
    INTERNAL_ERROR = auto()


@dataclasses.dataclass
class JudgeSummary:
    start_time: float
    total_time: float
    final_state: JudgeState
    final_score: List[int]
    total_round: int
    event_list: List[JudgeEvent] = dataclasses.field(repr=False)

    def __init__(self):
        self.start_time = time.time()
        self.total_time = 0
        self.final_state = JudgeState.INTERNAL_ERROR
        self.final_score = []
        self.event_list = [JudgeEvent(JudgeEventType.JUDGE_START, self.start_time, -1, -1, 0, "")]

    def appendAiConnected(self, ai_id: int):
        self.event_list.append(
            JudgeEvent(JudgeEventType.AI_CONNECTED, time.time(), -1, ai_id, 0, "")
        )

    def appendLogicBooted(self):
        self.event_list.append(
            JudgeEvent(JudgeEventType.LOGIC_BOOTED, time.time(), -1, -1, 0, "")
        )

    def appendNewRound(self, round: int, last_elapsed_time: float):
        self.event_list.append(
            JudgeEvent(JudgeEventType.NEW_ROUND, time.time(), round, -1, last_elapsed_time, "")
        )

    def appendAiRe(self, round: int, ai_id: int):
        self.event_list.append(
            JudgeEvent(JudgeEventType.AI_RE, time.time(), round, ai_id, 0, "")
        )

    def appendAiTle(self, round: int, ai_id: int):
        self.event_list.append(
            JudgeEvent(JudgeEventType.AI_TLE, time.time(), round, ai_id, 0, "")
        )

    def appendAiOle(self, round: int, ai_id: int):
        self.event_list.append(
            JudgeEvent(JudgeEventType.AI_OLE, time.time(), round, ai_id, 0, "")
        )

    def __judge_end(self, state: JudgeState):
        self.total_time = time.time() - self.start_time
        for entry in reversed(self.event_list):
            if entry.round != -1:
                self.total_round = entry.round
                break
        self.final_state = state

    def appendLogicCrashed(self):
        self.event_list.append(
            JudgeEvent(JudgeEventType.LOGIC_CRASHED, time.time(), -1, -1, 0, "")
        )
        self.__judge_end(JudgeState.LOGIC_CRASHED)

    def appendGameOver(self, score: List[int]):
        self.event_list.append(
            JudgeEvent(JudgeEventType.GAME_OVER, time.time(), -1, -1, 0, "")
        )
        self.final_score = score.copy()
        self.__judge_end(JudgeState.GAME_OVER)

    def appendInternalError(self):
        self.event_list.append(
            JudgeEvent(JudgeEventType.INTERNAL_ERROR, time.time(), -1, -1, 0, "")
        )
        self.__judge_end(JudgeState.INTERNAL_ERROR)
