from pydantic import BaseModel, Field


class {{ cookiecutter.model_name_class }}Create(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)


class {{ cookiecutter.model_name_class }}Update(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=1000)


class {{ cookiecutter.model_name_class }}Response(BaseModel):
    id: str
    name: str
    description: str | None


class {{ cookiecutter.model_name_class }}ListResponse(BaseModel):
    {{ cookiecutter.model_name_plural }}: list[{{ cookiecutter.model_name_class }}Response]
    total: int
