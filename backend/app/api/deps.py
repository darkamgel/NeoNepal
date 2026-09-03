"""Shared FastAPI route helpers."""

from fastapi import HTTPException
from sqlalchemy.orm import Session


def get_or_404(db: Session, model, obj_id: int, not_found_detail: str):
    """Fetch `model` by primary key or raise a 404 with `not_found_detail`.
    Was previously copy-pasted (query -> if not found -> raise) in every
    route that looks up a Watershed or Glacier by id.
    """
    obj = db.query(model).filter(model.id == obj_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail=not_found_detail)
    return obj
