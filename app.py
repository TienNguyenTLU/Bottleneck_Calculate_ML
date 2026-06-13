import os
import re
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

# Load CPU and GPU dictionaries for mapping
CPU_DICT_PATH = os.path.join('static', 'cpu_dict.json')
GPU_DICT_PATH = os.path.join('static', 'gpu_dict.json')

cpu_dict = {}
gpu_dict = {}

if os.path.exists(CPU_DICT_PATH):
    try:
        with open(CPU_DICT_PATH, 'r', encoding='utf-8') as f:
            cpu_dict = json.load(f)
    except Exception as e:
        print(f"Error loading CPU dictionary: {e}")

if os.path.exists(GPU_DICT_PATH):
    try:
        with open(GPU_DICT_PATH, 'r', encoding='utf-8') as f:
            gpu_dict = json.load(f)
    except Exception as e:
        print(f"Error loading GPU dictionary: {e}")

# Common hardware brands and noise words to ignore during similarity comparison
STRIP_KEYWORDS = {
    'asus', 'gigabyte', 'msi', 'zotac', 'evga', 'sapphire', 'powercolor', 'xfx', 
    'galax', 'colorful', 'palit', 'pny', 'asrock', 'rog', 'tuf', 'strix', 'aorus', 
    'gaming', 'windforce', 'dual', 'trio', 'oc', 'edition', 'vga', 'cpu', 'gpu', 
    'box', 'card', 'graphics', 'processor', 'threadripper', 'core', 'geforce', 'radeon',
    'chinh', 'hang', 'chính', 'hãng', 'ultra', 'super', 'ti', 'xt', 'xtx', 'pro',
    'intel', 'amd', 'nvidia', 'gddr6', 'gddr5', 'gb', 'mb', 'speed', 'hz'
}

def normalize_name(name):
    if not name:
        return ""
    name = name.lower()
    # Split conjoined 3-5 digit model numbers and letters (e.g. 5070ti -> 5070 ti)
    name = re.sub(r'(\d{3,5})([a-z]+)', r'\1 \2', name)
    name = re.sub(r'([a-z]+)(\d{3,5})', r'\1 \2', name)
    # Replace non-alphanumeric chars with spaces
    name = re.sub(r'[^a-z0-9\s]', ' ', name)
    return " ".join(name.split())

def extract_model_numbers(name):
    # Extract numbers that are likely part of the model name (e.g. 12400, 3600, 4060, 960)
    # Ignore standalone small numbers like 1, 2, 3, 4, 8, 12, 16
    numbers = re.findall(r'\b\d{3,5}\b', name)
    return set(numbers)

def find_best_match(user_name, dictionary):
    norm_user = normalize_name(user_name)
    if not norm_user:
        return None
        
    # Check for direct case-insensitive match first
    for name in dictionary.keys():
        if name.lower() == user_name.lower() or normalize_name(name) == norm_user:
            return name

    user_tokens = set(norm_user.split())
    user_models = extract_model_numbers(norm_user)
    user_meaningful = user_tokens - STRIP_KEYWORDS
    
    best_match = None
    best_score = -1
    
    for db_name in dictionary.keys():
        norm_db = normalize_name(db_name)
        db_tokens = set(norm_db.split())
        db_models = extract_model_numbers(norm_db)
        
        # 1. Enforce model number matching if present in user name
        if user_models and not (user_models & db_models):
            continue
            
        # 2. Score based on token overlap (both raw and meaningful)
        meaningful_overlap = len(user_meaningful & (db_tokens - STRIP_KEYWORDS))
        raw_overlap = len(user_tokens & db_tokens)
        
        # Check for specific modifiers like 'ti', 'super', 'xt', 'xtx'
        modifier_score = 0
        for mod in ['ti', 'super', 'xt', 'xtx']:
            if (mod in user_tokens) == (mod in db_tokens):
                modifier_score += 1
            elif mod in user_tokens or mod in db_tokens:
                modifier_score -= 1.5
                
        # Total score
        score = (meaningful_overlap * 3) + (raw_overlap * 1) + modifier_score
        
        if score > best_score:
            best_score = score
            best_match = db_name
            
    return best_match

