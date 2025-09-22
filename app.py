import os
import datetime
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    login_user,
    login_required,
    logout_user,
    UserMixin,
    current_user,
)
from flask_migrate import Migrate

# ---------------------------
# Flask Setup
# ---------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "campus_shield_secret")

# Database setup
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///campus_shield.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Password hashing
bcrypt = Bcrypt(app)

# Email Config - Updated with better defaults
GMAIL_USER = "janeebkonami@gmail.com"
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')  # Replace with your new app password

app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", GMAIL_USER)
app.config["MAIL_PASSWORD"] = os.environ.get("GMAIL_APP_PASSWORD", GMAIL_APP_PASSWORD)
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_USERNAME", GMAIL_USER)

# if not app.config["MAIL_USERNAME"] or not app.config["MAIL_PASSWORD"]:
#     raise ValueError("MAIL_USERNAME or MAIL_PASSWORD not set properly!")


# # Debug: Print mail config (remove in production)
# print(f"Mail Username: {app.config['MAIL_USERNAME']}")
# print(f"Mail Password: {'*' * len(app.config['MAIL_PASSWORD'])}")

mail = Mail(app)

# Admin email
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "janeebkonami@gmail.com")

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# Enable debugging logs
logging.basicConfig(level=logging.DEBUG)
app.config["PROPAGATE_EXCEPTIONS"] = True

@app.route("/test-email")
def test_email():
    print("DEBUG: MAIL_USERNAME =", app.config["MAIL_USERNAME"])
    print("DEBUG: MAIL_PASSWORD length =", len(app.config["MAIL_PASSWORD"]))
    print(app.config['MAIL_PASSWORD'])

    try:
        msg = Message(
            subject="Test Email",
            sender=app.config["MAIL_DEFAULT_SENDER"],
            recipients=[ADMIN_EMAIL],
            body="This is a test email from Campus Shield."
        )
        mail.send(msg)
        return "✅ Test email sent successfully!"
    except Exception as e:
        return f"❌ Email failed: {e}"



# ---------------------------
# Models
# ---------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    subject = db.Column(db.String(255), nullable=False)
    severity = db.Column(db.String(50), default="Medium")
    details = db.Column(db.Text, nullable=False)
    anonymous = db.Column(db.Boolean, default=False)
    proof_file = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(20), default="Pending")
    date = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Poll(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.String(255))
    option1 = db.Column(db.String(100))
    option2 = db.Column(db.String(100))
    option3 = db.Column(db.String(100))
    option4 = db.Column(db.String(100))


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey("poll.id"))
    option = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)


# ---------------------------
# User Loader
# ---------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def home():
    return render_template("welcome.html")


# ---------------------------
# Register
# ---------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = bcrypt.generate_password_hash(request.form["password"]).decode("utf-8")

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "danger")
            return redirect(url_for("register"))

        new_user = User(name=name, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------------------
# Login / Logout
# ---------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("awareness"))
        else:
            flash("Invalid email or password", "danger")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("login"))


