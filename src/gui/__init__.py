from typing import Optional

from core.judger import Judger


class GuiGlobVar:
    judger: Optional[Judger] = None


glob_var = GuiGlobVar()
