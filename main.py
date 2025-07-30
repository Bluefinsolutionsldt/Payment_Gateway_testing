from fastapi import FastAPI, HTTPException
from selcom_apigw_client import apigwClient
from pydantic import BaseModel
import logging
from typing import Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Selcom API Full Service Test")

# API credentials and base URL
API_KEY = os.getenv("SELCOM_API_KEY")
API_SECRET = os.getenv("SELCOM_API_SECRET")
BASE_URL = os.getenv("SELCOM_BASE_URL", "https://api.sandbox.selcom.fake/v1")  # Fake base URL, change as needed
VENDOR_ID = os.getenv("SELCOM_VENDOR_ID")
# PIN will be passed as a parameter, not loaded from dotenv

# Initialize Selcom API client
client = apigwClient.Client(BASE_URL, API_KEY, API_SECRET)

# Helper function to handle API responses
def handle_response(response, transid: str):
    result_code = response.get("resultcode")
    if result_code == "000":
        return {"status": "success", "response": response}
    elif result_code in ["111", "927"]:
        return {
            "status": "in_progress",
            "response": response,
            "message": f"Transaction {transid} in progress. Query status after 3 minutes."
        }
    elif result_code == "999":
        return {
            "status": "ambiguous",
            "response": response,
            "message": f"Transaction {transid} status ambiguous. Wait for reconciliation."
        }
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Transaction {transid} failed: {response.get('message')}"
        )

# Pydantic models for request payloads
class UtilityPaymentRequest(BaseModel):
    transid: str
    utilitycode: str
    utilityref: str
    amount: int
    msisdn: str

class WalletCashinRequest(BaseModel):
    transid: str
    utilitycode: str
    utilityref: str
    amount: int
    msisdn: str

class SelcomPesaCashinRequest(BaseModel):
    transid: str
    utilityref: str
    amount: int
    msisdn: str

class IMTRequest(BaseModel):
    messageId: str
    end2endId: str
    sender: dict
    sourceOfFunds: str
    recipient: dict
    currency: str
    amount: int
    purpose: str
    personalMessage: Optional[str] = None
    secretMessage: Optional[str] = None
    sourceFI: dict
    destinationFI: dict

class MerchantValidationRequest(BaseModel):
    transid: str
    amount: int
    reference: str

class MerchantNotificationRequest(BaseModel):
    transid: str
    reference: str
    amount: int
    result: str
    resultcode: str
    message: str

class POSPaymentRequest(BaseModel):
    transid: str
    currency: str
    amount: int
    payment_method: str
    msisdn: Optional[str] = None
    invoice_no: str

# Utility Payment Endpoints
@app.post("/test-utility-payment")
async def test_utility_payment(payment: UtilityPaymentRequest, pin: str):
    try:
        payload = {
            "transid": payment.transid,
            "utilitycode": payment.utilitycode,
            "utilityref": payment.utilityref,
            "amount": payment.amount,
            "vendor": VENDOR_ID,
            "pin": pin,
            "msisdn": payment.msisdn
        }
        logger.info(f"Sending utility payment request: {payload}")
        response = client.postFunc("/v1/utilitypayment/process", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, payment.transid)
    except Exception as e:
        logger.error(f"Error processing utility payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-utility-lookup")
