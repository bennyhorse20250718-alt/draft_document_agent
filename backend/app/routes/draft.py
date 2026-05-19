"""
Draft generation routes — full draft, streaming draft, refine, refine section, regenerate selection.
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas import (
    DraftRequest, DraftResponse, RefineRequest, RefineSectionRequest,
    RegenerateSelectionRequest, Citation,
)
from app.services.generation import get_generation_service, GenerationService
from app.services.retrieval import get_retrieval_service, RetrievalService

router = APIRouter(prefix="/draft", tags=["Draft"])


def _gen_svc() -> GenerationService:
    return get_generation_service()


def _ret_svc() -> RetrievalService:
    return get_retrieval_service()


def _fetch_reference_chunks(
    selected_doc_ids: list[str],
    topic: str,
    ret_svc: RetrievalService,
) -> list[dict]:
    """
    Retrieve full document text for each selected doc (or fall back to semantic
    search when no specific docs are chosen).  Returns one entry per document
    with the complete .txt file content so the LLM has maximum context.
    """
    if selected_doc_ids:
        chunks = []
        for doc_id in selected_doc_ids[:10]:
            full_text, meta = ret_svc.get_full_text_for_doc(doc_id)
            if full_text:
                chunks.append({"text": full_text, "metadata": meta})
        return chunks
    elif ret_svc.collection_count() > 0:
        # Semantic-search fallback: enrich each result with full document text
        search_results = ret_svc.search(topic, top_k=10)
        enriched = []
        for result in search_results:
            doc_id = result["metadata"].get("doc_id", "")
            if doc_id:
                full_text, meta = ret_svc.get_full_text_for_doc(doc_id)
                if full_text:
                    enriched.append({"text": full_text, "metadata": meta})
                    continue
            enriched.append(result)
        return enriched
    return []


@router.post("", response_model=DraftResponse, summary="Generate a full draft with citations")
async def generate_draft(
    request: DraftRequest,
    gen_svc: GenerationService = Depends(_gen_svc),
    ret_svc: RetrievalService = Depends(_ret_svc),
):
    try:
        ref_chunks = _fetch_reference_chunks(request.selected_doc_ids, request.topic, ret_svc)
        draft, citation_map = await gen_svc.generate_draft_with_citations(
            topic=request.topic,
            doc_type=request.doc_type,
            tone=request.tone,
            language=request.language,
            extra_instructions=request.extra_instructions,
            reference_chunks=ref_chunks,
        )
        citations = [Citation(**c) for c in citation_map]
        return DraftResponse(draft=draft, citations=citations)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")


@router.post("/stream", summary="Stream a draft (Server-Sent Events)")
async def generate_draft_stream(
    request: DraftRequest,
    gen_svc: GenerationService = Depends(_gen_svc),
    ret_svc: RetrievalService = Depends(_ret_svc),
):
    ref_chunks = _fetch_reference_chunks(request.selected_doc_ids, request.topic, ret_svc)

    async def event_generator():
        try:
            async for token in gen_svc.generate_draft_stream(
                topic=request.topic,
                doc_type=request.doc_type,
                tone=request.tone,
                language=request.language,
                extra_instructions=request.extra_instructions,
                reference_chunks=ref_chunks,
            ):
                yield f"data: {token}\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/refine", response_model=DraftResponse, summary="Refine the entire draft")
async def refine_draft(
    request: RefineRequest,
    gen_svc: GenerationService = Depends(_gen_svc),
):
    try:
        refined = await gen_svc.refine_draft(
            current_draft=request.current_draft,
            instruction=request.instruction,
            citations=[c.model_dump() for c in request.citations] if request.citations else None,
        )
        return DraftResponse(draft=refined)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")


@router.post("/refine-section", response_model=DraftResponse, summary="Rewrite a specific section")
async def refine_section(
    request: RefineSectionRequest,
    gen_svc: GenerationService = Depends(_gen_svc),
):
    try:
        refined = await gen_svc.refine_section(
            section_text=request.section_text,
            instruction=request.instruction,
            context=request.context,
        )
        return DraftResponse(draft=refined)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")


@router.post("/regenerate-selection", response_model=DraftResponse, summary="Regenerate a highlighted selection")
async def regenerate_selection(
    request: RegenerateSelectionRequest,
    gen_svc: GenerationService = Depends(_gen_svc),
):
    try:
        regenerated = await gen_svc.regenerate_selection(
            selected_text=request.selected_text,
            instruction=request.instruction,
            full_draft=request.full_draft,
            topic=request.topic,
            doc_type=request.doc_type,
            tone=request.tone,
            language=request.language,
            citations=[c.model_dump() for c in request.citations] if request.citations else None,
        )
        return DraftResponse(draft=regenerated)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {str(e)}")
