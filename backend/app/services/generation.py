"""
Draft generation service — calls any OpenAI-compatible LLM API (e.g. OpenRouter).
"""
import re
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)


def _strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks emitted by reasoning models (e.g. DeepSeek)."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


SYSTEM_PROMPT = """You are an expert document drafter specialising in formal official documents.
Your task is to draft a new document that:
1. Matches the writing style, tone, and structure of the provided reference documents. If the sentences can be directly reused from the references, do so and add an inline citation [N]. If you paraphrase or draw inspiration from the references, add an appropriate citation as well. Use the reference documents as templates for formatting, phrasing, and style ??especially for headers, salutations, sign-offs, and any formal language patterns.
2. Addresses the user's specific topic and instructions.
3. Uses formal, precise language appropriate for government or corporate communications.
4. Follows the same structural format as the references (headers, paragraph ordering, sign-off style).
5. Tables with figures: ACTIVELY scan ALL reference documents for numbers, percentages, dollar amounts, quantities, dates, and other quantitative data. Extract and use those exact figures in table cells with the appropriate [N] citation. Only use [BRACKET] placeholders when specific data is genuinely absent from all provided references.

Important rules:
- Output only the final document text. Do not include any reasoning, preamble, or explanation.
- Do not invent facts or statistics. If specific details are not provided, use appropriate placeholder text in [BRACKETS].
- Maintain the formality level requested by the user.
- When the topic involves comparisons, statistics, budgets, timelines, or structured data, present that
  information as a properly formatted Markdown table (| Col | Col | header row followed by |---|---| separator row).
- When you draw wording, phrasing, statistics, figures, or structural patterns from a numbered reference
  document, add an inline citation marker immediately after the relevant sentence, figure, or table cell,
  like [1] or [2]. Only cite reference numbers that were actually provided.
  Do not cite if no references are provided.
"""


