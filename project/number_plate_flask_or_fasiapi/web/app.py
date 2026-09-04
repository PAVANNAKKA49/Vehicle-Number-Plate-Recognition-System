from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
from ultralytics import YOLO
from paddleocr import PaddleOCR
from pymongo import MongoClient
import os
import cv2
import re
import base64
import random
import string
from pyngrok import ngrok, conf
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

import logging
from dotenv import load_dotenv
from email_utils import send_stolen_vehicle_alert
import time

# Load environment variables
load_dotenv()

# Optimization: Bypass PaddleOCR connectivity check to speed up startup
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'

app = Flask(__name__)
CORS(app) # Enable CORS for all routes
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = os.getenv('SECRET_KEY', 'default-secret-key-for-local-dev')

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# -------------------------------
# LOAD MODELS & DATABASE
# -------------------------------
# These are global so they load once when the server starts
model = YOLO("number_plate.pt")
ocr = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)

# MongoDB Connection
MONGO_URI = os.getenv('MONGO_URI', "mongodb://localhost:27017")
DB_NAME = os.getenv('DB_NAME', "vehicle_db")
COLLECTION_NAME = os.getenv('COLLECTION_NAME', "ap_vehicle_records")
OCR_THRESHOLD = float(os.getenv('OCR_CONFIDENCE_THRESHOLD', 0.85))

try:
    # Set a shorter connection timeout for quicker failure if offline
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    client.admin.command('ping')
    logger.info("✓ Connected to MongoDB Intelligence Portal")
except Exception as e:
    logger.warning(f"⚠ Remote Intelligence Portal Unreachable (DNS/Network): {e}")
    logger.info("ℹ Attempting local fallback connection...")
    try:
        client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=2000)
        client.admin.command('ping')
        logger.info("✓ Successfully connected to local fallback database.")
    except Exception as local_e:
        logger.error(f"✗ Critical Failure: All database connections failed. {local_e}")

db = client[DB_NAME]
collection = db[COLLECTION_NAME]
users_collection = db["users"]

# Cache to prevent alert spam (Plate -> Timestamp)
recently_alerted = {}
ALERT_COOLDOWN = 300 # 5 minutes

