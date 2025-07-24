# email_acknowledgment_system.py
# Complete Simple HTTP Server + SQLite Solution

import sqlite3
import smtplib
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time
import os

class EmailAcknowledgmentDB:
    """Database handler for email acknowledgments using SQLite"""
    
    def __init__(self, db_path="email_acknowledgments.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database and create table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS email_acknowledgments (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                subject TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✓ Database initialized: {self.db_path}")
    
    def create_email_record(self, email, subject):
        """Create a new email record and return the email ID"""
        email_id = str(uuid.uuid4())
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO email_acknowledgments (id, email, subject, status) 
            VALUES (?, ?, ?, 'pending')
        ''', (email_id, email, subject))
        
        conn.commit()
        conn.close()
        
        print(f"✓ Email record created: {email_id} for {email}")
        return email_id
    
    def update_status(self, email_id, status):
        """Update the acknowledgment status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE email_acknowledgments 
            SET status = ?, updated_at = ? 
            WHERE id = ?
        ''', (status, datetime.now().isoformat(), email_id))
        
        rows_affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_affected > 0:
            print(f"✓ Status updated: {email_id} -> {status}")
            return True
        else:
            print(f"✗ Email ID not found: {email_id}")
            return False
    
    def get_status(self, email_id):
        """Get the current status of an email"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email, subject, status, created_at, updated_at 
            FROM email_acknowledgments 
            WHERE id = ?
        ''', (email_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'email': result[0],
                'subject': result[1],
                'status': result[2],
                'created_at': result[3],
                'updated_at': result[4]
            }
        return None
    
    def get_all_records(self):
        """Get all email records"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, email, subject, status, created_at, updated_at 
            FROM email_acknowledgments 
            ORDER BY created_at DESC
        ''')
        
        records = cursor.fetchall()
        conn.close()
        
        return [
            {
                'id': record[0],
                'email': record[1], 
                'subject': record[2],
                'status': record[3],
                'created_at': record[4],
                'updated_at': record[5]
            }
            for record in records
        ]

class EmailSender:
    """Email sender class"""
    
    def __init__(self, smtp_server="smtp.gmail.com", smtp_port=587):
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.email = None
        self.password = None
        self.server_url = "http://localhost:8080"
    
    def configure_email(self, email, password):
        """Configure email credentials"""
        self.email = email
        self.password = password
        print(f"✓ Email configured: {email}")
    
    def send_acknowledgment_email(self, recipient, subject, message):
        """Send email with acknowledgment links"""
        if not self.email or not self.password:
            print("✗ Email credentials not configured!")
            return None
        
        # Create database record
        email_id = db.create_email_record(recipient, subject)
        
        # Create acknowledgment links
        ack_link = f"{self.server_url}/acknowledge/{email_id}"
        nack_link = f"{self.server_url}/decline/{email_id}"
        status_link = f"{self.server_url}/status/{email_id}"
        
        # Create HTML email content
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{subject}</title>
        </head>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                <h2 style="color: #333; margin-top: 0;">Email Acknowledgment Required</h2>
                <p style="color: #666; line-height: 1.6;">{message}</p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <h3 style="color: #333; margin-bottom: 20px;">Please choose your response:</h3>
                
                <a href="{ack_link}" 
                   style="background-color: #28a745; 
                          color: white; 
                          padding: 15px 30px; 
                          text-decoration: none; 
                          border-radius: 5px; 
                          font-weight: bold; 
                          margin: 0 10px;
                          display: inline-block;">
                    ✅ ACKNOWLEDGE
                </a>
                
                <a href="{nack_link}" 
                   style="background-color: #dc3545; 
                          color: white; 
                          padding: 15px 30px; 
                          text-decoration: none; 
                          border-radius: 5px; 
                          font-weight: bold; 
                          margin: 0 10px;
                          display: inline-block;">
                    ❌ DECLINE
                </a>
            </div>
            
            <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px; margin-top: 30px;">
                <p style="margin: 0; font-size: 14px; color: #6c757d;">
                    <strong>Tracking ID:</strong> {email_id}<br>
                    <strong>Check Status:</strong> <a href="{status_link}">{status_link}</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Create email message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = self.email
        msg['To'] = recipient
        
        # Attach HTML content
        html_part = MIMEText(html_body, 'html')
        msg.attach(html_part)
        
        try:
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email, self.password)
                server.send_message(msg)
            
            print(f"✅ Email sent successfully to {recipient}")
            print(f"📧 Email ID: {email_id}")
            print(f"🔗 Acknowledge: {ack_link}")
            print(f"🔗 Decline: {nack_link}")
            print(f"📊 Status: {status_link}")
            
            return email_id
            
        except Exception as e:
            print(f"✗ Error sending email: {e}")
            return None

class AcknowledgmentHandler(BaseHTTPRequestHandler):
    """HTTP request handler for acknowledgment links"""
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path_parts = parsed_path.path.strip('/').split('/')
        
        if len(path_parts) >= 2:
            action = path_parts[0]
            email_id = path_parts[1]
            
            if action == 'acknowledge':
                self.handle_acknowledge(email_id)
            elif action == 'decline':
                self.handle_decline(email_id)
            elif action == 'status':
                self.handle_status(email_id)
            else:
                self.handle_not_found()
        else:
            self.handle_dashboard()
    
    def handle_acknowledge(self, email_id):
        """Handle acknowledgment"""
        success = db.update_status(email_id, 'acknowledged')
        
        if success:
            html_response = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Acknowledged</title>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: Arial, sans-serif; text-align: center; background-color: #f8f9fa; padding: 50px;">
                <div style="background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #28a745; margin-bottom: 20px;">✅ Acknowledged Successfully!</h1>
                    <p style="font-size: 18px; color: #666;">Thank you for confirming your acknowledgment.</p>
                    <p style="color: #999; margin-top: 30px;">You can now close this window.</p>
                </div>
            </body>
            </html>
            """
        else:
            html_response = self.get_error_page("Invalid or expired link")
        
        self.send_html_response(html_response)
    
    def handle_decline(self, email_id):
        """Handle decline"""
        success = db.update_status(email_id, 'not_acknowledged')
        
        if success:
            html_response = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Declined</title>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: Arial, sans-serif; text-align: center; background-color: #f8f9fa; padding: 50px;">
                <div style="background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #dc3545; margin-bottom: 20px;">❌ Declined</h1>
                    <p style="font-size: 18px; color: #666;">Your response has been recorded.</p>
                    <p style="color: #999; margin-top: 30px;">You can now close this window.</p>
                </div>
            </body>
            </html>
            """
        else:
            html_response = self.get_error_page("Invalid or expired link")
        
        self.send_html_response(html_response)
    
    def handle_status(self, email_id):
        """Handle status check"""
        status_info = db.get_status(email_id)
        
        if status_info:
            status_color = {
                'pending': '#ffc107',
                'acknowledged': '#28a745',
                'not_acknowledged': '#dc3545'
            }.get(status_info['status'], '#6c757d')
            
            html_response = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Status Check</title>
                <meta charset="UTF-8">
            </head>
            <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px;">
                <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: 0 auto;">
                    <h1 style="color: #333; text-align: center;">📊 Email Status</h1>
                    
                    <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Email ID:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-family: monospace;">{email_id}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Email:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">{status_info['email']}</td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Subject:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">{status_info['subject']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Status:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">
                                <span style="background-color: {status_color}; color: white; padding: 4px 12px; border-radius: 15px; font-weight: bold;">
                                    {status_info['status'].upper()}
                                </span>
                            </td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Created:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">{status_info['created_at']}</td>
                        </tr>
                        <tr>
                            <td style="padding: 12px; border: 1px solid #dee2e6; font-weight: bold;">Updated:</td>
                            <td style="padding: 12px; border: 1px solid #dee2e6;">{status_info['updated_at']}</td>
                        </tr>
                    </table>
                </div>
            </body>
            </html>
            """
        else:
            html_response = self.get_error_page("Email ID not found")
        
        self.send_html_response(html_response)
    
    def handle_dashboard(self):
        """Handle dashboard (show all records)"""
        records = db.get_all_records()
        
        rows_html = ""
        for record in records:
            status_color = {
                'pending': '#ffc107',
                'acknowledged': '#28a745', 
                'not_acknowledged': '#dc3545'
            }.get(record['status'], '#6c757d')
            
            rows_html += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #dee2e6; font-family: monospace; font-size: 12px;">{record['id'][:8]}...</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{record['email']}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">{record['subject']}</td>
                <td style="padding: 8px; border: 1px solid #dee2e6;">
                    <span style="background-color: {status_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px;">
                        {record['status'].upper()}
                    </span>
                </td>
                <td style="padding: 8px; border: 1px solid #dee2e6; font-size: 12px;">{record['created_at']}</td>
            </tr>
            """
        
        html_response = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Email Acknowledgment Dashboard</title>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="30">
        </head>
        <body style="font-family: Arial, sans-serif; background-color: #f8f9fa; padding: 20px;">
            <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <h1 style="color: #333; text-align: center;">📧 Email Acknowledgment Dashboard</h1>
                <p style="text-align: center; color: #666;">Auto-refreshes every 30 seconds</p>
                
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    <thead>
                        <tr style="background-color: #343a40; color: white;">
                            <th style="padding: 12px; border: 1px solid #dee2e6;">ID</th>
                            <th style="padding: 12px; border: 1px solid #dee2e6;">Email</th>
                            <th style="padding: 12px; border: 1px solid #dee2e6;">Subject</th>
                            <th style="padding: 12px; border: 1px solid #dee2e6;">Status</th>
                            <th style="padding: 12px; border: 1px solid #dee2e6;">Created</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html if rows_html else '<tr><td colspan="5" style="text-align: center; padding: 20px; color: #666;">No emails sent yet</td></tr>'}
                    </tbody>
                </table>
                
                <div style="text-align: center; margin-top: 20px;">
                    <p style="color: #666;">
                        Total Records: {len(records)} | 
                        Server: <code>http://localhost:8080</code>
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        self.send_html_response(html_response)
    
    def handle_not_found(self):
        """Handle 404 errors"""
        html_response = self.get_error_page("Page not found")
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_response.encode())
    
    def get_error_page(self, message):
        """Generate error page HTML"""
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial, sans-serif; text-align: center; background-color: #f8f9fa; padding: 50px;">
            <div style="background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 500px; margin: 0 auto;">
                <h1 style="color: #dc3545;">❌ Error</h1>
                <p style="font-size: 18px; color: #666;">{message}</p>
                <a href="/" style="color: #007bff; text-decoration: none;">← Back to Dashboard</a>
            </div>
        </body>
        </html>
        """
    
    def send_html_response(self, html_content):
        """Send HTML response"""
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html_content.encode())

def start_server(port=8080):
    """Start the HTTP server"""
    server_address = ('', port)
    httpd = HTTPServer(server_address, AcknowledgmentHandler)
    print(f"🚀 Server starting on http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:{port}")
    print("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped")
        httpd.server_close()

# Global instances
db = EmailAcknowledgmentDB()
email_sender = EmailSender()

def main():
    """Main function to demonstrate usage"""
    print("=" * 60)
    print("📧 EMAIL ACKNOWLEDGMENT SYSTEM")
    print("=" * 60)
    
    # Start server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Wait a moment for server to start
    time.sleep(1)
    
    # Configure email credentials
    print("\n🔧 CONFIGURATION")
    print("Please enter your email credentials:")
    
    email = input("📧 Your email: ").strip()
    password = input("🔐 Your app password: ").strip()
    
    email_sender.configure_email(email, password)
    
    # Main loop
    while True:
        print("\n" + "=" * 60)
        print("OPTIONS:")
        print("1. Send acknowledgment email")
        print("2. Check email status") 
        print("3. View all records")
        print("4. Exit")
        print("=" * 60)
        
        choice = input("Choose option (1-4): ").strip()
        
        if choice == '1':
            print("\n📤 SEND EMAIL")
            recipient = input("Recipient email: ").strip()
            subject = input("Email subject: ").strip()
            message = input("Email message: ").strip()
            
            if recipient and subject and message:
                email_id = email_sender.send_acknowledgment_email(recipient, subject, message)
                if email_id:
                    print(f"\n✅ Email sent! ID: {email_id}")
                    print(f"🔗 Status: http://localhost:8080/status/{email_id}")
            else:
                print("❌ All fields are required!")
        
        elif choice == '2':
            print("\n📊 CHECK STATUS")
            email_id = input("Enter email ID: ").strip()
            status_info = db.get_status(email_id)
            
            if status_info:
                print(f"\n📧 Email: {status_info['email']}")
                print(f"📋 Subject: {status_info['subject']}")
                print(f"📊 Status: {status_info['status'].upper()}")
                print(f"📅 Created: {status_info['created_at']}")
                print(f"🔄 Updated: {status_info['updated_at']}")
            else:
                print("❌ Email ID not found!")
        
        elif choice == '3':
            print("\n📋 ALL RECORDS")
            records = db.get_all_records()
            
            if records:
                for record in records:
                    print(f"ID: {record['id']}")
                    print(f"  📧 {record['email']}")
                    print(f"  📋 {record['subject']}")
                    print(f"  📊 {record['status'].upper()}")
                    print(f"  📅 {record['created_at']}")
                    print()
            else:
                print("No records found!")
        
        elif choice == '4':
            print("\n👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid choice!")

if __name__ == "__main__":
    main()