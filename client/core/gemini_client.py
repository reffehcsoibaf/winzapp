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
import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import APIError, ClientError


# Python's mimetypes module doesn't know several audio extensions commonly
# seen in WhatsApp voice/media messages (WPPConnect/WhatsApp itself uses
# .ogg/.opus for voice notes, which Python DOES recognise correctly — this
# covers formats that show up in forwarded/shared audio instead). Without
# this, a file like a forwarded .m4a gets guessed as
# "application/octet-stream", which the Gemini API rejects outright with
# "Unsupported MIME type" instead of processing it as audio.
_EXTRA_MIME_TYPES = {
    ".m4a": "audio/mp4",
    ".3gp": "audio/3gpp",
    ".3gpp": "audio/3gpp",
    ".amr": "audio/amr",
    ".aac": "audio/aac",
    ".opus": "audio/ogg",
}
for _ext, _mime in _EXTRA_MIME_TYPES.items():
    mimetypes.add_type(_mime, _ext)


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
    return _wait_until_active(client, uploaded)


def _wait_until_active(client: genai.Client, uploaded_file, timeout_seconds: int = 90):
    """
    Files enviados pela File API do Gemini começam no estado PROCESSING —
    especialmente vídeos, que o Gemini precisa processar antes de ficarem
    utilizáveis — e só podem ser referenciados numa chamada depois de
    chegarem a ACTIVE. Sem essa espera, uma chamada feita cedo demais falha
    com "File ... is not in an ACTIVE state" mesmo com upload bem-sucedido.
    """
    deadline = time.monotonic() + timeout_seconds
    current = uploaded_file
    while getattr(current.state, "name", current.state) == "PROCESSING":
        if time.monotonic() >= deadline:
            raise GeminiClientError(
                "O Gemini demorou demais para processar este arquivo "
                "(comum com vídeos maiores). Tente novamente em instantes."
            )
        time.sleep(2)
        current = client.files.get(name=uploaded_file.name)

    state_name = getattr(current.state, "name", current.state)
    if state_name != "ACTIVE":
        raise GeminiClientError(
            "O Gemini não conseguiu processar este arquivo "
            f"(estado: {state_name}). Tente novamente ou com outro arquivo."
        )
    return current


def _generate_text(client: genai.Client, model: str, prompt: str, media_part) -> str:
    try:
        response = client.models.generate_content(
            model=model,
            contents=[media_part, prompt],
        )
    except ClientError as exc:
        # Erros comuns: chave inválida, cota excedida, arquivo rejeitado.
        if "Unsupported MIME type" in str(exc):
            raise GeminiClientError(
                "O Gemini não reconheceu o formato deste arquivo. Isso pode "
                "acontecer com formatos de áudio/vídeo menos comuns — "
                "avise o desenvolvedor para que esse formato seja tratado "
                f"corretamente. Detalhe técnico: {exc}"
            ) from exc
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


def ask_about_visual_media(
    file_path: str,
    api_key: str,
    question: str,
    *,
    model: str = DEFAULT_MODEL,
    is_video: bool = False,
) -> str:
    """
    Responde a uma pergunta específica sobre uma imagem ou vídeo já
    descrito antes — por exemplo, o preço de um produto num encarte
    promocional, ou um valor específico numa fatura, que a descrição geral
    não tenha mencionado.
    """
    client = _build_client(api_key)
    media_part = _upload_or_inline(client, file_path)

    tipo = "vídeo" if is_video else "imagem"
    prompt = (
        f"Com base neste {tipo}, responda em português do Brasil à "
        f"seguinte pergunta de forma direta e específica: {question.strip()}\n"
        "Se a informação pedida não estiver visível ou não puder ser "
        "determinada com confiança, diga isso claramente em vez de "
        "adivinhar. Responda apenas com a resposta, sem comentários "
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
