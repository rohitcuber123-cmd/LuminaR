import os
import secrets
import logging
from html import escape

from dotenv import load_dotenv
from brevo import Brevo
from brevo.transactional_emails import (
    SendTransacEmailRequestSender,
    SendTransacEmailRequestToItem,
)


load_dotenv()

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL")
SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "LuminaR")


def generate_otp():

    return str(100000 + secrets.randbelow(900000))


def send_otp_email(recipient_email, recipient_name, otp):

    try:
        client = Brevo(api_key=BREVO_API_KEY)

        client.transactional_emails.send_transac_email(

            subject="LuminaR Email Verification",

            html_content=f"""
            <html>
                <body>
                    <h2>Welcome to LuminaR</h2>

                    <p>Hello {escape(recipient_name)},</p>

                    <p>
                        Your LuminaR email verification code is:
                    </p>

                    <h1>{otp}</h1>

                    <p>
                        This code will expire in 10 minutes.
                    </p>

                    <p>
                        If you did not create this account,
                        you can ignore this email.
                    </p>
                </body>
            </html>
            """,

            sender=SendTransacEmailRequestSender(
                name=SENDER_NAME,
                email=SENDER_EMAIL
            ),

            to=[
                SendTransacEmailRequestToItem(
                    email=recipient_email,
                    name=recipient_name
                )
            ]
        )

        logging.getLogger('luminar.email').info('Verification email sent')

        return True

    except Exception:

        logging.getLogger('luminar.email').warning('Verification email delivery failed')

        return False
