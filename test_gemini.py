"""
Teste rápido de conexão com o Gemini.

Rode isso a partir da RAIZ do projeto (C:\\Users\\fabio\\WinZapp_Python),
com o ambiente virtual ativado:

    python test_gemini.py

Ele só confirma se a chave funciona (não usa nenhum arquivo de áudio/imagem
ainda) e, se você passar o caminho de um arquivo de áudio como argumento,
já testa a transcrição de verdade.

Exemplo com um áudio de teste:
    python test_gemini.py "C:\\caminho\\para\\audio.ogg"
"""

import os
import sys

from dotenv import load_dotenv

# Garante que conseguimos importar o módulo de dentro de client/core
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "client"))

from core.gemini_client import transcribe_audio, GeminiClientError  # noqa: E402

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY", "")

print("=" * 60)
if not api_key:
    print("ERRO: GEMINI_API_KEY não encontrada no .env")
    sys.exit(1)

print(f"Chave carregada do .env (começa com: {api_key[:10]}...)")
print("=" * 60)

if len(sys.argv) > 1:
    audio_path = sys.argv[1]
    print(f"\nTestando transcrição real do arquivo: {audio_path}\n")
    try:
        texto = transcribe_audio(audio_path, api_key)
        print("--- TRANSCRIÇÃO RECEBIDA ---")
        print(texto)
        print("--- FIM ---")
    except GeminiClientError as e:
        print(f"ERRO ao transcrever: {e}")
else:
    print(
        "\nNenhum arquivo de áudio informado. Para testar a transcrição de "
        "verdade, rode:\n"
        '    python test_gemini.py "C:\\caminho\\para\\um\\audio.ogg"\n'
    )
    print(
        "Por enquanto, isso só confirma que a chave foi carregada do .env "
        "corretamente."
    )
