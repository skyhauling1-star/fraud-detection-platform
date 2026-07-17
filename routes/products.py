from pydantic import ValidationError

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from database import get_connection
from models import ProductCreate, ProductUpdate

templates = Jinja2Templates(directory="templates")
router = APIRouter(prefix="/products", tags=["products"])


def _load_products():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name, price, stock_quantity, created_at, updated_at
            FROM products
            ORDER BY id DESC
            """
        ).fetchall()


def _first_validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    field = " ".join(str(part) for part in first_error.get("loc", [])).replace("_", " ").strip()
    message = first_error.get("msg", "Invalid value")
    if field:
        return f"{field.title()}: {message}."
    return f"{message}."


@router.get("")
def list_products(request: Request):
    products = _load_products()

    return templates.TemplateResponse(
        "products.html",
        {
            "request": request,
            "products": products,
            "error": None,
        },
    )


@router.post("")
def add_product(
    request: Request,
    name: str = Form(...),
    price: str = Form(...),
    stock_quantity: str = Form(...),
):
    try:
        payload = ProductCreate(
            name=name.strip(),
            price=price,
            stock_quantity=stock_quantity,
        )
    except ValidationError as exc:
        products = _load_products()
        return templates.TemplateResponse(
            "products.html",
            {
                "request": request,
                "products": products,
                "error": _first_validation_error_message(exc),
            },
            status_code=400,
        )

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO products (name, price, stock_quantity)
            VALUES (?, ?, ?)
            """,
            (payload.name, payload.price, payload.stock_quantity),
        )
        conn.commit()

    return RedirectResponse(url="/products", status_code=303)


@router.get("/{product_id}/edit")
def edit_product_page(request: Request, product_id: int):
    with get_connection() as conn:
        product = conn.execute(
            """
            SELECT id, name, price, stock_quantity, created_at, updated_at
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    return templates.TemplateResponse(
        "product_edit.html",
        {
            "request": request,
            "product": product,
            "error": None,
        },
    )


@router.post("/{product_id}/edit")
def edit_product(
    request: Request,
    product_id: int,
    name: str = Form(...),
    price: str = Form(...),
    stock_quantity: str = Form(...),
):
    with get_connection() as conn:
        existing_product = conn.execute(
            """
            SELECT id, name, price, stock_quantity, created_at, updated_at
            FROM products
            WHERE id = ?
            """,
            (product_id,),
        ).fetchone()

    if existing_product is None:
        raise HTTPException(status_code=404, detail="Product not found.")

    try:
        payload = ProductUpdate(
            name=name.strip(),
            price=price,
            stock_quantity=stock_quantity,
        )
    except ValidationError as exc:
        product_for_form = dict(existing_product)
        product_for_form["name"] = name.strip()
        product_for_form["price"] = price
        product_for_form["stock_quantity"] = stock_quantity

        return templates.TemplateResponse(
            "product_edit.html",
            {
                "request": request,
                "product": product_for_form,
                "error": _first_validation_error_message(exc),
            },
            status_code=400,
        )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE products
            SET name = ?,
                price = ?,
                stock_quantity = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.name, payload.price, payload.stock_quantity, product_id),
        )
        conn.commit()

    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Product not found.")

    return RedirectResponse(url="/products", status_code=303)
