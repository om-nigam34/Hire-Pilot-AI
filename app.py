import os
from datetime import timedelta
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from dotenv import load_dotenv

from utils.pdf_extract import extract_text_from_pdf, PDFExtractionError
from utils.similarity import compute_similarity, ModelUnavailableError
from utils.llm_client import evaluate_resume, generate_improvements, LLMClientError, LLMResponseError
from utils import db, auth

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-only-insecure-key")
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8MB upload capacity
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.permanent_session_lifetime = timedelta(days=7)

if not os.environ.get("FLASK_SECRET_KEY"):
    # This key signs the login session cookie
    print("WARNING: FLASK_SECRET_KEY not set - using an insecure default. Set it before deploying.")

MIN_JD_CHARS = 40


@app.before_request
def _ensure_db_ready():
    db.init_db()


#  Public pages 

@app.route("/")
def landing():
    if auth.get_current_user():
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if auth.get_current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        error = auth.validate_signup(username, email, password, confirm_password)
        if error:
            flash(error, "error")
            return render_template("signup.html", username=username, email=email), 400

        try:
            user_id = db.create_user(username, email, auth.hash_password(password))
        except (db.UsernameTakenError, db.EmailTakenError) as exc:
            flash(str(exc), "error")
            return render_template("signup.html", username=username, email=email), 400

        session.permanent = True
        session["user_id"] = user_id
        return redirect(url_for("dashboard"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if auth.get_current_user():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        identifier = (request.form.get("identifier") or "").strip()
        password = request.form.get("password") or ""

        user = db.get_user_by_username(identifier) or db.get_user_by_email(identifier.lower())

        if user is None or not auth.verify_password(password, user["password_hash"]):
            flash("Incorrect username/email or password.", "error")
            return render_template("login.html", identifier=identifier), 401

        session.permanent = True
        session["user_id"] = user["id"]
        return redirect(request.args.get("next") or url_for("dashboard"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


#  Protected page 

@app.route("/dashboard")
@auth.login_required
def dashboard():
    user = auth.get_current_user()
    history = db.list_sessions(user["id"], limit=10)
    return render_template("dashboard.html", history=history, user=user)


#  API --> every route below is scoped to the logged-in user 

@app.route("/api/analyze", methods=["POST"])
@auth.api_login_required
def analyze():
    user = auth.get_current_user()
    resume_file = request.files.get("resume")
    jd_text = (request.form.get("jd_text") or "").strip()

    #  Input validation 

    if resume_file is None or resume_file.filename == "":
        return jsonify(error="Please upload your resume as a PDF."), 400

    if not resume_file.filename.lower().endswith(".pdf"):
        return jsonify(error="Only PDF resumes are supported."), 400

    if len(jd_text) < MIN_JD_CHARS:
        return jsonify(error="Paste the full job description - It looks too short."), 400

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

    #  Step 5: persist, scoped to this user

    session_id = db.save_session(user["id"], resume_text, jd_text, similarity_score, evaluation, generation)

    return jsonify(
        session_id=session_id,
        similarity_score=similarity_score,
        evaluation=evaluation,
        generation=generation,
    )


@app.route("/api/history", methods=["GET"])
@auth.api_login_required
def history():
    user = auth.get_current_user()
    return jsonify(sessions=db.list_sessions(user["id"], limit=20))


@app.route("/api/session/<int:session_id>", methods=["GET"])
@auth.api_login_required
def session_detail(session_id):
    user = auth.get_current_user()
    record = db.get_session(session_id, user["id"])
    if record is None:
        return jsonify(error="Session not found."), 404
    return jsonify(record)


@app.errorhandler(413)
def too_large(_exc):
    return jsonify(error="That file is too large - please keep resumes under 8MB."), 413


if __name__ == "__main__":
    db.init_db()
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)