"""来源 parser：各类源文件 -> 统一 ParsedDocument。

后续新增 DatabaseExportParser 时，在此登记即可。
"""

from .excel_parser import ExcelParser
from .mineru_parser import MineruParser
from .word_parser import WordParser

__all__ = ["ExcelParser", "MineruParser", "WordParser"]
