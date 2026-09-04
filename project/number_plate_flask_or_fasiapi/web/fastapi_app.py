import os
import cv2
import re
import base64
import random
import string
import logging
import time
from datetime import datetime
from typing import List, Optional
from email_utils import send_stolen_vehicle_alert

from fastapi import FastAPI, UploadFile, Form, File, Request, Depends, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from ultralytics import YOLO
from paddleocr import PaddleOCR
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import jinja2
from pyngrok import ngrok, conf

# Load environment variables
load_dotenv()

# Optimization: Bypass PaddleOCR connectivity check to speed up startup
os.environ['DISABLE_MODEL_SOURCE_CHECK'] = 'True'

app = FastAPI()

# Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'default-secret-key-for-local-dev')
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_fastapi.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Mount static files (if needed, but templates handles them too)
if os.path.exists('templates'):
    app.mount("/static", StaticFiles(directory="templates"), name="static")

# -------------------------------
# LOAD MODELS & DATABASE
# -------------------------------
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

def login_required(request: Request):
    """Dependency for FastAPI to ensure user is logged in"""
    if 'username' not in request.session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not logged in"
        )
    return request.session['username']

def register_user(username, email, password):
    """Register a new user in MongoDB"""
    if db.users.find_one({"username": username}):
        return False, "Username already exists"
    if db.users.find_one({"email": email}):
        return False, "Email already registered"
    
    hashed_password = generate_password_hash(password)
    db.users.insert_one({
        "username": username,
        "email": email,
        "password": hashed_password,
        "created_at": datetime.utcnow()
    })
    return True, "Registration successful"

def authenticate_user(username, password):
    """Authenticate user login"""
    user = db.users.find_one({"username": username})
    if user and check_password_hash(user['password'], password):
        return True, user
    return False, "Invalid username or password"

# -------------------------------
# DATABASE FUNCTIONS
# -------------------------------

def search_vehicle_record(number_plate):
    """Search for existing vehicle record by number plate"""
    try:
        # Normalize plate for searching
        normalized_plate = number_plate.replace(" ", "").upper()
        record = collection.find_one({"_id": normalized_plate})
        
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
        logger.error(f"Error searching database: {e}")
        return {
            "found": False,
            "data": None,
            "error": str(e)
        }

def get_or_create_vehicle_record(number_plate):
    """
    Deprecated: Now only searches for existing records.
    Redirects to search_vehicle_record logic.
    """
    res = search_vehicle_record(number_plate)
    if res['found']:
        return {"status": "found", "data": res['data']}
    else:
        return {"status": "not_found", "data": None}

# -------------------------------
# CORE LOGIC WITH DATABASE INTEGRATION
# -------------------------------
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
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
        
        # IMPORTANT: PaddleOCR expects 3-channel image (BGR), even if it looks grayscale.
        processed_img = cv2.cvtColor(denoised, cv2.COLOR_GRAY2BGR)
        
        return processed_img
    except Exception as e:
        logger.error(f"Preprocessing error: {e}")
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

            # Get vehicle record from database
            db_record = search_vehicle_record(formatted_plate.replace(" ", ""))

            if formatted_plate not in plate_detections:
                plate_detections[formatted_plate] = {
                    'state': state_name,
                    'img_base64': mat_to_base64(plate_img),
                    'count': 1,
                    'db_status': "found" if db_record['found'] else "not_found",
                    'vehicle_details': db_record['data'],
                    'is_stolen': db_record.get('is_stolen', False)
                }

                # STOLEN VEHICLE ALERT LOGIC
                if db_record.get('is_stolen', False):
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
# ROUTES (FastAPI Equivalents)
# -------------------------------
# -------------------------------
# FLASH MESSAGE HELPERS (Simulation for Jinja2)
# -------------------------------
def flash(request: Request, message: str, category: str = "info"):
    if "flash_messages" not in request.session:
        request.session["flash_messages"] = []
    request.session["flash_messages"].append((category, message))

