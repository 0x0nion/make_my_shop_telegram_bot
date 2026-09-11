from typing import Generic, TypeVar, Type, Sequence, Any, Iterable
from sqlalchemy import select, delete, func, exists, inspect
from sqlalchemy.ext.asyncio import AsyncSession
from shopcrm_core.db.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Универсальный базовый репозиторий для SQLAlchemy 2.0.
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
        # Кэшируем названия колонок для безопасной проверки при update
        self._column_names = set(inspect(model).mapper.column_attrs.keys())

    async def get_by_id(
        self,
        entity_id: Any,
        options: Sequence[Any] | None = None
    ) -> ModelType | None:
        """Получить запись по ID c поддержкой joinedload/selectinload."""
        stmt = select(self.model).where(self.model.id == entity_id)
        if options:
            stmt = stmt.options(*options)
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_one(
        self,
        *expressions: Any,
        options: Sequence[Any] | None = None
    ) -> ModelType | None:
        """Получить одну запись по условиям."""
        stmt = select(self.model).where(*expressions)
        if options:
            stmt = stmt.options(*options)
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_all(
        self,
        *expressions: Any,
        options: Sequence[Any] | None = None,
        order_by: Sequence[Any] | Any | None = None,
        limit: int | None = None,
        offset: int | None = None
    ) -> list[ModelType]:
        """Получить список записей."""
        stmt = select(self.model).where(*expressions)
        if options:
            stmt = stmt.options(*options)
        if order_by is not None:
            if isinstance(order_by, (list, tuple)):
                stmt = stmt.order_by(*order_by)
            else:
                stmt = stmt.order_by(order_by)
        if offset is not None:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        return list(result.unique().scalars().all())

    async def create(self, **kwargs: Any) -> ModelType:
        """Создать экземпляр, закоммитить и обновить состояние объекта."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)
        return instance

    async def create_without_commit(self, **kwargs: Any) -> ModelType:
        """Создать экземпляр и выполнить flush (без commit)."""
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def create_many(self, instances_data: Iterable[dict[str, Any]]) -> list[ModelType]:
        """Пакетное создание объектов."""
        instances = [self.model(**data) for data in instances_data]
        self.session.add_all(instances)
        await self.session.commit()
        return instances

    async def update(
        self,
        entity_id: Any,
        **kwargs: Any
    ) -> ModelType | None:
        """
        Безопасное обновление через ORM с обновлением состояния в памяти.
        """
        instance = await self.get_by_id(entity_id)
        if instance:
            for key, value in kwargs.items():
                if key in self._column_names:
                    setattr(instance, key, value)
            await self.session.commit()
            await self.session.refresh(instance)
        return instance

    async def delete_by_id(self, entity_id: Any) -> bool:
        """Удалить запись по ID."""
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def delete_where(self, *expressions: Any) -> int:
        """Удалить записи по условиям."""
        stmt = delete(self.model).where(*expressions)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def exists(self, *expressions: Any) -> bool:
        """Проверить существование записи."""
        stmt = select(exists().where(*expressions))
        result = await self.session.execute(stmt)
        return bool(result.scalar())

    async def count(self, *expressions: Any) -> int:
        """Посчитать количество записей."""
        stmt = select(func.count()).select_from(self.model)
        if expressions:
            stmt = stmt.where(*expressions)
        result = await self.session.execute(stmt)
        return result.scalar() or 0