import requests
import streamlit as st

def generate_consent_token(client_id):
    """Generate DhanHQ consent token"""
    
    url = "https://auth.dhan.co/app/generate-consent"
    
    params = {
        "client_id": client_id,
        "redirect_uri": "https://google.com"  # Redirect after consent
    }
    
    try:
        response = requests.post(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            consent_id = data.get('consent_id')
            consent_url = data.get('consent_url')
            
            return consent_id, consent_url
        else:
            return None, None
            
    except Exception as e:
        st.error(f"Consent generation error: {str(e)}")
        return None, None

def get_access_token_with_consent(client_id, api_secret, consent_id):
    """Get access token using consent ID"""
    
    url = "https://api.dhan.co/v2/access-token"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "client_id": client_id,
        "api_secret": api_secret,
        "consent_id": consent_id
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return data.get('access_token')
        else:
            return None
            
    except Exception as e:
        st.error(f"Token generation error: {str(e)}")
        return None
