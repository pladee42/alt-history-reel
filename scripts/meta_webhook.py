#!/usr/bin/env python3
"""
meta_webhook.py - Meta/Instagram Webhook Handler

Handles webhook verification and receives update notifications from Meta.
For development: Run with ngrok
For production: Deploy to Cloud Run

Usage:
    # Set environment variables
    export META_APP_SECRET="your_app_secret"
    export META_VERIFY_TOKEN="your_custom_verify_token"
    
    # Run the webhook server
    python scripts/meta_webhook.py
    
    # In another terminal, expose via ngrok
    ngrok http 5000
    
    # Use the ngrok URL + /webhook as your Meta callback URL
    # Example: https://xxxx.ngrok.io/webhook
"""

import os
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv(override=True)

app = Flask(__name__)

# Configuration from environment
APP_SECRET = os.getenv('META_APP_SECRET', '')
VERIFY_TOKEN = os.getenv('META_VERIFY_TOKEN', 'timeline_b_verify_token')

# Store received webhooks (in-memory, for testing)
received_webhooks = []


@app.route('/')
def index():
    """Display received webhooks."""
    return jsonify(received_webhooks)


@app.route('/webhook', methods=['GET'])
def verify_webhook():
    """
    Handle webhook verification from Meta.
    
    Meta sends a GET request with:
    - hub.mode: 'subscribe'
    - hub.verify_token: Your verify token
    - hub.challenge: A random string to echo back
    """
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    print(f"🔐 Webhook verification request:")
    print(f"   Mode: {mode}")
    print(f"   Token: {token}")
    print(f"   Challenge: {challenge}")
    
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print(f"   ✅ Verification successful!")
        return challenge, 200
    else:
        print(f"   ❌ Verification failed! Token mismatch.")
        print(f"   Expected: {VERIFY_TOKEN}")
        print(f"   Received: {token}")
        return 'Forbidden', 403


@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Handle incoming webhook notifications from Meta.
    
    Notifications include:
    - Media status updates (when Reels finish processing)
    - Comment notifications
    - Other Instagram Graph API events
    """
    # Verify signature (recommended for production)
    signature = request.headers.get('X-Hub-Signature-256', '')
    
    if APP_SECRET and signature:
        payload = request.get_data()
        expected_signature = 'sha256=' + hmac.new(
            APP_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            print("   ⚠️ Invalid signature!")
            return 'Invalid signature', 403
    
    # Parse the webhook payload
    data = request.get_json()
    
    print(f"\n📬 Webhook received:")
    print(json.dumps(data, indent=2))
    
    # Store for display
    received_webhooks.append({
        'timestamp': str(os.popen('date').read().strip()),
        'data': data
    })
    
    # Keep only last 10 webhooks
    if len(received_webhooks) > 10:
        received_webhooks.pop(0)
    
    # Process the webhook (add your logic here)
    if 'entry' in data:
        for entry in data['entry']:
            # Handle Instagram-specific events
            if 'changes' in entry:
                for change in entry['changes']:
                    field = change.get('field')
                    value = change.get('value')
                    
                    print(f"   📌 Field: {field}")
                    print(f"   📦 Value: {value}")
                    
                    # Handle media status updates
                    if field == 'media':
                        handle_media_update(value)
    
    return 'OK', 200


def handle_media_update(value):
    """Handle media status updates."""
    media_id = value.get('media_id')
    status = value.get('status')
    
    print(f"\n🎬 Media Update:")
    print(f"   Media ID: {media_id}")
    print(f"   Status: {status}")
    
    # Add your logic here, e.g., update database, send notification


@app.route('/health')
def health():
    """Health check endpoint for Cloud Run."""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    port = int(os.getenv('PORT', 8081))
    
    print("\n" + "=" * 60)
    print("🔗 Meta Webhook Handler")
    print("=" * 60)
    print(f"\n📍 Running on port {port}")
    print(f"🔑 Verify Token: {VERIFY_TOKEN}")
    print(f"🔐 App Secret: {'***' + APP_SECRET[-4:] if APP_SECRET else 'Not set'}")
    
    print("\n📝 Configuration:")
    print(f"   1. Expose this server via ngrok:")
    print(f"      ngrok http {port}")
    print(f"   2. Use the ngrok URL + /webhook as your callback URL")
    print(f"   3. Use '{VERIFY_TOKEN}' as your verify token in Meta Dashboard")
    
    print("\n🚀 Starting server...")
    app.run(host='0.0.0.0', port=port, debug=True)
