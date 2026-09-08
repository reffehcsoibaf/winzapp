"""Mostra o caminho completo do arquivo de log ativo do WinZapp."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from app_paths import log_path  # noqa: E402

print(log_path("log.log"))
