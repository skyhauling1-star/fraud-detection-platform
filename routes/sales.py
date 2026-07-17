from typing import Optional

from pydantic import ValidationError

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection
from models import SaleCreate

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/sales", tags=["sales"])


def _normalize_customer_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    normalized = name.strip().lower()
    return normalized or None


def _load_products():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name, price, stock_quantity
            FROM products
            ORDER BY name ASC
            """
        ).fetchall()


def _load_recent_sales():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                s.id,
                s.product_id,
                p.name AS product_name,
                s.quantity,
                s.unit_price,
                s.total_amount,
                s.payment_type,
                s.customer_name,
                s.customer_phone,
                s.debt_id,
                s.created_at
            FROM sales s
            JOIN products p ON p.id = s.product_id
            ORDER BY s.id DESC
            LIMIT 20
            """
        ).fetchall()


def _first_validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    field = " ".join(str(part) for part in first_error.get("loc", [])).replace("_", " ").strip()
    message = first_error.get("msg", "Invalid value")
    if field:
        return f"{field.title()}: {message}."
    return f"{message}."


def _render_sales_page(
    request: Request,
    error: Optional[str] = None,
    form_data: Optional[dict] = None,
):
    return templates.TemplateResponse(
        "sales.html",
        {
            "request": request,
            "products": _load_products(),
            "recent_sales": _load_recent_sales(),
            "error": error,
            "success": request.query_params.get("success"),
            "form_data": form_data or {},
        },
        status_code=400 if error else 200,
    )


@router.get("")
def sales_page(request: Request):
    return _render_sales_page(request=request)


@router.post("")
def record_sale(
    request: Request,
    product_id: str = Form(...),
    quantity: str = Form(...),
    payment_type: str = Form(...),
    customer_name: Optional[str] = Form(default=None),
    customer_phone: Optional[str] = Form(default=None),
):
    clean_name = (customer_name or "").strip() or None
    normalized_name = _normalize_customer_name(clean_name)
    clean_phone = (customer_phone or "").strip() or None

    try:
        payload = SaleCreate(
            product_id=product_id,
            quantity=quantity,
            payment_type=payment_type,
            customer_name=clean_name,
            customer_phone=clean_phone,
        )
    except ValidationError as exc:
        return _render_sales_page(
            request=request,
            error=_first_validation_error_message(exc),
            form_data={
                "product_id": product_id,
                "quantity": quantity,
                "payment_type": payment_type,
                "customer_name": clean_name or "",
                "customer_phone": clean_phone or "",
            },
        )

    if payload.payment_type == "credit" and not payload.customer_name:
        return _render_sales_page(
            request=request,
            error="Customer name is required for credit sales.",
            form_data={
                "product_id": payload.product_id,
                "quantity": payload.quantity,
                "payment_type": payload.payment_type,
                "customer_name": payload.customer_name or "",
                "customer_phone": payload.customer_phone or "",
            },
        )

    with get_connection() as conn:
        product = conn.execute(
            """
            SELECT id, name, price, stock_quantity
            FROM products
            WHERE id = ?
            """,
            (payload.product_id,),
        ).fetchone()

        if product is None:
            return _render_sales_page(
                request=request,
                error="Selected product does not exist.",
                form_data={
                    "product_id": payload.product_id,
                    "quantity": payload.quantity,
                    "payment_type": payload.payment_type,
                    "customer_name": payload.customer_name or "",
                    "customer_phone": payload.customer_phone or "",
                },
            )

        if product["stock_quantity"] < payload.quantity:
            return _render_sales_page(
                request=request,
                error="Insufficient stock for this sale.",
                form_data={
                    "product_id": payload.product_id,
                    "quantity": payload.quantity,
                    "payment_type": payload.payment_type,
                    "customer_name": payload.customer_name or "",
                    "customer_phone": payload.customer_phone or "",
                },
            )

        unit_price = float(product["price"])
        total_amount = unit_price * payload.quantity
        debt_id = None

        if payload.payment_type == "credit":
            debt = conn.execute(
                """
                SELECT id, amount_owed
                FROM debts
                WHERE customer_name = ?
                  AND ((customer_phone IS NULL AND ? IS NULL) OR customer_phone = ?)
                LIMIT 1
                """,
                (normalized_name, payload.customer_phone, payload.customer_phone),
            ).fetchone()

            if debt is None:
                cursor = conn.execute(
                    """
                    INSERT INTO debts (customer_name, customer_phone, amount_owed)
                    VALUES (?, ?, ?)
                    """,
                    (normalized_name, payload.customer_phone, total_amount),
                )
                debt_id = cursor.lastrowid
            else:
                debt_id = debt["id"]
                conn.execute(
                    """
                    UPDATE debts
                    SET amount_owed = amount_owed + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (total_amount, debt_id),
                )

        conn.execute(
            """
            INSERT INTO sales (
                product_id,
                debt_id,
                quantity,
                unit_price,
                total_amount,
                payment_type,
                customer_name,
                customer_phone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.product_id,
                debt_id,
                payload.quantity,
                unit_price,
                total_amount,
                payload.payment_type,
                clean_name,
                payload.customer_phone,
            ),
        )

        conn.execute(
            """
            UPDATE products
            SET stock_quantity = stock_quantity - ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.quantity, payload.product_id),
        )

        conn.commit()

    return RedirectResponse(url="/sales?success=Sale+recorded+successfully", status_code=303)
