import os
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

from utils.pdf_extract import extract_text_from_pdf, PDFExtractionError
from utils.similarity import compute_similarity, ModelUnavailableError
from utils.llm_client import evaluate_resume, generate_improvements, LLMClientError, LLMResponseError
from utils import db

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-insecure-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB upload capacity

MIN_JD_CHARS = 40


@app.before_request
def _ensure_db_ready():
    db.init_db()


# Pages


@app.route("/")
def index():
    history = db.list_sessions(limit=10)
    return render_template("index.html", history=history)


# API


@app.route("/api/analyze", methods=["POST"])
def analyze():
    resume_file = request.files.get("resume")
    jd_text = (request.form.get("jd_text") or "").strip()

    #  Input validation 

    if resume_file is None or resume_file.filename == "":
        return jsonify(error="Please upload your resume as a PDF."), 400

    if not resume_file.filename.lower().endswith(".pdf"):
        return jsonify(error="Only PDF resumes are supported right now."), 400

    if len(jd_text) < MIN_JD_CHARS:
        return jsonify(error="Paste the full job description (it looks too short)."), 400

    #  Step 1: PDF -> text

    try:
        resume_text = extract_text_from_pdf(resume_file.stream)
    except PDFExtractionError as exc:
        return jsonify(error=str(exc)), 400

    #  Step 2: similarity score 

    try:
        similarity_score = compute_similarity(resume_text, jd_text)
    except ModelUnavailableError as exc:
        return jsonify(error=str(exc)), 503

    #  Step 3: LLM call 1 - evaluate

    try:
        evaluation = evaluate_resume(resume_text, jd_text)
    except LLMClientError as exc:
        return jsonify(error=str(exc)), 502
    except LLMResponseError as exc:
        return jsonify(error=f"The evaluation step returned something we couldn't parse: {exc}"), 502

    #  Step 4: LLM call 2 - generate (chained on step 3)

    try:
        generation = generate_improvements(evaluation, resume_text, jd_text)
    except LLMClientError as exc:
        return jsonify(error=str(exc)), 502
    except LLMResponseError as exc:
        return jsonify(error=f"The rewrite step returned something we couldn't parse: {exc}"), 502

    #  Step 5: persist

    session_id = db.save_session(resume_text, jd_text, similarity_score, evaluation, generation)

    return jsonify(
        session_id=session_id,
        similarity_score=similarity_score,
        evaluation=evaluation,
        generation=generation,
    )


@app.route("/api/history", methods=["GET"])
def history():
    # list of past sessions for the sidebar.
    return jsonify(sessions=db.list_sessions(limit=20))


@app.route("/api/session/<int:session_id>", methods=["GET"])
def session_detail(session_id):
    record = db.get_session(session_id)
    if record is None:
        return jsonify(error="Session not found."), 404
    return jsonify(record)


@app.errorhandler(413)
def too_large(_exc):
    return jsonify(error="That file is too large - please keep resumes under 8MB."), 413


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)