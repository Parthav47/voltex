"""
email_sender.py

Sends emails via SMTP (Gmail).

Uses Python's built-in smtplib — no extra library needed.
Keeps all email logic isolated here — event_consumer.py
just calls send_order_confirmation() and doesn't know
anything about SMTP or HTML templates.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_EMAIL = os.environ.get("SMTP_EMAIL", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Voltex")


def _send_email(to_email: str, subject: str, html_body: str) -> None:
    """
    Core email sending function.

    Uses STARTTLS — connects on port 587 (plain),
    then upgrades to encrypted connection.
    More compatible than port 465 (SSL from the start).

    Raises an exception if sending fails —
    caller handles and records the error.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{EMAIL_FROM_NAME} <{SMTP_EMAIL}>"
    msg["To"] = to_email

    # Attach HTML part
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()        # upgrade to encrypted connection
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_email, msg.as_string())


def send_order_confirmation(
    to_email: str,
    user_name: str,
    order_id: str,
    amount: int,        # in paise
) -> None:
    """
    Send order confirmation email after payment success.

    amount is in paise (Razorpay format) — convert to rupees for display.
    """
    amount_rupees = amount / 100
    order_short = order_id[:8].upper()

    subject = f"Order confirmed — #{order_short}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                 background: #f9f9f9; margin: 0; padding: 40px 20px;">

      <div style="max-width: 480px; margin: 0 auto; background: #ffffff;
                  border: 1px solid #e5e5e5; border-radius: 12px; overflow: hidden;">

        <!-- Header -->
        <div style="background: #1a1a1a; padding: 28px 32px;">
          <p style="color: #ffffff; font-size: 20px; font-weight: 600; margin: 0;">
            Voltex
          </p>
        </div>

        <!-- Body -->
        <div style="padding: 32px;">
          <h1 style="font-size: 22px; font-weight: 600; margin: 0 0 8px;">
            Order confirmed! ✓
          </h1>
          <p style="color: #888; font-size: 14px; margin: 0 0 28px;">
            Hi {user_name}, your payment was successful.
          </p>

          <!-- Order details -->
          <div style="background: #f9f9f9; border-radius: 8px; padding: 20px; margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
              <span style="font-size: 13px; color: #888;">Order ID</span>
              <span style="font-size: 13px; font-weight: 500;">#{order_short}</span>
            </div>
            <div style="display: flex; justify-content: space-between;">
              <span style="font-size: 13px; color: #888;">Amount paid</span>
              <span style="font-size: 13px; font-weight: 500;">
                ₹{amount_rupees:,.2f}
              </span>
            </div>
          </div>

          <p style="font-size: 14px; color: #555; line-height: 1.6; margin: 0 0 24px;">
            We're preparing your order and will notify you once it ships.
            Thank you for shopping with Voltex.
          </p>

          <a href="http://localhost:3000/orders/{order_id}"
             style="display: inline-block; background: #1a1a1a; color: #ffffff;
                    font-size: 14px; font-weight: 500; padding: 12px 24px;
                    border-radius: 8px; text-decoration: none;">
            View order
          </a>
        </div>

        <!-- Footer -->
        <div style="padding: 20px 32px; border-top: 1px solid #f0f0f0;">
          <p style="font-size: 12px; color: #aaa; margin: 0;">
            Voltex Electronics · This is an automated email, please do not reply.
          </p>
        </div>

      </div>
    </body>
    </html>
    """

    _send_email(to_email, subject, html)


def send_order_placed(
    to_email: str,
    user_name: str,
    order_id: str,
) -> None:
    """
    Send order acknowledgement email immediately after checkout.
    This fires BEFORE payment — it is NOT a confirmation.
    """
    order_short = order_id[:8].upper()
    subject = f"We received your order — #{order_short}"

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                 background: #f9f9f9; margin: 0; padding: 40px 20px;">

      <div style="max-width: 480px; margin: 0 auto; background: #ffffff;
                  border: 1px solid #e5e5e5; border-radius: 12px; overflow: hidden;">

        <div style="background: #1a1a1a; padding: 28px 32px;">
          <p style="color: #ffffff; font-size: 20px; font-weight: 600; margin: 0;">
            Voltex
          </p>
        </div>

        <div style="padding: 32px;">
          <h1 style="font-size: 22px; font-weight: 600; margin: 0 0 8px;">
            We got your order
          </h1>
          <p style="color: #888; font-size: 14px; margin: 0 0 24px;">
            Hi {user_name}, we received order #{order_short}.
            Complete your payment to confirm it.
          </p>

          <a href="http://localhost:3000/orders/{order_id}"
             style="display: inline-block; background: #1a1a1a; color: #ffffff;
                    font-size: 14px; font-weight: 500; padding: 12px 24px;
                    border-radius: 8px; text-decoration: none;">
            View order
          </a>
        </div>

        <div style="padding: 20px 32px; border-top: 1px solid #f0f0f0;">
          <p style="font-size: 12px; color: #aaa; margin: 0;">
            Voltex Electronics · This is an automated email, please do not reply.
          </p>
        </div>

      </div>
    </body>
    </html>
    """

    _send_email(to_email, subject, html)