"""Authenticated Knowledge Tools routes, independent of inference services."""
from typing import Literal

from fastapi import Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from backend.dependencies import get_current_user
from rag.services.knowledge_artifacts import KnowledgeArtifacts


class ArtifactRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['document'] = 'document'
    mode: Literal['quick', 'detailed'] = 'quick'


QuestionType = Literal['mcq', 'fill_blank', 'matching']


class QuizRequest(ArtifactRequest):
    questionTypes: list[QuestionType] = Field(default_factory=lambda: ['mcq', 'fill_blank'], min_length=1, max_length=3)
    questionCount: int = Field(default=12, ge=1, le=30, strict=True)


def install_knowledge_artifacts(app, documents):
    service = KnowledgeArtifacts(documents)
    app.state.knowledge_artifacts = service

    def private_response(response: Response):
        response.headers['Cache-Control'] = 'no-store'

    prefix = '/rag/documents/{document_id}'
    guards = [Depends(private_response)]

    @app.get(prefix + '/artifacts', dependencies=guards)
    def list_artifacts(document_id: str, user=Depends(get_current_user)):
        return service.list(document_id, user)

    @app.post(prefix + '/artifacts/quiz', dependencies=guards)
    def generate_quiz(document_id: str, request: QuizRequest, user=Depends(get_current_user)):
        return service.generate(document_id, 'quiz', user, request.mode, request.questionTypes, request.questionCount)

    @app.post(prefix + '/artifacts/{kind}', dependencies=guards)
    def generate(document_id: str, kind: Literal['key-concepts', 'summary', 'flashcards', 'mindmap'],
                 request: ArtifactRequest, user=Depends(get_current_user)):
        return service.generate(document_id, kind, user, request.mode)

    @app.get(prefix + '/artifacts/{artifact_id}', dependencies=guards)
    def get(document_id: str, artifact_id: str, user=Depends(get_current_user)):
        return service.get(document_id, artifact_id, user)

    @app.delete(prefix + '/artifacts/{artifact_id}', dependencies=guards)
    def delete(document_id: str, artifact_id: str, user=Depends(get_current_user)):
        return service.delete(document_id, artifact_id, user)

    @app.get(prefix + '/sources/{chunk_id}', dependencies=guards)
    def source(document_id: str, chunk_id: str, user=Depends(get_current_user)):
        return service.source(document_id, chunk_id, user)

    return service
