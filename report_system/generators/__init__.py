"""
Pacote para geradores de relatórios.
"""

from .report_generator import SimpleReportGenerator
from .html_report_generator import HTMLReportGenerator

__all__ = ['SimpleReportGenerator', 'HTMLReportGenerator']
