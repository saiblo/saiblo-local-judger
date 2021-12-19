from typing import Optional

from core.judger import Judger
from core.summary import JudgeSummary


class GuiGlobVar:
    judger_config = None
    judger: Optional[Judger] = None
    summary: Optional[JudgeSummary] = None


glob_var = GuiGlobVar()
