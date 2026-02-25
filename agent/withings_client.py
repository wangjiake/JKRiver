
import hashlib
import hmac
import time
import logging
from urllib.parse import urlencode

import requests

logger = logging.getLogger(__name__)

AUTH_URL = "https://account.withings.com/oauth2_user/authorize2"
TOKEN_URL = "https://wbsapi.withings.net/v2/oauth2"
MEASURE_URL = "https://wbsapi.withings.net/measure"
ACTIVITY_URL = "https://wbsapi.withings.net/v2/measure"
SLEEP_URL = "https://wbsapi.withings.net/v2/sleep"

MEASURE_TYPES = {
    1: ("weight", "kg"),
    6: ("fat_ratio", "%"),
    8: ("fat_mass", "kg"),
    76: ("muscle_mass", "kg"),
    88: ("bone_mass", "kg"),
    9: ("diastolic_bp", "mmHg"),
    10: ("systolic_bp", "mmHg"),
    11: ("heart_pulse", "bpm"),
}

def get_authorize_url(client_id: str, callback_url: str, scopes: str,
                      state: str = "") -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": callback_url,
        "scope": scopes,
        "state": state or "withings_auth",
    }
    return f"{AUTH_URL}?{urlencode(params)}"

def _get_nonce(client_id: str, consumer_secret: str) -> str:
    timestamp = str(int(time.time()))
    sign_data = f"getnonce,{client_id},{timestamp}"
    signature = hmac.new(
        consumer_secret.encode(), sign_data.encode(), hashlib.sha256
    ).hexdigest()
    resp = requests.post(
        TOKEN_URL,
        data={
            "action": "getnonce",
            "client_id": client_id,
            "timestamp": timestamp,
            "signature": signature,
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("status") == 0:
        return data["body"]["nonce"]
    raise RuntimeError(f"Failed to get nonce: {data}")

def exchange_code(client_id: str, consumer_secret: str, code: str,
                  callback_url: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "action": "requesttoken",
            "client_id": client_id,
            "client_secret": consumer_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": callback_url,
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Token exchange failed: {data}")
    body = data["body"]
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_in": body["expires_in"],
        "userid": str(body.get("userid", "")),
        "scope": body.get("scope", ""),
    }

def refresh_tokens(client_id: str, consumer_secret: str,
                   refresh_token: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "action": "requesttoken",
            "client_id": client_id,
            "client_secret": consumer_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=15,
    )
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"Token refresh failed: {data}")
    body = data["body"]
    return {
        "access_token": body["access_token"],
        "refresh_token": body["refresh_token"],
        "expires_in": body["expires_in"],
        "userid": str(body.get("userid", "")),
        "scope": body.get("scope", ""),
    }

def convert_measure_value(raw_value: int, unit: int) -> float:
    return raw_value * (10 ** unit)

def get_measures(access_token: str, startdate: int, enddate: int) -> dict:
    resp = requests.post(
        MEASURE_URL,
        data={
            "action": "getmeas",
            "startdate": startdate,
            "enddate": enddate,
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"get_measures failed: {data}")
    return data.get("body", {})

def get_activity(access_token: str, startdateymd: str,
                 enddateymd: str) -> dict:
    resp = requests.post(
        ACTIVITY_URL,
        data={
            "action": "getactivity",
            "startdateymd": startdateymd,
            "enddateymd": enddateymd,
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"get_activity failed: {data}")
    return data.get("body", {})

def get_sleep_summary(access_token: str, startdateymd: str,
                      enddateymd: str) -> dict:
    resp = requests.post(
        SLEEP_URL,
        data={
            "action": "getsummary",
            "startdateymd": startdateymd,
            "enddateymd": enddateymd,
        },
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    data = resp.json()
    if data.get("status") != 0:
        raise RuntimeError(f"get_sleep_summary failed: {data}")
    return data.get("body", {})
