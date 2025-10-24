# app/services/email_service.py

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import os
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.sendgrid_api_key = os.getenv("SENDGRID_API_KEY", "")
        self.sender_email = os.getenv("SENDER_EMAIL", "")
        
        # Check if email is configured
        self.is_configured = bool(self.sendgrid_api_key and self.sender_email)
        
        if not self.is_configured:
            logger.warning("⚠️  SendGrid not configured. Set SENDGRID_API_KEY and SENDER_EMAIL env variables.")
    
    def send_application_confirmation(self, user_email: str, user_name: str, job_title: str, 
                                    company_name: str, job_location: str) -> bool:
        """Send application confirmation email using SendGrid API"""
        if not self.is_configured:
            logger.info("📧 SendGrid not configured, skipping application email")
            return False
        
        try:
            # Create the email message
            message = Mail(
                from_email=Email(self.sender_email, "Job-Swipe"),
                to_emails=To(user_email),
                subject="✓ Application Submitted - Job-Swipe"
            )
            
            # HTML content with unsubscribe
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        margin: 0;
                        padding: 0;
                        background-color: #f5f5f5;
                    }}
                    .email-container {{
                        max-width: 600px;
                        margin: 40px auto;
                        background-color: #ffffff;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 40px 20px;
                        text-align: center;
                        color: white;
                    }}
                    .header-icon {{
                        font-size: 48px;
                        margin-bottom: 10px;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 32px;
                        font-weight: 600;
                    }}
                    .success-badge {{
                        background-color: #d4edda;
                        color: #155724;
                        padding: 12px 24px;
                        margin: 20px;
                        border-radius: 6px;
                        display: inline-block;
                        font-weight: 500;
                    }}
                    .content {{
                        padding: 40px;
                    }}
                    .job-title {{
                        font-size: 24px;
                        font-weight: 600;
                        color: #1a202c;
                        margin: 0 0 10px 0;
                    }}
                    .company-info {{
                        color: #718096;
                        font-size: 16px;
                        margin-bottom: 30px;
                    }}
                    .message-box {{
                        background-color: #f7fafc;
                        border-left: 4px solid #667eea;
                        padding: 20px;
                        margin: 30px 0;
                        border-radius: 4px;
                    }}
                    .message-box p {{
                        margin: 10px 0;
                    }}
                    .sent-items {{
                        margin: 20px 0;
                    }}
                    .sent-items h3 {{
                        font-size: 16px;
                        font-weight: 600;
                        margin-bottom: 10px;
                    }}
                    .sent-items ul {{
                        list-style: none;
                        padding: 0;
                    }}
                    .sent-items li {{
                        padding: 8px 0;
                        padding-left: 24px;
                        position: relative;
                    }}
                    .sent-items li:before {{
                        content: "•";
                        position: absolute;
                        left: 8px;
                        color: #667eea;
                        font-weight: bold;
                    }}
                    .footer-note {{
                        background-color: #e6f2ff;
                        padding: 20px;
                        margin-top: 30px;
                        border-radius: 6px;
                        display: flex;
                        align-items: center;
                    }}
                    .footer-note-icon {{
                        font-size: 24px;
                        margin-right: 12px;
                    }}
                    .footer {{
                        background-color: #f7fafc;
                        padding: 20px;
                        text-align: center;
                        color: #718096;
                        font-size: 14px;
                    }}
                    .unsubscribe {{
                        font-size: 12px;
                        line-height: 20px;
                        margin-top: 10px;
                        text-align: center;
                    }}
                    .unsubscribe a {{
                        color: #667eea;
                        text-decoration: none;
                    }}
                    .unsubscribe a:hover {{
                        text-decoration: underline;
                    }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <!-- Header -->
                    <div class="header">
                        <div class="header-icon">✨</div>
                        <h1>Job-Swipe</h1>
                    </div>
                    
                    <!-- Success Badge -->
                    <div style="text-align: center; margin-top: -10px;">
                        <div class="success-badge">
                            ✓ Application Submitted
                        </div>
                    </div>
                    
                    <!-- Content -->
                    <div class="content">
                        <!-- Job Details -->
                        <h2 class="job-title">{job_title}</h2>
                        <div class="company-info">
                            <strong>{company_name}</strong> • {job_location}
                        </div>
                        
                        <!-- Message Box -->
                        <div class="message-box">
                            <p>Hi {user_name},</p>
                            <p>Great news! Your application has been successfully submitted through Job-Swipe.</p>
                            
                            <div class="sent-items">
                                <h3>What was sent:</h3>
                                <ul>
                                    <li>Your Application</li>
                                    <li>Resume</li>
                                </ul>
                            </div>
                            
                            <p>Good luck! 🍀</p>
                        </div>
                        
                        <!-- Footer Note -->
                        <div class="footer-note">
                            <span class="footer-note-icon">📱</span>
                            <div>
                                <strong>Track your application</strong> in the Job-Swipe mobile app
                            </div>
                        </div>
                    </div>
                    
                    <!-- Footer -->
                    <div class="footer">
                        <p>This is an automated message from Job-Swipe.</p>
                        <p>© 2025 Job-Swipe. All rights reserved.</p>
                        
                        <!-- Unsubscribe Section -->
                        <div class="unsubscribe">
                            <p>
                                <a href="<%asm_group_unsubscribe_raw_url%>">Unsubscribe</a> | 
                                <a href="<%asm_preferences_raw_url%>">Email Preferences</a>
                            </p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            message.content = Content("text/html", html_content)
            
            # Enable click tracking and unsubscribe
            message.tracking_settings = {
                "click_tracking": {"enable": True},
                "open_tracking": {"enable": True}
            }
            
            # Send via SendGrid API
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            logger.info(f"✅ Application confirmation email sent to {user_email} (Status: {response.status_code})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send application email: {e}")
            return False
    
    def send_saved_job_notification(self, user_email: str, user_name: str, 
                                   job_title: str, company_name: str) -> bool:
        """Send saved job notification email using SendGrid API"""
        if not self.is_configured:
            logger.info("📧 SendGrid not configured, skipping saved job email")
            return False
        
        try:
            message = Mail(
                from_email=Email(self.sender_email, "Job-Swipe"),
                to_emails=To(user_email),
                subject="💾 Job Saved - Job-Swipe"
            )
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        margin: 0;
                        padding: 0;
                        background-color: #f5f5f5;
                    }}
                    .email-container {{
                        max-width: 600px;
                        margin: 40px auto;
                        background-color: #ffffff;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        padding: 40px 20px;
                        text-align: center;
                        color: white;
                    }}
                    .content {{
                        padding: 40px;
                    }}
                    .job-title {{
                        font-size: 24px;
                        font-weight: 600;
                        margin-bottom: 10px;
                    }}
                    .message-box {{
                        background-color: #f7fafc;
                        border-left: 4px solid #667eea;
                        padding: 20px;
                        margin: 20px 0;
                        border-radius: 4px;
                    }}
                    .footer {{
                        background-color: #f7fafc;
                        padding: 20px;
                        text-align: center;
                        color: #718096;
                        font-size: 14px;
                    }}
                    .unsubscribe {{
                        font-size: 12px;
                        margin-top: 10px;
                    }}
                    .unsubscribe a {{
                        color: #667eea;
                        text-decoration: none;
                    }}
                </style>
            </head>
            <body>
                <div class="email-container">
                    <div class="header">
                        <h1>💾 Job Saved</h1>
                    </div>
                    <div class="content">
                        <div class="message-box">
                            <p>Hi {user_name},</p>
                            <p>You've saved this job for later:</p>
                            <h2 class="job-title">{job_title}</h2>
                            <p><strong>{company_name}</strong></p>
                            <p>You can view all your saved jobs in the Job-Swipe app anytime.</p>
                        </div>
                    </div>
                    <div class="footer">
                        <p>© 2025 Job-Swipe. All rights reserved.</p>
                        <div class="unsubscribe">
                            <p>
                                <a href="<%asm_group_unsubscribe_raw_url%>">Unsubscribe</a> | 
                                <a href="<%asm_preferences_raw_url%>">Email Preferences</a>
                            </p>
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            
            message.content = Content("text/html", html_content)
            
            # Enable tracking
            message.tracking_settings = {
                "click_tracking": {"enable": True},
                "open_tracking": {"enable": True}
            }
            
            sg = SendGridAPIClient(self.sendgrid_api_key)
            response = sg.send(message)
            
            logger.info(f"✅ Saved job notification sent to {user_email} (Status: {response.status_code})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send saved job email: {e}")
            return False

# Singleton instance
email_service = EmailService()