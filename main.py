from fastapi import FastAPI, HTTPException, Request, Header, Depends
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import uuid
import logging
from typing import Optional, List, Dict, Any
import httpx
from selcom_apigw_client import apigwClient
import datetime
import base64
import hashlib
import hmac
import asyncio
import json
from fastapi import status

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

# --- Dependency for C2B Webhook Authentication ---
async def verify_c2b_token(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith("Bearer ") or authorization.split(" ")[1] != C2B_BEARER_TOKEN:
        logger.warning("Unauthorized C2B webhook access attempt.")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized: Invalid C2B Bearer Token")
    return authorization

# --- Pydantic Models for API Requests and Responses ---
class SelcomGenericResponse(BaseModel):
    reference: Optional[str] = None
    resultcode: Optional[str] = None
    result: Optional[str] = None
    message: Optional[str] = None
    data: Optional[Any] = None

class CreateOrderMinimalRequest(BaseModel):
    vendor: Optional[str] = None
    order_id: str
    buyer_email: str
    buyer_name: str
    buyer_phone: str
    amount: int
    currency: str = "TZS"
    redirect_url: Optional[str] = None
    cancel_url: Optional[str] = None
    webhook: Optional[str] = None
    buyer_remarks: Optional[str] = None
    merchant_remarks: Optional[str] = None
    no_of_items: int = 1
    header_colour: Optional[str] = None
    link_colour: Optional[str] = None
    button_colour: Optional[str] = None
    expiry: Optional[int] = None

class CreateOrderMinimalResponseData(BaseModel):
    gateway_buyer_uuid: Optional[str] = None
    payment_token: Optional[str] = None
    qr: Optional[str] = None
    payment_gateway_url: Optional[str] = None

class CreateOrderMinimalApiResponse(SelcomGenericResponse):
    data: Optional[List[CreateOrderMinimalResponseData]] = None

class CancelOrderRequest(BaseModel):
    order_id: str

class GetOrderStatusRequest(BaseModel):
    order_id: str

class GetOrderStatusResponseData(BaseModel):
    order_id: str
    creation_date: str
    amount: str
    payment_status: str
    transid: Optional[str] = None
    channel: Optional[str] = None
    reference: Optional[str] = None
    msisdn: Optional[str] = None

class GetOrderStatusApiResponse(SelcomGenericResponse):
    data: Optional[List[GetOrderStatusResponseData]] = None

class ListAllOrdersRequest(BaseModel):
    fromdate: str
    todate: str

class ListAllOrdersResponseData(BaseModel):
    order_id: str
    creation_date: str
    amount: str
    payment_status: str
    result: Optional[str] = None

class ListAllOrdersApiResponse(SelcomGenericResponse):
    data: Optional[List[ListAllOrdersResponseData]] = None

class FetchStoredCardTokensRequest(BaseModel):
    buyer_userid: str
    gateway_buyer_uuid: str

class FetchStoredCardTokensResponseData(BaseModel):
    masked_card: str
    creation_date: str
    card_token: str
    name: str
    card_type: str
    id: Optional[str] = None

class FetchStoredCardTokensApiResponse(SelcomGenericResponse):
    data: Optional[List[FetchStoredCardTokensResponseData]] = None

class DeleteStoredCardRequest(BaseModel):
    id: str
    gateway_buyer_uuid: str

class ProcessCardPaymentRequest(BaseModel):
    transid: str
    vendor: Optional[str] = None
    order_id: str
    card_token: str
    buyer_userid: Optional[str] = None
    gateway_buyer_uuid: str

class ProcessWalletPullPaymentRequest(BaseModel):
    transid: str
    order_id: str
    msisdn: str

class ProcessSelcomPesaPullPaymentRequest(BaseModel):
    transid: str
    order_id: str
    msisdn: str

class CreateTillAliasRequest(BaseModel):
    vendor: Optional[str] = None
    name: str
    memo: str

class CreateTillAliasResponseData(BaseModel):
    till_alias: str

class CreateTillAliasApiResponse(SelcomGenericResponse):
    data: Optional[List[CreateTillAliasResponseData]] = None

class WebhookPaymentStatusRequest(BaseModel):
    result: str
    resultcode: str
    order_id: str
    transid: str
    reference: str
    channel: Optional[str] = None
    amount: Optional[str] = None
    phone: Optional[str] = None
    payment_status: str

class BillingInfo(BaseModel):
    firstname: str
    lastname: str
    address_1: str
    address_2: Optional[str] = None
    city: str
    state_or_region: str
    postcode_or_pobox: str
    country: str
    phone: str

class CreateOrderRequest(BaseModel):
    vendor: Optional[str] = None
    order_id: str
    buyer_email: str
    buyer_name: str
    buyer_phone: str
    amount: int
    currency: str = "TZS"
    payment_methods: str = "ALL"
    no_of_items: int
    billing: BillingInfo

class CreateOrderApiResponse(SelcomGenericResponse):
    data: Optional[List[CreateOrderMinimalResponseData]] = None

# --- FastAPI Routes ---
@app.post("/checkout/create-order-minimal", response_model=CreateOrderMinimalApiResponse)
async def create_order_minimal_route(request_payload: CreateOrderMinimalRequest):
    logger.info(f"Received request to create order: {request_payload.order_id}")
    order_path = "/v1/checkout/create-order-minimal"
    order_payload = request_payload.model_dump(exclude_unset=True)
    order_payload["vendor"] = VENDOR_ID
    if isinstance(order_payload["amount"], float) and order_payload["amount"].is_integer():
        order_payload["amount"] = int(order_payload["amount"])
    if "buyer_remarks" not in order_payload or order_payload["buyer_remarks"] is None:
        order_payload["buyer_remarks"] = "None"
    if "merchant_remarks" not in order_payload or order_payload["merchant_remarks"] is None:
        order_payload["merchant_remarks"] = "None"
    try:
        response_data = await asyncio.to_thread(client.postFunc, order_path, order_payload)
        logger.info(f"Selcom API response for create-order-minimal: {response_data}")
        if response_data.get("result") == "SUCCESS":
            payment_gateway_url = response_data.get("data", [{}])[0].get("payment_gateway_url")
            if payment_gateway_url:
                try:
                    decoded_url = base64.b64decode(payment_gateway_url).decode('utf-8')
                    if response_data.get("data") and len(response_data["data"]) > 0:
                        response_data["data"][0]["payment_gateway_url"] = decoded_url
                except Exception as e:
                    logger.warning(f"Failed to decode payment_gateway_url: {payment_gateway_url}, Error: {e}")
            return CreateOrderMinimalApiResponse(**response_data)
        else:
            error_message = response_data.get("message", "Order creation failed at Selcom.")
            http_status_code = status.HTTP_400_BAD_REQUEST
            if response_data.get("resultcode") == "403":
                http_status_code = status.HTTP_401_UNAUTHORIZED
            elif response_data.get("resultcode") == "422":
                http_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=http_status_code, detail=error_message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/checkout/create-order", response_model=CreateOrderApiResponse)
async def create_order_route(request_payload: CreateOrderRequest):
    logger.info(f"Received request to create full order: {request_payload.order_id}")
    order_path = "/v1/checkout/create-order"
    order_payload = request_payload.model_dump(exclude_unset=True)
    order_payload["vendor"] = VENDOR_ID
    if isinstance(order_payload["amount"], float) and order_payload["amount"].is_integer():
        order_payload["amount"] = int(order_payload["amount"])
    billing_data = order_payload.pop("billing")
    for key, value in billing_data.items():
        order_payload[f"billing.{key}"] = value
    try:
        response_data = await asyncio.to_thread(client.postFunc, order_path, order_payload)
        logger.info(f"Selcom API response for create-order: {response_data}")
        if response_data.get("result") == "SUCCESS":
            payment_gateway_url = response_data.get("data", [{}])[0].get("payment_gateway_url")
            if payment_gateway_url:
                try:
                    decoded_url = base64.b64decode(payment_gateway_url).decode('utf-8')
                    if response_data.get("data") and len(response_data["data"]) > 0:
                        response_data["data"][0]["payment_gateway_url"] = decoded_url
                except Exception as e:
                    logger.warning(f"Failed to decode payment_gateway_url: {payment_gateway_url}, Error: {e}")
            return CreateOrderApiResponse(**response_data)
        else:
            error_message = response_data.get("message", "Order creation failed at Selcom.")
            http_status_code = status.HTTP_400_BAD_REQUEST
            if response_data.get("resultcode") == "403":
                http_status_code = status.HTTP_401_UNAUTHORIZED
            elif response_data.get("resultcode") == "422":
                http_status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
            raise HTTPException(status_code=http_status_code, detail=error_message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.delete("/checkout/cancel-order", response_model=SelcomGenericResponse)
async def cancel_order_route(request_payload: CancelOrderRequest):
    logger.info(f"Received request to cancel order: {request_payload.order_id}")
    cancel_path = "/v1/checkout/cancel-order"
    try:
        response_data = await asyncio.to_thread(client.deleteFunc, cancel_path, request_payload.model_dump())
        logger.info(f"Selcom API response for cancel-order: {response_data}")
        return SelcomGenericResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.get("/checkout/order-status", response_model=GetOrderStatusApiResponse)
async def get_order_status_route(order_id: str):
    logger.info(f"Received request to get status for order: {order_id}")
    status_path = "/v1/checkout/order-status"
    try:
        response_data = await asyncio.to_thread(client.getFunc, status_path, {"order_id": order_id})
        logger.info(f"Selcom API response for order-status: {response_data}")
        return GetOrderStatusApiResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.get("/checkout/list-orders", response_model=ListAllOrdersApiResponse)
async def list_all_orders_route(fromdate: str, todate: str):
    logger.info(f"Received request to list orders from {fromdate} to {todate}")
    list_path = "/v1/checkout/list-orders"
    try:
        response_data = await asyncio.to_thread(client.getFunc, list_path, {"fromdate": fromdate, "todate": todate})
        logger.info(f"Selcom API response for list-orders: {response_data}")
        return ListAllOrdersApiResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing orders from {fromdate} to {todate}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.get("/checkout/stored-cards", response_model=FetchStoredCardTokensApiResponse)
async def fetch_stored_card_tokens_route(buyer_userid: str, gateway_buyer_uuid: str):
    logger.info(f"Received request to fetch stored cards for user: {buyer_userid}")
    fetch_path = "/v1/checkout/stored-cards"
    try:
        response_data = await asyncio.to_thread(client.getFunc, fetch_path, {"buyer_userid": buyer_userid, "gateway_buyer_uuid": gateway_buyer_uuid})
        logger.info(f"Selcom API response for stored-cards: {response_data}")
        return FetchStoredCardTokensApiResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching stored cards for user {buyer_userid}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.delete("/checkout/delete-card", response_model=SelcomGenericResponse)
async def delete_stored_card_route(request_payload: DeleteStoredCardRequest):
    logger.info(f"Received request to delete card ID: {request_payload.id} for UUID: {request_payload.gateway_buyer_uuid}")
    delete_path = "/v1/checkout/delete-card"
    try:
        response_data = await asyncio.to_thread(client.deleteFunc, delete_path, request_payload.model_dump())
        logger.info(f"Selcom API response for delete-card: {response_data}")
        return SelcomGenericResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting card {request_payload.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/checkout/card-payment", response_model=SelcomGenericResponse)
async def process_card_payment_route(request_payload: ProcessCardPaymentRequest):
    logger.info(f"Received request to process card payment for order: {request_payload.order_id}")
    card_payment_path = "/v1/checkout/card-payment"
    payload = request_payload.model_dump(exclude_unset=True)
    payload["vendor"] = VENDOR_ID
    try:
        response_data = await asyncio.to_thread(client.postFunc, card_payment_path, payload)
        logger.info(f"Selcom API response for card-payment: {response_data}")
        return SelcomGenericResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing card payment for order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/checkout/wallet-payment", response_model=SelcomGenericResponse)
async def process_wallet_pull_payment_route(request_payload: ProcessWalletPullPaymentRequest):
    logger.info(f"Received request to process wallet pull payment for order: {request_payload.order_id}")
    wallet_payment_path = "/v1/checkout/wallet-payment"
    try:
        response_data = await asyncio.to_thread(client.postFunc, wallet_payment_path, request_payload.model_dump())
        logger.info(f"Selcom API response for wallet-payment: {response_data}")
        return SelcomGenericResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing wallet pull payment for order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/checkout/selcompesa-payment", response_model=SelcomGenericResponse)
async def process_selcom_pesa_pull_payment_route(request_payload: ProcessSelcomPesaPullPaymentRequest):
    logger.info(f"Received request to process Selcom Pesa payment for order: {request_payload.order_id}")
    selcom_pesa_path = "/v1/checkout/selcompesa-payment"
    try:
        response_data = await asyncio.to_thread(client.postFunc, selcom_pesa_path, request_payload.model_dump())
        logger.info(f"Selcom API response for selcompesa-payment: {response_data}")
        return SelcomGenericResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing Selcom Pesa payment for order {request_payload.order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/checkout/create-till-alias", response_model=CreateTillAliasApiResponse)
async def create_till_alias_route(request_payload: CreateTillAliasRequest):
    logger.info(f"Received request to create till alias for name: {request_payload.name}")
    till_alias_path = "/v1/checkout/create-till-alias"
    payload = request_payload.model_dump(exclude_unset=True)
    payload["vendor"] = VENDOR_ID
    try:
        response_data = await asyncio.to_thread(client.postFunc, till_alias_path, payload)
        logger.info(f"Selcom API response for create-till-alias: {response_data}")
        return CreateTillAliasApiResponse(**response_data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating till alias for {request_payload.name}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")

@app.post("/webhook/payment-status", status_code=status.HTTP_200_OK)
async def selcom_payment_webhook(
    request: Request,
    authorization: str = Depends(verify_c2b_token)
):
    logger.info("Received Selcom payment status webhook.")
    raw_body = await request.body()
    headers = request.headers
    try:
        payload = json.loads(raw_body.decode('utf-8'))
        webhook_data = WebhookPaymentStatusRequest(**payload)
        logger.info(f"Webhook Payload: {webhook_data.model_dump_json(indent=2)}")
        if webhook_data.payment_status == "COMPLETED":
            logger.info(f"Payment COMPLETED for Order ID: {webhook_data.order_id}, Trans ID: {webhook_data.transid}")
        elif webhook_data.payment_status == "PENDING":
            logger.info(f"Payment PENDING for Order ID: {webhook_data.order_id}, Trans ID: {webhook_data.transid}")
        elif webhook_data.payment_status == "CANCELLED" or webhook_data.payment_status == "USERCANCELLED":
            logger.info(f"Payment CANCELLED for Order ID: {webhook_data.order_id}, Trans ID: {webhook_data.transid}")
        elif webhook_data.payment_status == "REJECTED":
            logger.info(f"Payment REJECTED for Order ID: {webhook_data.order_id}, Trans ID: {webhook_data.transid}")
        else:
            logger.warning(f"Unknown payment status received: {webhook_data.payment_status} for Order ID: {webhook_data.order_id}")
        return {"status": "success", "message": "Webhook received and processed."}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON received in webhook: {raw_body.decode('utf-8')}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.")
    except Exception as e:
        logger.error(f"Error processing payment status webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal server error: {e}")