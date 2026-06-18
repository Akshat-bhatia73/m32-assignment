"""Turn an uploaded file (text / PDF / image) into plain transcript text.

Used by `POST /meetings/extract` so the chat composer can accept a transcript file or a
screenshot of notes. Text and PDFs are parsed locally; images are transcribed by the LLM's
vision capability (Gemini is multimodal). The returned text flows back into the chat as a normal
message, so the existing router → extractor path handles it unchanged.
"""

import base64
import io

_TEXT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}
_TEXT_EXTS = (".txt", ".md", ".markdown", ".csv", ".log", ".text")
_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif")

MAX_BYTES = 10 * 1024 * 1024  # 10 MB — generous for notes, guards against huge uploads

_VISION_PROMPT = (
    "This image is a screenshot or photo of meeting notes / a transcript. Transcribe ALL of the "
    "text exactly as written, preserving line breaks and bullet structure. Output only the "
    "transcript text — no commentary, no headings you add yourself."
)


class TranscriptError(ValueError):
    """A user-facing problem with the uploaded file (bad type, empty, unreadable)."""


def _looks_like(filename: str, exts: tuple[str, ...]) -> bool:
    return filename.lower().endswith(exts)


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency missing
        raise TranscriptError("PDF support isn't available on the server.") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:
        raise TranscriptError("I couldn't read that PDF — it may be corrupt or encrypted.") from exc
    text = text.strip()
    if not text:
        raise TranscriptError(
            "That PDF has no selectable text (it may be a scan). Try a screenshot image instead."
        )
    return text


async def _extract_image(data: bytes, content_type: str) -> str:
    from app.llm.provider import get_llm, has_llm

    if not has_llm():
        raise TranscriptError("Image transcription needs an LLM key configured on the server.")
    from langchain_core.messages import HumanMessage

    from app.agents.conversation import extract_text

    mime = content_type if content_type in _IMAGE_TYPES else "image/png"
    b64 = base64.b64encode(data).decode("ascii")
    llm = get_llm(temperature=0.0)
    try:
        ai = await llm.ainvoke(
            [
                HumanMessage(
                    content=[
                        {"type": "text", "text": _VISION_PROMPT},
                        {"type": "image_url", "image_url": f"data:{mime};base64,{b64}"},
                    ]
                )
            ]
        )
    except Exception as exc:
        raise TranscriptError("I couldn't read that image. Try a clearer screenshot.") from exc
    text = extract_text(ai.content).strip()
    if not text:
        raise TranscriptError("I couldn't find any text in that image.")
    return text


async def extract_transcript(filename: str, content_type: str | None, data: bytes) -> str:
    """Return plain text extracted from an uploaded transcript file or image."""
    if not data:
        raise TranscriptError("That file is empty.")
    if len(data) > MAX_BYTES:
        raise TranscriptError("That file is too large (max 10 MB).")

    filename = filename or "upload"
    content_type = (content_type or "").split(";")[0].strip().lower()

    if content_type in _IMAGE_TYPES or _looks_like(filename, _IMAGE_EXTS):
        return await _extract_image(data, content_type)
    if content_type == "application/pdf" or _looks_like(filename, (".pdf",)):
        return _extract_pdf(data)
    if content_type in _TEXT_TYPES or _looks_like(filename, _TEXT_EXTS) or not content_type:
        try:
            text = data.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise TranscriptError("That file isn't readable as text.") from exc
        if not text:
            raise TranscriptError("That file is empty.")
        return text

    raise TranscriptError(
        "Unsupported file type. Upload a .txt, .md, or .pdf transcript, or an image screenshot."
    )
