from flask import Blueprint, request, jsonify, send_file
import io
from services.storage_service import upload_file, download_file, list_files

file_bp = Blueprint("file_bp", __name__)

# ✅ Upload API
@file_bp.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    user_id = request.form.get("user_id")
    session_id = request.form.get("session_id")

    if not file:
        return jsonify({"error": "No file provided"}), 400

    result = upload_file(file, user_id, session_id)
    return jsonify(result)


# ✅ Download API
@file_bp.route("/download", methods=["GET"])
def download():
    user_id = request.args.get("user_id")
    session_id = request.args.get("session_id")
    file_name = request.args.get("file_name")

    file_bytes = download_file(user_id, session_id, file_name)

    return send_file(
        io.BytesIO(file_bytes),
        download_name=file_name,
        as_attachment=True
    )


# ✅ Get File Names API
@file_bp.route("/files", methods=["GET"])
def get_files():
    user_id = request.args.get("user_id")
    session_id = request.args.get("session_id")

    files = list_files(user_id, session_id)

    return jsonify({
        "files": files
    })