{% if cookiecutter.logging == "structlog" -%}
from app.logging_config import get_logger
{%- else -%}
from logging import getLogger
{%- endif %}
from fastapi import APIRouter, Depends, HTTPException

from app.api.models.{{cookiecutter.model_name}} import (
    {{cookiecutter.model_name_class}}Create,
    {{cookiecutter.model_name_class}}ListResponse,
    {{cookiecutter.model_name_class}}Response,
    {{cookiecutter.model_name_class}}Update,
)
from app.dependencies import get_{{cookiecutter.model_name}}_service
from app.services.{{cookiecutter.model_name}}_service import {{cookiecutter.model_name_class}}Service

router = APIRouter(prefix="/api/v1/{{cookiecutter.model_name_plural}}", tags=["{{cookiecutter.model_name_plural}}"])
{% if cookiecutter.logging == "structlog" -%}
logger = get_logger(__name__)
{%- else -%}
logger = getLogger(__name__)
{%- endif %}


@router.post("/", response_model={{cookiecutter.model_name_class}}Response, status_code=201)
async def create_{{cookiecutter.model_name}}(
    data: {{cookiecutter.model_name_class}}Create,
    service: {{cookiecutter.model_name_class}}Service = Depends(get_{{cookiecutter.model_name}}_service),
) -> {{cookiecutter.model_name_class}}Response:
    return await service.create(data)


@router.get("/", response_model={{cookiecutter.model_name_class}}ListResponse)
async def list_{{cookiecutter.model_name_plural}}(
    service: {{cookiecutter.model_name_class}}Service = Depends(get_{{cookiecutter.model_name}}_service),
) -> {{cookiecutter.model_name_class}}ListResponse:
    return await service.list_all()


@router.get("/{item_id}", response_model={{cookiecutter.model_name_class}}Response)
async def get_{{cookiecutter.model_name}}(
    item_id: str,
    service: {{cookiecutter.model_name_class}}Service = Depends(get_{{cookiecutter.model_name}}_service),
) -> {{cookiecutter.model_name_class}}Response:
    result = await service.get_by_id(item_id)
    if not result:
        raise HTTPException(status_code=404, detail="{{cookiecutter.model_name_class}} not found")
    return result


@router.put("/{item_id}", response_model={{cookiecutter.model_name_class}}Response)
async def update_{{cookiecutter.model_name}}(
    item_id: str,
    data: {{cookiecutter.model_name_class}}Update,
    service: {{cookiecutter.model_name_class}}Service = Depends(get_{{cookiecutter.model_name}}_service),
) -> {{cookiecutter.model_name_class}}Response:
    result = await service.update(item_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="{{cookiecutter.model_name_class}} not found")
    return result


@router.delete("/{item_id}", status_code=204)
async def delete_{{cookiecutter.model_name}}(
    item_id: str,
    service: {{cookiecutter.model_name_class}}Service = Depends(get_{{cookiecutter.model_name}}_service),
) -> None:
    deleted = await service.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="{{cookiecutter.model_name_class}} not found")
