import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
import os
import logging

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # Email configuration - hardcoded credentials
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = "jiyanshujain321@gmail.com"
        self.sender_password = "vrrqxltjuwmespbs"
        self.app_name = "Job-Swipe"
        
    def create_application_email_html(self, user_name, job_title, company_name, location):
        """Create HTML email template for job application confirmation"""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                    background-color: #f4f4f4;
                }}
                .container {{
                    max-width: 600px;
                    margin: 20px auto;
                    background: white;
                    border-radius: 8px;
                    overflow: hidden;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 30px 20px;
                    text-align: center;
                }}
                .logo {{
                    font-size: 32px;
                    font-weight: bold;
                    color: white;
                    margin-bottom: 10px;
                }}
                .content {{
                    padding: 40px 30px;
                }}
                .success-badge {{
                    display: inline-flex;
                    align-items: center;
                    background-color: #e8f5e9;
                    color: #2e7d32;
                    padding: 8px 16px;
                    border-radius: 20px;
                    font-size: 14px;
                    font-weight: 600;
                    margin-bottom: 20px;
                }}
                .checkmark {{
                    display: inline-block;
                    width: 16px;
                    height: 16px;
                    background-color: #4caf50;
                    border-radius: 50%;
                    margin-right: 8px;
                    position: relative;
                }}
                .checkmark:after {{
                    content: "✓";
                    color: white;
                    position: absolute;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    font-size: 12px;
                }}
                .job-title {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #1a1a1a;
                    margin: 20px 0 10px 0;
                }}
                .company-info {{
                    color: #666;
                    font-size: 16px;
                    margin-bottom: 30px;
                }}
                .company-name {{
                    font-weight: 600;
                    color: #333;
                }}
                .message {{
                    background-color: #f9f9f9;
                    padding: 20px;
                    border-radius: 6px;
                    margin: 20px 0;
                    border-left: 4px solid #667eea;
                }}
                .items-list {{
                    list-style: none;
                    padding: 0;
                    margin: 20px 0;
                }}
                .items-list li {{
                    padding: 8px 0;
                    padding-left: 25px;
                    position: relative;
                }}
                .items-list li:before {{
                    content: "•";
                    color: #667eea;
                    font-weight: bold;
                    position: absolute;
                    left: 0;
                }}
                .mobile-app-highlight {{
                    background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%);
                    border: 2px solid #667eea;
                    border-radius: 8px;
                    padding: 20px;
                    margin: 25px 0;
                    text-align: center;
                }}
                .mobile-app-highlight .icon {{
                    font-size: 36px;
                    margin-bottom: 10px;
                }}
                .mobile-app-highlight h3 {{
                    color: #667eea;
                    margin: 10px 0;
                    font-size: 20px;
                }}
                .mobile-app-highlight p {{
                    color: #555;
                    margin: 10px 0;
                    font-size: 15px;
                }}
                .footer {{
                    background-color: #f9f9f9;
                    padding: 20px 30px;
                    text-align: center;
                    color: #666;
                    font-size: 14px;
                    border-top: 1px solid #eee;
                }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    text-decoration: none;
                    border-radius: 6px;
                    font-weight: 600;
                    margin: 20px 0;
                    transition: transform 0.2s;
                }}
                .button:hover {{
                    transform: translateY(-2px);
                }}
                .status-note {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                    font-size: 14px;
                    color: #856404;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <div style="font-size: 48px; margin-bottom: 10px;">📧</div>
                    <div class="logo">{self.app_name}</div>
                </div>
                
                <div class="content">
                    <div class="success-badge">
                        <span class="checkmark"></span>
                        Application submitted
                    </div>
                    
                    <div class="job-title">{job_title}</div>
                    
                    <div class="company-info">
                        <span class="company-name">{company_name}</span> - {location}
                    </div>
                    
                    <div class="message">
                        <p>Hi {user_name},</p>
                        <p>Great news! Your application has been successfully submitted through {self.app_name}.</p>
                        <p><strong>The following items were sent to {company_name}:</strong></p>
                        <ul class="items-list">
                            <li>Application</li>
                            <li>Resume</li>
                        </ul>
                        <p>Good luck! 🍀</p>
                    </div>
                    
                    <div class="mobile-app-highlight">
                        <div class="icon">📱</div>
                        <h3>Track Your Application</h3>
                        <p><strong>Stay updated on-the-go!</strong></p>
                        <p>Open the {self.app_name} mobile app to track your application status, receive real-time notifications, and manage all your job applications in one place.</p>
                    </div>
                    
                    <div class="status-note">
                        <strong>📊 What's Next?</strong><br>
                        We'll keep you updated on the status of your application. The employer will reach out directly if they're interested in moving forward with your candidacy.
                    </div>
                </div>
                
                <div class="footer">
                    <p>This email was sent by {self.app_name}</p>
                    <p>© {datetime.now().year} {self.app_name}. All rights reserved.</p>
                    <p style="font-size: 12px; margin-top: 10px;">
                        This is an automated message. Please do not reply to this email.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        return html
    
    async def send_application_confirmation(
        self, 
        recipient_email: str, 
        user_name: str, 
        job_title: str, 
        company_name: str, 
        location: str
    ):
        """Send application confirmation email to user"""
        try:
            logger.info(f"📧 Sending application confirmation email to {recipient_email}")
            
            if not self.sender_email or not self.sender_password:
                logger.error("❌ Email credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"{self.app_name} Application: {job_title}"
            msg['From'] = f"{self.app_name} <{self.sender_email}>"
            msg['To'] = recipient_email
            
            # Create HTML content
            html_content = self.create_application_email_html(
                user_name=user_name,
                job_title=job_title,
                company_name=company_name,
                location=location
            )
            
            # Create plain text version
            text_content = f"""
            Application Submitted - {self.app_name}
            
            Hi {user_name},
            
            Your application has been successfully submitted!
            
            Job Title: {job_title}
            Company: {company_name}
            Location: {location}
            
            The following items were sent to {company_name}:
            • Application
            • Resume
            
            📱 TRACK YOUR APPLICATION
            Open the {self.app_name} mobile app to track your application status, receive real-time notifications, and manage all your job applications in one place.
            
            Good luck!
            
            What's Next?
            We'll keep you updated on the status of your application. The employer will reach out directly if they're interested in moving forward.
            
            ---
            This is an automated message from {self.app_name}.
            © {datetime.now().year} {self.app_name}. All rights reserved.
            """
            
            # Attach both plain text and HTML versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"✅ Email sent successfully to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send email: {str(e)}")
            return False
    
    async def send_saved_job_notification(
        self, 
        recipient_email: str, 
        user_name: str, 
        job_title: str, 
        company_name: str
    ):
        """Send notification when user saves a job"""
        try:
            logger.info(f"📧 Sending saved job notification to {recipient_email}")
            
            if not self.sender_email or not self.sender_password:
                logger.error("❌ Email credentials not configured")
                return False
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"Job Saved - {job_title}"
            msg['From'] = f"{self.app_name} <{self.sender_email}>"
            msg['To'] = recipient_email
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <div style="max-width: 600px; margin: 0 auto; background: #f9f9f9; padding: 30px; border-radius: 10px;">
                    <h2 style="color: #667eea;">💾 Job Saved</h2>
                    <p>Hi {user_name},</p>
                    <p>You saved a job on {self.app_name}!</p>
                    <div style="background: white; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin: 0 0 10px 0;">{job_title}</h3>
                        <p style="color: #666; margin: 0;">{company_name}</p>
                    </div>
                    <div style="background: linear-gradient(135deg, #667eea15 0%, #764ba215 100%); border: 2px solid #667eea; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">
                        <div style="font-size: 36px; margin-bottom: 10px;">📱</div>
                        <p style="color: #667eea; font-weight: bold; font-size: 18px; margin: 10px 0;">Access Your Saved Jobs Anytime</p>
                        <p style="color: #555; margin: 10px 0;">Open the {self.app_name} mobile app to view all your saved jobs, apply when ready, and never miss an opportunity!</p>
                    </div>
                    <p>Don't forget to apply when you're ready!</p>
                </div>
            </body>
            </html>
            """
            
            part = MIMEText(html, 'html')
            msg.attach(part)
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"✅ Saved job notification sent to {recipient_email}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {str(e)}")
            return False

# Create singleton instance
email_service = EmailService()