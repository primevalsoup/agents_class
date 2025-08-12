import gradio as gr
import requests
import base64
import os
from dotenv import load_dotenv
import urllib.parse
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import time

# Load environment variables
load_dotenv(override=True)

# Spotify credentials
spotify_client_id = os.getenv("SPOTIFY_CLIENT_ID")
spotify_client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

# We'll use a separate port for the OAuth callback
CALLBACK_PORT = 8888
spotify_redirect_uri = f"http://localhost:{CALLBACK_PORT}/callback"

# Global state to store tokens and authorization code
auth_state = {"code": None, "tokens": None, "error": None}

class CallbackHandler(BaseHTTPRequestHandler):
    """Handle the OAuth callback from Spotify"""
    
    def do_GET(self):
        # Parse the callback URL
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/callback':
            # Extract query parameters
            query_params = urllib.parse.parse_qs(parsed_path.query)
            
            if 'code' in query_params:
                auth_state["code"] = query_params['code'][0]
                # Send success response
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #1DB954;">Success!</h1>
                    <p>Authorization complete. You can close this window and return to the Gradio app.</p>
                    <script>window.close();</script>
                </body>
                </html>
                """)
            elif 'error' in query_params:
                auth_state["error"] = query_params.get('error', ['Unknown error'])[0]
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                self.wfile.write(b"""
                <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: #ff0000;">Authorization Failed</h1>
                    <p>Please return to the Gradio app and try again.</p>
                </body>
                </html>
                """)
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

def start_callback_server():
    """Start a temporary server to handle the OAuth callback"""
    server = HTTPServer(('localhost', CALLBACK_PORT), CallbackHandler)
    server.timeout = 120  # 2 minute timeout
    server.handle_request()  # Handle just one request then stop

def get_auth_url():
    """Generate the authorization URL for Spotify OAuth."""
    if not spotify_client_id:
        return "Error: SPOTIFY_CLIENT_ID not found in .env file"
    
    auth_url = "https://accounts.spotify.com/authorize"
    scopes = "user-top-read"
    
    params = {
        "client_id": spotify_client_id,
        "response_type": "code",
        "redirect_uri": spotify_redirect_uri,
        "scope": scopes,
        "show_dialog": "true"
    }
    
    url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    
    # Try to open in browser
    try:
        webbrowser.open(url)
        return f"Authorization URL opened in browser!\n\nIf it didn't open, visit:\n{url}\n\nAfter authorizing, paste the full redirect URL below."
    except:
        return f"Please visit this URL to authorize:\n{url}\n\nAfter authorizing, paste the full redirect URL below."

def exchange_code(redirect_url):
    """Extract code from redirect URL and exchange for tokens."""
    if not redirect_url:
        return "Please paste the redirect URL first"
    
    if not spotify_client_id or not spotify_client_secret:
        return "Error: SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET not found in .env file"
    
    try:
        # Extract code from redirect URL
        parsed_url = urllib.parse.urlparse(redirect_url)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        if 'code' not in query_params:
            return "Error: No authorization code found in the URL. Make sure you pasted the complete redirect URL."
        
        authorization_code = query_params['code'][0]
        
        # Exchange code for tokens
        token_url = "https://accounts.spotify.com/api/token"
        
        credentials = f"{spotify_client_id}:{spotify_client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": authorization_code,
            "redirect_uri": spotify_redirect_uri
        }
        
        response = requests.post(token_url, headers=headers, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            tokens["access_token"] = token_data["access_token"]
            tokens["refresh_token"] = token_data["refresh_token"]
            
            return f"""✅ Success! Your tokens:

SPOTIFY_ACCESS_TOKEN={token_data["access_token"][:50]}...
SPOTIFY_REFRESH_TOKEN={token_data["refresh_token"][:50]}...

Add these to your .env file:
SPOTIFY_ACCESS_TOKEN={token_data["access_token"]}
SPOTIFY_REFRESH_TOKEN={token_data["refresh_token"]}

Then run: load_dotenv(override=True)"""
        else:
            error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
            return f"❌ Failed to exchange code: {response.status_code}\n{error_data}"
            
    except Exception as e:
        return f"Error processing redirect URL: {str(e)}"

def copy_env_format():
    """Generate .env format for easy copying."""
    if not tokens["access_token"] or not tokens["refresh_token"]:
        return "No tokens available yet. Please complete the authorization flow first."
    
    env_format = f"""# Add these lines to your .env file:
SPOTIFY_ACCESS_TOKEN={tokens["access_token"]}
SPOTIFY_REFRESH_TOKEN={tokens["refresh_token"]}"""
    
    return env_format

# Create Gradio interface
with gr.Blocks(title="Spotify OAuth Helper") as app:
    gr.Markdown("""
    # Spotify OAuth Token Helper
    
    This app helps you get Spotify access tokens for your application.
    
    ## Prerequisites:
    1. Create a Spotify app at https://developer.spotify.com/dashboard
    2. Add these to your .env file:
       - `SPOTIFY_CLIENT_ID=your_client_id`
       - `SPOTIFY_CLIENT_SECRET=your_client_secret`
       - `SPOTIFY_REDIRECT_URI=http://localhost:7860` (or your custom URI)
    """)
    
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Step 1: Generate Authorization URL")
            auth_btn = gr.Button("🔐 Generate Auth URL", variant="primary")
            auth_output = gr.Textbox(label="Authorization URL", lines=5)
            
            gr.Markdown("### Step 2: Paste Redirect URL")
            redirect_input = gr.Textbox(
                label="Paste the full redirect URL here after authorizing",
                placeholder="http://localhost:7860?code=AQD...",
                lines=2
            )
            exchange_btn = gr.Button("🔄 Exchange Code for Tokens", variant="primary")
            
        with gr.Column():
            gr.Markdown("### Step 3: Get Your Tokens")
            token_output = gr.Textbox(label="Token Results", lines=12)
            
            gr.Markdown("### Copy .env Format")
            copy_btn = gr.Button("📋 Get .env Format", variant="secondary")
            env_output = gr.Textbox(label=".env Format", lines=5)
    
    # Event handlers
    auth_btn.click(fn=get_auth_url, outputs=auth_output)
    exchange_btn.click(fn=exchange_code, inputs=redirect_input, outputs=token_output)
    copy_btn.click(fn=copy_env_format, outputs=env_output)
    
    gr.Markdown("""
    ---
    ### How to use:
    1. Click "Generate Auth URL" and authorize the app in your browser
    2. Copy the entire redirect URL from your browser's address bar
    3. Paste it in the box and click "Exchange Code for Tokens"
    4. Copy the tokens to your .env file
    5. In your notebook, run `load_dotenv(override=True)` to reload
    """)

if __name__ == "__main__":
    print(f"Starting Spotify OAuth Helper on {spotify_redirect_uri}")
    print(f"Make sure your Spotify app's redirect URI is set to: {spotify_redirect_uri}")
    app.launch(server_port=7860)