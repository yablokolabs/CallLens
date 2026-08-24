"""Rubric endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from calllens.api.rubric_registry import RubricRegistry
from calllens.domain.rubric import Rubric
from calllens.rubrics.loader import RubricParseError, parse_rubric
from calllens.rubrics.validator import validate_rubric

router = APIRouter(prefix="/api/v1/rubrics", tags=["rubrics"])


def _registry(request: Request) -> RubricRegistry:
    return request.app.state.calllens.rubrics


@router.get("")
async def list_rubrics(request: Request) -> list[Rubric]:
    return _registry(request).list()


@router.get("/{name}")
async def get_rubric(request: Request, name: str) -> Rubric:
    rubric = _registry(request).get(name)
    if rubric is None:
        raise HTTPException(status_code=404, detail=f"rubric '{name}' not found")
    return rubric


@router.post("/validate")
async def validate_rubric_payload(payload: dict) -> dict:
    """Validate a rubric document without registering it."""
    try:
        rubric = parse_rubric(payload)
    except RubricParseError as exc:
        return {"valid": False, "issues": [str(exc)]}
    issues = validate_rubric(rubric)
    if issues:
        return {"valid": False, "issues": issues}
    return {"valid": True, "name": rubric.name, "version": rubric.version}


@router.post("")
async def create_rubric(request: Request, payload: dict) -> Rubric:
    """Register a custom rubric (declarative, versioned)."""
    try:
        rubric = parse_rubric(payload)
    except RubricParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    issues = validate_rubric(rubric)
    if issues:
        raise HTTPException(status_code=422, detail=issues)
    _registry(request).register(rubric)
    return rubric
