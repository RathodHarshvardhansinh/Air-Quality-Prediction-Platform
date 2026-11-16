CITIES = {
    "ahmedabad": {
        "name": "Ahmedabad",
        "country": "IN",
        "latitude": 23.0225,
        "longitude": 72.5714
    },
    "mehsana": {
        "name": "Mehsana",
        "country": "IN",
        "latitude": 23.5880,
        "longitude": 72.3693
    },
    "surat": {
        "name": "Surat",
        "country": "IN",
        "latitude": 21.1702,
        "longitude": 72.8311
    },
    "vadodara": {
        "name": "Vadodara",
        "country": "IN",
        "latitude": 22.3072,
        "longitude": 73.1812
    },
    "gandhinagar": {
        "name": "Gandhinagar",
        "country": "IN",
        "latitude": 23.2156,
        "longitude": 72.6369
    }
}


# =====================================
# Cities used to collect HISTORY and train the model
# (python backend/fetch_city_history.py --all).
# Visnagar already has its own history, so it is skipped unless you pass --refresh.
# Add or remove cities freely: (name, latitude, longitude)
# =====================================
HISTORY_CITIES = [
    # Gujarat
    ("Ahmedabad", 23.0225, 72.5714), ("Gandhinagar", 23.2156, 72.6369), ("Surat", 21.1702, 72.8311),
    ("Vadodara", 22.3072, 73.1812), ("Rajkot", 22.3039, 70.8022), ("Bhavnagar", 21.7645, 72.1519),
    ("Jamnagar", 22.4707, 70.0577), ("Junagadh", 21.5222, 70.4579), ("Anand", 22.5645, 72.9289),
    ("Mehsana", 23.5880, 72.3693), ("Vapi", 20.3893, 72.9106),
    # North
    ("Delhi", 28.6139, 77.2090), ("Chandigarh", 30.7333, 76.7794), ("Amritsar", 31.6340, 74.8723),
    ("Ludhiana", 30.9010, 75.8573), ("Dehradun", 30.3165, 78.0322), ("Jaipur", 26.9124, 75.7873),
    ("Jodhpur", 26.2389, 73.0243), ("Udaipur", 24.5854, 73.7125), ("Lucknow", 26.8467, 80.9462),
    ("Kanpur", 26.4499, 80.3319), ("Varanasi", 25.3176, 82.9739), ("Agra", 27.1767, 78.0081),
    # Central / East
    ("Bhopal", 23.2599, 77.4126), ("Indore", 22.7196, 75.8577), ("Nagpur", 21.1458, 79.0882),
    ("Raipur", 21.2514, 81.6296), ("Patna", 25.5941, 85.1376), ("Ranchi", 23.3441, 85.3096),
    ("Kolkata", 22.5726, 88.3639), ("Bhubaneswar", 20.2961, 85.8245), ("Guwahati", 26.1445, 91.7362),
    # West / South
    ("Mumbai", 19.0760, 72.8777), ("Pune", 18.5204, 73.8567), ("Nashik", 19.9975, 73.7898),
    ("Hyderabad", 17.3850, 78.4867), ("Visakhapatnam", 17.6868, 83.2185), ("Bengaluru", 12.9716, 77.5946),
    ("Chennai", 13.0827, 80.2707), ("Coimbatore", 11.0168, 76.9558), ("Kochi", 9.9312, 76.2673),
    ("Thiruvananthapuram", 8.5241, 76.9366),
]