# Data for generating new records (COMMENTED OUT - Support Manual Registration Only)
# LOCATIONS = ["Visakhapatnam","Vijayawada","Guntur","Nellore","Kurnool",
#              "Rajahmundry","Tirupati","Kadapa","Anantapur","Ongole",
#              "Hyderabad","Kakinada","Eluru","Chittoor"]
# 
# VEHICLE_TYPES = ["Petrol", "Diesel", "EV", "CNG", "Hybrid"]
# 
# VEHICLE_MAP = {
#     "Bike": ["Hero Splendor", "Bajaj Pulsar", "Royal Enfield Classic 350", "Yamaha FZ"],
#     "Car": ["Maruti Swift", "Hyundai i20", "Honda City", "Tata Nexon"],
#     "Bus": ["Volvo B8R", "Ashok Leyland 1616"],
#     "Truck": ["Tata Ace", "Mahindra Bolero Pickup"]
# }
# 
# NAMES = [
#     "Rajesh", "Ramesh", "Suresh", "Mahesh", "Ajay", "Anil", "Amit", "Arjun", "Aryan", "Ashok",
#     "Balaji", "Bhushan", "Bhargav", "Bhanu", "Bhavesh", "Bikram", "Bipin", "Bishal", "Brijesh", "Brijmohan",
#     "Chandra", "Chandran", "Chiranjeev", "Chirag", "Chirayu", "Chitra", "Charan", "Chakradhar", "Chandrakant", "Chandrasekar",
#     "Deepak", "Dhaval", "Dhiraj", "Dhruv", "Dhruvesh", "Dilip", "Dinesh", "Dinakar", "Dharmesh", "Darshit",
#     "Eshwar", "Eshwer", "Eswar", "Eswara", "Ekanth", "Eknath", "Ekalavya", "Ekaraj",
#     "Farhan", "Faisal", "Fahad", "Faraz", "Farooq", "Fardeen", "Faiz", "Fakhir", "Fareed", "Faiaz",
#     "Gaurav", "Gautam", "Govind", "Gopal", "Ghanshyam", "Girish", "Girdhar", "Giridhar", "Gajanan", "Gajendra",
#     "Harsh", "Harshad", "Harshit", "Harshul", "Hashim", "Harikrishna", "Hariom", "Hari", "Haresh", "Harmeet",
#     "Indresh", "Indrajit", "Inder", "Inderpal", "Ishant", "Ishwar", "Ishaan", "Ishaq", "Ish", "Iskander",
#     "Jagat", "Jagdish", "Jagjit", "Jagriti", "Jainendra", "Jaiveer", "Jaipal", "Jai", "Jairam", "Jais",
#     "Kamal", "Kamesh", "Karthik", "Kailash", "Karan", "Karun", "Karthikeyan", "Kalpesh", "Kalpit", "Kamran",
# ]
# 
# SURNAMES = [
#     "Sharma", "Singh", "Patel", "Kumar", "Reddy", "Rao", "Gupta", "Joshi", "Verma", "Pandey",
#     "Nair", "Menon", "Iyer", "Iyengar", "Desai", "Kapoor", "Malhotra", "Bhat", "Pillai", "Krishnan",
#     "Bhatnagar", "Chaudhary", "Mishra", "Tiwari", "Tripathi", "Saxena", "Sinha", "Dutta", "Roy", "Sen",
#     "Ghosh", "Banerjee", "Chatterjee", "Dasgupta", "Saha", "Mukherjee", "Ganguly", "Bose", "Dey", "Majumdar",
# ]
# 
states = {
    "AN":"Andaman and Nicobar","AP":"Andhra Pradesh","AR":"Arunachal Pradesh",
    "AS":"Assam","BR":"Bihar","CH":"Chandigarh","DN":"Dadra and Nagar Haveli",
    "DD":"Daman and Diu","DL":"Delhi","GA":"Goa","GJ":"Gujarat",
    "HR":"Haryana","HP":"Himachal Pradesh","JK":"Jammu and Kashmir",
    "KA":"Karnataka","KL":"Kerala","LD":"Lakshadweep","MP":"Madhya Pradesh",
    "MH":"Maharashtra","MN":"Manipur","ML":"Meghalaya","MZ":"Mizoram",
    "NL":"Nagaland","OD":"Odisha","PY":"Pondicherry","PN":"Punjab",
    "RJ":"Rajasthan","SK":"Sikkim","TN":"Tamil Nadu","TR":"Tripura",
    "UP":"Uttar Pradesh","WB":"West Bengal","CG":"Chhattisgarh",
    "TS":"Telangana","JH":"Jharkhand","UK":"Uttarakhand"
}


def mat_to_base64(img):
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

# -------------------------------
# AUTHENTICATION FUNCTIONS
# -------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def register_user(username, email, password):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = users_collection.find_one({"$or": [{"username": username}, {"email": email}]})
        if existing_user:
            return {"success": False, "message": "Username or email already exists"}
        
        # Create new user
        user = {
            "username": username,
            "email": email,
            "password": generate_password_hash(password)
        }
        users_collection.insert_one(user)
        return {"success": True, "message": "Registration successful"}
    except Exception as e:
        return {"success": False, "message": f"Registration error: {str(e)}"}

def authenticate_user(username, password):
    """Authenticate user login"""
    try:
        user = users_collection.find_one({"username": username})
        if user and check_password_hash(user["password"], password):
            return {"success": True, "user_id": str(user["_id"]), "username": user["username"], "email": user.get("email")}
        else:
            return {"success": False, "message": "Invalid username or password"}
    except Exception as e:
        return {"success": False, "message": f"Authentication error: {str(e)}"}

# -------------------------------
# HELPER FUNCTIONS FOR DATA GENERATION
# -------------------------------

# -------------------------------
# HELPER FUNCTIONS FOR DATA GENERATION (REMOVED/DISABLED)
# -------------------------------
# Auto-generation logic removed to support manual registration only.