async def test_utility_lookup(utilitycode: str, utilityref: str, transid: str):
    try:
        payload = {"utilitycode": utilitycode, "utilityref": utilityref, "transid": transid}
        logger.info(f"Sending utility lookup request: {payload}")
        response = client.getFunc("/v1/utilitypayment/lookup", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing utility lookup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-utility-query")
async def test_utility_query(transid: str):
    try:
        payload = {"transid": transid}
        logger.info(f"Sending utility query request: {payload}")
        response = client.getFunc("/v1/utilitypayment/query", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing utility query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Wallet Cashin Endpoints
@app.post("/test-wallet-cashin")
async def test_wallet_cashin(cashin: WalletCashinRequest, pin: str):
    try:
        payload = {
            "transid": cashin.transid,
            "utilitycode": cashin.utilitycode,
            "utilityref": cashin.utilityref,
            "amount": cashin.amount,
            "vendor": VENDOR_ID,
            "pin": pin,
            "msisdn": cashin.msisdn
        }
        logger.info(f"Sending wallet cashin request: {payload}")
        response = client.postFunc("/v1/walletcashin/process", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, cashin.transid)
    except Exception as e:
        logger.error(f"Error processing wallet cashin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-wallet-namelookup")
async def test_wallet_namelookup(utilitycode: str, utilityref: str, transid: str):
    try:
        payload = {"utilitycode": utilitycode, "utilityref": utilityref, "transid": transid}
        logger.info(f"Sending wallet name lookup request: {payload}")
        response = client.getFunc("/v1/walletcashin/namelookup", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing wallet name lookup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-wallet-query")
async def test_wallet_query(transid: str):
    try:
        payload = {"transid": transid}
        logger.info(f"Sending wallet query request: {payload}")
        response = client.getFunc("/v1/walletcashin/query", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing wallet query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Selcom Pesa Cashin Endpoint
@app.post("/test-selcom-pesa-cashin")
async def test_selcom_pesa_cashin(cashin: SelcomPesaCashinRequest, pin: str):
    try:
        payload = {
            "transid": cashin.transid,
            "utilityref": cashin.utilityref,
            "amount": cashin.amount,
            "vendor": VENDOR_ID,
            "pin": pin,
            "msisdn": cashin.msisdn
        }
        logger.info(f"Sending Selcom Pesa cashin request: {payload}")
        response = client.postFunc("/v1/selcompesa/cashin", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, cashin.transid)
    except Exception as e:
        logger.error(f"Error processing Selcom Pesa cashin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# International Money Transfer (IMT) Endpoints
@app.post("/test-imt-send-money")
async def test_imt_send_money(imt: IMTRequest, pin: str):
    try:
        payload = {
            "messageId": imt.messageId,
            "end2endId": imt.end2endId,
            "sender": imt.sender,
            "sourceOfFunds": imt.sourceOfFunds,
            "recipient": imt.recipient,
            "vendor": VENDOR_ID,
            "pin": pin,
            "currency": imt.currency,
            "amount": imt.amount,
            "purpose": imt.purpose,
            "personalMessage": imt.personalMessage,
            "secretMessage": imt.secretMessage,
            "sourceFI": imt.sourceFI,
            "destinationFI": imt.destinationFI
        }
        logger.info(f"Sending IMT send money request: {payload}")
        response = client.postFunc("/v1/imt/send-money", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, imt.messageId)
    except Exception as e:
        logger.error(f"Error processing IMT send money: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-imt-wallet-namelookup")
async def test_imt_wallet_namelookup(utilitycode: str, utilityref: str, transid: str):
    try:
        payload = {"utilitycode": utilitycode, "utilityref": utilityref, "transid": transid}
        logger.info(f"Sending IMT wallet name lookup request: {payload}")
        response = client.getFunc("/v1/imt/wallet-namelookup", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing IMT wallet name lookup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-imt-bank-namelookup")
async def test_imt_bank_namelookup(bank: str, account: str, transid: str):
    try:
        payload = {"bank": bank, "account": account, "transid": transid}
        logger.info(f"Sending IMT bank name lookup request: {payload}")
        response = client.getFunc("/v1/imt/bank-namelookup", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, transid)
    except Exception as e:
        logger.error(f"Error processing IMT bank name lookup: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/test-imt-query")
async def test_imt_query(messageId: str):
    try:
        payload = {"messageId": messageId}
        logger.info(f"Sending IMT query request: {payload}")
        response = client.getFunc("/v1/imt/query", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, messageId)
    except Exception as e:
        logger.error(f"Error processing IMT query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Merchant Payment Processing Endpoints
@app.post("/test-merchant-validation")
async def test_merchant_validation(validation: MerchantValidationRequest):
    try:
        payload = {
            "transid": validation.transid,
            "amount": validation.amount,
            "reference": validation.reference
        }
        logger.info(f"Sending merchant validation request: {payload}")
        response = client.postFunc("/validation", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, validation.transid)
    except Exception as e:
        logger.error(f"Error processing merchant validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/test-merchant-notification")
async def test_merchant_notification(notification: MerchantNotificationRequest):
    try:
        payload = {
            "transid": notification.transid,
            "reference": notification.reference,
            "amount": notification.amount,
            "result": notification.result,
            "resultcode": notification.resultcode,
            "message": notification.message
        }
        logger.info(f"Sending merchant notification request: {payload}")
        response = client.postFunc("/notification", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, notification.transid)
    except Exception as e:
        logger.error(f"Error processing merchant notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/test-pos-payment")
async def test_pos_payment(payment: POSPaymentRequest):
    try:
        payload = {
            "transid": payment.transid,
            "currency": payment.currency,
            "amount": payment.amount,
            "payment_method": payment.payment_method,
            "msisdn": payment.msisdn,
            "invoice_no": payment.invoice_no
        }
        logger.info(f"Sending POS payment request: {payload}")
        response = client.postFunc("/v1/checkout/initiate-pos-payment", payload)
        logger.info(f"Received response: {response}")
        return handle_response(response, payment.transid)
    except Exception as e:
        logger.error(f"Error processing POS payment: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# Root endpoint for testing
@app.get("/")
async def root():
    return {"message": "Selcom API Full Service Test Server is running"}