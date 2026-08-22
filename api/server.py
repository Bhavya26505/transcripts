import os
import sys
import json
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string

# Force UTF-8 stdout for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from src.user_analysis_pipeline import UserAnalysisPipeline, ALLOWED_EXTENSIONS

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB max limit

# Global dictionary tracking active and completed pipelines in memory
ACTIVE_PIPELINES = {}

@app.route("/")
def index():
    html_path = PROJECT_ROOT / "frontend" / "index.html"
    if html_path.exists():
        return render_template_string(html_path.read_text(encoding="utf-8"))
    return "Transcript Adherence Analyzer Web UI (index.html missing)", 404

@app.route("/api/analyze", methods=["POST"])
def start_analysis():
    if 'file' not in request.files:
        return jsonify({"error": "No file part in request."}), 400

    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({"error": "No file selected for upload."}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({"error": f"Unsupported file type '{ext}'. Supported types: .srt, .vtt, .txt"}), 400

    # Save uploaded file temporarily to uploads directory
    uploads_dir = config.DATA_DIR / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temp_path = uploads_dir / file.filename
    file.save(temp_path)

    # Instantiate pipeline
    pipeline = UserAnalysisPipeline()
    ACTIVE_PIPELINES[pipeline.analysis_id] = pipeline
    file_size_kb = temp_path.stat().st_size / 1024
    print(f"\n[API] [POST /api/analyze] 📥 Received upload: '{file.filename}' ({file_size_kb:.1f} KB) -> Created Analysis ID: {pipeline.analysis_id}", flush=True)

    # Run pipeline asynchronously in background thread
    def run_worker():
        pipeline.run_pipeline(temp_path, filename=file.filename)

    thread = threading.Thread(target=run_worker)
    thread.daemon = True
    thread.start()

    return jsonify({
        "analysis_id": pipeline.analysis_id,
        "status": "PROCESSING",
        "current_stage": "INPUT_VALIDATION",
        "stages": pipeline.stages_status
    }), 200

@app.route("/api/analyze/<analysis_id>", methods=["GET"])
def get_status(analysis_id):
    # Check in-memory active pipeline
    pipeline = ACTIVE_PIPELINES.get(analysis_id)
    if pipeline:
        res_data = pipeline.result_data
        if pipeline.status == "COMPLETED" and not res_data:
            result_file = config.DATA_DIR / "user_analysis" / analysis_id / "final_result.json"
            if result_file.exists():
                with open(result_file, "r", encoding="utf-8") as f:
                    res_data = json.load(f)

        return jsonify({
            "analysis_id": analysis_id,
            "status": pipeline.status,
            "current_stage": pipeline.current_stage,
            "error": pipeline.error_message,
            "stages": pipeline.stages_status,
            "result": res_data if pipeline.status == "COMPLETED" else None
        })

    # Check on-disk persisted result or status
    user_dir = config.DATA_DIR / "user_analysis" / analysis_id
    result_file = user_dir / "final_result.json"
    status_file = user_dir / "status.json"

    if result_file.exists():
        with open(result_file, "r", encoding="utf-8") as f:
            res_data = json.load(f)
        return jsonify({
            "analysis_id": analysis_id,
            "status": "COMPLETED",
            "current_stage": "SCORING_FINALIZATION",
            "error": None,
            "result": res_data
        })

    if status_file.exists():
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status_data = json.load(f)
            return jsonify(status_data)
        except Exception:
            pass

    if user_dir.exists():
        return jsonify({
            "analysis_id": analysis_id,
            "status": "FAILED",
            "current_stage": "INTERRUPTED",
            "error": "The pipeline execution was interrupted due to a server reload. Please re-upload your file to analyze.",
            "stages": []
        }), 200

    return jsonify({"error": f"Analysis ID '{analysis_id}' not found."}), 404

@app.route("/api/analyze/<analysis_id>/result", methods=["GET"])
def get_result(analysis_id):
    result_file = config.DATA_DIR / "user_analysis" / analysis_id / "final_result.json"
    if not result_file.exists():
        return jsonify({"error": f"Result for analysis ID '{analysis_id}' not found or processing incomplete."}), 404

    with open(result_file, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    return jsonify(res_data)

@app.route("/api/analyze/<analysis_id>/download/json", methods=["GET"])
def download_json(analysis_id):
    result_file = config.DATA_DIR / "user_analysis" / analysis_id / "final_result.json"
    if not result_file.exists():
        return jsonify({"error": f"Result for analysis ID '{analysis_id}' not found."}), 404
    return send_file(result_file, as_attachment=True, download_name=f"{analysis_id}_result.json")

@app.route("/api/analyze/<analysis_id>/download/csv", methods=["GET"])
def download_csv(analysis_id):
    csv_file = config.DATA_DIR / "user_analysis" / analysis_id / "segment_timeline.csv"
    if not csv_file.exists():
        return jsonify({"error": f"CSV export for analysis ID '{analysis_id}' not found."}), 404
    return send_file(csv_file, as_attachment=True, download_name=f"{analysis_id}_timeline.csv")

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "true").lower() in ("true", "1", "yes")
    print("Starting Phase 11 Transcript Adherence Analyzer Server...")
    print("Server URL: http://127.0.0.1:5000")
    print(f"Debug Mode: {'ON' if debug_mode else 'OFF'}")
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)

