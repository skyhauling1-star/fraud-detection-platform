from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from database import get_connection, init_db
from routes.debts import router as debts_router
from routes.products import router as products_router
from routes.sales import router as sales_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Shop Inventory & Debt Tracker", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


@app.get("/")
def dashboard(request: Request):
    with get_connection() as conn:
        today_sales_row = conn.execute(
            """
            SELECT COALESCE(SUM(total_amount), 0) AS today_total_sales
            FROM sales
            WHERE DATE(created_at, 'localtime') = DATE('now', 'localtime')
            """
        ).fetchone()

        debt_row = conn.execute(
            """
            SELECT COALESCE(SUM(amount_owed), 0) AS total_outstanding_debt
            FROM debts
            """
        ).fetchone()

        low_stock_products = conn.execute(
            """
            SELECT id, name, stock_quantity, price
            FROM products
            WHERE stock_quantity < 5
            ORDER BY stock_quantity ASC, name ASC
            """
        ).fetchall()

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "today_total_sales": round(float(today_sales_row["today_total_sales"]), 2),
            "total_outstanding_debt": round(float(debt_row["total_outstanding_debt"]), 2),
            "low_stock_products": low_stock_products,
        },
    )


app.include_router(products_router)
app.include_router(sales_router)
app.include_router(debts_router)
