import os
import json
import time
import hashlib
from dataclasses import dataclass
from typing import Dict, Any

from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =========================
# Location Model
# =========================

@dataclass
class LocationContext:
    lat: float
    lon: float
    timestamp: int  # seconds


def quantize(value: float, precision: float) -> float:
    return round(value / precision) * precision


def build_location_fingerprint(ctx: LocationContext) -> bytes:
    """
    Build a STABLE (but coarse) fingerprint so small GPS noise doesn't break decryption.
    """

    # 🔧 Tune these for tolerance
    lat_q = quantize(ctx.lat, 0.001)   # ~100m
    lon_q = quantize(ctx.lon, 0.001)

    time_window = ctx.timestamp // 300  # 5-minute window

    # Simulated "satellite-like" features
    pseudo_sat = hashlib.sha256(
        f"{lat_q}:{lon_q}:{time_window}".encode()
    ).hexdigest()

    payload = {
        "lat": lat_q,
        "lon": lon_q,
        "t": time_window,
        "sat": pseudo_sat[:16],
    }

    return json.dumps(payload, sort_keys=True).encode()


# =========================
# Key Derivation
# =========================

def derive_key(user_secret: bytes, location_fp: bytes) -> bytes:
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=location_fp,
        info=b"geo-lock-v1",
    )
    return hkdf.derive(user_secret)


# =========================
# Encryption
# =========================

def encrypt_file(input_path: str, output_path: str, key: bytes):
    with open(input_path, "rb") as f:
        data = f.read()

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    ciphertext = aesgcm.encrypt(nonce, data, None)

    blob = {
        "nonce": nonce.hex(),
        "ciphertext": ciphertext.hex(),
    }

    with open(output_path, "w") as f:
        json.dump(blob, f)


def decrypt_file(input_path: str, output_path: str, key: bytes):
    with open(input_path, "r") as f:
        blob = json.load(f)

    nonce = bytes.fromhex(blob["nonce"])
    ciphertext = bytes.fromhex(blob["ciphertext"])

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    with open(output_path, "wb") as f:
        f.write(plaintext)


# =========================
# High-level API
# =========================

def encrypt_with_location(
    input_path: str,
    output_path: str,
    user_secret: str,
    lat: float,
    lon: float,
):
    ctx = LocationContext(lat=lat, lon=lon, timestamp=int(time.time()))
    fp = build_location_fingerprint(ctx)
    key = derive_key(user_secret.encode(), fp)

    encrypt_file(input_path, output_path, key)


def decrypt_with_location(
    input_path: str,
    output_path: str,
    user_secret: str,
    lat: float,
    lon: float,
):
    ctx = LocationContext(lat=lat, lon=lon, timestamp=int(time.time()))
    fp = build_location_fingerprint(ctx)
    key = derive_key(user_secret.encode(), fp)

    decrypt_file(input_path, output_path, key)