# ---------------------------
# Complaint
# ---------------------------
@app.route("/complaint", methods=["GET", "POST"])
@login_required
def complaint():
    if request.method == "POST":
        subject = request.form.get("subject")
        severity = request.form.get("severity")
        details = request.form["details"]
        anonymous = bool(request.form.get("anonymous"))

        # Handle file upload
        proof_file = None
        if "proof_file" in request.files:
            file = request.files["proof_file"]
            if file.filename:
                upload_dir = os.path.join("static", "uploads")
                os.makedirs(upload_dir, exist_ok=True)
                proof_file = f"uploads/{file.filename}"
                file.save(os.path.join("static", proof_file))

        new_complaint = Complaint(
            student_id=None if anonymous else current_user.id,
            subject=subject,
            severity=severity,
            details=details,
            anonymous=anonymous,
            proof_file=proof_file,
        )
        db.session.add(new_complaint)
        db.session.commit()

        # Email to Admin with detailed error handling
        email_sent = False
        try:
            msg = Message(
                subject=f"🚨 New Complaint (Severity: {severity})",
                sender=app.config["MAIL_DEFAULT_SENDER"],
                recipients=[ADMIN_EMAIL]
            )
            
            proof_text = (
                f"Proof: http://127.0.0.1:5000/static/{proof_file}"
                if proof_file else "Proof: None"
            )
            
            msg.body = (
                f"Complaint ID: {new_complaint.id}\n"
                f"Student: {'Anonymous' if anonymous else current_user.name}\n"
                f"Subject: {subject}\n"
                f"Severity: {severity}\n"
                f"Details: {details}\n"
                f"{proof_text}\n"
                f"Date: {new_complaint.date}"
            )
            
            mail.send(msg)
            email_sent = True
            flash("✅ Complaint submitted and email sent to Admin!", "success")
            app.logger.info(f"Email sent successfully for complaint {new_complaint.id}")
            
        except Exception as e:
            app.logger.error(f"Email failed: {str(e)}")
            app.logger.error(f"Mail config - Server: {app.config['MAIL_SERVER']}, Port: {app.config['MAIL_PORT']}")
            app.logger.error(f"Mail config - Username: {app.config['MAIL_USERNAME']}")
            
            flash(f"⚠️ Complaint #{new_complaint.id} saved successfully, but email notification failed. Admin will still review it.", "warning")

        return redirect(url_for("track", complaint_id=new_complaint.id))

    return render_template("complaint.html")
# ---------------------------
# Track Complaint
# ---------------------------
@app.route("/track/<int:complaint_id>")
@login_required
def track(complaint_id):
    complaint = Complaint.query.get_or_404(complaint_id)
    return render_template("track.html", complaint=complaint)


@app.route("/track", methods=["GET", "POST"])
@login_required
def track_search():
    if request.method == "POST":
        cid = request.form["complaint_id"]
        return redirect(url_for("track", complaint_id=cid))
    return render_template("track_search.html")


# ---------------------------
# Awareness
# ---------------------------
@app.route("/awareness")
@login_required
def awareness():
    return render_template("awareness/index.html")


@app.route("/awareness/<page>")
@login_required
def awareness_page(page):
    return render_template(f"awareness/{page}.html")


# ---------------------------
# Polls
# ---------------------------
@app.route("/polls", methods=["GET", "POST"])
@login_required
def polls():
    polls = Poll.query.all()

    if not polls:
        sample = Poll(
            question="Should strict action be taken against ragging?",
            option1="Yes, strict punishment",
            option2="No, only counseling",
            option3="Maybe, depends on severity",
            option4="Not sure",
        )
        db.session.add(sample)
        db.session.commit()
        polls = Poll.query.all()

    if request.method == "POST":
        poll_id = request.form["poll_id"]
        option = request.form["option"]

        existing_vote = Vote.query.filter_by(
            poll_id=poll_id, user_id=current_user.id
        ).first()
        if existing_vote:
            flash("⚠️ You already voted!", "warning")
        else:
            vote = Vote(poll_id=poll_id, option=option, user_id=current_user.id)
            db.session.add(vote)
            db.session.commit()
            flash("✅ Vote recorded!", "success")

        return redirect(url_for("poll_results", poll_id=poll_id))

    return render_template("polls/index.html", polls=polls)


@app.route("/polls/<int:poll_id>/results")
@login_required
def poll_results(poll_id):
    poll = Poll.query.get_or_404(poll_id)
    votes = Vote.query.filter_by(poll_id=poll_id).all()

    results = {poll.option1: 0, poll.option2: 0, poll.option3: 0, poll.option4: 0}
    for v in votes:
        if v.option in results:
            results[v.option] += 1

    return render_template("polls/results.html", poll=poll, results=results)


# ---------------------------
# Run App
# ---------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
