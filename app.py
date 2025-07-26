from flask import Flask, render_template, request
import os
import re
import smtplib
import dns.resolver
import socket

app = Flask(__name__)

# ✅ Email Syntax Check
def is_valid_syntax(email):
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

# ✅ Get MX Records
def get_mx_records(domain):
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return sorted([(r.preference, str(r.exchange)) for r in answers])
    except Exception as e:
        return None

# ✅ SMTP-Level Check
def smtp_check(email, mx_records):
    from_address = 'check@yourdomain.com'  # Dummy sender
    for preference, mx in mx_records:
        try:
            server = smtplib.SMTP(timeout=10)
            server.connect(mx)
            server.helo(socket.gethostname())
            server.mail(from_address)
            code, message = server.rcpt(email)
            server.quit()
            if code == 250 or code == 251:
                return f"✅ SMTP Response: {code} {message.decode()}"
            else:
                return f"❌ SMTP Rejected: {code} - {message.decode()}"
        except Exception as e:
            continue
    return "❌ SMTP check failed or all MX failed."

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/check', methods=['POST'])
def check_email():
    email = request.form['email']
    results = []

    # Step 1: Syntax Check
    if not is_valid_syntax(email):
        results.append("❌ Invalid email syntax.")
        return render_template('index.html', result='\n'.join(results))

    results.append("✅ Email syntax is valid.")

    # Step 2: MX Check
    domain = email.split('@')[1]
    mx_records = get_mx_records(domain)
    if not mx_records:
        results.append("❌ No MX records found for domain.")
        return render_template('index.html', result='\n'.join(results))
    
    results.append("✅ MX records found:")
    for priority, mx in mx_records:
        results.append(f" - {mx} (Priority {priority})")

    # Step 3: SMTP Check
    smtp_result = smtp_check(email, mx_records)
    results.append(smtp_result)

    return render_template('index.html', result='\n'.join(results))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
