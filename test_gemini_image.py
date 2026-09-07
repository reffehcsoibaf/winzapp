"""
Teste rápido de descrição de imagem com o Gemini.

Rode a partir da RAIZ do projeto, com o venv ativado:

    python test_gemini_image.py "C:\\caminho\\para\\imagem.png"
"""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from core.gemini_client import describe_visual_media, GeminiClientError  # noqa: E402

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")

if not api_key:
    print("ERRO: GEMINI_API_KEY não encontrada no .env")
    sys.exit(1)

if len(sys.argv) < 2:
    print('Uso: python test_gemini_image.py "C:\\caminho\\para\\imagem.png"')
    sys.exit(1)

image_path = sys.argv[1]
print(f"Descrevendo imagem: {image_path}\n")

try:
    descricao = describe_visual_media(image_path, api_key, is_video=False)
    print("--- DESCRIÇÃO RECEBIDA ---")
    print(descricao)
    print("--- FIM ---")
except GeminiClientError as e:
    print(f"ERRO ao descrever imagem: {e}")
