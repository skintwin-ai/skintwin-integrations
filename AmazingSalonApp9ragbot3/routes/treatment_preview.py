
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required
from utils.ai_utils import generate_treatment_preview

bp = Blueprint('treatment_preview', __name__)

@bp.route('/treatment-preview')
@login_required
def preview_page():
    return render_template('treatment_preview.html')

@bp.route('/api/generate-preview', methods=['POST'])
@login_required
def generate_preview():
    if 'image' not in request.files:
        return jsonify({"error": "No image provided"}), 400
        
    image_file = request.files['image']
    treatment_type = request.form.get('treatment_type')
    
    preview_url = generate_treatment_preview(image_file, treatment_type)
    
    if preview_url:
        return jsonify({"preview_url": preview_url})
    else:
        return jsonify({"error": "Failed to generate preview"}), 500
