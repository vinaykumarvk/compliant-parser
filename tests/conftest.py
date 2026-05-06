"""Shared async test infrastructure for IQW unit tests.

Provides a lightweight MockAsyncSession that stores ORM model instances
in memory, avoiding any dependency on SQLite or PostgreSQL for unit tests.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from unittest.mock import MagicMock

import sqlalchemy as sa


# ---------------------------------------------------------------------------
# Lightweight mock for AsyncSession
# ---------------------------------------------------------------------------

class _MockScalarsResult:
    """Wraps a list of ORM objects to mimic scalars() result."""

    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return list(self._items)

    def first(self) -> Optional[Any]:
        return self._items[0] if self._items else None

    def __iter__(self):
        return iter(self._items)


class _MockResult:
    """Wraps query results to mimic execute() result."""

    def __init__(self, items: list, scalar_value: Any = None) -> None:
        self._items = items
        self._scalar_value = scalar_value

    def scalars(self) -> _MockScalarsResult:
        return _MockScalarsResult(self._items)

    def scalar(self) -> Any:
        return self._scalar_value

    def first(self) -> Optional[Any]:
        return self._items[0] if self._items else None

    def scalar_one_or_none(self) -> Optional[Any]:
        if len(self._items) == 0:
            return None
        if len(self._items) == 1:
            return self._items[0]
        raise Exception("Multiple rows returned for scalar_one_or_none")


class MockAsyncSession:
    """In-memory mock of AsyncSession for unit tests.

    Stores ORM objects keyed by (table_name, primary_key).
    Supports add/flush/get/execute with basic select filtering.
    """

    def __init__(self) -> None:
        # {table_name: {pk: obj}}
        self._store: dict[str, dict[str, Any]] = {}

    def _table_for(self, obj_or_cls) -> str:
        cls = obj_or_cls if isinstance(obj_or_cls, type) else type(obj_or_cls)
        return cls.__tablename__

    def _pk_for(self, obj) -> str:
        return obj.id

    def add(self, obj: Any) -> None:
        table = self._table_for(obj)
        if table not in self._store:
            self._store[table] = {}
        # Ensure created_at is set if not already
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(timezone.utc)
        self._store[table][self._pk_for(obj)] = obj

    async def flush(self) -> None:
        """No-op — objects are stored immediately in add()."""
        pass

    async def commit(self) -> None:
        """No-op for mock."""
        pass

    async def rollback(self) -> None:
        """No-op for mock."""
        pass

    async def close(self) -> None:
        """No-op for mock."""
        pass

    async def refresh(self, obj: Any, attribute_names: Optional[list] = None) -> None:
        """No-op — relationships are already in-memory on the object."""
        pass

    async def delete(self, obj: Any) -> None:
        """Remove an object from the in-memory store."""
        table = self._table_for(obj)
        pk = self._pk_for(obj)
        store = self._store.get(table, {})
        store.pop(pk, None)

    async def get(self, model_cls: type, pk: str) -> Optional[Any]:
        table = model_cls.__tablename__
        store = self._store.get(table, {})
        return store.get(pk)

    async def execute(self, stmt: Any) -> _MockResult:
        """Handle select() and count() statements."""
        # Handle count queries like select(func.count()).select_from(subquery)
        if _is_count_query(stmt):
            inner = _extract_inner_select(stmt)
            if inner is not None:
                items = self._resolve_select(inner)
            else:
                items = self._resolve_select(stmt)
            return _MockResult([], scalar_value=len(items))

        # Handle regular select queries
        items = self._resolve_select(stmt)
        return _MockResult(items)

    def _resolve_select(self, stmt: Any) -> list:
        """Resolve a select statement against the in-memory store."""
        # Get the target model class from the statement
        model_cls = _extract_model_from_stmt(stmt)
        if model_cls is None:
            return []

        table = model_cls.__tablename__
        items = list(self._store.get(table, {}).values())

        # Apply where clauses
        items = _apply_where_clauses(stmt, items)

        # Apply ordering
        items = _apply_ordering(stmt, items)

        # Apply offset/limit
        if hasattr(stmt, "_offset_clause") and stmt._offset_clause is not None:
            offset = stmt._offset_clause.value if hasattr(stmt._offset_clause, "value") else int(stmt._offset_clause)
            items = items[offset:]
        if hasattr(stmt, "_limit_clause") and stmt._limit_clause is not None:
            limit = stmt._limit_clause.value if hasattr(stmt._limit_clause, "value") else int(stmt._limit_clause)
            items = items[:limit]

        return items

    def clear(self) -> None:
        """Clear all stored objects."""
        self._store.clear()


def _is_count_query(stmt: Any) -> bool:
    """Check if this is a count() query."""
    try:
        cols = stmt.selected_columns
        for col in cols:
            if hasattr(col, "name") and col.name == "count_1":
                return True
            if "count" in str(col).lower():
                return True
    except Exception:
        pass
    return False


def _extract_inner_select(stmt: Any) -> Optional[Any]:
    """For count-over-subquery, extract the inner SELECT that carries filters."""
    try:
        if hasattr(stmt, "froms") and stmt.froms:
            table = stmt.froms[0]
            # Subquery wraps an inner select via .element
            if hasattr(table, "element"):
                return table.element
    except Exception:
        pass
    return None


def _extract_model_from_stmt(stmt: Any) -> Optional[type]:
    """Extract the ORM model class from a select statement."""
    try:
        # For select(Model)
        if hasattr(stmt, "froms") and stmt.froms:
            table = stmt.froms[0]
            # For subquery-based count queries
            if hasattr(table, "element"):
                return _extract_model_from_stmt(table.element)
            # Get model from table name
            from models import Base
            for mapper in Base.registry.mappers:
                if mapper.local_table is table:
                    return mapper.class_
        # Try column_descriptions
        if hasattr(stmt, "column_descriptions"):
            for desc in stmt.column_descriptions:
                if "entity" in desc and desc["entity"] is not None:
                    return desc["entity"]
    except Exception:
        pass
    return None


def _apply_where_clauses(stmt: Any, items: list) -> list:
    """Apply where clause filters from the statement."""
    if not hasattr(stmt, "whereclause") or stmt.whereclause is None:
        return items

    clause = stmt.whereclause
    return [item for item in items if _evaluate_clause(clause, item)]


def _evaluate_clause(clause: Any, obj: Any) -> bool:
    """Evaluate a SQLAlchemy where clause against an ORM object."""
    # Handle AND (BooleanClauseList)
    if hasattr(clause, "clauses"):
        op = getattr(clause, "operator", None)
        if op is not None and hasattr(op, "__name__") and op.__name__ == "and_":
            return all(_evaluate_clause(c, obj) for c in clause.clauses)
        if op is not None and hasattr(op, "__name__") and op.__name__ == "or_":
            return any(_evaluate_clause(c, obj) for c in clause.clauses)
        # Default to AND
        return all(_evaluate_clause(c, obj) for c in clause.clauses)

    # Handle comparison operators (BinaryExpression)
    if hasattr(clause, "left") and hasattr(clause, "right"):
        left = clause.left
        right = clause.right
        op = clause.operator

        # Get the column name from the left side
        col_name = None
        if hasattr(left, "key"):
            col_name = left.key
        elif hasattr(left, "name"):
            col_name = left.name

        if col_name is None:
            return True  # Can't evaluate, pass through

        obj_val = getattr(obj, col_name, None)
        # Handle enum values for comparison
        if hasattr(obj_val, "value"):
            obj_val = obj_val.value

        # Get the comparison value
        cmp_val = None
        if hasattr(right, "value"):
            cmp_val = right.value
        elif hasattr(right, "effective_value"):
            cmp_val = right.effective_value
        else:
            cmp_val = right

        # Handle enum comparison values
        if hasattr(cmp_val, "value"):
            cmp_val = cmp_val.value

        op_name = getattr(op, "__name__", str(op))
        if op_name == "eq" or "eq" in str(op):
            return obj_val == cmp_val
        if op_name == "ne" or "ne" in str(op):
            return obj_val != cmp_val
        if op_name == "ge" or ">=" in str(op):
            if obj_val is None:
                return False
            return str(obj_val) >= str(cmp_val)
        if op_name == "le" or "<=" in str(op):
            if obj_val is None:
                return False
            return str(obj_val) <= str(cmp_val)
        if "like" in str(op).lower() or "ilike" in str(op).lower():
            if obj_val is None:
                return False
            # Simple LIKE/ILIKE: convert % wildcards
            pattern = str(cmp_val).lower().replace("%", "")
            return pattern in str(obj_val).lower()

    return True  # Can't evaluate, pass through


def _apply_ordering(stmt: Any, items: list) -> list:
    """Apply ORDER BY from the statement."""
    if not hasattr(stmt, "_order_by_clauses") or not stmt._order_by_clauses:
        return items

    for clause in reversed(stmt._order_by_clauses):
        col_name = None
        reverse = False

        # Unwrap nested UnaryExpressions (e.g. nulls_first / nulls_last wrapping)
        current = clause
        while hasattr(current, "element") and hasattr(current, "modifier"):
            mod_name = getattr(current.modifier, "__name__", "") if current.modifier else ""
            if "desc" in mod_name:
                reverse = True
            # If the inner element is another UnaryExpression, keep unwrapping
            inner = current.element
            if hasattr(inner, "modifier"):
                current = inner
            else:
                # inner is the actual column
                if hasattr(inner, "key"):
                    col_name = inner.key
                elif hasattr(inner, "name"):
                    col_name = inner.name
                break

        # Fallback: bare column references
        if col_name is None:
            if hasattr(clause, "key"):
                col_name = clause.key
            elif hasattr(clause, "name"):
                col_name = clause.name

        if col_name:
            _cn = col_name  # capture for lambda
            items.sort(
                key=lambda x, _c=_cn: (getattr(x, _c, None) is None, str(getattr(x, _c, "") or "")),
                reverse=reverse,
            )

    return items


# ---------------------------------------------------------------------------
# Async test base
# ---------------------------------------------------------------------------

class AsyncTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class for async ORM tests.

    Creates a fresh MockAsyncSession for every test method.
    Provides ``self.db`` ready for use.
    """

    async def asyncSetUp(self) -> None:
        self.db = MockAsyncSession()

    async def asyncTearDown(self) -> None:
        self.db.clear()