@jinja2.pass_context
def get_flashed_messages(context: dict, with_categories: bool = False):
    request = context.get("request")
    if not request or "flash_messages" not in request.session:
        return []
    messages = request.session.pop("flash_messages", [])
    if with_categories:
        return messages
    return [m[1] for m in messages]

templates.env.globals.update(get_flashed_messages=get_flashed_messages)

# -------------------------------
# ROUTES (Full Parity with Flask)
# -------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    if 'username' not in request.session:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if 'username' in request.session:
        return RedirectResponse(url="/")
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_post(request: Request):
    try:
        data = await request.json()
        username = data.get('username')
        password = data.get('password')
    except:
        # Fallback for form data if needed
        form_data = await request.form()
        username = form_data.get('username')
        password = form_data.get('password')

    if not username or not password:
        return JSONResponse({"success": False, "message": "All fields are required"})

    success, result = authenticate_user(username, password)
    if success:
        request.session['username'] = username
        request.session['user_email'] = result.get('email')
        logger.info(f"User {username} logged in successfully")
        return JSONResponse({"success": True, "redirect": "/"})
    else:
        logger.warning(f"Failed login attempt for {username}")
        return JSONResponse({"success": False, "message": result})

@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register_post(request: Request):
    data = await request.json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirm_password')

    if not all([username, email, password, confirm_password]):
        return JSONResponse({"success": False, "message": "All fields are required"})

    if password != confirm_password:
        return JSONResponse({"success": False, "message": "Passwords do not match"})

    success, message = register_user(username, email, password)
    if success:
        logger.info(f"New user registered: {username}")
        return JSONResponse({"success": True, "redirect": "/login"})
    else:
        return JSONResponse({"success": False, "message": message})

@app.get("/register-vehicle", response_class=HTMLResponse)
async def register_vehicle_get(request: Request, username: str = Depends(login_required)):
    return templates.TemplateResponse("register_vehicle.html", {"request": request})

@app.post("/register-vehicle")
async def register_vehicle_post(
    request: Request,
    vehicle_number: str = Form(...),
    owner_name: str = Form(...),
    phone_number: str = Form(...),
    email: str = Form(...),
    owner_location: str = Form(...),
    vehicle_category: str = Form(...),
    vehicle_type: str = Form(...),
    vehicle_name: str = Form(...)
):
    if 'username' not in request.session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        normalized_plate = vehicle_number.replace(" ", "").upper()
        if db.ap_vehicle_records.find_one({"_id": normalized_plate}):
            flash(request, "Vehicle number already registered!", "error")
            return templates.TemplateResponse("register_vehicle.html", {"request": request})

        new_record = {
            "_id": normalized_plate,
            "details": {
                "vehicle_number": vehicle_number.upper(),
                "owner_name": owner_name,
                "phone_number": phone_number,
                "email": email,
                "owner_location": owner_location,
                "vehicle_category": vehicle_category,
                "vehicle_type": vehicle_type,
                "vehicle_name": vehicle_name
            },
            "is_stolen": False,
            "created_at": datetime.utcnow()
        }
        db.ap_vehicle_records.insert_one(new_record)
        flash(request, "Vehicle registered successfully!", "success")
        logger.info(f"Vehicle {vehicle_number} registered by {request.session['username']}")
    except Exception as e:
        logger.error(f"Error registering vehicle: {e}")
        flash(request, "Error during registration. Please try again.", "error")

    return templates.TemplateResponse("register_vehicle.html", {"request": request})

@app.get("/complaint", response_class=HTMLResponse)
async def complaint_get(request: Request, username: str = Depends(login_required)):
    return templates.TemplateResponse("complaint.html", {"request": request})

