# Subscription-Based Checkout with Kintsugi Tax API

This project implements a subscription-based checkout system using Stripe Checkout and Kintsugi's Tax API for dynamic tax calculation.

## Setup

1. Copy `.env.example` to `.env` and fill in your credentials:
   ```
   cp .env.example .env
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your Stripe subscription product and price:
   - Create a product in your Stripe dashboard
   - Create a recurring price for the product
   - Update the `SUBSCRIPTION_PRICE_ID` in `main.py` with your price ID

4. Run the application:
   ```
   uvicorn main:app --reload
   ```

5. Visit http://localhost:8000 to test the checkout flow

