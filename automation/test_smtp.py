#!/usr/bin/env python3
"""
Test Zoho SMTP connection
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Test config
SMTP_SERVER = "smtp.zoho.com"
SMTP_PORT = 465  # SSL
USERNAME = "mike.josephh@zohomail.com.au"
PASSWORD = "Angok2028$$"  # User's actual password
FROM_EMAIL = "mike.josephh@zohomail.com.au"
TO_EMAIL = "mike.josephh@zohomail.com.au"  # Send to self as test

# Create test message
msg = MIMEMultipart()
msg['From'] = FROM_EMAIL
msg['To'] = TO_EMAIL
msg['Subject'] = "SMTP Test - Connor Corp Outreach"
body = "This is a test email from Connor Corp outreach system. If you see this, SMTP is working."
msg.attach(MIMEText(body, 'plain'))

try:
    print("Connecting to smtp.zoho.com:465...")
    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    print("Connected. Logging in...")
    server.login(USERNAME, PASSWORD)
    print("Login successful!")
    server.send_message(msg)
    print("Test email sent successfully!")
    server.quit()
    print("Ready to send outreach emails.")
except Exception as e:
    print(f"Error: {e}")
    print()
    print("If 'Authentication failed' - need app-specific password:")
    print("1. Log into https://mail.zoho.com")
    print("2. Settings → Security → App Passwords")
    print("3. Generate app password for 'Other'")
    print("4. Use that password instead")
