import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import base64
from datetime import datetime
import logging
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

def get_address_from_coords(lat, lon):
    """
    Performs reverse geocoding to get a human-readable address.
    """
    try:
        geolocator = Nominatim(user_agent="indiscan_lpr_system")
        location = geolocator.reverse(f"{lat}, {lon}", timeout=10)
        if location:
            return location.address
        return "Address Unavailable"
    except Exception as e:
        logger.error(f"Reverse geocoding failed: {e}")
        return "Address Unavailable"

def send_stolen_vehicle_alert(plate, details, image_base64, recipient_email=None, lat=None, lon=None, officer_email=None):
    """
    Sends an email alert when a stolen vehicle is detected.
    
    Args:
        plate (str): The detected license plate number.
        details (dict): Additional vehicle details from the database.
        image_base64 (str): Base64 encoded image of the detected plate or vehicle.
        recipient_email (str, optional): The email address of the vehicle owner.
        lat (str, optional): Detected latitude.
        lon (str, optional): Detected longitude.
        officer_email (str, optional): The email address of the scanning officer.
    """
    sender_email = os.getenv('ALERT_EMAIL')
    sender_password = os.getenv('ALERT_PASSWORD')
    
    # If no recipient_email provided, fallback to the sender_email (admin)
    if not recipient_email:
        recipient_email = sender_email 
    
    if not sender_email or not sender_password:
        logger.error("Email credentials not found in environment variables.")
        return False

    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = f"IndiScan Alert <{sender_email}>"
        msg['To'] = recipient_email
        msg['Subject'] = f"🚨 STOLEN VEHICLE ALERT: {plate}"

        # Get current time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get human-readable address if coordinates are available
        address = "Unavailable"
        if lat and lon:
            address = get_address_from_coords(lat, lon)

        # Create body
        location_info = ""
        if lat and lon:
            map_url = f"https://www.google.com/maps?q={lat},{lon}"
            location_info = f"""
            <div style="background-color: #e2f3f5; padding: 15px; border-radius: 5px; border: 1px solid #3d5afe; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #3d5afe;">📍 Officer's Current Location (Scanning Point):</h3>
                <p>The vehicle was spotted by an officer at this coordinate address:</p>
                <p><strong>Actual Address:</strong> {address}</p>
                <p><strong>Coordinates:</strong> {lat}, {lon}</p>
                <p><a href="{map_url}" style="background-color: #3d5afe; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">View on Google Maps</a></p>
            </div>
            """
        else:
             # In mandatory GPS mode, this should theoretically not be hit if coordinates are missing
             location_info = """
            <div style="background-color: #fff3cd; padding: 15px; border-radius: 5px; border: 1px solid #856404; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #856404;">⚠ Location Warning:</h3>
                <p>The scanning officer's GPS coordinates were unavailable at the time of detection.</p>
            </div>
            """

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="background-color: #f8d7da; color: #721c24; padding: 20px; border-radius: 5px; border: 1px solid #f5c6cb; margin-bottom: 20px;">
                <h2 style="margin-top: 0;">🚨 Stolen Vehicle Detected!</h2>
                <p>Dear {details.get('owner_name', 'Vehicle Owner') if details else 'Vehicle Owner'},</p>
                <p>A vehicle marked as <strong>STOLEN</strong> has been detected by a patrolling officer.</p>
            </div>
            
            {location_info}

            <h3>Detection Details:</h3>
            <ul>
                <li><strong>Plate Number:</strong> {plate}</li>
                <li><strong>Detection Time:</strong> {now}</li>
            </ul>
        """
        
        if details:
            body += "<h3>Vehicle Information:</h3><ul>"
            body += f"<li><strong>Vehicle Model:</strong> {details.get('vehicle_name', 'N/A')}</li>"
            body += f"<li><strong>Manufacturer:</strong> {details.get('vehicle_category', 'N/A')}</li>"
            body += "</ul>"
            
        if officer_email:
            body += f"""
            <div style="background-color: #f1f8ff; padding: 15px; border-radius: 5px; border: 1px solid #cce5ff; margin-bottom: 20px;">
                <h3 style="margin-top: 0; color: #004085;">👮 Officer Contact:</h3>
                <p>You can reach out to the scanning officer directly at this email address regarding the detection:</p>
                <p><strong>Email:</strong> <a href="mailto:{officer_email}">{officer_email}</a></p>
            </div>
            """
            
        body += """
            <p>If you have any information or if this vehicle is currently with you, please contact the local authorities immediately.</p>
            <h3>Detection Image:</h3>
            <p>See attached image for reference.</p>
            <br>
            <p style="font-size: 0.8em; color: #666;">This is an automated alert from the IndiScan LPR System.</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(body, 'html'))

        # Attach image
        if image_base64:
            try:
                # Remove base64 header if present
                if ',' in image_base64:
                    image_base64 = image_base64.split(',')[1]
                
                img_data = base64.b64decode(image_base64)
                img = MIMEImage(img_data)
                img.add_header('Content-ID', '<detection_image>')
                msg.attach(img)
            except Exception as img_e:
                logger.error(f"Failed to attach image to email: {img_e}")

        # Connect and send
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
            
        logger.info(f"Stolen vehicle alert email sent for plate {plate}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False