def get_or_create_vehicle_record(number_plate):
    """
    Deprecated: Now only searches for existing records.
    Redirects to search_vehicle_record logic.
    """
    return search_vehicle_record(number_plate)


# Original mat_to_base64 remains unchanged
def mat_to_base64_old(img):
    _, buffer = cv2.imencode('.jpg', img)
    return base64.b64encode(buffer).decode('utf-8')

# Search for existing plate in database without modification
def search_vehicle_record(number_plate):
    """Search for existing vehicle record by number plate"""
    try:
        record = collection.find_one({"_id": number_plate})
        if record:
            return {
                "found": True,
                "data": record["details"],
                "is_stolen": record.get("is_stolen", False)
            }
        else:
            return {
                "found": False,
                "data": None
            }
    except Exception as e:
        print(f"Error searching database: {e}")
        return {
            "found": False,
            "data": None,
            "error": str(e)
        }

# -------------------------------
# CORE LOGIC WITH DATABASE INTEGRATION
# -------------------------------

def preprocess_plate(img):
    """Preprocess image to improve OCR accuracy"""
    try:
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Upscale if too small
        height, width = gray.shape
        if width < 300:
            scale_factor = 300 / width
            gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
        # Apply Adaptive Thresholding
        # binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # IMPORTANT: PaddleOCR expects 3-channel image (BGR), even if it looks grayscale.
        # Sending a 2D array (grayscale) causes 'IndexError: tuple index out of range' in normalization.
        processed_img = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return processed_img
    except Exception as e:
        print(f"Preprocessing error: {e}")
        return img

def clean_plate_text(text):
    """Clean and validate plate text"""
    # Remove common OCR artifacts for 'IND'
    text = re.sub(r'^(IND|1ND|IN0|IHD|1HD|IDN)', '', text, flags=re.IGNORECASE)
    
    # Remove non-alphanumeric except spaces
    text = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    return text

def correct_characters(text, pattern_type):
    """Context-aware character correction"""
    chars = list(text)
    
    # Mapping for Letters (when we expect a letter but got a digit)
    digit_to_char = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B', '4': 'A', '6': 'G'}
    
    # Mapping for Digits (when we expect a digit but got a letter)
    char_to_digit = {'O': '0', 'I': '1', 'Z': '2', 'S': '5', 'B': '8', 'A': '4', 'G': '6', 'Q': '0'}

    if pattern_type == "standard": # AP02AB1234
        # First 2 chars -> Letters (AP)
        for i in range(min(2, len(chars))):
            if chars[i].isdigit(): chars[i] = digit_to_char.get(chars[i], chars[i])
            
        # Next 2 chars -> Digits (02)
        for i in range(2, min(4, len(chars))):
            if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
            
        # Next 1 or 2 chars -> Letters (AB) or (A)
        if len(chars) == 10:
            for i in range(4, 6):
                if chars[i].isdigit(): chars[i] = digit_to_char.get(chars[i], chars[i])
            # Last 4 -> Digits
            for i in range(6, 10):
                if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
                
        elif len(chars) == 9: # AP02A1234
             if chars[4].isdigit(): chars[4] = digit_to_char.get(chars[4], chars[4])
             # Last 4 -> Digits
             for i in range(5, 9):
                if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])

    elif pattern_type == "old": # AP021234
         # First 2 -> Letters
         for i in range(min(2, len(chars))):
            if chars[i].isdigit(): chars[i] = digit_to_char.get(chars[i], chars[i])
         # Next 2 -> Digits
         for i in range(2, min(4, len(chars))):
            if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
         # Last 4 -> Digits
         for i in range(4, min(8, len(chars))):
             if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
             
    elif pattern_type == "bharat": # 22BH1234AB
        # First 2 -> Digits
        for i in range(min(2, len(chars))):
            if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
        # DB -> Letters (Bharat)
        for i in range(2, min(4, len(chars))):
             if chars[i].isdigit(): chars[i] = digit_to_char.get(chars[i], chars[i])
        # Next 4 -> Digits
        for i in range(4, min(8, len(chars))):
             if chars[i].isalpha(): chars[i] = char_to_digit.get(chars[i], chars[i])
        # Last 1 or 2 -> Letters
        for i in range(8, len(chars)):
             if chars[i].isdigit(): chars[i] = digit_to_char.get(chars[i], chars[i])

    return "".join(chars)

