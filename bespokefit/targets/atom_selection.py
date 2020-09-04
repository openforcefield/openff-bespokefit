"""
Methods related to selecting ff terms to fit
"""

from enum import Enum


class TorsionSelection(str, Enum):

    All = "all"
    NonTerminal = "non-terminal"
    TerminalOnly = "terminal-only"
