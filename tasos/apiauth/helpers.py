#
# Copyright Tristen Georgiou 2023
#
from enum import Enum
from typing import TypeVar, Generic

from pydantic import BaseModel, Field
from pydantic.generics import GenericModel

T = TypeVar("T")


class BaseFilterQueryParams(BaseModel):
    """
    The base filter parameters for a database query
    """

    limit: int = Field(default=10, ge=1, le=100, description="The number of items to return")
    offset: int = Field(default=0, ge=0, description="The offset to start from")


class Paginated(GenericModel, Generic[T]):
    """
    A generic paginated response model
    """

    total: int
    items: list[T]


class OrderDirection(Enum):
    """
    The order direction for a query result set
    """

    asc = "asc"
    desc = "desc"
