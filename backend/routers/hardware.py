"""Hardware CRUD router for Hardware Hub.

Exposes three endpoints that cover the full lifecycle of a hardware item:

* ``GET  /api/hardware``       — paginated list with optional filter / sort.
* ``POST /api/hardware``       — register a new hardware item (admin only).
* ``PUT  /api/hardware/{id}``  — partial update, including toggling the
                                 ``'Repair'`` status flag (admin only).

Admin-only enforcement is lightweight for the MVP: endpoints accept an
``X-User-Role`` request header and reject non-admin callers with HTTP 403.
A proper RBAC layer backed by JWT claims should replace this in production.
"""

from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Hardware
from backend.schemas import HardwareCreate, HardwareRead, HardwareUpdate

router: APIRouter = APIRouter(prefix="/api/hardware", tags=["Hardware"])

_VALID_STATUSES: frozenset[str] = frozenset({"Available", "In Use", "Repair"})
_SORTABLE_FIELDS: frozenset[str] = frozenset({"id", "name", "brand", "purchase_date", "status"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _require_admin(x_user_role: str | None) -> None:
    """Raise HTTP 403 if the caller is not an admin.

    Args:
        x_user_role: Value of the ``X-User-Role`` request header.

    Raises:
        HTTPException (403): If the header is missing or not ``'admin'``.
    """
    if x_user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this operation.",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=list[HardwareRead],
    summary="List hardware items",
)
def list_hardware(
    db: Session = Depends(get_db),
    filter_status: Literal["Available", "In Use", "Repair"] | None = Query(
        default=None,
        alias="status",
        description="Filter by hardware status.",
    ),
    brand: str | None = Query(
        default=None, description="Filter by brand name (case-insensitive, partial match)."
    ),
    name: str | None = Query(
        default=None, description="Filter by device name (case-insensitive, partial match)."
    ),
    sort_by: str = Query(
        default="id",
        description="Column to sort by. Allowed: id, name, brand, purchase_date, status.",
    ),
    order: Literal["asc", "desc"] = Query(default="asc", description="Sort direction."),
) -> list[Hardware]:
    """Return a filtered and sorted list of hardware items.

    All filter parameters are optional and combinable.

    Args:
        db: Injected SQLAlchemy session.
        filter_status: If provided, only items with this status are returned.
        brand: Case-insensitive partial match on the ``brand`` column.
        name: Case-insensitive partial match on the ``name`` column.
        sort_by: Column name to order results by.  Defaults to ``'id'``.
        order: ``'asc'`` (default) or ``'desc'``.

    Returns:
        List of :class:`~backend.schemas.HardwareRead` objects.

    Raises:
        HTTPException (400): If ``sort_by`` is not a recognised column name.
    """
    if sort_by not in _SORTABLE_FIELDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by value '{sort_by}'. Allowed: {sorted(_SORTABLE_FIELDS)}.",
        )

    query = db.query(Hardware)

    if filter_status is not None:
        query = query.filter(Hardware.status == filter_status)
    if brand is not None:
        query = query.filter(Hardware.brand.ilike(f"%{brand}%"))
    if name is not None:
        query = query.filter(Hardware.name.ilike(f"%{name}%"))

    sort_col = getattr(Hardware, sort_by)
    query = query.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    return query.all()


@router.post(
    "",
    response_model=HardwareRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new hardware item (admin only)",
)
def create_hardware(
    payload: HardwareCreate,
    db: Session = Depends(get_db),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> Hardware:
    """Create and persist a new hardware record.

    Args:
        payload: Validated :class:`~backend.schemas.HardwareCreate` body.
        db: Injected SQLAlchemy session.
        x_user_role: Value of the ``X-User-Role`` request header; must be
            ``'admin'``.

    Returns:
        The newly created :class:`~backend.schemas.HardwareRead` object.

    Raises:
        HTTPException (403): If caller is not an admin.
    """
    _require_admin(x_user_role)

    hw: Hardware = Hardware(**payload.model_dump())
    db.add(hw)
    db.commit()
    db.refresh(hw)
    return hw


@router.put(
    "/{hardware_id}",
    response_model=HardwareRead,
    summary="Update hardware / toggle Repair status (admin only)",
)
def update_hardware(
    hardware_id: int,
    payload: HardwareUpdate,
    db: Session = Depends(get_db),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> Hardware:
    """Partially update a hardware item's fields.

    Accepts any subset of hardware fields; only supplied (non-``None``) values
    are written.  This endpoint is the intended mechanism for an admin to
    toggle an item between ``'Available'`` and ``'Repair'``.

    Args:
        hardware_id: Primary key of the hardware item to update.
        payload: Partial update body; only non-``None`` fields are applied.
        db: Injected SQLAlchemy session.
        x_user_role: Value of the ``X-User-Role`` request header; must be
            ``'admin'``.

    Returns:
        The updated :class:`~backend.schemas.HardwareRead` object.

    Raises:
        HTTPException (403): If caller is not an admin.
        HTTPException (404): If no hardware item with ``hardware_id`` exists.
    """
    _require_admin(x_user_role)

    hw: Hardware | None = db.get(Hardware, hardware_id)
    if hw is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hardware with id={hardware_id} not found.",
        )

    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(hw, field, value)

    db.commit()
    db.refresh(hw)
    return hw
