#!/usr/bin/env python3
"""
Test Zoho SMTP with TLS (port 587)
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.zoho.com"
SMTP_PORT = 587
USERNAME = "mike.josephh@zohomail.com.au"
PASSWORD = "Angok2028$$"
FROM_EMAIL = "mike.josephh@zohomail.com.au"
TO_EMAIL = "mike.josephh@zohomail.com.au"

msg = MIMEMultipart()
msg['From'] = FROM_EMAIL
msg['To'] = TO_EMAIL
msg['Subject'] = "SMTP TLS Test - Connor Corp"
body = "TLS test email. If you see this, TLS SMTP is working."
msg.attach(MIMEText(body, 'plain'))

try:
    print("Connecting to smtp.zoho.com:587...")
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    print("TLS started. Logging in...")
    server.login(USERNAME, PASSWORD)
    print("Login successful!")
    server.send_message(msg)
    print("Test email sent successfully!")
    server.quit()
except Exception as e:
    print(f"Error: {e}")
    print("\nBoth SSL (465) and TLS (587) failed.")
    print("Need app-specific password from Zoho settings.")
