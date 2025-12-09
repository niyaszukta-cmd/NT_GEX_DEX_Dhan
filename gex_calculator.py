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
    """GEX/DEX Calculator using DhanHQ Rolling Options API"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = str(client_id).strip() if client_id else None
        self.access_token = str(access_token).strip() if access_token else None
        self.base_url = "https://api.dhan.co/v2"
        
        if self.client_id and self.access_token:
            print(f"✅ DhanHQ Rolling Options API configured")
    
    def get_rolling_option_data(self, security_id, strike_offset, option_type, days_back=1):
        """Fetch rolling options data for a specific strike"""
        
        url = f"{self.base_url}/charts/rollingoption"
        
        headers = {
            "access-token": self.access_token,
            "client-id": self.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Get date range (last trading day)
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)
        
        payload = {
            "exchangeSegment": "NSE_FNO",
            "interval": "1",
            "securityId": security_id,
            "instrument": "OPTIDX",
            "expiryFlag": "WEEK",
            "expiryCode": 0,
            "strike": strike_offset,
            "drvOptionType": option_type,
            "requiredData": ["open", "high", "low", "close", "volume", "oi", "iv", "strike", "spot"],
            "fromDate": from_date.strftime('%Y-%m-%d'),
            "toDate": to_date.strftime('%Y-%m-%d')
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except:
            return None
    
    def fetch_multiple_strikes(self, security_id, strikes_range=10):
        """Fetch data for multiple strikes around ATM"""
        
        all_strikes_data = []
        
        print(f"📊 Fetching rolling options data...")
        
        # Fetch for multiple strikes
        strike_offsets = []
        strike_offsets.append("ATM")
        for i in range(1, strikes_range + 1):
            strike_offsets.append(f"ATM+{i}")
            strike_offsets.append(f"ATM-{i}")
        
        underlying_price = None
        
        for offset in strike_offsets:
            # Fetch CALL data
            call_data = self.get_rolling_option_data(security_id, offset, "CALL", days_back=2)
            
            # Fetch PUT data
            put_data = self.get_rolling_option_data(security_id, offset, "PUT", days_back=2)
            
            if call_data and 'data' in call_data and call_data['data'].get('ce'):
                ce = call_data['data']['ce']
                
                # Get latest values (last timestamp)
                if ce.get('strike') and len(ce['strike']) > 0:
                    strike = ce['strike'][-1]
                    
                    # Get spot price (underlying)
                    if ce.get('spot') and len(ce['spot']) > 0 and underlying_price is None:
                        underlying_price = ce['spot'][-1]
                    
                    call_oi = ce['oi'][-1] if ce.get('oi') and len(ce['oi']) > 0 else 0
                    call_iv = ce['iv'][-1] if ce.get('iv') and len(ce['iv']) > 0 else 15
                    call_ltp = ce['close'][-1] if ce.get('close') and len(ce['close']) > 0 else 0
                    call_volume = ce['volume'][-1] if ce.get('volume') and len(ce['volume']) > 0 else 0
                    
                    # Get PUT data
                    put_oi = 0
                    put_iv = 15
                    put_ltp = 0
                    put_volume = 0
                    
                    if put_data and 'data' in put_data and put_data['data'].get('ce'):
                        pe = put_data['data']['ce']
                        put_oi = pe['oi'][-1] if pe.get('oi') and len(pe['oi']) > 0 else 0
                        put_iv = pe['iv'][-1] if pe.get('iv') and len(pe['iv']) > 0 else 15
                        put_ltp = pe['close'][-1] if pe.get('close') and len(pe['close']) > 0 else 0
                        put_volume = pe['volume'][-1] if pe.get('volume') and len(pe['volume']) > 0 else 0
                    
                    all_strikes_data.append({
                        'Strike': float(strike),
                        'Call_OI': int(call_oi),
                        'Call_IV': float(call_iv) / 100 if call_iv > 1 else float(call_iv),
                        'Call_LTP': float(call_ltp),
                        'Call_Volume': int(call_volume),
                        'Put_OI': int(put_oi),
                        'Put_IV': float(put_iv) / 100 if put_iv > 1 else float(put_iv),
                        'Put_LTP': float(put_ltp),
                        'Put_Volume': int(put_volume)
                    })
        
        return all_strikes_data, underlying_price
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation using Rolling Options API"""
        
        try:
            print(f"🔄 Fetching {symbol} using Rolling Options API...")
            
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            # Fetch data for multiple strikes
            parsed_data, underlying_price = self.fetch_multiple_strikes(security_id, strikes_range)
            
            if not parsed_data or not underlying_price:
                raise Exception("No data from Rolling Options API. Market may be closed or Data APIs not enabled.")
            
            print(f"✅ Got {len(parsed_data)} strikes")
            
            # Create DataFrame
            df = pd.DataFrame(parsed_data)
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['Strike']).sort_values('Strike').reset_index(drop=True)
            
            print(f"💰 Underlying: ₹{underlying_price:,.2f}")
            
            # Calculate time to expiry (assume weekly expiry - next Thursday)
            today = datetime.now()
            days_ahead = (3 - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            expiry_date = today + timedelta(days=days_ahead)
            days_to_expiry = max((expiry_date - today).days, 1)
            T = days_to_expiry / 365.0
            
            # Calculate Greeks
            df['Call_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)), axis=1)
            df['Put_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)), axis=1)
            df['Call_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'), axis=1)
            df['Put_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'), axis=1)
            
            # GEX/DEX calculations
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
            
            print(f"✅ Calculation complete!")
            
            return df, underlying_price, "DhanHQ Rolling Options API", atm_info
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error: {error_msg}")
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
