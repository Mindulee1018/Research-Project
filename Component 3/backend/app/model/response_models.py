from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class GenericResponse(BaseModel, Generic[T]):
    status_code: int = Field(default=200)
    success: bool = Field(default=True)
    message: str = Field(default="OK")
    error_code: Optional[str] = Field(default=None)
    data: Optional[T] = Field(default=None)

    @classmethod
    def success_response(
        cls,
        data: Optional[T] = None,
        message: str = "Success",
        status_code: int = 200,
    ) -> "GenericResponse[T]":
        return cls(
            status_code=status_code,
            success=True,
            message=message,
            error_code=None,
            data=data,
        )

    @classmethod
    def failed_response(
        cls,
        message: str,
        error_code: str,
        status_code: int = 400,
        data: Optional[T] = None,
    ) -> "GenericResponse[T]":
        return cls(
            status_code=status_code,
            success=False,
            message=message,
            error_code=error_code,
            data=data,
        )


class GenericPaginationResponse(GenericResponse[T], Generic[T]):
    page: int = Field(default=1)
    page_size: int = Field(default=10)
    total_records: int = Field(default=0)
    total_pages: int = Field(default=0)