@app.post("/complaint")
async def complaint_post(
    request: Request,
    vehicle_number: str = Form(...),
    action: str = Form(...),
    description: str = Form(None)
):
    if 'username' not in request.session:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        normalized_plate = vehicle_number.replace(" ", "").upper()
        record = db.ap_vehicle_records.find_one({"_id": normalized_plate})

        if not record:
            flash(request, f"No record found for {vehicle_number}. Please register it first.", "error")
        else:
            is_stolen = (action == "mark_stolen")
            db.ap_vehicle_records.update_one(
                {"_id": normalized_plate},
                {"$set": {"is_stolen": is_stolen, "last_complaint": description, "updated_at": datetime.utcnow()}}
            )
            status_text = "STOLEN" if is_stolen else "SAFE"
            flash(request, f"Vehicle {vehicle_number} successfully marked as {status_text}.", "success")
            logger.info(f"Vehicle {vehicle_number} status updated to {status_text} by {request.session['username']}")
    except Exception as e:
        logger.error(f"Error updating complaint: {e}")
        flash(request, "Error updating status. Please try again.", "error")

    return templates.TemplateResponse("complaint.html", {"request": request})

@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login")

@app.get("/api/get-username")
async def get_username(request: Request):
    return {"username": request.session.get('username')}

@app.post('/check-plate')
async def check_plate_route(request: Request, data: dict):
    """Check if a number plate exists in the database"""
    number_plate = data.get('number_plate', '').strip().upper()
    
    if not number_plate:
        return JSONResponse({"error": "Number plate is required"}, status_code=400)
    
    search_result = search_vehicle_record(number_plate)
    
    if search_result['found']:
        return JSONResponse({
            "status": "found",
            "message": f"Vehicle record found for {number_plate}",
            "data": search_result['data'],
            "is_stolen": search_result['is_stolen']
        })
    else:
        return JSONResponse({
            "status": "not_found",
            "message": f"No record found for {number_plate}"
        })

@app.post('/upload')
async def upload(
    request: Request,
    media_type: str = Form(...),
    latitude: Optional[str] = Form(None),
    longitude: Optional[str] = Form(None),
    file: List[UploadFile] = File(...)
):
    if 'username' not in request.session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    location_data = {"latitude": latitude, "longitude": longitude} if latitude and longitude else None
    officer_email = request.session.get('user_email')
    all_results = []

    for uploaded_file in file:
        if not uploaded_file.filename:
            continue
        
        file_path = os.path.join(UPLOAD_FOLDER, uploaded_file.filename)
        
        try:
            # Save uploaded file
            contents = await uploaded_file.read()
            with open(file_path, 'wb') as f:
                f.write(contents)

            if media_type == "video":
                cap = cv2.VideoCapture(file_path)
                fps = cap.get(cv2.CAP_PROP_FPS)
                if fps <= 0: fps = 30  # Fallback
                
                # Sample 1 frame every second
                frame_interval = int(fps)
                
                final_detections = {}
                frame_idx = 0
                while True:
                    ret, frame = cap.read()
                    if not ret: 
                        break
                    
                    if frame_idx % frame_interval == 0:
                        _, detections = process_logic(frame, location_data=location_data, officer_email=officer_email)
                        for p, info in detections.items():
                            if p not in final_detections:
                                final_detections[p] = info
                            else:
                                final_detections[p]['count'] += 1
                    
                    frame_idx += 1
                    
                cap.release()
                all_results.append({
                    "filename": uploaded_file.filename, 
                    "type": "video", 
                    "plates": final_detections
                })
            else:
                img = cv2.imread(file_path)
                if img is None:
                    logger.error(f"Failed to read image: {file_path}")
                    continue
                processed_img, detections = process_logic(img, location_data=location_data, officer_email=officer_email)
                all_results.append({
                    "filename": uploaded_file.filename,
                    "type": "image", 
                    "main_img": mat_to_base64(processed_img), 
                    "plates": detections
                })
        except Exception as e:
            logger.error(f"Error processing file {uploaded_file.filename}: {e}")
        finally:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.error(f"Error deleting temp file {file_path}: {e}")

    return JSONResponse(content=all_results)

if __name__ == '__main__':
    import uvicorn
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

    uvicorn.run(app, host="0.0.0.0", port=5000)