def process_logic(img, location_data=None, officer_email=None):
    results = model(img)
    plate_detections = {}
    
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            
            # EXPAND ROI Logic: Add 10% padding to capture edges
            h, w, _ = img.shape
            padding_x = int((x2 - x1) * 0.1)
            padding_y = int((y2 - y1) * 0.1)
            
            x1_crop = max(0, x1 - padding_x)
            y1_crop = max(0, y1 - padding_y)
            x2_crop = min(w, x2 + padding_x)
            y2_crop = min(h, y2 + padding_y)
            
            plate_img = img[y1_crop:y2_crop, x1_crop:x2_crop]
            if plate_img.size == 0: continue

            # Preprocess the plate image for better OCR
            processed_plate_img = preprocess_plate(plate_img)

            # Use predict() instead of ocr() to avoid TypeError
            ocr_result = ocr.predict(processed_plate_img)
            
            found_text = ""
            max_height = 0
            
            # Robust parsing of PaddleOCR result
            if ocr_result:
                for result_obj in ocr_result:
                    texts = []
                    boxes = []
                    scores = []
                    
                    if hasattr(result_obj, 'rec_texts'): 
                        texts = result_obj.rec_texts
                        scores = result_obj.rec_scores if hasattr(result_obj, 'rec_scores') else [1.0] * len(texts)
                    elif isinstance(result_obj, dict) and 'rec_texts' in result_obj:
                        texts = result_obj['rec_texts']
                        scores = result_obj.get('rec_scores', [1.0] * len(texts))
                    
                    if hasattr(result_obj, 'dt_polys'):
                        boxes = result_obj.dt_polys
                    elif hasattr(result_obj, 'dt_boxes'):
                         boxes = result_obj.dt_boxes
                    elif isinstance(result_obj, dict) and 'dt_polys' in result_obj:
                        boxes = result_obj['dt_polys']

                    if texts and boxes and len(texts) == len(boxes):
                        for poly in boxes:
                            ys = [p[1] for p in poly]
                            text_height = max(ys) - min(ys)
                            if text_height > max_height:
                                max_height = text_height
                        
                        valid_items = []
                        for i, text_str in enumerate(texts):
                            # Confidence Check
                            confidence = scores[i]
                            if confidence < OCR_THRESHOLD:
                                logger.info(f"Discarded low confidence text: {text_str} ({confidence:.2f})")
                                continue

                            poly = boxes[i]
                            ys = [p[1] for p in poly]
                            text_height = max(ys) - min(ys)
                            min_y = min(ys)
                            
                            if text_height >= max_height * 0.6:
                                valid_items.append((min_y, text_str))
                        
                        valid_items.sort(key=lambda x: x[0])
                        found_text = " ".join([item[1] for item in valid_items])
                    elif texts:
                        # Simple confidence filtering for fallback
                        filtered_texts = [t for i, t in enumerate(texts) if scores[i] >= OCR_THRESHOLD]
                        found_text = " ".join(filtered_texts)
            
            # Cleanup
            cleaned_text = clean_plate_text(found_text)
            if cleaned_text:
                logger.info(f"Raw OCR: {found_text} -> Cleaned: {cleaned_text}")
            
            if not cleaned_text:
                continue

            final_plate = cleaned_text
            is_valid_format = False
            
            # Check patterns
            if 8 <= len(cleaned_text) <= 12:           
                if re.match(r'^[A-Z]{2}[0-9A-Z]{2}[A-Z]{1,2}[0-9A-Z]{4}$', cleaned_text):
                     final_plate = correct_characters(cleaned_text, "standard")
                     is_valid_format = True
                elif re.match(r'^[A-Z]{2}[0-9A-Z]{2}[0-9A-Z]{4}$', cleaned_text):
                     final_plate = correct_characters(cleaned_text, "old")
                     is_valid_format = True
                elif re.match(r'^[0-9]{2}BH[0-9]{4}[A-Z]{1,2}$', cleaned_text):
                     final_plate = correct_characters(cleaned_text, "bharat")
                     is_valid_format = True
            
            # Format display string
            if is_valid_format:
                if len(final_plate) == 10:
                     formatted_plate = f"{final_plate[:2]} {final_plate[2:4]} {final_plate[4:6]} {final_plate[6:10]}"
                elif len(final_plate) == 9:
                     formatted_plate = f"{final_plate[:2]} {final_plate[2:4]} {final_plate[4:5]} {final_plate[5:9]}"
                else:
                     formatted_plate = final_plate
            else:
                formatted_plate = final_plate

            state_name = states.get(final_plate[:2], "Unknown State") if (is_valid_format and final_plate[:2].isalpha()) else "Unknown State"

            # Database search logic for flask_app.py (searching only)
            if is_valid_format:
                # Use the clean version for DB lookup as IDs ignore spaces usually
                db_id = formatted_plate.replace(" ", "")
                search_res = search_vehicle_record(db_id)
                if search_res['found']:
                    db_record = {
                        "status": "found",
                        "data": search_res['data'],
                        "is_stolen": search_res['is_stolen']
                    }
                else:
                    db_record = {
                        "status": "not_found",
                        "data": None,
                        "is_stolen": False
                    }
            else:
                db_record = {
                    "status": "unknown",
                    "data": "unknown",
                    "is_stolen": False
                }

            if formatted_plate not in plate_detections:
                plate_detections[formatted_plate] = {
                    'state': state_name,
                    'img_base64': mat_to_base64(plate_img),
                    'count': 1,
                    'db_status': db_record['status'],
                    'vehicle_details': db_record['data'],
                    'is_stolen': db_record['is_stolen']
                }
                
                # STOLEN VEHICLE ALERT LOGIC
                if db_record['is_stolen']:
                    current_time = time.time()
                    last_alert_time = recently_alerted.get(formatted_plate, 0)
                    
                    if current_time - last_alert_time > ALERT_COOLDOWN:
                        logger.info(f"🚨 ALERT: Stolen vehicle detected: {formatted_plate}. Sending email...")
                        
                        # Get owner email from database record
                        # owner_email = db_record['data'].get('email') if db_record['data'] else None
                        owner_email = "beliveryogi95@gmail.com"
                        
                        # Add location data to details if provided
                        if location_data and db_record['data']:
                            db_record['data']['latitude'] = location_data.get('latitude')
                            db_record['data']['longitude'] = location_data.get('longitude')
                        else:
                            logger.warning(f"⚠ WARNING: Stolen plate {formatted_plate} detected WITHOUT GPS coordinates! Location data is missing from the request.")

                        send_stolen_vehicle_alert(
                            formatted_plate, 
                            db_record['data'], 
                            plate_detections[formatted_plate]['img_base64'],
                            recipient_email=owner_email,
                            lat=location_data.get('latitude') if location_data else None,
                            lon=location_data.get('longitude') if location_data else None,
                            officer_email=officer_email
                        )
                        recently_alerted[formatted_plate] = current_time
                    else:
                        logger.info(f"Stolen vehicle {formatted_plate} detected again, but cooldown active.")
            else:
                plate_detections[formatted_plate]['count'] += 1

            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(img, formatted_plate, (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
    
    return img, plate_detections

# -------------------------------
# ROUTES
# -------------------------------
@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html')
    else:
        return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400
        
        result = authenticate_user(username, password)
        if result['success']:
            session['user_id'] = result['user_id']
            session['username'] = result['username']
            session['user_email'] = result.get('email')
            logger.info(f"User logged in: {username}")
            return jsonify({"success": True, "redirect": url_for('index')})
        else:
            logger.warning(f"Failed login attempt for user: {username}")
            return jsonify(result), 401
    
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        confirm_password = data.get('confirm_password', '').strip()
        
        if not username or not email or not password or not confirm_password:
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        if password != confirm_password:
            return jsonify({"success": False, "message": "Passwords do not match"}), 400
        
        if len(password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters"}), 400
        
        result = register_user(username, email, password)
        if result['success']:
            return jsonify({"success": True, "redirect": url_for('login')})
        else:
            return jsonify(result), 400
    
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/register-vehicle', methods=['GET', 'POST'])
@login_required
def register_vehicle():
    if request.method == 'POST':
        data = request.form
        vehicle_number = data.get('vehicle_number', '').strip().upper()
        
        if not vehicle_number:
             from flask import flash
             flash("Vehicle Number is required", "error")
             return render_template('register_vehicle.html')

        if collection.find_one({"_id": vehicle_number}):
            from flask import flash
            flash("Vehicle already registered", "warning")
            return render_template('register_vehicle.html')

        new_record = {
            "_id": vehicle_number,
            "details": {
                "vehicle_number": vehicle_number,
                "owner_name": data.get('owner_name'),
                "owner_location": data.get('owner_location'),
                "phone_number": data.get('phone_number'),
                "email": data.get('email'),
                "vehicle_type": data.get('vehicle_type'),
                "vehicle_category": data.get('vehicle_category'),
                "vehicle_name": data.get('vehicle_name')
            },
            "is_stolen": False
        }
        
        try:
            collection.insert_one(new_record)
            logger.info(f"New vehicle registered: {vehicle_number}")
            from flask import flash
            flash(f"Vehicle {vehicle_number} registered successfully", "success")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error registering vehicle {vehicle_number}: {e}")
            from flask import flash
            flash(f"Error registering: {e}", "error")
            return render_template('register_vehicle.html')

    return render_template('register_vehicle.html')

@app.route('/complaint', methods=['GET', 'POST'])
@login_required
def complaint():
    if request.method == 'POST':
        vehicle_number = request.form.get('vehicle_number', '').strip().upper()
        action = request.form.get('action') # 'mark_stolen' or 'mark_safe'
        description = request.form.get('description')
        
        if not vehicle_number:
            from flask import flash
            flash("Vehicle Number is required", "error")
            return render_template('complaint.html')
            
        record = collection.find_one({"_id": vehicle_number})
        if not record:
             from flask import flash
             flash("Vehicle not found in database. Remove space in vehicle number if present", "warning")
             return render_template('complaint.html')
        
        new_status = True if action == 'mark_stolen' else False
        
        try:
            collection.update_one(
                {"_id": vehicle_number},
                {"$set": {"is_stolen": new_status}}
            )
            logger.info(f"Vehicle {vehicle_number} status updated to {'Stolen' if new_status else 'Safe'}")
            from flask import flash
            flash(f"Vehicle status updated successfully", "success")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Error updating status for {vehicle_number}: {e}")
            from flask import flash
            flash(f"Error updating status: {e}", "error")
            return render_template('complaint.html')

    return render_template('complaint.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/api/get-username', methods=['GET'])
def get_username():
    username = session.get('username', 'User')
    return jsonify({"username": username})

@app.route('/check-plate', methods=['POST'])
def check_plate():
    """Check if a number plate exists in the database"""
    data = request.get_json()
    number_plate = data.get('number_plate', '').strip().upper()
    
    if not number_plate:
        return jsonify({"error": "Number plate is required"}), 400
    
    search_result = search_vehicle_record(number_plate)
    
    if search_result['found']:
        return jsonify({
            "status": "found",
            "message": f"Vehicle record found for {number_plate}",
            "data": search_result['data'],
            "is_stolen": search_result['is_stolen']
        })
    else:
        return jsonify({
            "status": "not_found",
            "message": f"No record found for {number_plate}"
        })

@app.route('/check-or-create-plate', methods=['POST'])
def check_or_create_plate():
    """Check if plate exists, if not create new record and insert in DB"""
    data = request.get_json()
    number_plate = data.get('number_plate', '').strip().upper()
    
    if not number_plate:
        return jsonify({"error": "Number plate is required"}), 400
    
    # Validate if plate is in correct 10 digit format
    number_plate_clean = re.sub(r"[^A-Z0-9]", "", number_plate)
    
    if len(number_plate_clean) != 10:
        return jsonify({
            "status": "invalid_format",
            "message": "Number plate must be in correct 10 digit format",
            "data": "unknown",
            "is_stolen": False
        })
    
    search_result = search_vehicle_record(number_plate)
    
    if search_result['found']:
        return jsonify({
            "status": "found",
            "message": f"Record found for {number_plate}",
            "data": search_result['data'],
            "is_stolen": search_result['is_stolen']
        })
    else:
        return jsonify({
            "status": "not_found",
            "message": f"Record not found for {number_plate}",
            "data": None,
            "is_stolen": False
        })

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    media_type = request.form.get('media_type')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    location_data = {"latitude": lat, "longitude": lon} if lat and lon else None
    officer_email = session.get('user_email')
    
    files = request.files.getlist('file')
    all_results = []

    for file in files:
        if file.filename == '': continue
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        try:
            if media_type == "video":
                cap = cv2.VideoCapture(file_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                final_detections = {}
                for second in range(0, int(total_frames / fps) + 1):
                    frame_number = int(second * fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                    ret, frame = cap.read()
                    if not ret: break
                    _, detections = process_logic(frame, location_data=location_data, officer_email=officer_email)
                    for p, info in detections.items():
                        if p not in final_detections:
                            final_detections[p] = info
                        else:
                            final_detections[p]['count'] += 1
                cap.release()
                all_results.append({"filename": file.filename, "type": "video", "plates": final_detections})
            else:
                img = cv2.imread(file_path)
                if img is None:
                    logger.error(f"Failed to read image: {file_path}")
                    continue
                processed_img, detections = process_logic(img, location_data=location_data, officer_email=officer_email)
                all_results.append({
                    "filename": file.filename,
                    "type": "image", 
                    "main_img": mat_to_base64(processed_img), 
                    "plates": detections
                })
        except Exception as e:
            logger.error(f"Error processing file {file.filename}: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return jsonify(all_results)

# -------------------------------
# API ROUTES (FOR MOBILE/REACT NATIVE)
# -------------------------------
@app.route('/api/data', methods=['GET'])
def api_data():
    return jsonify({"status": "success", "message": "API is online"})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400
    
    result = authenticate_user(username, password)
    return jsonify(result)

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not email or not password:
        return jsonify({"success": False, "message": "All fields are required"}), 400
    
    result = register_user(username, email, password)
    return jsonify(result)

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    files = request.files.getlist('file')
    media_type = request.form.get('media_type', 'image')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    officer_username = request.form.get('officer_username')
    officer_email_from_mobile = request.form.get('officer_email')
    
    logger.info(f"MOBILE API: Received upload. Provided officer_username: '{officer_username}', email: '{officer_email_from_mobile}'")
    
    officer_email = officer_email_from_mobile
    if not officer_email and officer_username:
        user = users_collection.find_one({"username": officer_username})
        if user:
            officer_email = user.get('email')
            logger.info(f"MOBILE API: Resolved officer_email from DB: '{officer_email}'")
        else:
            logger.warning(f"MOBILE API: Could not find user document for username '{officer_username}'")

    if not latitude or not longitude:
        logger.warning(f"MOBILE API: Upload received without GPS coordinates. Officer: {officer_username or 'Unknown'}")

    all_results = []

    for file in files:
        if file.filename == '': continue
        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(file_path)

        try:
            if media_type == "video":
                cap = cv2.VideoCapture(file_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                final_detections = {}
                for second in range(0, int(total_frames / fps) + 1):
                    frame_number = int(second * fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                    ret, frame = cap.read()
                    if not ret: break
                    _, detections = process_logic(
                        frame,
                        location_data={"latitude": latitude, "longitude": longitude} if latitude and longitude else None,
                        officer_email=officer_email
                    )
                    for p, info in detections.items():
                        if p not in final_detections:
                            final_detections[p] = info
                        else:
                            final_detections[p]['count'] += 1
                cap.release()
                all_results.append({"filename": file.filename, "type": "video", "plates": final_detections})
            else:
                img = cv2.imread(file_path)
                if img is None: continue
                processed_img, detections = process_logic(
                    img,
                    location_data={"latitude": latitude, "longitude": longitude} if latitude and longitude else None,
                    officer_email=officer_email
                )
                all_results.append({
                    "filename": file.filename,
                    "type": "image", 
                    "plates": detections
                })
        except Exception as e:
            logger.error(f"API Error processing file: {e}")
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

    return jsonify(all_results)

@app.route('/api/check-plate', methods=['POST'])
def api_check_plate():
    data = request.get_json()
    number_plate = data.get('number_plate', '').strip().upper()
    if not number_plate:
        return jsonify({"error": "Number plate is required"}), 400
    return jsonify(search_vehicle_record(number_plate))

@app.route('/api/register-vehicle', methods=['POST'])
def api_register_vehicle():
    """Mobile: Register a new vehicle. Accepts JSON."""
    data = request.get_json()
    vehicle_number = data.get('vehicle_number', '').strip().upper()
    if not vehicle_number:
        return jsonify({"success": False, "message": "Vehicle number is required"}), 400

    if collection.find_one({"_id": vehicle_number}):
        return jsonify({"success": False, "message": "Vehicle already registered"}), 409

    new_record = {
        "_id": vehicle_number,
        "details": {
            "vehicle_number": vehicle_number,
            "owner_name": data.get('owner_name'),
            "owner_location": data.get('owner_location'),
            "phone_number": data.get('phone_number'),
            "email": data.get('email'),
            "vehicle_type": data.get('vehicle_type'),
            "vehicle_category": data.get('vehicle_category'),
            "vehicle_name": data.get('vehicle_name'),
        },
        "is_stolen": False
    }
    try:
        collection.insert_one(new_record)
        logger.info(f"[API] New vehicle registered: {vehicle_number}")
        return jsonify({"success": True, "message": f"Vehicle {vehicle_number} registered successfully"})
    except Exception as e:
        logger.error(f"[API] Error registering vehicle: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/complaint', methods=['POST'])
def api_complaint():
    """Mobile: Mark a vehicle as stolen or safe. Accepts JSON."""
    data = request.get_json()
    vehicle_number = data.get('vehicle_number', '').strip().upper()
    action = data.get('action')  # 'mark_stolen' or 'mark_safe'

    if not vehicle_number:
        return jsonify({"success": False, "message": "Vehicle number is required"}), 400
    if action not in ('mark_stolen', 'mark_safe'):
        return jsonify({"success": False, "message": "action must be 'mark_stolen' or 'mark_safe'"}), 400

    record = collection.find_one({"_id": vehicle_number})
    if not record:
        return jsonify({"success": False, "message": "Vehicle not found in database"}), 404

    new_status = (action == 'mark_stolen')
    try:
        collection.update_one({"_id": vehicle_number}, {"$set": {"is_stolen": new_status}})
        label = "Stolen" if new_status else "Safe"
        logger.info(f"[API] Vehicle {vehicle_number} marked as {label}")
        return jsonify({"success": True, "message": f"Vehicle marked as {label}", "is_stolen": new_status})
    except Exception as e:
        logger.error(f"[API] Complaint error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    # Initialize ngrok if token and domain are provided
    ngrok_token = os.getenv("NGROK_AUTHTOKEN")
    ngrok_domain = os.getenv("NGROK_DOMAIN")

    if ngrok_token and ngrok_domain:
        try:
            conf.get_default().auth_token = ngrok_token
            # Open a HTTP tunnel on the default port 5000
            public_url = ngrok.connect(5000, domain=ngrok_domain)
            print(f" * Ngrok tunnel available at {public_url}")
        except Exception as e:
            print(f" * Failed to start Ngrok tunnel: {e}")
    elif ngrok_token:
        try:
            conf.get_default().auth_token = ngrok_token
            public_url = ngrok.connect(5000)
            print(f" * Ngrok tunnel available at {public_url}")
        except Exception as e:
            print(f" * Failed to start Ngrok tunnel: {e}")

    app.run(debug=True, host='0.0.0.0', port=5000)