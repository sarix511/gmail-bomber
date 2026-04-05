from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, field_validator
from mangum import Mangum
import smtplib
import random
import string
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI(title="HAYATO SYSTEM — OTP API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Models ────────────────────────────────────────────────────────────────────

class BombRequest(BaseModel):
    recipientEmail: str
    count: int = 1
    senderEmail: str | None = None
    appPassword: str | None = None

    @field_validator("recipientEmail")
    @classmethod
    def must_be_gmail(cls, v: str) -> str:
        if not v.endswith("@gmail.com"):
            raise ValueError("Only @gmail.com addresses are supported")
        return v

    @field_validator("count")
    @classmethod
    def valid_count(cls, v: int) -> int:
        if v < 1 or v > 1000:
            raise ValueError("count must be between 1 and 1000")
        return v


class SetupRequest(BaseModel):
    senderEmail: str
    appPassword: str


# ─── Helpers ───────────────────────────────────────────────────────────────────

def generate_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


def get_credentials(sender_email: str | None, app_password: str | None):
    email = sender_email or os.environ.get("SENDER_EMAIL")
    pwd = app_password or os.environ.get("SENDER_APP_PASSWORD")
    if not email or not pwd:
        raise HTTPException(
            status_code=400,
            detail="Sender credentials not provided. Pass senderEmail + appPassword or set SENDER_EMAIL / SENDER_APP_PASSWORD env vars.",
        )
    return email, pwd


def smtp_send(sender_email: str, sender_password: str, recipient: str, otp: str, index: int, total: int):
    subject = f"⚡ OTP #{index} — HAYATO SYSTEM"
    body = f"""
╔══════════════════════════════════════╗
║     ⚡  HAYATO SYSTEM  🇵🇰  ⚡        ║
╚══════════════════════════════════════╝

 YOU ARE ATTACKED BY TEAM HAYATO ⚡⚡ 🇵🇰 FROM DARK WEB

 Your OTP #{index} of {total}:

        ➤  {otp}

 ⏳ Expires in 5 minutes
 🔒 Do NOT share this code.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   JUST KIDDING — IT'S A PRANK! 😂
   Sent with love by HAYATO SYSTEM 🇵🇰
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    msg = MIMEMultipart()
    msg["From"] = f'"HAYATO SYSTEM" <{sender_email}>'
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient, msg.as_string())


# ─── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "system": "HAYATO SYSTEM",
        "version": "1.0.0",
        "status": "online",
        "routes": {
            "POST /bomb":   "Send OTPs to a Gmail target",
            "POST /setup":  "Verify Gmail sender credentials",
            "GET  /status": "Check if env credentials are configured",
        },
    }


@app.get("/status")
def status():
    email = os.environ.get("SENDER_EMAIL")
    configured = bool(email and os.environ.get("SENDER_APP_PASSWORD"))
    return {
        "configured": configured,
        "senderEmail": email if configured else None,
    }


@app.post("/setup")
async def setup(body: SetupRequest):
    if not body.senderEmail.endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Only @gmail.com addresses are supported")
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.login(body.senderEmail, body.appPassword)
        return {"success": True, "message": "Credentials verified successfully ✅"}
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="Authentication failed — wrong email or App Password")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/bomb")
async def bomb(body: BombRequest):
    sender_email, sender_password = get_credentials(body.senderEmail, body.appPassword)

    sent = []
    failed = []

    for i in range(1, body.count + 1):
        otp = generate_otp()
        try:
            smtp_send(sender_email, sender_password, body.recipientEmail, otp, i, body.count)
            sent.append({"index": i, "otp": otp})
        except Exception as e:
            failed.append({"index": i, "error": str(e)})

    return {
        "success": True,
        "sent": len(sent),
        "failed": len(failed),
        "otps": sent,
        "message": f"💣 {len(sent)}/{body.count} OTPs sent to {body.recipientEmail}",
    }


# ─── Vercel ASGI handler ────────────────────────────────────────────────────────
handler = Mangum(app, lifespan="off")
