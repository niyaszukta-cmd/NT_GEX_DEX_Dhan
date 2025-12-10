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
    """GEX/DEX Calculator with DhanHQ Consent Flow"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = str(client_id).strip() if client_id else None
        self.access_token = str(access_token).strip() if access_token else None
        self.base_url = "https://api.dhan.co/v2"
        
        print(f"✅ Calculator initialized | Client: {self.client_id}")
    
    def generate_realistic_demo_data(self, symbol="NIFTY", underlying_price=None):
        """Generate realistic demo data"""
        
        if underlying_price is None:
            defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
            underlying_price = defaults.get(symbol, 24500)
        
        print(f"📊 Generating demo data for {symbol}")
        
        strikes = []
        for i in range(-18, 19):
            strike = int((underlying_price + i * 100) / 100) * 100
            strikes.append(strike)
        
        option_data = []
        
        for strike in strikes:
            distance = abs(strike - underlying_price)
            atm_factor = np.exp(-distance / 600)
            
            if strike < underlying_price:
                call_oi = int(np.random.uniform(30000, 300000) * atm_factor * 0.7)
                put_oi = int(np.random.uniform(50000, 600000) * atm_factor * 1.3)
            elif strike > underlying_price:
                call_oi = int(np.random.uniform(50000, 600000) * atm_factor * 1.3)
                put_oi = int(np.random.uniform(30000, 300000) * atm_factor * 0.7)
            else:
                call_oi = int(np.random.uniform(100000, 800000))
                put_oi = int(np.random.uniform(100000, 800000))
            
            base_iv = 15 + (distance / 150)
            call_iv = base_iv + np.random.uniform(-1, 2)
            put_iv = base_iv + np.random.uniform(0, 3)
            
            if strike >= underlying_price:
                intrinsic_call = max(0, underlying_price - strike)
                call_ltp = intrinsic_call + np.random.uniform(5, 80) * atm_factor
                put_ltp = max(0.5, (strike - underlying_price) * 0.4 + np.random.uniform(2, 15))
            else:
                call_ltp = max(0.5, np.random.uniform(2, 15))
                intrinsic_put = max(0, strike - underlying_price)
                put_ltp = intrinsic_put + np.random.uniform(5, 80) * atm_factor
            
            call_volume = int(np.random.uniform(5000, 100000) * atm_factor)
            put_volume = int(np.random.uniform(5000, 100000) * atm_factor)
            
            option_data.append({
                'Strike': strike,
                'Call_OI': call_oi,
                'Call_IV': call_iv / 100,
                'Call_LTP': round(call_ltp, 2),
                'Call_Volume': call_volume,
                'Put_OI': put_oi,
                'Put_IV': put_iv / 100,
                'Put_LTP': round(put_ltp, 2),
                'Put_Volume': put_volume
            })
        
        today = datetime.now()
        days_ahead = (3 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_thursday = today + timedelta(days=days_ahead)
        expiry = next_thursday.strftime('%Y-%m-%d')
        
        return option_data, [expiry], expiry, underlying_price
    
    def get_option_chain_dhanhq(self, symbol, expiry_index):
        """Try to get data from DhanHQ API"""
        
        if not self.client_id or not self.access_token:
            return None
        
        try:
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            # Get expiry list
            url = f"{self.base_url}/optionchain/expirylist"
            headers = {
                "access-token": self.access_token,
                "client-id": self.client_id,
                "Content-Type": "application/json"
            }
            payload = {"UnderlyingScrip": security_id, "UnderlyingSeg": "IDX_I"}
            
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success' and 'data' in data:
                    expiries = data['data']
                    
                    if expiries and len(expiries) > expiry_index:
                        selected_expiry = expiries[expiry_index]
                        
                        # Get option chain
                        url2 = f"{self.base_url}/optionchain"
                        payload2 = {
                            "UnderlyingScrip": security_id,
                            "UnderlyingSeg": "IDX_I",
                            "Expiry": selected_expiry
                        }
                        
                        response2 = requests.post(url2, json=payload2, headers=headers, timeout=5)
                        
                        if response2.status_code == 200:
                            data2 = response2.json()
                            if 'data' in data2:
                                print(f"✅ DhanHQ API data retrieved")
                                # Parse DhanHQ response
                                return self.parse_dhanhq_response(data2['data'], expiries, selected_expiry)
            
            return None
            
        except:
            return None
    
    def parse_dhanhq_response(self, option_chain_data, expiries, selected_expiry):
        """Parse DhanHQ option chain"""
        
        option_data = []
        underlying_ltp = option_chain_data.get('last_price', 24500)
        oc = option_chain_data.get('oc', {})
        
        for strike_str, strike_data in oc.items():
            try:
                strike = float(strike_str)
                
                ce_data = strike_data.get('ce', {})
                pe_data = strike_data.get('pe', {})
                
                option_data.append({
                    'Strike': strike,
                    'Call_OI': int(ce_data.get('oi', 0)),
                    'Call_IV': float(ce_data.get('implied_volatility', 15)) / 100 if ce_data.get('implied_volatility', 15) > 1 else 0.15,
                    'Call_LTP': float(ce_data.get('last_price', 0)),
                    'Call_Volume': int(ce_data.get('volume', 0)),
                    'Put_OI': int(pe_data.get('oi', 0)),
                    'Put_IV': float(pe_data.get('implied_volatility', 15)) / 100 if pe_data.get('implied_volatility', 15) > 1 else 0.15,
                    'Put_LTP': float(pe_data.get('last_price', 0)),
                    'Put_Volume': int(pe_data.get('volume', 0))
                })
            except:
                continue
        
        return option_data, expiries, selected_expiry, underlying_ltp
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation"""
        
        print(f"🔄 Fetching {symbol}...")
        
        # Try DhanHQ
        dhanhq_result = self.get_option_chain_dhanhq(symbol, expiry_index)
        
        if dhanhq_result:
            option_data_list, expiries, selected_expiry, underlying_price = dhanhq_result
            data_source = "DhanHQ Live API"
            print(f"✅ Using live DhanHQ data")
        else:
            option_data_list, expiries, selected_expiry, underlying_price = self.generate_realistic_demo_data(symbol)
            data_source = "Demo Data"
            print(f"📊 Using demo data")
        
        df = pd.DataFrame(option_data_list)
        
        # Filter strikes
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in range")
        
        # Time to expiry
        try:
            expiry_date = datetime.strptime(selected_expiry, '%Y-%m-%d')
        except:
            expiry_date = datetime.now() + timedelta(days=7)
        
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        # Greeks
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
        
        # ATM
        atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
        atm_row = df[df['Strike'] == atm_strike].iloc[0]
        
        atm_info = {
            'atm_strike': int(atm_strike),
            'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
        }
        
        return df, underlying_price, data_source, atm_info

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