def find_closest_cpu(user_name):
    return find_best_match(user_name, cpu_dict)

def find_closest_gpu(user_name):
    return find_best_match(user_name, gpu_dict)


app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Explanation mapping
EXPLANATIONS = {
    0: "Your system is well-balanced at this resolution. No significant hardware bottleneck detected; components operate harmoniously.",
    1: "CPU Bottleneck: At this resolution, the CPU single-core speed runs at maximum capacity while the GPU waits. Consider upgrading the processor.",
    2: "GPU Bottleneck: Render resolution is too taxing. The graphics card is bottlenecked while the CPU is underutilized. Consider upgrading the GPU.",
    3: "RAM Bottleneck: Low system memory capacity or slow BUS frequency is starving the processor and graphics card. Consider upgrading RAM."
}

def calculate_bottleneck_mathematically(cpu_single, cpu_multi, gpu_score, gpu_vram, ram_capacity, ram_bus_speed, res_width):
    # 1. RAM bottleneck check
    is_low_ram = (ram_capacity < 8) or \
                 (ram_capacity == 8 and (gpu_vram >= 12 or cpu_multi > 20000)) or \
                 (ram_capacity == 16 and gpu_vram >= 16 and res_width >= 3840)
                 
    is_slow_ram = (ram_bus_speed < 2133) or \
                  (cpu_multi > 35000 and ram_bus_speed < 3000)
                  
    if is_low_ram or is_slow_ram:
        confidence = 0.99
        if ram_capacity == 16 and gpu_vram >= 16 and res_width >= 3840:
            confidence = 0.85 # borderline RAM bottleneck
        return 3, confidence, 1.0 # fallback ratio
        
    # 2. Performance CPU/GPU bottleneck using ratio
    R = gpu_score / cpu_single
    
    # Thresholds based on resolution
    if res_width <= 1920: # 1080p
        low_threshold = 0.40
        high_threshold = 1.8
    elif res_width <= 2560: # 1440p
        low_threshold = 0.60
        high_threshold = 2.8
    else: # 4K (3840)
        low_threshold = 0.80
        high_threshold = 5.0
        
    if R < low_threshold:
        # GPU Bottleneck
        ratio_in_range = R / low_threshold
        confidence = 0.50 + 0.49 * (1.0 - ratio_in_range)
        return 2, min(0.99, max(0.50, confidence)), R
        
    elif R > high_threshold:
        # CPU Bottleneck
        ratio_in_range = high_threshold / R
        confidence = 0.50 + 0.49 * (1.0 - ratio_in_range)
        return 1, min(0.99, max(0.50, confidence)), R
        
    else:
        # Balanced
        mid = (low_threshold + high_threshold) / 2.0
        if R < mid:
            ratio_in_range = (R - low_threshold) / (mid - low_threshold)
        else:
            ratio_in_range = (high_threshold - R) / (high_threshold - mid)
            
        confidence = 0.50 + 0.49 * ratio_in_range
        return 0, min(0.99, max(0.50, confidence)), R

@app.route('/')
def home():
    if os.path.exists(os.path.join('templates', 'index.html')):
        return render_template('index.html')
    return jsonify({
        "status": "online",
        "message": "Flask Mathematical Bottleneck API is running. Post to /api/predict to run analysis."
    })

