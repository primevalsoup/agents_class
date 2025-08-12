from flask import Flask, request, redirect, render_template_string
import requests
import base64
import os
from dotenv import load_dotenv
import urllib.parse
import secrets
import string

load_dotenv(override=True)

app = Flask(__name__)
app.secret_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

REDIRECT_URI = f"https://{os.getenv('SPACE_HOST')}/callback"
SCOPE = "user-top-read"
tokens = {}

# HTML template for the home page
HOME_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spotify OAuth Helper</title>
</head>
<body>
    {% if has_credentials %}
        <div style="margin-bottom: 20px;">
            <p>Make sure to add this redirect URI to your Spotify app settings:</p>
            <code>{{ redirect_uri }}</code>
        </div>
        <button onclick="window.open('https://accounts.spotify.com/authorize?client_id={{ client_id }}&response_type=code&redirect_uri={{ redirect_uri | urlencode }}&scope={{ scope | urlencode }}&show_dialog=true', '_blank')">Authorize with Spotify</button>
    {% else %}
        <div>Missing Spotify credentials in .env file</div>
    {% endif %}
</body>
</html>
"""

# HTML template for the success page
SUCCESS_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Spotify OAuth - Success!</title>
</head>
<body>
    <p>Authorization Complete</p>
    <h3>Add to your .env file:</h3>
    <pre>SPOTIFY_ACCESS_TOKEN={{ access_token }}
SPOTIFY_REFRESH_TOKEN={{ refresh_token }}</pre>
</body>
</html>
"""

@app.route('/')
def home():
    """Display the home page"""
    error = request.args.get('error')
    has_credentials = CLIENT_ID and CLIENT_SECRET
    return render_template_string(HOME_TEMPLATE, error=error, has_credentials=has_credentials, redirect_uri=REDIRECT_URI, client_id=CLIENT_ID, scope=SCOPE)

@app.route('/authorize')
def authorize():
    """Redirect to Spotify authorization"""
    if not CLIENT_ID:
        return redirect('/?error=Missing SPOTIFY_CLIENT_ID')
    
    auth_url = "https://accounts.spotify.com/authorize"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "show_dialog": "true"
    }
    
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

@app.route('/callback')
def callback():
    """Handle the OAuth callback"""
    error = request.args.get('error')
    if error:
        return redirect(f'/?error=Authorization failed: {error}')
    
    code = request.args.get('code')
    if not code:
        return redirect('/?error=No authorization code received')
    
    # Exchange code for tokens
    token_url = "https://accounts.spotify.com/api/token"
    
    # Prepare auth header
    credentials = f"{CLIENT_ID}:{CLIENT_SECRET}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    
    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        tokens['access_token'] = token_data['access_token']
        tokens['refresh_token'] = token_data['refresh_token']
        
        return render_template_string(
            SUCCESS_TEMPLATE,
            access_token=token_data['access_token'],
            refresh_token=token_data['refresh_token']
        )
    else:
        error_msg = response.json().get('error_description', 'Unknown error')
        return redirect(f'/?error=Token exchange failed: {error_msg}')

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=7860)