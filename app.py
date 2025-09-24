from flask import (
    Flask, render_template, request, redirect,
    url_for, session, send_file, jsonify, flash
)
import qrcode
import io
import mysql.connector
import random as r
import smtplib
from email.message import EmailMessage
from deep_translator import GoogleTranslator

app = Flask(__name__)
app.secret_key = "supersecretkey"  # ⚠️ Use environment variable in production

# ---------------- MySQL config ----------------
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "MigrantCarePlus"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

# ---------------- Utility: send OTP ----------------
def send_otp_email(to_mail, purpose="Verification"):
    otp = ''.join(str(r.randint(0, 9)) for _ in range(6))
    session['otp'] = otp
    session['otp_email'] = to_mail

    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    from_mail = 'migrantcareplus@gmail.com'
    server.login(from_mail, 'afmi mliz abwv vuqi')  # ⚠️ Use env variable in production

    msg = EmailMessage()
    msg['Subject'] = f"{purpose} OTP"
    msg['From'] = from_mail
    msg['To'] = to_mail
    msg.set_content(
        f"Your MigrantCare+ {purpose} OTP is: {otp}\nDo not share it with anyone."
    )
    server.send_message(msg)
    server.quit()

# ---------------- QR code: generate URL to public profile ----------------
@app.route('/user-qr')
def user_qr():
    if "user" not in session:
        return redirect(url_for("login"))

    member_id = session["user"]
    profile_url = url_for('public_profile', member_id=member_id, _external=True)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4
    )
    qr.add_data(profile_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/png')

# ---------------- Public profile view (read-only) ----------------
@app.route('/profile/<member_id>')
def public_profile(member_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE member_id = %s", (member_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return "User not found", 404

    return render_template("public_profile.html", user=user)

# ---------------- Language Translation ----------------
@app.route('/translate', methods=['POST'])
def translate_text():
    data = request.get_json()
    text = data.get("text", "")
    target_lang = data.get("lang", "en")

    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return jsonify({"success": True, "translated": translated})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ---------------- Home & Profile ----------------
@app.route('/')
def home():
    return render_template('welcome-page.html')

@app.route('/profile')
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    member_id = session["user"]
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE member_id = %s", (member_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user:
        return redirect(url_for("login"))

    public_url = url_for('public_profile', member_id=member_id, _external=True)

    return render_template("profile.html", **user, public_url=public_url)

# ---------------- Edit profile ----------------
@app.route("/edit_profile", methods=["GET", "POST"])
def edit_profile():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    member_id = session["user"]

    errors = {}

    if request.method == "POST":
        fullName      = request.form["fullName"]
        age           = request.form["age"]
        dob           = request.form["dob"]
        gender        = request.form["gender"]
        phone         = request.form["phone"]
        email         = request.form["email"]
        nationality   = request.form["nationality"]
        blood         = request.form["blood"]
        fatherName    = request.form["fatherName"]
        motherName    = request.form["motherName"]
        fatherContact = request.form["fatherContact"]
        motherContact = request.form["motherContact"]
        marks         = request.form["marks"]
        issues        = request.form["issues"]
        workType      = request.form["workType"]
        workId        = request.form["workId"]
        insuranceNo   = request.form["insuranceNo"]
        insuranceValid= request.form["insuranceValid"]
        permAddr      = request.form["permAddr"]
        resAddr       = request.form["resAddr"]
        officeAddr    = request.form["officeAddr"]

        cursor.execute("""
            UPDATE users SET 
              fullName=%s, age=%s, dob=%s, gender=%s, phone=%s, email=%s, nationality=%s, blood=%s,
              fatherName=%s, motherName=%s, fatherContact=%s, motherContact=%s,
              marks=%s, issues=%s, workType=%s, workId=%s,
              insuranceNo=%s, insuranceValid=%s,
              permAddr=%s, resAddr=%s, officeAddr=%s
            WHERE member_id=%s
        """, (fullName, age, dob, gender, phone, email, nationality, blood,
              fatherName, motherName, fatherContact, motherContact,
              marks, issues, workType, workId,
              insuranceNo, insuranceValid,
              permAddr, resAddr, officeAddr,
              member_id))

        old_password     = request.form.get("old_password")
        new_password     = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if old_password or new_password or confirm_password:
            cursor.execute("SELECT password FROM users WHERE member_id = %s", (member_id,))
            user = cursor.fetchone()
            current_password = user["password"]

            if old_password != current_password:
                errors["old_password"] = "❌ Old password is incorrect"

            if new_password != confirm_password:
                errors["new_password"] = "❌ New passwords do not match"

            if not new_password.strip():
                errors["new_password"] = "❌ New password cannot be empty"

            if not errors:
                cursor.execute("UPDATE users SET password=%s WHERE member_id=%s",
                               (new_password, member_id))

        if errors:
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE member_id=%s", (member_id,))
            user = cursor.fetchone()
            cursor.close(); conn.close()
            return render_template("edit_profile.html", user=user, errors=errors)

        conn.commit()
        cursor.close(); conn.close()
        return redirect(url_for("profile"))

    cursor.execute("SELECT * FROM users WHERE member_id=%s", (member_id,))
    user = cursor.fetchone()
    cursor.close(); conn.close()
    return render_template("edit_profile.html", user=user, errors={})

# ---------------- Login ----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            login_id = data.get('member_id')
            password = data.get('password')
        else:
            login_id = request.form.get('member_id')
            password = request.form.get('password')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE member_id = %s", (login_id,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and user['password'] == password:
            session["user"] = user['member_id']
            if request.is_json:
                return jsonify({"success": True})
            return redirect(url_for('profile'))
        else:
            msg = "Invalid Member ID or Password"
            if request.is_json:
                return jsonify({"success": False, "message": msg})
            return render_template('login.html', error_msg=msg)

    return render_template('login.html')

# ---------------- Forgot Password ----------------
@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    email = ""
    member_id = request.args.get('member_id')
    if member_id:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT email FROM users WHERE member_id = %s", (member_id,))
        row = cursor.fetchone()
        if row:
            email = row['email']
        cursor.close()
        conn.close()

    if request.method == 'POST':
        email = request.form.get('email')
        if not email:
            return "Email required", 400
        send_otp_email(email, "Password Reset")
        return redirect(url_for('verify_reset_otp'))

    return render_template('forgot.html')

@app.route('/verify-reset-otp', methods=['GET', 'POST'])
def verify_reset_otp():
    if request.method == 'POST':
        input_otp = request.form.get('otp')
        if input_otp == session.get('otp'):
            session['otp_verified_email'] = session.get('otp_email')
            return redirect(url_for('set_new_password'))
        return "❌ Invalid OTP", 401
    return render_template('verify_reset_otp.html')

@app.route('/set-new-password', methods=['GET', 'POST'])
def set_new_password():
    if 'otp_verified_email' not in session:
        return redirect(url_for('forgot'))

    if request.method == 'POST':
        new_password = request.form.get('password')
        if not new_password:
            return "Password required", 400
        email = session['otp_verified_email']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET password=%s WHERE email=%s", (new_password, email))
        conn.commit()
        cur.close()
        conn.close()

        session.pop('otp_verified_email', None)
        session.pop('otp', None)
        session.pop('otp_email', None)

        return f"✅ Password updated successfully. <a href='{url_for('login')}'>Login now</a>"
    return render_template('set_new_password.html')

# ---------------- Registration OTP ----------------
@app.route('/send-registration-otp', methods=['POST'])
def send_registration_otp():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'msg': 'Email required'})

    otp = ''.join(str(r.randint(0,9)) for _ in range(6))
    session['registration_otp'] = otp
    session['registration_email'] = email

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        from_mail = 'migrantcareplus@gmail.com'
        server.login(from_mail, 'afmi mliz abwv vuqi')
        msg = EmailMessage()
        msg['Subject'] = "MigrantCare+ Registration OTP"
        msg['From'] = from_mail
        msg['To'] = email
        msg.set_content(f"Your OTP for MigrantCare+ registration is: {otp}")
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email send error:", e)
        return jsonify({'success': False, 'msg': 'Failed to send OTP'})

    return jsonify({'success': True})

