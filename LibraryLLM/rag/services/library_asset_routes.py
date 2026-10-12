"""Explicit per-library document AI, installed in the resident RAG process."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.dependencies import get_current_user
from rag.services.library_asset_pipeline import LibraryAssetPipeline, install_worker
from rag.services.knowledge_routes import ArtifactRequest, QuizRequest, ClozeGradeRequest


class LibraryRAGRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    query: str | None = Field(default=None, max_length=8000)
    question: str | None = Field(default=None, max_length=8000)
    depth: Literal['concise', 'normal', 'detailed', 'comprehensive'] = 'normal'

    @model_validator(mode='after')
    def question_alias(self):
        self.query = (self.query or self.question or '').strip()
        if not self.query:
            raise ValueError('Question cannot be empty.')
        if self.question and self.question.strip() != self.query:
            raise ValueError('Question aliases must identify the same question.')
        return self


def install_library_assets(app, engine, service=None):
    service = service or LibraryAssetPipeline(engine)
    app.state.library_assets = service
    router = APIRouter(prefix='/libraries/{library_id}/assets/{asset_id}', tags=['Library document AI'])

    def private(response: Response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'

    router.dependencies.append(Depends(private))

    @router.post('/rag')
    def ask(library_id: UUID, asset_id: UUID, request: LibraryRAGRequest, actor=Depends(get_current_user)):
        try:
            return service.ask(str(library_id), str(asset_id), actor, request.query, request.depth)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'Document questions are temporarily unavailable. Please retry.')

    @router.get('/artifacts')
    def artifacts(library_id: UUID, asset_id: UUID, actor=Depends(get_current_user)):
        return service.list_artifacts(str(library_id), str(asset_id), actor)

    @router.post('/artifacts/quiz')
    def quiz(library_id: UUID, asset_id: UUID, request: QuizRequest, actor=Depends(get_current_user)):
        return service.generate(str(library_id), str(asset_id), actor, 'quiz', request.mode,
                                request.questionTypes, request.questionCount)

    @router.post('/artifacts/{kind}')
    def generate(library_id: UUID, asset_id: UUID,
                 kind: Literal['key-concepts', 'summary', 'flashcards', 'mindmap'],
                 request: ArtifactRequest, actor=Depends(get_current_user)):
        return service.generate(str(library_id), str(asset_id), actor, kind, request.mode)

    @router.get('/artifacts/{artifact_id}')
    def artifact(library_id: UUID, asset_id: UUID, artifact_id: UUID, actor=Depends(get_current_user)):
        return service.get_artifact(str(library_id), str(asset_id), actor, str(artifact_id))

    @router.delete('/artifacts/{artifact_id}')
    def delete(library_id: UUID, asset_id: UUID, artifact_id: UUID, actor=Depends(get_current_user)):
        return service.delete_artifact(str(library_id), str(asset_id), actor, str(artifact_id))

    @router.get('/sources/{chunk_id}')
    def source(library_id: UUID, asset_id: UUID, chunk_id: str, actor=Depends(get_current_user)):
        return service.source(str(library_id), str(asset_id), actor, chunk_id)

    @router.post('/artifacts/{artifact_id}/cloze/{item_id}/grade')
    def grade(library_id: UUID, asset_id: UUID, artifact_id: UUID, item_id: str,
              request: ClozeGradeRequest, actor=Depends(get_current_user)):
        return service.grade(str(library_id), str(asset_id), actor, str(artifact_id), item_id, request.answer)

    app.include_router(router)
    install_worker(app, service)
    return service
