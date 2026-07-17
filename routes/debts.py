from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/debts", tags=["debts"])


def _load_debts():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, customer_name, customer_phone, amount_owed, created_at, updated_at
            FROM debts
            ORDER BY amount_owed DESC, updated_at DESC
            """
        ).fetchall()


def _render_debts_page(
    request: Request,
    error: Optional[str] = None,
):
    return templates.TemplateResponse(
        "debts.html",
        {
            "request": request,
            "debts": _load_debts(),
            "error": error,
            "success": request.query_params.get("success"),
        },
        status_code=400 if error else 200,
    )


@router.get("")
def list_debts(request: Request):
    return _render_debts_page(request=request)


@router.post("/{debt_id}/pay")
def mark_debt_paid(
    request: Request,
    debt_id: int,
    amount_paid: str = Form(...),
):
    try:
        payment = float(amount_paid)
    except ValueError:
        return _render_debts_page(request=request, error="Payment amount must be a number.")

    if payment <= 0:
        return _render_debts_page(request=request, error="Payment amount must be greater than zero.")

    with get_connection() as conn:
        debt = conn.execute(
            """
            SELECT id, amount_owed
            FROM debts
            WHERE id = ?
            """,
            (debt_id,),
        ).fetchone()

        if debt is None:
            raise HTTPException(status_code=404, detail="Debt not found.")

        current_owed = float(debt["amount_owed"])
        if current_owed <= 0:
            return _render_debts_page(request=request, error="This debt is already fully paid.")

        new_owed = current_owed - payment
        if new_owed < -0.01:
            return _render_debts_page(
                request=request,
                error="Payment cannot be greater than amount owed.",
            )

        # Round to 2 decimals for currency values to avoid floating-point artifacts.
        new_owed = round(new_owed, 2)
        if new_owed <= 0.01:
            new_owed = 0.0

        conn.execute(
            """
            UPDATE debts
            SET amount_owed = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_owed, debt_id),
        )
        conn.commit()

    if new_owed <= 0.01:
        return RedirectResponse(url="/debts?success=Debt+fully+paid", status_code=303)

    return RedirectResponse(url="/debts?success=Partial+payment+recorded", status_code=303)
