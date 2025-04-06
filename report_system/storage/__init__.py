"""
Pacote para gerenciamento de armazenamento (Google Drive, Docs).
"""

from .google_drive import GoogleDriveManager
from .google_docs import GoogleDocsManager

__all__ = ['GoogleDriveManager', 'GoogleDocsManager']
