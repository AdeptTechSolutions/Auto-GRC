import smtplib, imaplib, email, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

class EmailAutoReply:
    def __init__(self, email_addr, password, smtp_server='smtp.gmail.com', imap_server='imap.gmail.com'):
        self.email = email_addr
        self.password = password
        self.smtp_server = smtp_server
        self.imap_server = imap_server
        self.smtp = None
        self.imap = None
    
    def connect(self):
        """Establish SMTP and IMAP connections"""
        self.smtp = smtplib.SMTP(self.smtp_server, 587)
        self.smtp.starttls()
        self.smtp.login(self.email, self.password)
        
        self.imap = imaplib.IMAP4_SSL(self.imap_server)
        self.imap.login(self.email, self.password)
    
    def disconnect(self):
        """Close connections"""
        if self.smtp: self.smtp.quit()
        if self.imap: self.imap.close(), self.imap.logout()
    
    def send_email(self, recipient, subject, body):
        """Send email to recipient"""
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = self.email, recipient, subject
        msg.attach(MIMEText(body, 'plain'))
        self.smtp.send_message(msg)
        print(f"Email sent: {subject}")
    
    def extract_text(self, msg):
        """Extract text content from email message"""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode('utf-8').strip()
        else:
            return msg.get_payload(decode=True).decode('utf-8').strip() if msg.get_payload() else ""
    
    def check_reply(self, sender_email, subject_keywords, since_time):
        """Check for replies from sender containing subject keywords"""
        self.imap.select('INBOX')
        search_criteria = f'(FROM "{sender_email}" SINCE "{since_time.strftime("%d-%b-%Y")}")'
        _, messages = self.imap.search(None, search_criteria)
        
        for num in messages[0].split()[-10:]:
            _, msg_data = self.imap.fetch(num, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            if any(keyword.lower() in msg.get('Subject', '').lower() for keyword in subject_keywords):
                return self.extract_text(msg)
        return None
    
    def send_with_followup(self, recipient, subject, message, follow_up_message, wait_seconds=30):
        self.connect()
        """Send email and wait for reply, send follow-up if no response"""
        
        #start_time = datetime.now()
        print("yahan par email:",recipient)
        self.send_email(recipient,subject,message)

        return 
