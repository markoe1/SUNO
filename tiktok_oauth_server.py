"""
Simple OAuth callback server for TikTok sandbox testing with PKCE.
Listens on localhost:8000 and captures the auth code.
"""

from flask import Flask, request
import webbrowser
import os
import hashlib
import secrets
import base64
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/tiktok/callback"

# PKCE setup
def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_sha = hashlib.sha256(code_verifier.encode('utf-8')).digest()
    code_challenge = base64.urlsafe_b64encode(code_sha).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

code_verifier, code_challenge = generate_pkce_pair()

# Store captured code and verifier
captured_code = None
stored_code_verifier = code_verifier


@app.route('/auth/tiktok/callback', methods=['GET'])
def oauth_callback():
    """Capture the OAuth code from TikTok redirect."""
    global captured_code

    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return f'''
        <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>❌ Authorization Failed</h1>
                <p>Error: {error}</p>
                <p>{request.args.get('error_description', 'Unknown error')}</p>
            </body>
        </html>
        '''

    if code:
        captured_code = code
        return f'''
        <html>
            <head>
                <title>Authorization Successful</title>
                <style>
                    body {{ font-family: Arial; text-align: center; padding: 50px; background: #f0f0f0; }}
                    .container {{ background: white; padding: 30px; border-radius: 10px; max-width: 600px; margin: 0 auto; }}
                    h1 {{ color: #00d4ff; }}
                    .code {{ background: #f5f5f5; padding: 15px; border-radius: 5px; font-family: monospace; word-break: break-all; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>✅ Authorization Successful!</h1>
                    <p>Your code has been captured.</p>
                    <p>You can close this window and return to your terminal.</p>
                    <p style="color: #666; font-size: 12px;">Code: <span class="code">{code[:50]}...</span></p>
                </div>
            </body>
        </html>
        '''

    return "No code or error received"


@app.route('/code', methods=['GET'])
def get_code():
    """Endpoint to check if code has been captured."""
    if captured_code:
        return {'code': captured_code, 'code_verifier': stored_code_verifier}
    return {'code': None, 'code_verifier': None}


if __name__ == '__main__':
    print("=" * 80)
    print("TikTok OAuth Callback Server")
    print("=" * 80)
    print("\nStarting server on https://localhost:8000/")
    print("\nVisit this URL to authorize:")
    print()

    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/?"
        f"client_key={TIKTOK_CLIENT_KEY}"
        f"&scope=user.info.basic,video.upload"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    print(auth_url)
    print()
    print("Waiting for authorization...")
    print()

    # Optionally open browser automatically
    try:
        webbrowser.open(auth_url)
    except:
        pass

    # Run server on localhost
    app.run(host='0.0.0.0', port=8000, debug=False)
