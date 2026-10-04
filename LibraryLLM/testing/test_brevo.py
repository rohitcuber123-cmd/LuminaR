from backend.services.email_service import (
    generate_otp,
    send_otp_email
)


otp = generate_otp()

print("Generated OTP:", otp)

success = send_otp_email(
    "rohitcuber123@gmail.com",
    "Rohit",
    otp
)

print("Email sent:", success)