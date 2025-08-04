from fastapi import FastAPI, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import uuid
import logging
from typing import Optional
import httpx
from selcom_apigw_client import apigwClient

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', handlers=[
    logging.FileHandler("app.log"),
    logging.StreamHandler()
])
logger = logging.getLogger(__name__)

API_KEY = os.getenv("SELCOM_API_KEY")
API_SECRET = os.getenv("SELCOM_API_SECRET")
BASE_URL = os.getenv("SELCOM_BASE_URL")
VENDOR_ID = os.getenv("SELCOM_VENDOR_ID")
VENDOR_PIN = os.getenv("SELCOM_VENDOR_PIN")
C2B_BEARER_TOKEN = os.getenv("C2B_BEARER_TOKEN")

if not all([API_KEY, API_SECRET, BASE_URL, VENDOR_ID, VENDOR_PIN, C2B_BEARER_TOKEN]):
    raise ValueError("Missing one or more required environment variables.")

# Initialize Selcom API client using official library
client = apigwClient.Client(baseUrl=BASE_URL, apiKey=API_KEY, apiSecret=API_SECRET)

app = FastAPI(
    title="Selcom Integration API",
    description="A FastAPI application to handle Selcom B2C and C2B payments.",
    version="1.0.0"
)

class B2CWalletCashinRequest(BaseModel):
    utilitycode: str
    utilityref: str
    amount: float
    msisdn: str

class QueryStatusRequest(BaseModel):
    transid: str

class SelcomResponse(BaseModel):
    transid: str
    reference: str
    resultcode: str
    result: str
    message: str
    data: list

class C2BLookupPayload(BaseModel):
    operator: str
    transid: str
    reference: str
    utilityref: str
    msisdn: str

class C2BValidationPayload(BaseModel):
    operator: str
    transid: str
    reference: str
    utilityref: str
    amount: float
    msisdn: str

class C2BResponse(BaseModel):
    reference: str
    resultcode: str
    result: str
    message: str
    name: Optional[str] = None
    amount: Optional[float] = None

class PushUssdRequest(BaseModel):
    utilityref: str
    amount: float
    msisdn: str

class SelcomPushUssdResponse(BaseModel):
    transid: str
    reference: str
    resultcode: str
    result: str
    message: str
    data: Optional[list] = None

class SelcomQueryStatusResponse(BaseModel):
    transid: Optional[str] = None
    reference: Optional[str] = None
    resultcode: Optional[str] = None
    result: Optional[str] = None
    message: Optional[str] = None
    data: Optional[list] = None

class CreateOrderMinimalRequest(BaseModel):
    order_id: str
    buyer_email: str
    buyer_name: str
    buyer_phone: str
    amount: float
    currency: str = "TZS"
    buyer_remarks: Optional[str] = "None"
    merchant_remarks: Optional[str] = "None"
    no_of_items: int = 1

class CreateOrderMinimalResponse(BaseModel):
    status: str
    statusDesc: str
    reference: Optional[str] = None
    paymentGatewayUrl: Optional[str] = None
    order_id: Optional[str] = None

class PaymentWebhookRequest(BaseModel):
    transid: str
    reference: str
    order_id: str
    result: str
    resultcode: str
    payment_status: str

async def verify_c2b_token(authorization: Optional[str] = Header(None)):
    if authorization is None or authorization != f"Bearer {C2B_BEARER_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid C2B Bearer Token")
    return authorization

@app.post("/checkout/create-order-minimal", response_model=CreateOrderMinimalResponse)
def create_order_minimal(request: CreateOrderMinimalRequest):
    try:
        order_payload = {
            "vendor": VENDOR_ID,
            "order_id": request.order_id,
            "buyer_email": request.buyer_email,
            "buyer_name": request.buyer_name,
            "buyer_phone": request.buyer_phone,
            "amount": request.amount,
            "currency": request.currency,
            "buyer_remarks": request.buyer_remarks,
            "merchant_remarks": request.merchant_remarks,
            "no_of_items": request.no_of_items
        }
        order_path = "/v1/checkout/create-order-minimal"
        response_data = client.postFunc(order_path, order_payload)
        result_code = response_data.get("result")
        if result_code == "SUCCESS":
            payment_gateway_url = response_data.get("data", [{}])[0].get("payment_gateway_url", "none")
            reference = response_data.get("reference")
            wallet_payment_payload = {
                "transid": reference,
                "order_id": request.order_id,
                "msisdn": request.buyer_phone
            }
            wallet_payment_path = "/v1/checkout/wallet-payment"
            client.postFunc(wallet_payment_path, wallet_payment_payload)
            return CreateOrderMinimalResponse(
                status="200",
                statusDesc=result_code,
                reference=reference,
                paymentGatewayUrl=payment_gateway_url,
                order_id=request.order_id
            )
        else:
            return CreateOrderMinimalResponse(
                status="201",
                statusDesc=result_code
            )
    except Exception as e:
        logger.error(f"Error in /checkout/create-order-minimal: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/logs")
def get_logs(lines: int = 100):
    """
    Returns the last N lines from the application log file.
    """
    try:
        log_file = "app.log"
        if not os.path.exists(log_file):
            return {"error": "Log file not found."}
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        last_lines = all_lines[-lines:] if lines > 0 else all_lines
        return {"logs": [line.rstrip() for line in last_lines]}
    except Exception as e:
        logger.error(f"Error in /logs endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")