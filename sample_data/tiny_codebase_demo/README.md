# Tiny Codebase Demo

Small Flask-style workspace for testing Weave **Codebase / Workspace** fabrics.

## Contents

- `app/main.py` — API routes (`/health`, `/orders/...`)
- `app/orders.py` — domain `Order` / `OrderService`
- `app/billing.py` — external billing client
- `requirements.txt` — Flask dependency marker

## How to test

1. Zip this folder, **or** use **Upload folder** in Weave
2. Create Knowledge → **Codebase / Workspace**
3. Name: `Tiny Codebase Demo`
4. Migration goal (optional): `Monolith Flask API → separate Orders and Billing services`
5. Analyze → open graph → download migration JSON
