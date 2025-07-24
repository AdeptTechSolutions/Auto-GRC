from flask import Flask, request, render_template_string, jsonify
import base64
import json
import logging
from datetime import datetime
# Import your database class
from db import CompanyDatabase

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
db = CompanyDatabase()

# HTML templates for response pages
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Policy Acknowledgement - Success</title>
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 600px; 
            margin: 50px auto; 
            padding: 20px;
            background-color: #f5f5f5;
        }
        .success-container { 
            background: white; 
            padding: 30px; 
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }
        .success-icon { 
            font-size: 48px; 
            color: #28a745; 
            margin-bottom: 20px;
        }
        .error-icon { 
            font-size: 48px; 
            color: #dc3545; 
            margin-bottom: 20px;
        }
        h1 { color: #333; }
        .details { 
            background: #f8f9fa; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 20px 0;
            text-align: left;
        }
        .back-link {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
        .back-link:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="success-container">
        <div class="{{ icon_class }}">{{ icon }}</div>
        <h1>{{ title }}</h1>
        <p>{{ message }}</p>
        
        {% if details %}
        <div class="details">
            <strong>Details:</strong><br>
            Policy ID: {{ details.policy_id }}<br>
            Employee: {{ details.employee_email }}<br>
            Status: {{ details.status }}<br>
            Timestamp: {{ details.timestamp }}
        </div>
        {% endif %}
        
        <p><em>You can now close this tab. No further action is required.</em></p>
    </div>
</body>
</html>
"""

def get_employee_id_by_email(email):
    """Get employee ID from email address"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM employee WHERE email = ?", (email,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting employee ID for email {email}: {e}")
        return None

@app.route('/acknowledge', methods=['GET'])
def handle_acknowledgement():
    """Handle policy acknowledgement link clicks"""
    try:
        # Get encoded data from URL parameter
        encoded_data = request.args.get('data')
        
        if not encoded_data:
            return render_template_string(SUCCESS_TEMPLATE, 
                title="Error",
                message="Invalid acknowledgement link - missing data parameter.",
                icon="❌",
                icon_class="error-icon",
                details=None
            ), 400
        
        # Decode the data
        try:
            decoded_data = base64.urlsafe_b64decode(encoded_data.encode()).decode()
            data = json.loads(decoded_data)
        except Exception as decode_error:
            logger.error(f"Failed to decode acknowledgement data: {decode_error}")
            return render_template_string(SUCCESS_TEMPLATE,
                title="Error",
                message="Invalid acknowledgement link - corrupted data.",
                icon="❌",
                icon_class="error-icon",
                details=None
            ), 400
        
        # Extract required fields
        policy_id = data.get('policy_id')
        employee_email = data.get('email')
        status = data.get('status')
        
        # Validate required fields
        if not all([policy_id, employee_email, status]):
            return render_template_string(SUCCESS_TEMPLATE,
                title="Error", 
                message="Invalid acknowledgement link - missing required data.",
                icon="❌",
                icon_class="error-icon",
                details=None
            ), 400
        
        # Validate status
        if status not in ['ack', 'nak']:
            return render_template_string(SUCCESS_TEMPLATE,
                title="Error",
                message="Invalid acknowledgement status.",
                icon="❌", 
                icon_class="error-icon",
                details=None
            ), 400
        
        # Get employee ID from email
        employee_id = get_employee_id_by_email(employee_email)
        if not employee_id:
            return render_template_string(SUCCESS_TEMPLATE,
                title="Error",
                message="Employee not found in database.",
                icon="❌",
                icon_class="error-icon", 
                details=None
            ), 404
        
        # Update acknowledgement status in database
        success = db.update_acknowledgement_status(policy_id, employee_id, status)
        
        if success:
            # Log the acknowledgement
            logger.info(f"Policy {policy_id} acknowledgement updated: {employee_email} -> {status}")
            
            # Prepare response details
            details = {
                'policy_id': policy_id,
                'employee_email': employee_email,
                'status': 'Acknowledged' if status == 'ack' else 'Not Acknowledged',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            if status == 'ack':
                return render_template_string(SUCCESS_TEMPLATE,
                    title="Policy Acknowledged Successfully!",
                    message="Thank you for acknowledging this policy. Your response has been recorded.",
                    icon="✅",
                    icon_class="success-icon",
                    details=details
                )
            else:
                return render_template_string(SUCCESS_TEMPLATE,
                    title="Policy Non-Acknowledgement Recorded",
                    message="Your non-acknowledgement has been recorded. HR will contact you for further discussion.",
                    icon="⚠️",
                    icon_class="error-icon",
                    details=details
                )
        else:
            logger.error(f"Failed to update acknowledgement for policy {policy_id}, employee {employee_email}")
            return render_template_string(SUCCESS_TEMPLATE,
                title="Database Error",
                message="Failed to record your acknowledgement. Please contact IT support.",
                icon="❌",
                icon_class="error-icon",
                details=None
            ), 500
            
    except Exception as e:
        logger.error(f"Unexpected error in acknowledgement handler: {e}")
        return render_template_string(SUCCESS_TEMPLATE,
            title="System Error",
            message="An unexpected error occurred. Please contact IT support.",
            icon="❌",
            icon_class="error-icon",
            details=None
        ), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'Policy Acknowledgement Service'
    })

@app.route('/stats', methods=['GET'])
def acknowledgement_stats():
    """Get acknowledgement statistics (optional endpoint for monitoring)"""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Get overall stats
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM acknowledgements 
            GROUP BY status
        """)
        
        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = row[1]
        
        conn.close()
        
        return jsonify({
            'acknowledgement_stats': stats,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting acknowledgement stats: {e}")
        return jsonify({'error': 'Failed to get stats'}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template_string(SUCCESS_TEMPLATE,
        title="Page Not Found",
        message="The requested page was not found.",
        icon="❌",
        icon_class="error-icon",
        details=None
    ), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template_string(SUCCESS_TEMPLATE,
        title="Internal Server Error", 
        message="An internal server error occurred. Please contact IT support.",
        icon="❌",
        icon_class="error-icon",
        details=None
    ), 500

if __name__ == '__main__':
    print("🚀 Starting Policy Acknowledgement Service...")
    print("📧 Listening for email acknowledgement links...")
    print("🌐 Service available at: http://localhost:5000")
    print("💡 Health check: http://localhost:5000/health")
    print("📊 Stats: http://localhost:5000/stats")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0',  # Listen on all interfaces
        port=5000,
        debug=True,      # Remove in production
        threaded=True    # Handle multiple requests concurrently
    )