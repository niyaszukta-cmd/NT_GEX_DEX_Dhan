import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
import requests

class BlackScholesCalculator:
    @staticmethod
    def calculate_gamma(S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
        return gamma
    
    @staticmethod
    def calculate_delta(S, K, T, r, sigma, option_type='call'):
        if T <= 0 or sigma <= 0:
            return 0.0
        d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
        if option_type.lower() == 'call':
            delta = norm.cdf(d1)
        else:
            delta = norm.cdf(d1) - 1
        return delta

class EnhancedGEXDEXCalculator:
    """GEX/DEX Calculator - DhanHQ with Token Generation"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        
        # client_id = app_id, access_token = app_secret
        self.app_id = str(client_id).strip() if client_id else None
        self.app_secret = str(access_token).strip() if access_token else None
        
        self.base_url = "https://api.dhan.co/v2"
        self.auth_url = "https://auth.dhan.co/app/consumeApp-consent"
        self.jwt_token = None
        
        if self.app_id and self.app_secret:
            print(f"✅ DhanHQ configured")
            print(f"   App ID: {self.app_id}")
            print(f"   App Secret: {self.app_secret[:10]}...")
            
            # Generate JWT token
            self.generate_access_token()
    
    def generate_access_token(self):
        """Generate JWT Access Token from app_id and app_secret"""
        
        try:
            print(f"\n🔑 Generating Access Token...")
            
            headers = {
                "app_id": self.app_id,
                "app_secret": self.app_secret,
                "Content-Type": "application/json"
            }
            
            # Empty body for consent generation
            payload = {}
            
            response = requests.post(self.auth_url, json=payload, headers=headers, timeout=10)
            
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract access token from response
                self.jwt_token = data.get('accessToken')
                
                if self.jwt_token:
                    print(f"✅ Access Token generated successfully!")
                    print(f"   Token: {self.jwt_token[:20]}...{self.jwt_token[-10:]}")
                    return True
                else:
                    raise Exception(f"No accessToken in response: {data}")
            else:
                print(f"❌ Token generation failed")
                print(f"   Response: {response.text}")
                raise Exception(f"Failed to generate token: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Token generation error: {str(e)}")
            raise Exception(f"Could not generate access token: {str(e)}")
    
    def get_expiry_list(self, security_id, exchange_segment="IDX_I"):
        """Get expiry list using generated JWT token"""
        
        if not self.jwt_token:
            raise Exception("No JWT token available. Token generation failed.")
        
        url = f"{self.base_url}/optionchain/expirylist"
        
        headers = {
            "access-token": self.jwt_token,  # Use generated JWT token
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": str(exchange_segment)
        }
        
        try:
            print(f"\n📡 Calling Expiry List API...")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 401:
                print(f"⚠️ Token expired or invalid, regenerating...")
                self.generate_access_token()
                # Retry with new token
                headers["access-token"] = self.jwt_token
                response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded. Wait 3 seconds.")
            
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success' and 'data' in data:
                expiries = data['data']
                print(f"✅ Got {len(expiries)} expiries")
                return expiries
            else:
                raise Exception(f"API error: {data}")
                
        except Exception as e:
            raise Exception(f"Expiry list error: {str(e)}")
    
    def get_option_chain(self, security_id, exchange_segment, expiry):
        """Get option chain using JWT token"""
        
        if not self.jwt_token:
            raise Exception("No JWT token available")
        
        url = f"{self.base_url}/optionchain"
        
        headers = {
            "access-token": self.jwt_token,
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": str(exchange_segment),
            "Expiry": str(expiry)
        }
        
        try:
            print(f"\n📡 Calling Option Chain API...")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 401:
                print(f"⚠️ Token expired, regenerating...")
                self.generate_access_token()
                headers["access-token"] = self.jwt_token
                response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                print(f"✅ Option chain received")
                return data['data']
            else:
                raise Exception(f"No data: {data}")
                
        except Exception as e:
            raise Exception(f"Option chain error: {str(e)}")
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price"""
        defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
        return defaults.get(symbol, 24500)
    
    def parse_option_chain_response(self, option_chain_data):
        """Parse option chain"""
        
        parsed_data = []
        underlying_ltp = option_chain_data.get('last_price', 0)
        oc = option_chain_data.get('oc', {})
        
        for strike_str, strike_data in oc.items():
            try:
                strike = float(strike_str)
                
                ce_data = strike_data.get('ce', {})
                pe_data = strike_data.get('pe', {})
                
                parsed_data.append({
                    'Strike': strike,
                    'Call_OI': int(ce_data.get('oi', 0)),
                    'Call_IV': float(ce_data.get('implied_volatility', 15)) / 100 if ce_data.get('implied_volatility', 15) > 1 else float(ce_data.get('implied_volatility', 0.15)),
                    'Call_LTP': float(ce_data.get('last_price', 0)),
                    'Call_Volume': int(ce_data.get('volume', 0)),
                    'Put_OI': int(pe_data.get('oi', 0)),
                    'Put_IV': float(pe_data.get('implied_volatility', 15)) / 100 if pe_data.get('implied_volatility', 15) > 1 else float(pe_data.get('implied_volatility', 0.15)),
                    'Put_LTP': float(pe_data.get('last_price', 0)),
                    'Put_Volume': int(pe_data.get('volume', 0))
                })
            except:
                continue
        
        print(f"✅ Parsed {len(parsed_data)} strikes")
        return parsed_data, underlying_ltp
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation"""
        
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Starting {symbol} Analysis")
            print(f"{'='*60}")
            
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            # Get expiries
            expiries = self.get_expiry_list(security_id, "IDX_I")
            
            if not expiries:
                raise Exception("No expiries")
            
            if expiry_index >= len(expiries):
                expiry_index = 0
            
            selected_expiry = expiries[expiry_index]
            print(f"\n📅 Selected expiry: {selected_expiry}")
            
            # Get option chain
            option_chain_data = self.get_option_chain(security_id, "IDX_I", selected_expiry)
            
            # Parse
            parsed_data, underlying_price = self.parse_option_chain_response(option_chain_data)
            
            if not parsed_data:
                raise Exception("No data")
            
            df = pd.DataFrame(parsed_data)
            
            if underlying_price == 0:
                underlying_price = self.get_underlying_price(symbol)
            
            print(f"💰 Price: ₹{underlying_price:,.2f}")
            
            # Filter strikes
            df = df[
                (df['Strike'] >= underlying_price - strikes_range * 100) &
                (df['Strike'] <= underlying_price + strikes_range * 100)
            ].copy()
            
            if len(df) == 0:
                raise Exception("No strikes in range")
            
            print(f"📊 Processing {len(df)} strikes")
            
            # Time to expiry
            try:
                expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
            
            days_to_expiry = max((expiry_date - datetime.now()).days, 1)
            T = days_to_expiry / 365.0
            
            # Calculate Greeks
            df['Call_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)), axis=1)
            df['Put_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)), axis=1)
            df['Call_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'), axis=1)
            df['Put_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'), axis=1)
            
            # GEX/DEX
            df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * underlying_price * underlying_price * 0.01
            df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * underlying_price * underlying_price * 0.01 * -1
            df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
            df['Net_GEX_B'] = df['Net_GEX'] / 1e9
            
            df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * underlying_price * 0.01
            df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * underlying_price * 0.01
            df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
            df['Net_DEX_B'] = df['Net_DEX'] / 1e9
            
            total_gex = df['Net_GEX'].abs().sum()
            df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex * 100) if total_gex > 0 else 0
            df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
            
            # ATM info
            atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
            atm_row = df[df['Strike'] == atm_strike].iloc[0]
            
            atm_info = {
                'atm_strike': int(atm_strike),
                'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
            }
            
            print(f"\n✅ COMPLETE!")
            print(f"{'='*60}\n")
            
            return df, underlying_price, "DhanHQ API", atm_info
            
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}\n")
            raise Exception(str(e))

def calculate_dual_gex_dex_flow(df, futures_ltp):
    try:
        df_sorted = df.sort_values('Strike').copy()
        atm_idx = (df_sorted['Strike'] - futures_ltp).abs().idxmin()
        atm_position = df_sorted.index.get_loc(atm_idx)
        
        start_idx = max(0, atm_position - 5)
        end_idx = min(len(df_sorted), atm_position + 6)
        near_strikes = df_sorted.iloc[start_idx:end_idx]
        
        positive_gex = near_strikes[near_strikes['Net_GEX_B'] > 0]['Net_GEX_B'].sum()
        negative_gex = near_strikes[near_strikes['Net_GEX_B'] < 0]['Net_GEX_B'].sum()
        gex_near_total = positive_gex + negative_gex
        
        if gex_near_total > 50:
            gex_bias = "STRONG BULLISH"
        elif gex_near_total < -50:
            gex_bias = "VOLATILE"
        else:
            gex_bias = "NEUTRAL"
        
        dex_near_total = near_strikes['Net_DEX_B'].sum()
        dex_bias = "BULLISH" if dex_near_total > 0 else "BEARISH"
        
        return {
            'gex_near_total': gex_near_total,
            'dex_near_total': dex_near_total,
            'gex_near_bias': gex_bias,
            'dex_near_bias': dex_bias,
            'combined_bias': f"{gex_bias} + {dex_bias}"
        }
    except:
        return None

def detect_gamma_flip_zones(df):
    try:
        flip_zones = []
        df_sorted = df.sort_values('Strike').reset_index(drop=True)
        
        for i in range(len(df_sorted) - 1):
            current_gex = df_sorted.loc[i, 'Net_GEX_B']
            next_gex = df_sorted.loc[i + 1, 'Net_GEX_B']
            
            if (current_gex > 0 and next_gex < 0) or (current_gex < 0 and next_gex > 0):
                flip_zones.append({
                    'lower_strike': df_sorted.loc[i, 'Strike'],
                    'upper_strike': df_sorted.loc[i + 1, 'Strike'],
                    'type': 'Flip Zone'
                })
        
        return flip_zones
    except:
        return []
