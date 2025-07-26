from flask import Flask, render_template, request
import re
import dns.resolver
import smtplib
import socket

app = Flask(__name__)

# Helper Functions
def is_valid_syntax(email):
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def get_domain(email):
    return email.split('@')[-1]

def get_mx_records(domain):
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        return [str(r.exchange).rstrip('.') for r in answers]
    except:
        return []

def smtp_check(email, mx_records):
    from_address = 'verify@example.com'
    for mx in mx_records:
        try:
            server = smtplib.SMTP(timeout=10)
            server.connect(mx)
            server.helo()
            server.mail(from_address)
            code, message = server.rcpt(email)
            server.quit()
            if code in [250, 251]:
                return True
        except:
            continue
    return False

def is_disposable(domain):
    disposable_domains = ["mailinator.com", "10minutemail.com", "tempmail.com"]
    return domain in disposable_domains

# Routes
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/verify', methods=['POST'])
def verify():
    try:
        email = request.form['email']
        syntax = is_valid_syntax(email)

        if not syntax:
            return render_template('index.html', result={
                'email': email,
                'syntax': '❌',
                'domain': 'Invalid syntax',
                'mx': '❌',
                'smtp': '❌',
                'disposable': 'Unknown',
                'status': 'Invalid ❌',
                'suggestion': 'Invalid email format.'
            })

        domain = get_domain(email)
        mx_records = get_mx_records(domain)
        smtp = smtp_check(email, mx_records) if mx_records else False
        disposable = is_disposable(domain)

        result = {
            'email': email,
            'syntax': '✔️',
            'domain': domain,
            'mx': '✔️' if mx_records else '❌',
            'smtp': '✔️' if smtp else '❌',
            'disposable': 'Yes' if disposable else 'No',
            'status': 'Valid ✅' if smtp else 'Invalid ❌',
            'suggestion': 'Looks good!' if smtp else 'Try another email or check domain spelling.'
        }
        return render_template('index.html', result=result)

    except Exception as e:
        print(f"Error in verify(): {e}")
        return render_template('index.html', result={
            'email': 'Error',
            'syntax': '❌',
            'domain': 'Error',
            'mx': '❌',
            'smtp': '❌',
            'disposable': 'Unknown',
            'status': 'Error ❌',
            'suggestion': 'Internal Server Error. Try again later.'
        })

if __name__ == '__main__':
    import os
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
