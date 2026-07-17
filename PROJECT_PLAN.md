# Shop Inventory & Debt Tracker

## Purpose
Help small shop/kiosk owners in Nigeria track inventory, sales, and customer debt (credit sales) — replacing paper notebooks.

## v1 Features
1. Add/edit products (name, price, stock quantity)
2. Record a sale (cash or credit)
3. Track customer debts (name, phone, amount owed)
4. Mark debt as paid (full or partial)
5. Dashboard: today's sales, total outstanding debt, low-stock alerts

## Out of scope for v1
- Multi-user accounts
- SMS reminders
- Multiple branches
- Analytics/reports
- Barcode scanning

## Tech stack
- Backend: Python + FastAPI
- Database: SQLite
- Frontend: HTML templates + Tailwind CSS
- Deploy: Render.com (free tier) — later