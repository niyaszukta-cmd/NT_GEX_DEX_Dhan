import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta
import requests
import traceback

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
    """GEX/DEX Calculator using DhanHQ REST API"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = str(client_id).strip() if client_id else None
        self.access_token = str(access_token).strip() if access_token else None
        self.base_url = "https://api.dhan.co/v2"
        
        if self.client_id and self.access_token:
            print(f"✅ DhanHQ configured")
            print(f"   Client ID: {self.client_id}")
            print(f"   Token length: {len(self.access_token)} chars")
    
    def get_expiry_list(self, security_id, exchange_segment="IDX_I"):
        """Get expiry list from DhanHQ"""
        
        url = f"{self.base_url}/optionchain/expirylist"
        
        headers = {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": str(exchange_segment)
        }
        
        try:
            print(f"📡 Calling DhanHQ expiry list API...")
            print(f"   URL: {url}")
            print(f"   Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 401:
                raise Exception("🔴 Authentication failed. Access Token may be expired. Please regenerate at https://www.dhan.co/")
            
            if response.status_code == 429:
                raise Exception("🔴 Rate limit exceeded. DhanHQ allows 1 request per 3 seconds.")
            
            if response.status_code == 403:
                raise Exception("🔴 Access forbidden. Please ensure Data APIs are enabled in your Dhan account.")
            
            response.raise_for_status()
            data = response.json()
            
            print(f"✅ Response received")
            print(f"   Status: {data.get('status', 'unknown')}")
            
            if data.get('status') == 'success' and 'data' in data:
                expiries = data['data']
                print(f"✅ Got {len(expiries)} expiries")
                return expiries
            else:
                error_msg = data.get('message', data.get('error', 'Unknown error'))
                raise Exception(f"API returned error: {error_msg}")
                
        except requests.exceptions.Timeout:
            raise Exception("⏱️ Request timeout. Please try again.")
        except requests.exceptions.ConnectionError:
            raise Exception("🌐 Connection error. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            if not str(e):
                raise Exception(f"Unknown error occurred. Response: {response.text if 'response' in locals() else 'No response'}")
            raise
    
    def get_option_chain(self, security_id, exchange_segment, expiry):
        """Get option chain from DhanHQ"""
        
        url = f"{self.base_url}/optionchain"
        
        headers = {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": int(security_id),
            "UnderlyingSeg": str(exchange_segment),
            "Expiry": str(expiry)
        }
        
        try:
            print(f"📡 Calling DhanHQ option chain API...")
            print(f"   Expiry: {expiry}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 401:
                raise Exception("🔴 Authentication failed")
            
            if response.status_code == 429:
                raise Exception("🔴 Rate limit exceeded")
            
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                print(f"✅ Got option chain data")
                return data['data']
            else:
                error_msg = data.get('message', data.get('error', 'No data'))
                raise Exception(f"API error: {error_msg}")
                
        except Exception as e:
            if not str(e):
                raise Exception(f"Unknown error. Response: {response.text if 'response' in locals() else 'No response'}")
            raise
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price"""
        defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
        return defaults.get(symbol, 24500)
    
    def parse_option_chain_response(self, option_chain_data):
        """Parse DhanHQ option chain"""
        
        try:
            parsed_data = []
            underlying_ltp = option_chain_data.get('last_price', 0)
            oc = option_chain_data.get('oc', {})
            
            if not oc:
                raise Exception("No option chain data in response")
            
            print(f"📊 Parsing {len(oc)} strikes...")
            
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
                except Exception as parse_error:
                    print(f"⚠️ Error parsing strike {strike_str}: {str(parse_error)}")
                    continue
            
            print(f"✅ Parsed {len(parsed_data)} strikes")
            return parsed_data, underlying_ltp
            
        except Exception as e:
            print(f"❌ Parse error: {str(e)}")
            print(f"   Data keys: {list(option_chain_data.keys())}")
            raise Exception(f"Failed to parse option chain: {str(e)}")
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation"""
        
        try:
            print(f"\n{'='*60}")
            print(f"🔄 Starting {symbol} analysis...")
            print(f"{'='*60}\n")
            
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            # Get expiries
            print("STEP 1: Fetching expiry list...")
            expiries = self.get_expiry_list(security_id, "IDX_I")
            
            if not expiries or len(expiries) == 0:
                raise Exception("No expiries available. Market may be closed.")
            
            if expiry_index >= len(expiries):
                expiry_index = 0
            
            selected_expiry = expiries[expiry_index]
            print(f"📅 Selected expiry: {selected_expiry}")
            
            # Get option chain
            print("\nSTEP 2: Fetching option chain...")
            option_chain_data = self.get_option_chain(security_id, "IDX_I", selected_expiry)
            
            # Parse
            print("\nSTEP 3: Parsing option data...")
            parsed_data, underlying_price = self.parse_option_chain_response(option_chain_data)
            
            if not parsed_data:
                raise Exception("No option data available after parsing")
            
            df = pd.DataFrame(parsed_data)
            
            if underlying_price == 0:
                underlying_price = self.get_underlying_price(symbol)
            
            print(f"💰 Underlying price: ₹{underlying_price:,.2f}")
            
            # Filter
            print("\nSTEP 4: Filtering strikes...")
            df = df[
                (df['Strike'] >= underlying_price - strikes_range * 100) &
                (df['Strike'] <= underlying_price + strikes_range * 100)
            ].copy()
            
            if len(df) == 0:
                raise Exception(f"No strikes in range [{underlying_price - strikes_range * 100}, {underlying_price + strikes_range * 100}]")
            
            print(f"✅ Filtered to {len(df)} strikes")
            
            # Time to expiry
            try:
                expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
            
            days_to_expiry = max((expiry_date - datetime.now()).days, 1)
            T = days_to_expiry / 365.0
            print(f"📅 Days to expiry: {days_to_expiry}")
            
            # Greeks
            print("\nSTEP 5: Calculating Greeks...")
            df['Call_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)), axis=1)
            df['Put_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)), axis=1)
            df['Call_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'), axis=1)
            df['Put_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'), axis=1)
            
            # GEX/DEX
            print("STEP 6: Calculating GEX/DEX...")
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
            
            # ATM
            atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
            atm_row = df[df['Strike'] == atm_strike].iloc[0]
            
            atm_info = {
                'atm_strike': int(atm_strike),
                'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
            }
            
            print(f"\n{'='*60}")
            print(f"✅ CALCULATION COMPLETE!")
            print(f"{'='*60}\n")
            
            return df, underlying_price, "DhanHQ API", atm_info
            
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            print(f"\n{'='*60}")
            print(f"❌ ERROR: {error_msg}")
            print(f"{'='*60}")
            print(f"\nFull traceback:")
            print(traceback.format_exc())
            raise Exception(error_msg)

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
    except Exception as e:
        print(f"❌ Flow calculation error: {str(e)}")
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
    except Exception as e:
        print(f"❌ Gamma flip detection error: {str(e)}")
        return []
