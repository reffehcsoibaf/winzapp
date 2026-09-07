"""
core/gemini_client.py

Integração com a API do Gemini (Google) para acessibilidade no WinZapp:
    - Transcrição de mensagens de áudio/voz
    - Descrição de imagens e vídeos
    - Conversão de PDFs em texto acessível, com descrição das imagens internas

Todas as funções recebem a chave de API como parâmetro (não leem variáveis de
ambiente diretamente), para que o chamador decida se a chave vem do arquivo
.env (uso de desenvolvimento/teste) ou das configurações salvas pelo usuário
dentro do próprio WinZapp (uso normal, inclusive por outras pessoas que
usarem esta versão modificada).

Requer a biblioteca oficial:
    pip install google-genai
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError


# Modelo padrão. "gemini-2.5-flash" é rápido e de baixo custo, adequado para
# transcrição/descrição em tempo real. Pode futuramente virar uma opção na
# aba de configurações, se quiser deixar o usuário escolher entre
# velocidade/custo (flash) e qualidade máxima (pro).
DEFAULT_MODEL = "gemini-2.5-flash"

# Tamanho a partir do qual preferimos subir o arquivo pela File API do Gemini
# em vez de enviar os bytes embutidos direto no pedido. Arquivos de áudio e
# vídeo do WhatsApp costumam passar disso facilmente.
_INLINE_SIZE_LIMIT_BYTES = 15 * 1024 * 1024  # 15 MB


class GeminiClientError(Exception):
    """
    Erro amigável para exibir na interface do WinZapp.

    A mensagem já vem em português e pronta para ser falada pelo leitor de
    tela ou exibida numa caixa de mensagem — sem stacktraces nem termos
    técnicos, para não confundir quem estiver ouvindo com o leitor de tela.
    """


def _build_client(api_key: str) -> genai.Client:
    if not api_key or not api_key.strip():
        raise GeminiClientError(
            "Nenhuma chave de API do Gemini foi configurada. "
            "Abra Configurações > IA e Acessibilidade e informe sua chave."
        )
    return genai.Client(api_key=api_key.strip())


def _upload_or_inline(client: genai.Client, file_path: str):
    """
    Decide entre enviar o arquivo embutido no pedido (mais rápido para
    arquivos pequenos) ou fazer upload prévio pela File API do Gemini (mais
    confiável para arquivos maiores, como vídeos e PDFs longos).
    """
    path = Path(file_path)
    if not path.exists():
        raise GeminiClientError(f"Arquivo não encontrado: {file_path}")

    mime_type, _ = mimetypes.guess_type(str(path))
    mime_type = mime_type or "application/octet-stream"
    size = path.stat().st_size

    if size <= _INLINE_SIZE_LIMIT_BYTES:
        data = path.read_bytes()
        return types.Part.from_bytes(data=data, mime_type=mime_type)

    uploaded = client.files.upload(file=str(path))
    return uploaded


def _generate_text(client: genai.Client, model: str, prompt: str, media_part) -> str:
    try:
        response = client.models.generate_content(
            model=model,
            contents=[media_part, prompt],
        )
    except ClientError as exc:
        # Erros comuns: chave inválida, cota excedida, arquivo rejeitado.
        raise GeminiClientError(
            "O Gemini recusou o pedido. Verifique se a chave de API está "
            f"correta e se ainda há cota disponível. Detalhe técnico: {exc}"
        ) from exc
    except APIError as exc:
        raise GeminiClientError(
            f"O serviço do Gemini teve um problema temporário. Tente novamente em instantes. Detalhe técnico: {exc}"
        ) from exc

    text = (response.text or "").strip()
    if not text:
        raise GeminiClientError(
            "O Gemini não retornou nenhum conteúdo para este arquivo."
        )
    return text


def transcribe_audio(
    file_path: str,
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
    language_hint: Optional[str] = "português do Brasil",
) -> str:
    """
    Transcreve uma mensagem de áudio/voz para texto.

    Retorna apenas o texto transcrito, pronto para ser mostrado na janela
    navegável de resultado.
    """
    client = _build_client(api_key)
    media_part = _upload_or_inline(client, file_path)

    prompt = (
        "Transcreva integralmente o áudio a seguir para texto corrido, em "
        f"{language_hint}. Não resuma e não corte nada. Use pontuação "
        "adequada para facilitar a leitura por um leitor de tela. Se houver "
        "trechos inaudíveis, indique com '[inaudível]'. Responda apenas com "
        "a transcrição, sem comentários adicionais."
    )
    return _generate_text(client, model, prompt, media_part)


def describe_visual_media(
    file_path: str,
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
    is_video: bool = False,
) -> str:
    """
    Descreve o conteúdo de uma imagem ou vídeo para uma pessoa cega ou com
    baixa visão.
    """
    client = _build_client(api_key)
    media_part = _upload_or_inline(client, file_path)

    tipo = "vídeo" if is_video else "imagem"
    prompt = (
        f"Descreva este {tipo} para uma pessoa cega, em português do Brasil. "
        "Descreva de forma clara e objetiva o que aparece: pessoas, objetos, "
        "ambiente, cores relevantes, texto visível na imagem, e, se for "
        "vídeo, a sequência de ações e qualquer fala ou som importante. "
        "Evite frases como 'a imagem mostra' — descreva diretamente o "
        "conteúdo. Responda apenas com a descrição, sem comentários "
        "adicionais."
    )
    return _generate_text(client, model, prompt, media_part)


def pdf_to_accessible_text(
    file_path: str,
    api_key: str,
    *,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Converte o conteúdo de um PDF em texto acessível, descrevendo também as
    imagens encontradas dentro do documento, no ponto em que elas aparecem.
    """
    client = _build_client(api_key)
    media_part = _upload_or_inline(client, file_path)

    prompt = (
        "Extraia todo o texto deste PDF, em português do Brasil, mantendo a "
        "ordem de leitura natural do documento (título, parágrafos, "
        "listas, tabelas). Sempre que houver uma imagem, gráfico ou "
        "diagrama no documento, insira no lugar correspondente uma "
        "descrição entre colchetes, no formato: "
        "'[Imagem: descrição do que aparece]'. Não pule nenhuma página. "
        "Responda apenas com o texto acessível resultante, sem comentários "
        "adicionais."
    )
    return _generate_text(client, model, prompt, media_part)
