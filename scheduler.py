import streamlit as st
import pandas as pd
from datetime import datetime
import re
import time
import sqlite3
from db import CompanyDatabase  
from gemini import gemini_class  
from Email import EmailAutoReply
import base64
import json
from urllib.parse import urlencode
from dotenv import load_dotenv
import os
from Email import EmailAutoReply
load_dotenv()
EMAIL=os.getenv("EMAIL")
PASSWORD=os.getenv("PASSWORD")
db = CompanyDatabase()

# Get email instance
email_bot = EmailAutoReply(EMAIL, PASSWORD)


conn = db.get_connection()
cursor = conn.cursor()

# Query to get acknowledgement status for this specific policy
query = """
SELECT 
    e.id as employee_id,
    e.name as employee_name,
    e.email as employee_email,
    e.department,
    e.work_mode,
    a.status,
    a.updated_at,
    a.created_at
FROM acknowledgements a
JOIN employee e ON a.employee_id = e.id
ORDER BY e.name
"""

cursor.execute(query)
acknowledgement_data = cursor.fetchall()
conn.close()

if acknowledgement_data:    
    # Convert data to DataFrame for easier handling
    columns = ['employee_id', 'employee_name', 'employee_email', 'department', 'work_mode', 'status', 'updated_at', 'created_at']
    status_df = pd.DataFrame(acknowledgement_data, columns=columns)

    subject="Policy Acknowledgement Reminder"
    message="It is requested to please acknowledge the previously shared email regarding new policy implementation \n Best Regards \n Compliance Department"

    # Create custom table with status indicators
    for idx, row in status_df.iterrows():
        if(row['status']=="not responded"):
            print(row['employee_email'])
            email_bot.send_with_followup(row['employee_email'],subject,message," ")
            
            
