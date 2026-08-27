"""Tencent Cloud SMS sender.

Credentials are read only from environment variables (never hardcoded):
    TENCENT_SMS_SECRET_ID
    TENCENT_SMS_SECRET_KEY
    TENCENT_SMS_SDK_APP_ID
    TENCENT_SMS_SIGN_NAME
    TENCENT_SMS_TEMPLATE_ID

The sender is pluggable: when credentials are absent the service is reported as
"not configured" (the API must return SMS_SERVICE_NOT_CONFIGURED), and when
SMS_MOCK_MODE=1 the send is a no-op so automated tests never hit real SMS.
"""
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timezone

logger = logging.getLogger("tencent_sms")

# Tencent Cloud SMS constants.
SMS_HOST = "sms.tencentcloudapi.com"
SMS_SERVICE = "sms"
SMS_VERSION = "2021-01-11"
SMS_REGION = ""


class SmsNotConfiguredError(RuntimeError):
    pass


class SmsSendError(RuntimeError):
    pass


def sms_configured() -> bool:
    return all(
        os.getenv(name)
        for name in (
            "TENCENT_SMS_SECRET_ID",
            "TENCENT_SMS_SECRET_KEY",
            "TENCENT_SMS_SDK_APP_ID",
            "TENCENT_SMS_SIGN_NAME",
            "TENCENT_SMS_TEMPLATE_ID",
        )
    )


def _sign_tc3(secret_id: str, secret_key: str, payload: str, timestamp: int) -> str:
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")
    canonical_headers = "content-type:application/json; charset=utf-8\nhost:{}\n".format(SMS_HOST)
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        [
            "POST",
            "/",
            "",
            canonical_headers,
            signed_headers,
            hashed_payload,
        ]
    )
    credential_scope = f"{date}/{SMS_SERVICE}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = "\n".join(
        ["TC3-HMAC-SHA256", str(timestamp), credential_scope, hashed_canonical_request]
    )

    def _hmac(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

    secret_date = _hmac(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac(secret_date, SMS_SERVICE)
    secret_signing = _hmac(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "TC3-HMAC-SHA256 "
        f"Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    return authorization


def send_verification_sms(phone: str, code: str) -> None:
    """Send a 6-digit verification code to a canonical +86 phone number."""
    if not sms_configured():
        raise SmsNotConfiguredError("SMS service is not configured")

    # Mock mode is for automated tests only; never reach real SMS in tests.
    if os.getenv("SMS_MOCK_MODE") == "1":
        logger.info("[sms][mock] send code to %s", phone)
        return

    secret_id = os.getenv("TENCENT_SMS_SECRET_ID")
    secret_key = os.getenv("TENCENT_SMS_SECRET_KEY")
    sdk_app_id = os.getenv("TENCENT_SMS_SDK_APP_ID")
    sign_name = os.getenv("TENCENT_SMS_SIGN_NAME")
    template_id = os.getenv("TENCENT_SMS_TEMPLATE_ID")

    payload = json.dumps(
        {
            "PhoneNumberSet": [phone],
            "SmsSdkAppId": sdk_app_id,
            "SignName": sign_name,
            "TemplateId": template_id,
            "TemplateParamSet": [code, "5"],
        }
    )
    timestamp = int(time.time())
    authorization = _sign_tc3(secret_id, secret_key, payload, timestamp)

    request = urllib.request.Request(
        f"https://{SMS_HOST}",
        data=payload.encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Host": SMS_HOST,
            "X-TC-Action": "SendSms",
            "X-TC-Version": SMS_VERSION,
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Region": SMS_REGION,
            "Authorization": authorization,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise SmsSendError(f"SMS request failed: {exc}") from exc

    resp = body.get("Response", {})
    send_status_set = resp.get("SendStatusSet") or []
    if resp.get("Error"):
        raise SmsSendError(f"SMS API error: {resp['Error']}")
    if not send_status_set or send_status_set[0].get("Code") != "Ok":
        raise SmsSendError("SMS send failed")
