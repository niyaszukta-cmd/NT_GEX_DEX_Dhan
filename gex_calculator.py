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
    """GEX/DEX Calculator using DhanHQ REST API (Official v2)"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.base_url = "https://api.dhan.co/v2"
        
        if client_id and access_token:
            print(f"✅ DhanHQ REST API configured | Client: {client_id}")
    
    def get_expiry_list(self, security_id, exchange_segment="IDX_I"):
        """Get expiry list using DhanHQ REST API"""
        
        url = f"{self.base_url}/optionchain/expirylist"
        
        headers = {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": security_id,
            "UnderlyingSeg": exchange_segment
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'success' and 'data' in data:
                expiries = data['data']
                print(f"✅ Got {len(expiries)} expiries from DhanHQ")
                return expiries
            else:
                raise Exception(f"API returned: {data}")
                
        except Exception as e:
            print(f"⚠️ Expiry list error: {str(e)}")
            raise
    
    def get_option_chain(self, security_id, exchange_segment, expiry):
        """Get option chain using DhanHQ REST API"""
        
        url = f"{self.base_url}/optionchain"
        
        headers = {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json"
        }
        
        payload = {
            "UnderlyingScrip": security_id,
            "UnderlyingSeg": exchange_segment,
            "Expiry": expiry
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data:
                print(f"✅ Got option chain from DhanHQ")
                return data['data']
            else:
                raise Exception(f"API returned: {data}")
                
        except Exception as e:
            print(f"⚠️ Option chain error: {str(e)}")
            raise
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price - use defaults for now"""
        defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
        return defaults.get(symbol, 24500)
    
    def parse_option_chain_response(self, option_chain_data):
        """Parse DhanHQ option chain response format"""
        
        parsed_data = []
        
        # Get underlying LTP
        underlying_ltp = option_chain_data.get('last_price', 24500)
        
        # Get option chain dictionary
        oc = option_chain_data.get('oc', {})
        
        for strike_str, strike_data in oc.items():
            try:
                strike = float(strike_str)
                
                # Parse CE (Call) data
                ce_data = strike_data.get('ce', {})
                call_oi = ce_data.get('oi', 0)
                call_iv = ce_data.get('implied_volatility', 15)
                call_ltp = ce_data.get('last_price', 0)
                call_volume = ce_data.get('volume', 0)
                
                # Parse PE (Put) data
                pe_data = strike_data.get('pe', {})
                put_oi = pe_data.get('oi', 0)
                put_iv = pe_data.get('implied_volatility', 15)
                put_ltp = pe_data.get('last_price', 0)
                put_volume = pe_data.get('volume', 0)
                
                parsed_data.append({
                    'Strike': strike,
                    'Call_OI': int(call_oi),
                    'Call_IV': float(call_iv) / 100 if call_iv > 1 else float(call_iv),
                    'Call_LTP': float(call_ltp),
                    'Call_Volume': int(call_volume),
                    'Put_OI': int(put_oi),
                    'Put_IV': float(put_iv) / 100 if put_iv > 1 else float(put_iv),
                    'Put_LTP': float(put_ltp),
                    'Put_Volume': int(put_volume)
                })
                
            except Exception as e:
                continue
        
        print(f"✅ Parsed {len(parsed_data)} strikes")
        return parsed_data, underlying_ltp
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation using DhanHQ REST API"""
        
        try:
            print(f"🔄 Fetching {symbol} from DhanHQ REST API...")
            
            # Security ID mapping
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            exchange_segment = "IDX_I"
            
            # Step 1: Get expiry list
            expiries = self.get_expiry_list(security_id, exchange_segment)
            
            if not expiries:
                raise Exception("No expiries available")
            
            # Select expiry
            if expiry_index >= len(expiries):
                expiry_index = 0
            selected_expiry = expiries[expiry_index]
            
            print(f"📅 Selected expiry: {selected_expiry}")
            
            # Step 2: Get option chain
            option_chain_data = self.get_option_chain(security_id, exchange_segment, selected_expiry)
            
            # Step 3: Parse option chain
            parsed_data, underlying_price = self.parse_option_chain_response(option_chain_data)
            
            if not parsed_data:
                raise Exception("No data after parsing")
            
            # Create DataFrame
            df = pd.DataFrame(parsed_data)
            
            # Use API underlying price if available, else use default
            if underlying_price == 0:
                underlying_price = self.get_underlying_price(symbol)
            
            print(f"💰 Underlying: ₹{underlying_price:,.2f}")
            
            # Filter strikes
            df = df[
                (df['Strike'] >= underlying_price - strikes_range * 100) &
                (df['Strike'] <= underlying_price + strikes_range * 100)
            ].copy()
            
            if len(df) == 0:
                raise Exception("No strikes in range")
            
            print(f"✅ Processing {len(df)} strikes")
            
            # Calculate time to expiry
            try:
                expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
            
            days_to_expiry = max((expiry_date - datetime.now()).days, 1)
            T = days_to_expiry / 365.0
            
            # Calculate Greeks
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
            
            # GEX calculations
            df['Call_GEX'] = df['Call_Gamma'] * df['Call_OI'] * underlying_price * underlying_price * 0.01
            df['Put_GEX'] = df['Put_Gamma'] * df['Put_OI'] * underlying_price * underlying_price * 0.01 * -1
            df['Net_GEX'] = df['Call_GEX'] + df['Put_GEX']
            df['Net_GEX_B'] = df['Net_GEX'] / 1e9
            
            # DEX calculations
            df['Call_DEX'] = df['Call_Delta'] * df['Call_OI'] * underlying_price * 0.01
            df['Put_DEX'] = df['Put_Delta'] * df['Put_OI'] * underlying_price * 0.01
            df['Net_DEX'] = df['Call_DEX'] + df['Put_DEX']
            df['Net_DEX_B'] = df['Net_DEX'] / 1e9
            
            # Hedging pressure
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
            
            print(f"✅ Calculation complete!")
            
            return df, underlying_price, "DhanHQ REST API v2", atm_info
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            print(f"❌ {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
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
