from flask import Flask, render_template, jsonify, request
import ephem
import math
from geopy.geocoders import OpenCage
from datetime import datetime
import os
from dotenv import load_dotenv
import requests
import json
import warnings

load_dotenv()

BASE_API_URL = "https://api.langflow.astra.datastax.com"
LANGFLOW_ID = "b90d566a-8de1-482e-a09f-81b7eb853eab"
APPLICATION_TOKEN = "AstraCS:thHykKNzwLnMCEvhZmCdDuJH:e1cdbaf6e71b8b5a6ddb8560657b6f39a6f0a99b4ff29d597ea9272f40f34711"
ENDPOINT = "myend"

DEFAULT_TWEAKS = {
    "ChatInput-6G5p5": {},
    "OpenAIModel-v7SJ3": {},
    "Prompt-KzAbP": {},
    "ChatOutput-OXqr3": {}
}

OPENCAGE_API_KEY = os.getenv('OPENCAGE_API_KEY')
geolocator = OpenCage(api_key=OPENCAGE_API_KEY)

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer",
    "Leo", "Virgo", "Libra", "Scorpio",
    "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]
SIDEREAL_OFFSET = 0

app = Flask(__name__)

def run_flow(message: str, output_type: str = "chat", input_type: str = "chat", tweaks: dict = None) -> dict:
    """
    Run a flow with a given message and optional tweaks.
    
    Args:
        message (str): The message to send to the flow
        output_type (str): The type of output expected
        input_type (str): The type of input being sent
        tweaks (dict): Optional tweaks to customize the flow
    
    Returns:
        dict: The JSON response from the flow
    """
    api_url = f"{BASE_API_URL}/lf/{LANGFLOW_ID}/api/v1/run/{ENDPOINT}"
    
    payload = {
        "input_value": message,
        "output_type": output_type,
        "input_type": input_type,
    }
    
    if tweaks:
        payload["tweaks"] = tweaks
    else:
        payload["tweaks"] = DEFAULT_TWEAKS
    
    headers = {
        "Authorization": f"Bearer {APPLICATION_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {str(e)}")
        return {"error": f"API Request failed: {str(e)}"}

def calculate_zodiac_sign(year, month, day, hour, minute, latitude, longitude):
    """Calculate the Sun's zodiac sign based on the position."""
    birth_datetime = f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}"
    observer = ephem.Observer()
    observer.date = birth_datetime
    observer.lat = str(latitude)
    observer.lon = str(longitude)

    sun = ephem.Sun(observer)
    sun_position = sun.ra * 180.0 / math.pi - SIDEREAL_OFFSET

    if sun_position < 0:
        sun_position += 360

    sign_index = int(sun_position // 30)
    return ZODIAC_SIGNS[sign_index]

def generate_kundali_svg(zodiac_sign):
    """Generate a Kundali chart as SVG."""
    size = 400
    center = size / 2
    radius = size * 0.4
    
    svg = [f'<svg viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">']
    svg.append(f'<circle cx="{center}" cy="{center}" r="{radius}" fill="none" stroke="#B4A05A" stroke-width="2"/>')
    
    for i in range(12):
        angle = i * 30
        rad_angle = math.radians(angle)
        x1 = center + radius * math.cos(rad_angle)
        y1 = center + radius * math.sin(rad_angle)
        
        svg.append(f'<line x1="{center}" y1="{center}" x2="{x1}" y2="{y1}" stroke="#B4A05A" stroke-width="1"/>')
        
        text_radius = radius * 1.1
        text_x = center + text_radius * math.cos(rad_angle)
        text_y = center + text_radius * math.sin(rad_angle)
        svg.append(f'<text x="{text_x}" y="{text_y}" fill="#B4A05A" text-anchor="middle" '
                  f'transform="rotate({angle}, {text_x}, {text_y})">{ZODIAC_SIGNS[i].split()[0]}</text>')

    current_sign_index = ZODIAC_SIGNS.index(zodiac_sign)
    highlight_angle = current_sign_index * 30
    highlight_rad = math.radians(highlight_angle)
    highlight_x = center + radius * 0.8 * math.cos(highlight_rad)
    highlight_y = center + radius * 0.8 * math.sin(highlight_rad)
    
    svg.append(f'<circle cx="{highlight_x}" cy="{highlight_y}" r="10" fill="#D63447"/>')
    svg.append('</svg>')
    return ''.join(svg)
    

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit():
    try:
        data = request.get_json()
        if not all(key in data for key in ['name', 'dob', 'time', 'city', 'state']):
            return jsonify({"error": "Missing required fields"}), 400

        dob = datetime.strptime(data['dob'], '%Y-%m-%d')
        birth_time = datetime.strptime(data['time'], '%H:%M').time()
        
        location = geolocator.geocode(f"{data['city']}, {data['state']}")
        if not location:
            return jsonify({"error": "Location not found"}), 404

        zodiac_sign = calculate_zodiac_sign(
            dob.year, dob.month, dob.day,
            birth_time.hour, birth_time.minute,
            location.latitude, location.longitude
        )
        
        langflow_input = (
            f"Name is {data['name']}, date of birth {dob.strftime('%B %d %Y')}, "
            f"place of birth {data['state']}, {data['city']}, time of birth {birth_time.strftime('%I:%M %p')}, "
            f"zodiac sign {zodiac_sign}. Current mood: {data.get('mood', '')}. "
            f"Reflection: {data.get('reflection', '')}"
        )
        
        ai_response = run_flow(
            message=langflow_input,
            output_type="text",
            input_type="text"
        )
        
        response = {
            "spiritual_insight": ai_response.get("message") or ai_response,
            "kundali": generate_kundali_svg(zodiac_sign),
            "zodiac_sign": zodiac_sign,
            "birth_details": {
                "name": data['name'],
                "date": dob.strftime('%B %d, %Y'),
                "time": birth_time.strftime('%I:%M %p'),
                "location": f"{data['city']}, {data['state']}",
                "coordinates": {
                    "latitude": location.latitude,
                    "longitude": location.longitude
                }
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        message = data.get('message', '')
        
        ai_response = run_flow(
            message=message,
            output_type="chat",
            input_type="chat"
        )
        
        try:
            if isinstance(ai_response, dict):
                if "error" in ai_response:
                    return jsonify({
                        "message": ai_response["error"],
                        "status": "error",
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
                    })
                
                
                message = (
                    ai_response.get("message") or
                    ai_response.get("response") or
                    (ai_response.get("outputs", [{}])[0].get("output", {}).get("content")) or
                    "No response content found"
                )
            else:
                message = str(ai_response)
            
            return jsonify({
                "message": message,
                "status": "success",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            })
            
        except Exception as e:
            return jsonify({
                "message": f"Error parsing response: {str(e)}",
                "status": "error",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            })
        
    except Exception as e:
        return jsonify({
            "message": f"Server error: {str(e)}",
            "status": "error",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