# ---------------- Check Email ----------------
@app.route('/check_email', methods=['POST'])
def check_email():
    email = request.json.get('email', '').strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE LOWER(email) = %s LIMIT 1", (email,))
    exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()
    return jsonify({'exists': exists})

# ---------------- Create Account ----------------
@app.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        email = request.form.get("email").strip().lower()
        otp_input = request.form.get("email_otp")

        if otp_input != session.get("registration_otp") or email != session.get("registration_email"):
            return "❌ Invalid OTP. Please verify your email.", 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE LOWER(email) = %s LIMIT 1", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return "❌ Email already registered", 400
        cursor.close()
        conn.close()

        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        if not new_password:
            return "❌ Password required", 400
        if new_password != confirm_password:
            return "❌ Passwords do not match", 400

        user = {
            "fullName": request.form.get("fullname"),
            "age": request.form.get("age"),
            "dob": request.form.get("dob"),
            "gender": request.form.get("gender"),
            "phone": request.form.get("phone"),
            "email": email,
            "nationality": request.form.get("nationality"),
            "blood": request.form.get("blood_group"),
            "fatherName": request.form.get("father"),
            "motherName": request.form.get("mother"),
            "fatherContact": request.form.get("father_phone"),
            "motherContact": request.form.get("mother_phone"),
            "marks": request.form.get("identity_marks"),
            "issues": request.form.get("health_issues"),
            "workType": request.form.get("work_type"),
            "workId": request.form.get("work_permit"),
            "insuranceNo": request.form.get("insurance_no"),
            "insuranceValid": request.form.get("insurance_validity"),
            "permAddr": request.form.get("permanent_address"),
            "resAddr": request.form.get("residential_address"),
            "officeAddr": request.form.get("office_address"),
            "member_id": request.form.get("member_id"),
            "password": new_password,
            "role": "Migrant Worker"
        }

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users 
            (fullName, age, dob, gender, phone, email, nationality, blood, fatherName, motherName,
             fatherContact, motherContact, marks, issues, workType, workId, insuranceNo, insuranceValid,
             permAddr, resAddr, officeAddr, member_id, password, role)
            VALUES (%(fullName)s, %(age)s, %(dob)s, %(gender)s, %(phone)s, %(email)s, %(nationality)s, %(blood)s,
             %(fatherName)s, %(motherName)s, %(fatherContact)s, %(motherContact)s, %(marks)s, %(issues)s,
             %(workType)s, %(workId)s, %(insuranceNo)s, %(insuranceValid)s, %(permAddr)s, %(resAddr)s,
             %(officeAddr)s, %(member_id)s, %(password)s, %(role)s)
        """, user)
        conn.commit()
        cursor.close()
        conn.close()

        session.pop("registration_otp", None)
        session.pop("registration_email", None)

        session["user"] = user["member_id"]
        return redirect(url_for("profile"))

    return render_template('create-account.html')

# ---------------- Reports & Logout ----------------
@app.route('/reports')
def report():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template('report.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == '__main__':
    app.run(debug=True)
