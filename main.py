from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import stripe
import httpx
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import json

# Load environment variables
load_dotenv()

app = FastAPI()

# templates and static files
templates = Jinja2Templates(directory="templates")


# Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

# Kintsugi API configuration
KINTSUGI_API_URL = "https://api.trykintsugi.com/v1/tax/estimate"
KINTSUGI_HEADERS = {
    "X-API-KEY": os.getenv('KINTSUGI_API_KEY'),
    "x-organization-id": os.getenv('KINTSUGI_ORG_ID'),
    "Content-Type": "application/json"
}

# Constants
SUBSCRIPTION_PRICE_ID = "price_1QxU7SFjcd67I34X3X5XaHo0"  
BASE_PRICE = 1000 

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stripe_public_key": os.getenv('STRIPE_PUBLISHABLE_KEY')}
    )

async def get_tax_estimate(amount: int):
    # current UTC time
    current_utc = datetime.now(timezone.utc)
    
    tax_request_data = {
        "date": current_utc.isoformat(),
        "external_id": f"est_{int(current_utc.timestamp())}",
        "total_amount": amount,
        "currency": "USD",
        "customer": {
            "street_1": "10 1/2nd Street, East",
            "city": "Houston",
            "state": "TX",
            "postal_code": "77008",
            "country": "US"
        },
        "addresses": [
            {
                "type": "SHIP_TO",
                "street_1": "10 1/2nd Street, East",
                "city": "Houston",
                "state": "TX",
                "postal_code": "77008",
                "country": "US"
            }
        ],
        "transaction_items": [
            {
                "external_product_id": "prod_RrCWtJMg5ktz14",
                "date": current_utc.isoformat(),
                "product_name": "Form Subscription",
                "amount": amount,
                "quantity": 1
            }
        ],
        "simulate_active_registration": False
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            KINTSUGI_API_URL,
            headers=KINTSUGI_HEADERS,
            json=tax_request_data
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to calculate tax")
        
        tax_data = response.json()
        
        taxable_amount = float(tax_data.get('taxable_amount', amount))  
        tax_rate = float(tax_data.get('tax_rate_calculated', 0))      
        
        
        calculated_tax = taxable_amount * tax_rate  
        effective_tax_rate = round((calculated_tax / amount) * 100, 2) 
        
        tax_description = []
        # Build tax description from individual tax components
        for item in tax_data.get('transaction_items', []):
            for tax_item in item.get('tax_items', []):
                tax_description.append(f"{tax_item['name']}: ${float(tax_item['amount']):.2f}")
        
        return {
            'tax_rate': effective_tax_rate, 
            'tax_description': ' + '.join(tax_description)
        }

@app.post("/create-checkout-session")
async def create_checkout_session():
    try:
        # Get tax estimate
        tax_info = await get_tax_estimate(BASE_PRICE)
        
        # tax rate in Stripe
        tax_rate = stripe.TaxRate.create(
            display_name="Sales Tax",
            description=tax_info['tax_description'],
            percentage=tax_info['tax_rate'],
            inclusive=False,
            country='US',
            jurisdiction='TX',
        )

        # checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': SUBSCRIPTION_PRICE_ID,
                'quantity': 1,
                'tax_rates': [tax_rate.id],
            }],
            mode='subscription',
            success_url=os.getenv('DOMAIN') + '/success',
            cancel_url=os.getenv('DOMAIN') + '/cancel',
            customer_email=None,  
            billing_address_collection='auto',  
            shipping_address_collection={
                'allowed_countries': ['US']  # Restrict to US addresses
            },
            automatic_tax={
                'enabled': False  # We're using manual tax calculation via Kintsugi
            },
            tax_id_collection={
                'enabled': False 
            },
            metadata={
                'tax_jurisdiction': 'TX',
                'tax_calculation': 'kintsugi'
            }
        )
        
        return {"id": checkout_session.id}
        
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/success")
async def success(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/cancel")
async def cancel(request: Request):
    return templates.TemplateResponse("cancel.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
