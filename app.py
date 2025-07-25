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
load_dotenv()
EMAIL=os.getenv("EMAIL")
PASSWORD=os.getenv("PASSWORD")

# --- Page Configuration ---
st.set_page_config(
    page_title="GRC Policy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Initialize Database ---
@st.cache_resource
def get_database():
    """Initialize and return database instance"""
    db = CompanyDatabase()
    db.create_tables()  
    db.initialize_sample_data()
    return db

# Get database instance
db = get_database()

# Get email instance
email_bot = EmailAutoReply(EMAIL, PASSWORD)
#email_bot.connect()

# --- Session State Setup ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = ''
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'dashboard'
if 'policy_status_view' not in st.session_state:
    st.session_state.policy_status_view = None

# --- Login Screen ---
def login_page():
    st.markdown("<h1 style='text-align: center; color: #333333;'>Welcome to GRC Dashboard</h1>", unsafe_allow_html=True)
    st.write("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        if st.button("Login"):
            if username and password:
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.current_page = 'dashboard'  
                st.rerun()
            else:
                st.error("Please enter valid credentials.")

def parse_email(text):
    # Extract subject
    subject_match = re.search(r"Subject:\s*(.*)", text)
    subject = subject_match.group(1).strip() if subject_match else None

    # Extract body (everything after subject line)
    parts = re.split(r"Subject:.*?\n\s*\n", text, maxsplit=1)
    body = parts[1].strip() if len(parts) > 1 else None

    print("Subject:", subject)
    print("\nBody:\n", body)

    return subject, body

def generate_acknowledgement_links(policy_id, employee_email, base_url="http://localhost:5000"):
    """
    Generate acknowledgement and non-acknowledgement links for email
    """
    # Create data payload
    ack_data = {
        'policy_id': policy_id,
        'email': employee_email,
        'status': 'ack'
    }
    
    nak_data = {
        'policy_id': policy_id,
        'email': employee_email,
        'status': 'nak'
    }
    
    # Encode data as base64 for URL safety
    ack_encoded = base64.urlsafe_b64encode(json.dumps(ack_data).encode()).decode()
    nak_encoded = base64.urlsafe_b64encode(json.dumps(nak_data).encode()).decode()
    
    # Create links
    ack_link = f"{base_url}/acknowledge?data={ack_encoded}"
    nak_link = f"{base_url}/acknowledge?data={nak_encoded}"
    
    return ack_link, nak_link

def create_email_body_with_links(original_body, policy_id, employee_email):
    """
    Modify the email body to include acknowledgement links
    """
    ack_link, nak_link = generate_acknowledgement_links(policy_id, employee_email)
    
    # Add acknowledgement section to email body
    acknowledgement_section = f"""

    ---

    POLICY ACKNOWLEDGEMENT REQUIRED:

    Please click one of the following links to acknowledge this policy:

    ✅ I ACKNOWLEDGE and will comply with this policy:
    {ack_link}

    ❌ I DO NOT ACKNOWLEDGE this policy (requires discussion):
    {nak_link}

    Important: You must click one of these links to complete your policy acknowledgement.

    ---
    """
    
    # Append to original body
    modified_body = original_body + acknowledgement_section
    return modified_body

def implement_policy_background(policy):
    """
    Process and implement policy in the background without opening new page
    Returns: (success: bool, message: str, email_count: int)
    """
    try:
        # Get recipient emails - this should return employee records, not just emails
        # We need both email and employee ID for acknowledgement links
        employees_df = db.search_employees_full(department=policy['department'], work_mode=policy['work_mode'])
        
        if employees_df.empty:
            return False, "No recipients found for this policy", 0
        
        # Process with Gemini AI
        g = gemini_class()
        gemini_output = g.process_policy(policy['text'])
        
        # Parse email content
        subject, body = parse_email(text=gemini_output)
        
        # Send personalized emails with acknowledgement links
        email_list = []
        for _, employee in employees_df.iterrows():
            # Create personalized email body with acknowledgement links
            personalized_body = create_email_body_with_links(
                original_body=body,
                policy_id=policy['id'],
                employee_email=employee['email']
            )
            
            email_list.append({
                'email': employee['email'],
                'subject': subject,
                'body': personalized_body
            })
            #print("Idhar email ha:",email_list['email'])
        
        # Send all emails
        success_count = 0
        for email_data in email_list:
            try:
                # Assuming your email_bot has a method to send individual emails
                print("Idhar email ha:",email_data['email'])
                email_bot.send_with_followup(
                    email_data['email'], 
                    email_data['subject'], 
                    email_data['body'],
                    "none"
                )
                success_count += 1
            except Exception as email_error:
                print(f"Failed to send email to {email_data['email']}: {email_error}")
        
        # Mark policy as implemented
        if db.update_policy(policy['id'], status="Implemented"):
            return True, f"Policy #{policy['id']} successfully implemented and sent to {success_count}/{len(email_list)} recipients!", success_count
        else:
            return False, "Failed to update policy status in database", success_count
            
    except Exception as e:
        return False, f"Error implementing policy: {str(e)}", 0

def search_employees_full(self, **kwargs):
    """
    Search employees by various criteria and return full employee records
    (Modified version of search_employees that returns full records instead of just emails)
    """
    conn = self.get_connection()
    
    conditions = []
    values = []
    
    for field, value in kwargs.items():
        if field in ['name', 'gender', 'position', 'department', 'work_mode']:
            conditions.append(f"{field} = ?")
            values.append(value)
        elif field == 'min_age':
            conditions.append("age >= ?")
            values.append(value)
        elif field == 'max_age':
            conditions.append("age <= ?")
            values.append(value)
    
    if not conditions:
        print("❌ No valid search criteria provided.")
        conn.close()
        return pd.DataFrame()
    
    try:
        query = f"SELECT * FROM employee WHERE {' AND '.join(conditions)}"
        df = pd.read_sql_query(query, conn, params=values)
        return df
    
    except sqlite3.Error as e:
        print(f"❌ Error searching employees: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

# --- Policy Status Page ---
def policy_status_page():
    policy = st.session_state.policy_status_view
    
    if not policy:
        st.error("No policy selected for status view.")
        if st.button("Back to Dashboard"):
            st.session_state.current_page = 'dashboard'
            st.session_state.policy_status_view = None
            st.rerun()
        return
    
    # Header with back button
    col1, col2 = st.columns([1, 6])
    with col1:
        if st.button("← Back", type="secondary"):
            st.session_state.current_page = 'dashboard'
            st.session_state.policy_status_view = None
            st.rerun()
    
    with col2:
        st.markdown(f"<h1 style='color: #0066CC;'>Policy Status - #{policy['id']}</h1>", unsafe_allow_html=True)
    
    st.write("---")
    
    # Display policy details
    st.markdown("### Policy Details")
    details_cols = st.columns([1, 1])
    with details_cols[0]:
        st.markdown(f"**Department:** {policy['department']}")
        st.markdown(f"**Work Mode:** {policy['work_mode']}")
        st.markdown(f"**Status:** {policy['status']}")
    
    st.markdown("### Policy Text")
    st.info(policy['text'])
    
    st.write("---")
    
    # Get real acknowledgement data from database
    try:
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
        WHERE a.policy_id = ?
        ORDER BY e.name
        """
        
        cursor.execute(query, (policy['id'],))
        acknowledgement_data = cursor.fetchall()
        conn.close()
        
        if acknowledgement_data:
            st.markdown("### Policy Recipients Status")
            
            # Convert data to DataFrame for easier handling
            columns = ['employee_id', 'employee_name', 'employee_email', 'department', 'work_mode', 'status', 'updated_at', 'created_at']
            status_df = pd.DataFrame(acknowledgement_data, columns=columns)
            
            # Display the status table with real data
            st.markdown("#### Recipients and Their Response Status")
            
            # Add refresh button
            col_refresh1, col_refresh2 = st.columns([1, 5])
            with col_refresh1:
                if st.button("🔄 Refresh", type="secondary"):
                    st.rerun()
            
            # Create custom table with status indicators
            for idx, row in status_df.iterrows():
                cols = st.columns([2.5, 2, 1.5, 2, 1.5])
                
                cols[0].write(row['employee_email'])
                cols[1].write(row['employee_name'])
                
                # Status with color coding
                status = row['status']
                if status == 'ack':
                    cols[2].markdown("✅ **Acknowledged**")
                    status_color = "green"
                elif status == 'nak':
                    cols[2].markdown("❌ **Not Acknowledged**") 
                    status_color = "red"
                else:  # not responded
                    cols[2].markdown("⏳ **Not Responded**")
                    status_color = "orange"
                
                # Show last updated time
                if row['updated_at']:
                    updated_time = pd.to_datetime(row['updated_at']).strftime('%Y-%m-%d %H:%M')
                    cols[3].write(f"Updated: {updated_time}")
                else:
                    created_time = pd.to_datetime(row['created_at']).strftime('%Y-%m-%d %H:%M')
                    cols[3].write(f"Created: {created_time}")
                
                # Manual status update button (for admin use)
                with cols[4]:
                    with st.popover("Update Status"):
                        new_status = st.selectbox(
                            "Status", 
                            ['not responded', 'ack', 'nak'], 
                            index=['not responded', 'ack', 'nak'].index(status),
                            key=f"status_select_{row['employee_id']}"
                        )
                        
                        if st.button("Update", key=f"update_status_{row['employee_id']}"):
                            success = db.update_acknowledgement_status(
                                policy['id'], 
                                row['employee_id'], 
                                new_status
                            )
                            if success:
                                st.success("Status updated successfully!")
                                st.rerun()
                            else:
                                st.error("Failed to update status")
            
            # Summary statistics with real data
            st.write("---")
            st.markdown("### Response Summary")
            
            summary_cols = st.columns(4)
            
            total_recipients = len(status_df)
            ack_count = len(status_df[status_df['status'] == 'ack'])
            nak_count = len(status_df[status_df['status'] == 'nak'])
            not_responded = len(status_df[status_df['status'] == 'not responded'])
            
            with summary_cols[0]:
                st.metric("Total Recipients", total_recipients)
            
            with summary_cols[1]:
                st.metric("Acknowledged", ack_count, delta=None)
            
            with summary_cols[2]:
                st.metric("Not Acknowledged", nak_count, delta=None)
            
            with summary_cols[3]:
                st.metric("Not Responded", not_responded, delta=None)
            
            # Progress bar and response rate
            if total_recipients > 0:
                response_rate = ((ack_count + nak_count) / total_recipients) * 100
                acknowledgement_rate = (ack_count / total_recipients) * 100
                
                progress_cols = st.columns(2)
                with progress_cols[0]:
                    st.markdown(f"**Response Rate: {response_rate:.1f}%**")
                    st.progress(response_rate / 100)
                
                with progress_cols[1]:
                    st.markdown(f"**Acknowledgement Rate: {acknowledgement_rate:.1f}%**")
                    st.progress(acknowledgement_rate / 100)
                
                # Show detailed breakdown
                st.markdown("#### Detailed Breakdown")
                breakdown_data = {
                    'Status': ['Acknowledged', 'Not Acknowledged', 'Not Responded'],
                    'Count': [ack_count, nak_count, not_responded],
                    'Percentage': [
                        f"{(ack_count/total_recipients)*100:.1f}%",
                        f"{(nak_count/total_recipients)*100:.1f}%", 
                        f"{(not_responded/total_recipients)*100:.1f}%"
                    ]
                }
                breakdown_df = pd.DataFrame(breakdown_data)
                st.dataframe(breakdown_df, hide_index=True, use_container_width=True)
        
        else:
            st.warning("No acknowledgement records found for this policy. This might indicate:")
            st.write("- No employees match the policy criteria (department/work mode)")
            st.write("- The policy was created before the acknowledgement system was implemented")
            st.write("- There might be an issue with the database")
            
            # Show which employees would be eligible
            try:
                eligible_employees_df = db.search_employees_full(
                    department=policy['department'], 
                    work_mode=policy['work_mode']
                )
                
                if not eligible_employees_df.empty:
                    st.markdown("#### Eligible Employees (not yet in acknowledgement system):")
                    st.dataframe(eligible_employees_df[['name', 'email', 'department', 'work_mode']], 
                               hide_index=True, use_container_width=True)
                    
                    if st.button("Create Acknowledgement Entries for These Employees"):
                        employee_ids = eligible_employees_df['id'].tolist()
                        db.create_acknowledgement_entries(policy['id'], employee_ids)
                        st.success(f"Created acknowledgement entries for {len(employee_ids)} employees!")
                        st.rerun()
                else:
                    st.info("No employees found matching this policy's criteria.")
                    
            except Exception as e:
                st.error(f"Error checking eligible employees: {str(e)}")
            
    except Exception as e:
        st.error(f"Error fetching acknowledgement data: {str(e)}")
        st.write("Please check your database connection and ensure the tables exist.")
        
        # Provide some debugging information
        with st.expander("Debug Information"):
            st.write(f"Policy ID: {policy.get('id', 'Not found')}")
            st.write(f"Database file: {db.db_name}")
            st.write(f"Error details: {str(e)}")

# --- Dashboard Page ---
def dashboard_page():
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    if st.sidebar.button("Logout"):
        st.session_state.authenticated = False
        st.session_state.username = ''
        st.session_state.current_page = 'dashboard'
        st.session_state.policy_status_view = None
        st.rerun()
    
    st.markdown("<h1 style='text-align: center; color: #0066CC;'>Policy Dashboard</h1>", unsafe_allow_html=True)
    st.write("---")

    # Add New Policy
    with st.expander("Add New Policy"):
        new_text = st.text_input("Policy Text")
        new_department = st.selectbox("Department", ["HR", "IT", "Compliance", "Finance", "Operations"])
        new_workmode = st.selectbox("Work Mode", ["Onsite", "Remote"])
        new_status = st.selectbox("Status", ["Not Implemented", "Implemented"])
        
        if st.button("Add Policy"):
            if new_text.strip():
                success = db.insert_policy(new_text, new_department, new_workmode, new_status)
                if success:
                    st.success("Policy added successfully!")
                    st.rerun()
            else:
                st.error("Please enter policy text.")

    # Get all policies from database
    policies_df = db.view_policies()
    
    if not policies_df.empty:
        st.markdown("### Current Policies")
        
        # Create header row
        header_cols = st.columns([0.5, 3, 1.2, 1.2, 1.5, 3])
        header_cols[0].markdown("**ID**")
        header_cols[1].markdown("**Policy**")
        header_cols[2].markdown("**Department**")
        header_cols[3].markdown("**Work Mode**")
        header_cols[4].markdown("**Status**")
        header_cols[5].markdown("**Actions**")

        # Display each policy
        for _, row in policies_df.iterrows():
            cols = st.columns([0.5, 3, 1.2, 1.2, 1.5, 3])
            
            cols[0].write(str(row['id']))
            cols[1].write(row['policy_text'])
            cols[2].write(row['department'])
            cols[3].write(row['work_mode'])
            
            # Status with color coding
            if row['status'] == 'Implemented':
                cols[4].markdown("✅ **Implemented**")
            else:
                cols[4].markdown("❌ **Not Implemented**")

            # Action buttons
            with cols[5]:
                action_cols = st.columns([1, 1, 1, 1])
                
                # Status button
                with action_cols[0]:
                    if st.button("📊 Status", key=f"status_{row['id']}", help="View recipient status"):
                        st.session_state.policy_status_view = {
                            'id': row['id'],
                            'text': row['policy_text'],
                            'department': row['department'],
                            'work_mode': row['work_mode'],
                            'status': row['status']
                        }
                        st.session_state.current_page = 'policy_status'
                        st.rerun()
                
                # Edit button
                with action_cols[1]:
                    if st.button("✏️ Edit", key=f"edit_{row['id']}"):
                        st.session_state[f"editing_{row['id']}"] = True
                        st.rerun()
                
                # Delete button
                with action_cols[2]:
                    if st.button("🗑️ Delete", key=f"delete_{row['id']}", type="secondary"):
                        if db.delete_policy(row['id']):
                            st.success(f"Policy {row['id']} deleted!")
                            st.rerun()
                
                # MODIFIED: Implement button with background processing
                with action_cols[3]:
                    if row['status'] == "Not Implemented":
                        if st.button("🚀 Implement", key=f"implement_{row['id']}", type="primary"):
                            # Create policy object for background processing
                            policy = {
                                'id': row['id'],
                                'text': row['policy_text'],
                                'department': row['department'],
                                'work_mode': row['work_mode']
                            }
                            
                            # Create placeholders for status updates
                            status_placeholder = st.empty()
                            progress_bar = st.progress(0)
                            
                            try:
                                implement_policy_background(policy)
                            #     # Step 1: Finding recipients
                                status_placeholder.info("📋 Finding recipients...")
                                progress_bar.progress(20)
                                time.sleep(0.5)  # Brief pause for visual feedback
                                
                                
                            #     # Step 2: Processing with AI
                                status_placeholder.info("🤖 Processing with AI...")
                                progress_bar.progress(40)
                                time.sleep(0.5)
                            
                                
                            #     # Step 3: Sending emails
                                status_placeholder.info("📧 Sending emails...")
                                progress_bar.progress(70)
                                time.sleep(0.5)
                                
                                
                            #     # Step 4: Updating database
                                status_placeholder.info("💾 Updating database...")
                                progress_bar.progress(90)
                                time.sleep(0.5)
                                
                                
                            #     # Success
                                progress_bar.progress(100)
                                status_placeholder.success(f"✅ Policy #{policy['id']} implemented successfully! Sent to  recipients.")
                                time.sleep(0.5)
                                st.rerun()
                                
                                
                            except Exception as e:
                                status_placeholder.error(f"❌ Error implementing policy: {str(e)}")
                                progress_bar.empty()
                                time.sleep(3)
                                status_placeholder.empty()
                    else:
                        st.markdown("✅ **Done**")

            # Edit form (appears when edit button is clicked)
            if st.session_state.get(f"editing_{row['id']}", False):
                with st.container():
                    st.write("---")
                    st.subheader(f"Edit Policy {row['id']}")
                    
                    edit_cols = st.columns([2, 1, 1, 1])
                    
                    with edit_cols[0]:
                        edited_text = st.text_area(
                            "Policy Text", 
                            value=row['policy_text'], 
                            key=f"edit_text_{row['id']}"
                        )
                    
                    with edit_cols[1]:
                        edited_department = st.selectbox(
                            "Department",
                            ["HR", "IT", "Compliance", "Finance", "Operations"],
                            index=["HR", "IT", "Compliance", "Finance", "Operations"].index(row['department']) 
                            if row['department'] in ["HR", "IT", "Compliance", "Finance", "Operations"] else 0,
                            key=f"edit_dept_{row['id']}"
                        )
                    
                    with edit_cols[2]:
                        edited_workmode = st.selectbox(
                            "Work Mode",
                            ["Onsite", "Remote"],
                            index=0 if row['work_mode'] == "Onsite" else 1,
                            key=f"edit_mode_{row['id']}"
                        )
                    
                    with edit_cols[3]:
                        edited_status = st.selectbox(
                            "Status",
                            ["Not Implemented", "Implemented"],
                            index=0 if row['status'] == "Not Implemented" else 1,
                            key=f"edit_status_{row['id']}"
                        )
                    
                    # Save/Cancel buttons
                    save_cols = st.columns([1, 1, 8])
                    
                    with save_cols[0]:
                        if st.button("Save Changes", key=f"save_{row['id']}", type="primary"):
                            if edited_text.strip():
                                success = db.update_policy(
                                    row['id'],
                                    policy_text=edited_text,
                                    department=edited_department,
                                    work_mode=edited_workmode,
                                    status=edited_status
                                )
                                if success:
                                    st.success("Policy updated successfully!")
                                    del st.session_state[f"editing_{row['id']}"]
                                    st.rerun()
                            else:
                                st.error("Policy text cannot be empty.")
                    
                    with save_cols[1]:
                        if st.button("Cancel", key=f"cancel_{row['id']}"):
                            del st.session_state[f"editing_{row['id']}"]
                            st.rerun()
                    
                    st.write("---")

    else:
        st.info("No policies found in the database.")

    # Policy Statistics
    if not policies_df.empty:
        st.markdown("### Policy Statistics")
        
        stats_cols = st.columns(4)
        
        total_policies = len(policies_df)
        implemented = len(policies_df[policies_df['status'] == 'Implemented'])
        not_implemented = len(policies_df[policies_df['status'] == 'Not Implemented'])
        implementation_rate = (implemented / total_policies * 100) if total_policies > 0 else 0
        
        with stats_cols[0]:
            st.metric("Total Policies", total_policies)
        
        with stats_cols[1]:
            st.metric("Implemented", implemented)
        
        with stats_cols[2]:
            st.metric("Not Implemented", not_implemented)
        
        with stats_cols[3]:
            st.metric("Implementation Rate", f"{implementation_rate:.1f}%")

        # Department-wise breakdown
        if 'department' in policies_df.columns:
            st.markdown("### Department-wise Policy Distribution")
            dept_stats = policies_df.groupby(['department', 'status']).size().unstack(fill_value=0)
            st.bar_chart(dept_stats)

# --- Main Application Logic ---
if not st.session_state.authenticated:
    login_page()
else:
    # Handle different pages based on current_page session state
    if st.session_state.current_page == 'dashboard':
        dashboard_page()
    elif st.session_state.current_page == 'policy_status':
        policy_status_page()
    else:
        # Fallback to dashboard if unknown page
        st.session_state.current_page = 'dashboard'
        dashboard_page()

# --- Footer ---
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")