def _build_messages(
    topic: str,
    doc_type: str,
    tone: str,
    language: str,
    extra_instructions: str,
    reference_chunks: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Build the message array for the LLM.
    Returns (messages, citation_map) where citation_map is a list of
    {ref_num, source, doc_id, excerpt} dicts (1-indexed).
    """
    citation_map: list[dict] = []
    ref_text = ""
    for i, chunk in enumerate(reference_chunks[:10], 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "Unknown")
        doc_id = meta.get("doc_id", "")
        excerpt = chunk["text"][:200].replace("\n", " ")
        citation_map.append({
            "ref_num": i,
            "source": source,
            "doc_id": doc_id,
            "excerpt": excerpt,
        })
        ref_text += (
            f"\n--- Reference [{i}]: {source} "
            f"(Type: {meta.get('doc_type', '')}, Date: {meta.get('date', '')}) ---\n"
            f"{chunk['text']}\n"
        )

    official_reply_rule = (
        "\n**Special rule for Official Reply:** Answer the question given by user only directly and concisely. "
        "Do not add background context, unsolicited explanations, or tangential information — "
        "only provide what directly responds to each question raised."
        if doc_type == "Official Reply" else ""
    )

    user_message = f"""Please draft a new {doc_type} document with the following parameters:

**Topic/Subject:** {topic}
**Tone:** {tone}
**Language:** {language}
{f"**Additional Instructions:** {extra_instructions}" if extra_instructions else ""}{official_reply_rule}

**Reference Documents (use these as style and format templates, and cite them inline as [1], [2], etc.):**
{ref_text if ref_text else "No reference documents provided — use standard formal style."}

Now draft the {doc_type} document (remember to add inline citations [N] where appropriate):"""

    return (
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        citation_map,
    )


def _find_reference_evidence(draft: str, ref_num: int, chunk_text: str) -> str:
    """Find the most relevant sentence from chunk_text for citation [ref_num] in the draft."""
    marker = f"[{ref_num}]"
    stop = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'of', 'in', 'on', 'at', 'to', 'for', 'with', 'by', 'from', 'and', 'or', 'but',
        'not', 'that', 'this', 'it', 'its', 'as', 'we', 'our', 'they', 'their', 'which',
        'also', 'such', 'these', 'those', 'there', 'when', 'all', 'any', 'some', 'into',
    }
    # Collect content keywords from draft sentences that use this citation
    draft_kw: set[str] = set()
    for line in draft.split('\n'):
        if marker not in line:
            continue
        clean = re.sub(r'\[\d+\]', '', line)
        for sent in re.split(r'(?<=[.!?])\s+', clean):
            for w in sent.lower().split():
                w = w.strip('.,;:()[]"\'')
                if len(w) > 3 and w not in stop and w.isalpha():
                    draft_kw.add(w)
    if not draft_kw:
        return chunk_text[:350]
    # Score each sentence in the reference chunk by keyword overlap with draft
    ref_sentences = re.split(r'(?<=[.!?])\s+', chunk_text)
    best, best_score = "", 0
    for sent in ref_sentences:
        if len(sent.strip()) < 15:
            continue
        sent_words = {w.strip('.,;:()[]"\' ').lower() for w in sent.split()}
        score = len(draft_kw & sent_words)
        if score > best_score:
            best_score = score
            best = sent
    return best.strip() if best else chunk_text[:350]


class GenerationService:
    def __init__(self):
        settings = get_settings()
        default_headers: dict[str, str] = {}
        if settings.openrouter_site_url:
            default_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_site_name:
            default_headers["X-Title"] = settings.openrouter_site_name
        self._client = AsyncOpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            default_headers=default_headers or None,
        )
        self._model = settings.llm_model
        self._max_tokens = settings.llm_max_tokens

    async def generate_draft(
        self,
        topic: str,
        doc_type: str = "Official Reply",
        tone: str = "Formal",
        language: str = "English",
        extra_instructions: str = "",
        reference_chunks: list[dict] | None = None,
    ) -> str:
        """Generate a complete draft (non-streaming, no citations returned)."""
        messages, _ = _build_messages(
            topic, doc_type, tone, language, extra_instructions, reference_chunks or []
        )
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        )
        return _strip_think_tags(response.choices[0].message.content or "")

    async def generate_draft_with_citations(
        self,
        topic: str,
        doc_type: str = "Official Reply",
        tone: str = "Formal",
        language: str = "English",
        extra_instructions: str = "",
        reference_chunks: list[dict] | None = None,
    ) -> tuple[str, list[dict]]:
        """Generate a draft and return (draft_text, citation_map)."""
        chunks = reference_chunks or []
        messages, citation_map = _build_messages(
            topic, doc_type, tone, language, extra_instructions, chunks
        )
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
        )
        draft = _strip_think_tags(response.choices[0].message.content or "")
        # Enrich citations with the most relevant passage from each reference chunk
        chunk_lookup = {i + 1: chunks[i]["text"] for i in range(min(len(chunks), 10))}
        for cit in citation_map:
            n = cit["ref_num"]
            cit["highlighted_text"] = (
                _find_reference_evidence(draft, n, chunk_lookup[n]) if n in chunk_lookup else ""
            )
        return draft, citation_map

    async def generate_draft_stream(
        self,
        topic: str,
        doc_type: str = "Official Reply",
        tone: str = "Formal",
        language: str = "English",
        extra_instructions: str = "",
        reference_chunks: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """Stream the draft token-by-token (for SSE endpoints)."""
        messages, _ = _build_messages(
            topic, doc_type, tone, language, extra_instructions, reference_chunks or []
        )
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.4,
            max_tokens=self._max_tokens,
            stream=True,
        )
        buf = ""
        in_think = False
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if not delta:
                continue
            buf += delta
            # Stream-strip <think> blocks without buffering the whole response
            if not in_think:
                if "<think>" in buf:
                    before, _, rest = buf.partition("<think>")
                    if before:
                        yield before
                    buf = rest
                    in_think = True
                else:
                    # Retain last 7 chars in case a tag spans chunks
                    if len(buf) > 7:
                        yield buf[:-7]
                        buf = buf[-7:]
            else:
                if "</think>" in buf:
                    _, _, rest = buf.partition("</think>")
                    buf = rest
                    in_think = False
        if buf and not in_think:
            yield buf

    async def refine_draft(
        self,
        current_draft: str,
        instruction: str,
        citations: list[dict] | None = None,
    ) -> str:
        """Refine an existing draft based on a user instruction."""
        ref_context = ""
        if citations:
            lines = ["Reference documents used in this draft (context for revision):"]
            for c in citations:
                lines.append(f"  [{c['ref_num']}] {c['source']}: \"{c['excerpt'][:150]}\"")
            ref_context = "\n".join(lines) + "\n\n"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{ref_context}"
                    f"Here is the current draft:\n\n{current_draft}\n\n"
                    f"Please revise it according to this instruction: {instruction}\n\n"
                    "Output only the revised document."
                ),
            },
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            max_tokens=4096,
        )
        return _strip_think_tags(response.choices[0].message.content or "")

    async def refine_section(
        self,
        section_text: str,
        instruction: str,
        context: str = "",
    ) -> str:
        """Rewrite a specific section of the document."""
        context_prefix = f"Document context:\n{context}\n\n" if context else ""
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{context_prefix}"
                    f"Rewrite this section according to the instruction.\n\n"
                    f"Section:\n{section_text}\n\n"
                    f"Instruction: {instruction}\n\n"
                    "Output only the rewritten section."
                ),
            },
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            max_tokens=1024,
        )
        return _strip_think_tags(response.choices[0].message.content or "")

    async def regenerate_selection(
        self,
        selected_text: str,
        instruction: str,
        full_draft: str = "",
        topic: str = "",
        doc_type: str = "Official Reply",
        tone: str = "Formal",
        language: str = "English",
        citations: list[dict] | None = None,
    ) -> str:
        """Regenerate only the highlighted/selected portion of the draft."""
        context_note = f"Full document context:\n{full_draft}\n\n" if full_draft else ""
        task_note = (
            f"You are rewriting a selected portion of a {doc_type} document.\n"
            f"Topic: {topic}\nTone: {tone}\nLanguage: {language}\n\n"
            if topic else
            f"You are rewriting a selected portion of a {doc_type} document.\n\n"
        )
        ref_context = ""
        if citations:
            lines = ["Reference documents used in this draft (context for revision):"]
            for c in citations:
                lines.append(f"  [{c['ref_num']}] {c['source']}: \"{c['excerpt'][:150]}\"")
            ref_context = "\n".join(lines) + "\n\n"
        user_instruction = instruction or "Rewrite this selection maintaining the same style, tone, and format."
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{task_note}"
                    f"{ref_context}"
                    f"{context_note}"
                    f"Selected text to rewrite:\n{selected_text}\n\n"
                    f"Instruction: {user_instruction}\n\n"
                    "Output only the rewritten replacement text, nothing else."
                ),
            },
        ]
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.4,
            max_tokens=1024,
        )
        return _strip_think_tags(response.choices[0].message.content or "")


_service: "GenerationService | None" = None


def get_generation_service() -> GenerationService:
    global _service
    if _service is None:
        _service = GenerationService()
    return _service
