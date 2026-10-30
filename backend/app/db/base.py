from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from sqlalchemy import DateTime, MetaData, Numeric, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Money = Annotated[Decimal, mapped_column(Numeric(12, 2))]
Json = Annotated[Any, mapped_column(JSONB)]
CreatedAt = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=func.now())]


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}
