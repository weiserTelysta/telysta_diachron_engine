from dataclasses import dataclass,field
from typing import List

@dataclass
class GlobalSettings:
    '''
    这里是全局运行时的参数，决定引擎的功能的。
    '''

    seed:int = 0
    is_LLM:bool = False

globalsettings = GlobalSettings();