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
    """GEX/DEX Calculator using DhanHQ REST API v2"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = str(client_id).strip() if client_id else None
        self.access_token = str(access_token).strip() if access_token else None
        self.base_url = "https://api.dhan.co/v2"
        
        if self.client_id and self.access_token:
            print(f"✅ DhanHQ API configured")
            print(f"   Client ID: {self.client_id}")
            print(f"   Token length: {len(self.access_token)} characters")
    
    def get_expiry_list(self, security_id, exchange_segment="IDX_I"):
        """Get expiry list from DhanHQ - Official API v2"""
        
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
            print(f"\n📡 Calling DhanHQ Expiry List API...")
            print(f"   URL: {url}")
            print(f"   Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Response Status: {response.status_code}")
            print(f"📊 Response Text (first 500 chars): {response.text[:500]}")
            
            # Handle specific HTTP errors
            if response.status_code == 401:
                raise Exception("Authentication failed. Access Token may be expired. Please regenerate at https://www.dhan.co/")
            
            if response.status_code == 403:
                raise Exception("Access forbidden. Please ensure Data APIs are enabled in your Dhan account.")
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded. DhanHQ allows 1 request per 3 seconds. Please wait and try again.")
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            # Parse response
            data = response.json()
            
            print(f"✅ Response received")
            print(f"   Full Response Keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            print(f"   Status: {data.get('status', 'unknown')}")
            
            # FIXED: DhanHQ API v2 response structure
            # Response: {"data": ["2024-10-17", ...], "status": "success"}
            if data.get('status') == 'success':
                expiries = data.get('data', [])
                
                if not expiries or len(expiries) == 0:
                    raise Exception("No expiries available. Market may be closed or there are no active option contracts.")
                
                print(f"✅ Found {len(expiries)} expiries: {expiries[:3]}...")
                return expiries
            else:
                # Handle error response
                error_msg = data.get('remarks', data.get('message', data.get('error', 'Unknown API error')))
                error_code = data.get('errorCode', data.get('status', 'unknown'))
                raise Exception(f"API Error [{error_code}]: {error_msg}")
                
        except requests.exceptions.Timeout:
            raise Exception("Request timeout. Please check your internet connection and try again.")
        except requests.exceptions.ConnectionError:
            raise Exception("Connection error. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {str(e)}")
        except ValueError as e:
            raise Exception(f"Invalid JSON response: {str(e)}")
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            raise Exception(error_msg)
    
    def get_option_chain(self, security_id, exchange_segment, expiry):
        """Get option chain from DhanHQ - Official API v2"""
        
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
            print(f"\n📡 Calling DhanHQ Option Chain API...")
            print(f"   Expiry: {expiry}")
            print(f"   Payload: {payload}")
            
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            print(f"📊 Response Status: {response.status_code}")
            
            if response.status_code == 401:
                raise Exception("Authentication failed. Access Token may be expired.")
            
            if response.status_code == 403:
                raise Exception("Access forbidden. Enable Data APIs in Dhan account.")
            
            if response.status_code == 429:
                raise Exception("Rate limit exceeded. Wait 3 seconds between requests.")
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")
            
            data = response.json()
            
            print(f"📊 Response Keys: {data.keys() if isinstance(data, dict) else 'Not a dict'}")
            
            # FIXED: DhanHQ API v2 response structure
            # Response: {"data": {"last_price": 24964.25, "oc": {...}}}
            if 'data' in data:
                option_data = data['data']
                print(f"✅ Option chain data received")
                print(f"   Data Keys: {option_data.keys() if isinstance(option_data, dict) else 'Not a dict'}")
                return option_data
            else:
                error_msg = data.get('remarks', data.get('message', data.get('error', 'No data in response')))
                raise Exception(f"API error: {error_msg}")
                
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error"
            raise Exception(error_msg)
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price - fallback defaults"""
        defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
        return defaults.get(symbol, 24500)
    
    def parse_option_chain_response(self, option_chain_data):
        """Parse DhanHQ option chain - Official response structure"""
        
        try:
            parsed_data = []
            
            # FIXED: Get underlying LTP from response
            # Response structure: {"last_price": 24964.25, "oc": {...}}
            underlying_ltp = float(option_chain_data.get('last_price', 0))
            
            # Get option chain dictionary
            oc = option_chain_data.get('oc', {})
            
            if not oc:
                raise Exception("No option chain data ('oc') in response")
            
            print(f"\n📊 Parsing option chain...")
            print(f"   Underlying LTP: ₹{underlying_ltp:,.2f}")
            print(f"   Total strikes: {len(oc)}")
            
            # Parse each strike
            for strike_str, strike_data in oc.items():
                try:
                    strike = float(strike_str)
                    
                    # FIXED: Get CE (Call) data - DhanHQ uses 'ce' and 'pe'
                    ce_data = strike_data.get('ce', {})
                    call_oi = int(ce_data.get('oi', 0))
                    call_iv = float(ce_data.get('implied_volatility', 15))
                    call_ltp = float(ce_data.get('last_price', 0))
                    call_volume = int(ce_data.get('volume', 0))
                    
                    # Get Greeks if available (DhanHQ provides them!)
                    ce_greeks = ce_data.get('greeks', {})
                    call_delta_api = float(ce_greeks.get('delta', 0))
                    call_gamma_api = float(ce_greeks.get('gamma', 0))
                    call_theta = float(ce_greeks.get('theta', 0))
                    call_vega = float(ce_greeks.get('vega', 0))
                    
                    # FIXED: Get PE (Put) data
                    pe_data = strike_data.get('pe', {})
                    put_oi = int(pe_data.get('oi', 0))
                    put_iv = float(pe_data.get('implied_volatility', 15))
                    put_ltp = float(pe_data.get('last_price', 0))
                    put_volume = int(pe_data.get('volume', 0))
                    
                    # Get Put Greeks
                    pe_greeks = pe_data.get('greeks', {})
                    put_delta_api = float(pe_greeks.get('delta', 0))
                    put_gamma_api = float(pe_greeks.get('gamma', 0))
                    put_theta = float(pe_greeks.get('theta', 0))
                    put_vega = float(pe_greeks.get('vega', 0))
                    
                    # Convert IV from percentage to decimal if needed
                    call_iv_decimal = call_iv / 100 if call_iv > 1 else call_iv
                    put_iv_decimal = put_iv / 100 if put_iv > 1 else put_iv
                    
                    parsed_data.append({
                        'Strike': strike,
                        'Call_OI': call_oi,
                        'Call_IV': call_iv_decimal,
                        'Call_LTP': call_ltp,
                        'Call_Volume': call_volume,
                        'Call_Delta_API': call_delta_api,
                        'Call_Gamma_API': call_gamma_api,
                        'Call_Theta': call_theta,
                        'Call_Vega': call_vega,
                        'Put_OI': put_oi,
                        'Put_IV': put_iv_decimal,
                        'Put_LTP': put_ltp,
                        'Put_Volume': put_volume,
                        'Put_Delta_API': put_delta_api,
                        'Put_Gamma_API': put_gamma_api,
                        'Put_Theta': put_theta,
                        'Put_Vega': put_vega
                    })
                    
                except (ValueError, KeyError, TypeError) as e:
                    print(f"⚠️ Error parsing strike {strike_str}: {str(e)}")
                    continue
            
            if not parsed_data:
                raise Exception("No valid strike data found in option chain")
            
            print(f"✅ Successfully parsed {len(parsed_data)} strikes")
            
            return parsed_data, underlying_ltp
            
        except Exception as e:
            print(f"❌ Parse error: {str(e)}")
            raise Exception(f"Failed to parse option chain: {str(e)}")
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation function"""
        
        try:
            print(f"\n{'='*70}")
            print(f"  NYZTrade GEX/DEX Analysis - {symbol}")
            print(f"{'='*70}")
            
            # Security ID mapping (from DhanHQ instrument list)
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 442}
            security_id = security_map.get(symbol, 13)
            
            print(f"\n   Security ID for {symbol}: {security_id}")
            
            # STEP 1: Get expiry list
            print(f"\n[STEP 1] Fetching expiry list...")
            expiries = self.get_expiry_list(security_id, "IDX_I")
            
            # Select expiry
            if expiry_index >= len(expiries):
                expiry_index = 0
            
            selected_expiry = expiries[expiry_index]
            print(f"📅 Selected expiry: {selected_expiry}")
            
            # STEP 2: Get option chain
            print(f"\n[STEP 2] Fetching option chain...")
            import time
            time.sleep(3)  # Rate limit: 1 request per 3 seconds
            option_chain_data = self.get_option_chain(security_id, "IDX_I", selected_expiry)
            
            # STEP 3: Parse data
            print(f"\n[STEP 3] Parsing option data...")
            parsed_data, underlying_price = self.parse_option_chain_response(option_chain_data)
            
            # Use fallback if no LTP
            if underlying_price == 0:
                underlying_price = self.get_underlying_price(symbol)
                print(f"   Using fallback price: ₹{underlying_price:,.2f}")
            
            # Create DataFrame
            df = pd.DataFrame(parsed_data)
            
            # STEP 4: Filter strikes
            print(f"\n[STEP 4] Filtering strikes...")
            strike_step = 50 if symbol in ["NIFTY", "FINNIFTY"] else 100
            range_points = strikes_range * strike_step
            
            df = df[
                (df['Strike'] >= underlying_price - range_points) &
                (df['Strike'] <= underlying_price + range_points)
            ].copy()
            
            if len(df) == 0:
                raise Exception(f"No strikes in range ±{range_points} from ₹{underlying_price:,.0f}")
            
            print(f"✅ {len(df)} strikes in analysis range")
            
            # STEP 5: Calculate time to expiry
            print(f"\n[STEP 5] Calculating time to expiry...")
            try:
                expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
            
            days_to_expiry = max((expiry_date - datetime.now()).days, 1)
            T = days_to_expiry / 365.0
            print(f"📅 Days to expiry: {days_to_expiry} | T = {T:.4f}")
            
            # STEP 6: Use API Greeks or Calculate
            print(f"\n[STEP 6] Processing Greeks...")
            
            # Check if API provides Greeks
            has_api_greeks = df['Call_Gamma_API'].abs().sum() > 0
            
            if has_api_greeks:
                print("   Using DhanHQ API Greeks (delta, gamma from API)")
                df['Call_Gamma'] = df['Call_Gamma_API']
                df['Put_Gamma'] = df['Put_Gamma_API']
                df['Call_Delta'] = df['Call_Delta_API']
                df['Put_Delta'] = df['Put_Delta_API']
            else:
                print("   Calculating Greeks using Black-Scholes...")
                df['Call_Gamma'] = df.apply(
                    lambda r: self.bs_calc.calculate_gamma(
                        underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)
                    ), axis=1
                )
                
                df['Put_Gamma'] = df.apply(
                    lambda r: self.bs_calc.calculate_gamma(
                        underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)
                    ), axis=1
                )
                
                df['Call_Delta'] = df.apply(
                    lambda r: self.bs_calc.calculate_delta(
                        underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'
                    ), axis=1
                )
                
                df['Put_Delta'] = df.apply(
                    lambda r: self.bs_calc.calculate_delta(
                        underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'
                    ), axis=1
                )
            
            # STEP 7: Calculate GEX and DEX
            print(f"\n[STEP 7] Calculating GEX and DEX...")
            
            # GEX Calculation: Gamma * OI * Spot^2 * 0.01
            # Call GEX is positive (dealers are short calls, need to buy on rise)
            # Put GEX is negative (dealers are short puts, need to sell on rise)
            df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * underlying_price * underlying_price * 0.01
            df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * underlying_price * underlying_price * 0.01 * -1
            df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
            df['Net_GEX_B'] = df['Net_GEX'] / 1e9
            
            # DEX Calculation: Delta * OI * Spot * 0.01
            df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * underlying_price * 0.01
            df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * underlying_price * 0.01
            df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
            df['Net_DEX_B'] = df['Net_DEX'] / 1e9
            
            # Additional metrics
            total_gex = df['Net_GEX'].abs().sum()
            df['Hedging_Pressure'] = (df['Net_GEX'] / total_gex * 100) if total_gex > 0 else 0
            df['Total_Volume'] = df['Call_Volume'] + df['Put_Volume']
            
            # ATM info
            atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort().iloc[0]]['Strike']
            atm_row = df[df['Strike'] == atm_strike].iloc[0]
            
            atm_info = {
                'atm_strike': int(atm_strike),
                'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP'],
                'expiry_date': selected_expiry,
                'days_to_expiry': days_to_expiry
            }
            
            print(f"\n{'='*70}")
            print(f"  ✅ CALCULATION COMPLETE!")
            print(f"  Underlying: ₹{underlying_price:,.2f}")
            print(f"  Total Net GEX: {df['Net_GEX_B'].sum():.4f}B")
            print(f"  ATM Strike: {atm_info['atm_strike']}")
            print(f"  ATM Straddle: ₹{atm_info['atm_straddle_premium']:.2f}")
            print(f"{'='*70}\n")
            
            return df, underlying_price, "DhanHQ API v2", atm_info
            
        except Exception as e:
            error_msg = str(e) if str(e) else "Unknown error occurred"
            print(f"\n{'='*70}")
            print(f"  ❌ ERROR: {error_msg}")
            print(f"{'='*70}\n")
            print(f"Full traceback:")
            print(traceback.format_exc())
            raise Exception(error_msg)

def calculate_dual_gex_dex_flow(df, futures_ltp):
    """Calculate GEX/DEX flow metrics"""
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
    """Detect gamma flip zones"""
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


# Test function to verify API connectivity
def test_dhan_api(client_id, access_token):
    """Test DhanHQ API connection"""
    print("\n" + "="*70)
    print("  DHAN HQ API CONNECTION TEST")
    print("="*70)
    
    calc = EnhancedGEXDEXCalculator(client_id=client_id, access_token=access_token)
    
    try:
        # Test expiry list
        print("\n[TEST 1] Fetching NIFTY expiry list...")
        expiries = calc.get_expiry_list(13, "IDX_I")
        print(f"✅ SUCCESS! Found {len(expiries)} expiries")
        print(f"   First 3 expiries: {expiries[:3]}")
        
        # Test option chain
        print("\n[TEST 2] Fetching option chain for first expiry...")
        import time
        time.sleep(3)  # Rate limit
        oc_data = calc.get_option_chain(13, "IDX_I", expiries[0])
        print(f"✅ SUCCESS! Got option chain data")
        print(f"   Underlying LTP: {oc_data.get('last_price', 'N/A')}")
        print(f"   Number of strikes: {len(oc_data.get('oc', {}))}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    # Example usage - replace with your credentials
    CLIENT_ID = "your_client_id"
    ACCESS_TOKEN = "your_access_token"
    
    # Test the API
    test_dhan_api(CLIENT_ID, ACCESS_TOKEN)
