# HOW TO — SQLAlchemy, Pydantic Schemas, and Alembic

## models.py = the actual database table (SQLAlchemy)

```python
class ListingReforgeOption(Base):       # ← creates the real DB table
    __tablename__ = "listing_reforge_options"
    id = Column(Integer, primary_key=True)
    option_name = Column(Text, nullable=False)
    level = Column(Integer, nullable=True)
    ...
```

This is **what exists in PostgreSQL**. Alembic reads these classes to generate migrations (`CREATE TABLE`, `ALTER TABLE`).

## schemas.py = the API shape (Pydantic)

```python
class ListingReforgeOptionOut(BaseModel):   # ← controls what the API returns
    option_name: str
    level: Optional[int] = None
    max_level: Optional[int] = None
```

This is a **filter/projection**. Notice it has only 3 fields — no `id`, no `listing_id`, no `created_at`. The API client doesn't need those internal fields. Pydantic schemas control:
- What fields are **exposed** in API responses (`*Out`)
- What fields are **accepted** in API requests (`*Create`, `*Request`)
- Validation and type coercion

## Base = the glue

```python
from .connector import Base

class Listing(Base):  # ← inherits from Base
```

`Base = declarative_base()` — it's SQLAlchemy's magic base class. Any class inheriting from it becomes a mapped table. SQLAlchemy's registry tracks all `Base` subclasses, which is how Alembic discovers your tables automatically.

## The flow

```
models.py (Base)          schemas.py (BaseModel)
     │                           │
     │  defines real DB table    │  defines API shape
     │                           │
     ▼                           ▼
 PostgreSQL               FastAPI response
 ┌──────────────────┐     ┌─────────────────┐
 │ listing_reforge_  │     │ {               │
 │   options         │     │   "option_name", │
 │ - id              │     │   "level",       │
 │ - listing_id      │ ──► │   "max_level"    │
 │ - option_name     │     │ }               │
 │ - level           │     └─────────────────┘
 │ - max_level       │       only 3 of 6 columns
 │ - created_at      │
 └──────────────────┘
```

## Alembic's role

Alembic **only cares about `models.py`**. When you run `alembic revision --autogenerate`, it diffs your `Base.metadata` (all model classes) against the live DB and generates a migration script. It never touches `schemas.py`.

## Inspecting the DB

Alembic is strictly a migration tool — it has no commands for querying rows or inspecting table definitions.

**Options for inspecting the DB:**

1. **`psql`** — the standard choice
   ```bash
   psql -h localhost -U mabinogi -d mabinogi
   \d listings          -- column definitions
   SELECT * FROM listings LIMIT 5;
   ```

2. **SQLAlchemy in a Python shell** — uses your existing models
   ```bash
   cd backend && python3 -c "
   from db.session import SessionLocal
   from db import models
   db = SessionLocal()
   print([c.name for c in models.Listing.__table__.columns])
   print(db.query(models.Listing).first().__dict__)
   "
   ```

3. **`alembic current`** / **`alembic history`** — only tells you which migrations have run, not table contents

## Example: listing_reforge_options columns

From `backend/db/models.py` (`ListingReforgeOption`):

| Column | Type | Notes |
|---|---|---|
| `id` | Integer | PK |
| `listing_id` | Integer | FK → listings.id (CASCADE) |
| `reforge_option_id` | Integer | FK → reforge_options.id (nullable) |
| `option_name` | Text | The reforge name |
| `level` | Integer | nullable |
| `max_level` | Integer | nullable |
| `created_at` | DateTime | auto |
