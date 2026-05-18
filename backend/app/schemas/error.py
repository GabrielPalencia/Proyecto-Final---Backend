from pydantic import BaseModel


class ErrorResponse(BaseModel):
    error: str
    message: str
    detail: str | list | None = None
