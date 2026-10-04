import os
import random

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

    return str(random.randint(100000, 999999))


def send_otp_email(recipient_email, recipient_name, otp):

    client = Brevo(
        api_key=BREVO_API_KEY
    )

    try:

        result = client.transactional_emails.send_transac_email(

            subject="LuminaR Email Verification",

            html_content=f"""
            <html>
                <body>
                    <h2>Welcome to LuminaR</h2>

                    <p>Hello {recipient_name},</p>

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

        print("Brevo message ID:", result.message_id)

        return True

    except Exception as error:

        print("Brevo API error:", error)

        return False