@app.route('/api/predict', methods=['POST'])
def predict():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "No JSON payload provided"}), 400

    # Map CPU Name to specs if provided
    if 'cpu_name' in data and data['cpu_name']:
        cpu_name_input = data['cpu_name']
        cpu_match = cpu_dict.get(cpu_name_input)
        if not cpu_match:
            closest = find_closest_cpu(cpu_name_input)
            if closest:
                cpu_match = cpu_dict[closest]
                data['cpu_name'] = closest
        
        if cpu_match:
            data['cpu_clock_speed'] = cpu_match['clock_speed']
            data['cpu_single_bench_score'] = cpu_match['single_bench_score']
            data['cpu_multi_bench_score'] = cpu_match['multi_bench_score']
        elif 'cpu_clock_speed' not in data or 'cpu_single_bench_score' not in data or 'cpu_multi_bench_score' not in data:
            return jsonify({"success": False, "error": f"CPU model '{cpu_name_input}' not found in database, and manual specifications not provided."}), 400

    # Map GPU Name to specs if provided
    if 'gpu_name' in data and data['gpu_name']:
        gpu_name_input = data['gpu_name']
        gpu_match = gpu_dict.get(gpu_name_input)
        if not gpu_match:
            closest = find_closest_gpu(gpu_name_input)
            if closest:
                gpu_match = gpu_dict[closest]
                data['gpu_name'] = closest
        
        if gpu_match:
            data['gpu_vram'] = gpu_match['vram']
            data['gpu_bench_score'] = gpu_match['gpu_bench_score']
        elif 'gpu_vram' not in data or 'gpu_bench_score' not in data:
            return jsonify({"success": False, "error": f"GPU model '{gpu_name_input}' not found in database, and manual specifications not provided."}), 400

    # Ensure required input fields are present
    required_fields = [
        'cpu_clock_speed',
        'cpu_single_bench_score',
        'cpu_multi_bench_score',
        'ram_capacity',
        'ram_bus_speed',
        'gpu_vram',
        'gpu_bench_score'
    ]
    for field in required_fields:
        if field not in data:
            return jsonify({"success": False, "error": f"Missing input parameter: {field}"}), 400

    # We predict for three resolutions
    resolutions = [
        {"name": "1080", "width": 1920, "height": 1080},
        {"name": "1440", "width": 2560, "height": 1440},
        {"name": "2160", "width": 3840, "height": 2160}
    ]

    predictions_report = []

    for res in resolutions:
        # Run mathematical analysis
        pred_class, pred_probability, R = calculate_bottleneck_mathematically(
            cpu_single=float(data['cpu_single_bench_score']),
            cpu_multi=float(data['cpu_multi_bench_score']),
            gpu_score=float(data['gpu_bench_score']),
            gpu_vram=int(data['gpu_vram']),
            ram_capacity=int(data['ram_capacity']),
            ram_bus_speed=int(data['ram_bus_speed']),
            res_width=res['width']
        )

        # Distribute remaining probability realistically for frontend visualization
        probabilities = [0.0, 0.0, 0.0, 0.0]
        probabilities[pred_class] = float(pred_probability)
        
        remaining = 1.0 - pred_probability
        if pred_class == 0:
            # Balanced: remaining goes to CPU or GPU bottleneck depending on R vs mid
            if res['width'] <= 1920:
                mid = (0.40 + 1.8) / 2.0
            elif res['width'] <= 2560:
                mid = (0.60 + 2.8) / 2.0
            else:
                mid = (0.80 + 5.0) / 2.0
                
            if R < mid:
                probabilities[2] = float(remaining) # GPU Bottleneck
            else:
                probabilities[1] = float(remaining) # CPU Bottleneck
        else:
            # CPU/GPU/RAM Bottleneck: remaining goes to Balanced
            probabilities[0] = float(remaining)

        predictions_report.append({
            "resolution": res["name"],
            "resolution_label": f"{res['width']}x{res['height']}",
            "predicted_type": pred_class,
            "probability": float(pred_probability),
            "probabilities": probabilities,
            "explanation": EXPLANATIONS.get(pred_class, "Unknown bottleneck class")
        })

    return jsonify({
        "success": True,
        "predictions": predictions_report
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
