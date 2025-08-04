from fastapi import FastAPI, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import uuid
import logging
from typing import Optional
from auth import SelcomClient
import httpx

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("SELCOM_API_KEY")
API_SECRET = os.getenv("SELCOM_API_SECRET")
BASE_URL = os.getenv("SELCOM_BASE_URL")
VENDOR_ID = os.getenv("SELCOM_VENDOR_ID")
VENDOR_PIN = os.getenv("SELCOM_VENDOR_PIN")
C2B_BEARER_TOKEN = os.getenv("C2B_BEARER_TOKEN")

if not all([API_KEY, API_SECRET, BASE_URL, VENDOR_ID, VENDOR_PIN, C2B_BEARER_TOKEN]):
    raise ValueError("Missing one or more required environment variables.")

selcom_client = SelcomClient(api_key=API_KEY, api_secret=API_SECRET, base_url=BASE_URL)

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

async def verify_c2b_token(authorization: Optional[str] = Header(None)):
    if authorization is None or authorization != f"Bearer {C2B_BEARER_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized: Invalid C2B Bearer Token")
    return authorization

@app.get("/b2c/balance", response_model=SelcomResponse)
async def get_float_balance():
    transid = str(uuid.uuid4())
    data = {
        "vendor": VENDOR_ID,
        "pin": VENDOR_PIN,
        "transid": transid
    }
    response = await selcom_client.get(path="/v1/vendor/balance", params=data)
    response.raise_for_status()
    return response.json()

@app.post("/b2c/wallet-cashin")
async def wallet_cashin(request: B2CWalletCashinRequest):
    transid = str(uuid.uuid4())
    payment_payload = {
        "transid": transid,
        "utilitycode": request.utilitycode,
        "utilityref": request.utilityref,
        "amount": request.amount,
        "vendor": VENDOR_ID,
        "pin": VENDOR_PIN,
        "msisdn": request.msisdn,
    }
    try:
        response = await selcom_client.post(path="/v1/walletcashin/process", data=payment_payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Selcom API error: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())

@app.get("/b2c/query-status", response_model=SelcomResponse)
async def query_b2c_status(transid: str):
    params = {"transid": transid}
    response = await selcom_client.get(path="/v1/walletcashin/query", params=params)
    response.raise_for_status()
    return response.json()

@app.post("/c2b/lookup", response_model=C2BResponse)
async def c2b_lookup(payload: C2BLookupPayload, auth_header: str = Depends(verify_c2b_token)):
    logger.info(f"C2B Lookup request received: {payload.dict()}")
    if payload.utilityref == "INVALID_REF":
        return C2BResponse(
            reference=payload.reference,
            resultcode="010",
            result="FAIL",
            message="Invalid account or payment reference"
        )
    return C2BResponse(
        reference=payload.reference,
        resultcode="000",
        result="SUCCESS",
        message="Payment reference is valid",
        name="John Doe",
        amount=1000.00
    )

@app.post("/c2b/validation", response_model=C2BResponse)
async def c2b_validation(payload: C2BValidationPayload, auth_header: str = Depends(verify_c2b_token)):
    logger.info(f"C2B Validation request received: {payload.dict()}")
    return C2BResponse(
        reference=payload.reference,
        resultcode="000",
        result="SUCCESS",
        message="Payment is valid"
    )

@app.post("/c2b/notification", response_model=C2BResponse)
async def c2b_notification(payload: C2BValidationPayload, auth_header: str = Depends(verify_c2b_token)):
    logger.info(f"C2B Notification received: {payload.dict()}")
    return C2BResponse(
        reference=payload.reference,
        resultcode="000",
        result="SUCCESS",
        message="Payment has been successfully posted"
    )

@app.post("/wallet/push-ussd", response_model=SelcomPushUssdResponse)
async def push_ussd_payment(request: PushUssdRequest):
    transid = str(uuid.uuid4())
    payload = {
        "transid": transid,
        "utilityref": request.utilityref,
        "amount": request.amount,
        "vendor": VENDOR_ID,
        "pin": VENDOR_PIN,
        "msisdn": request.msisdn,
    }
    try:
        response = await selcom_client.post(path="/v1/wallet/pushussd", data=payload)
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"Push USSD successful for transid: {transid}, Selcom reference: {response_data.get('reference')}")
        return response_data
    except httpx.HTTPStatusError as e:
        logger.error(f"Selcom API error during Push USSD: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())

@app.get("/c2b/query-status", response_model=SelcomQueryStatusResponse)
async def query_c2b_status(transid: Optional[str] = None, reference: Optional[str] = None):
    if not transid and not reference:
        raise HTTPException(status_code=400, detail="Either 'transid' or 'reference' must be provided.")
    params = {}
    if transid:
        params["transid"] = transid
    if reference:
        params["reference"] = reference
    try:
        response = await selcom_client.get(path="/v1/c2b/query-status", params=params)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Selcom API error during C2B status query: {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.json())

@app.get("/")
async def root():
    return {"message": "Selcom Integration API is running"}