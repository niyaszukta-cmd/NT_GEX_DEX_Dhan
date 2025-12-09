import pandas as pd
import numpy as np
from scipy.stats import norm
from datetime import datetime, timedelta

# Import DhanHQ
try:
    from dhanhq import DhanContext, dhanhq
    DHAN_NEW = True
except ImportError:
    from dhanhq import dhanhq
    DHAN_NEW = False

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
    """GEX/DEX Calculator with Demo Data Fallback"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
        self.use_demo = False
        
        if client_id and access_token:
            try:
                if DHAN_NEW:
                    dhan_context = DhanContext(client_id, access_token)
                    self.dhan = dhanhq(dhan_context)
                else:
                    self.dhan = dhanhq(client_id, access_token)
                print(f"✅ DhanHQ initialized")
            except Exception as e:
                print(f"⚠️ DhanHQ init warning: {e}")
    
    def generate_demo_data(self, symbol="NIFTY", underlying_price=None):
        """Generate realistic demo option chain data"""
        
        if underlying_price is None:
            defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
            underlying_price = defaults.get(symbol, 24500)
        
        print(f"📊 Generating demo data for {symbol} at ₹{underlying_price:,.0f}")
        
        # Generate strikes around current price
        strikes = []
        for i in range(-20, 21):
            strike = int((underlying_price + i * 100) / 100) * 100
            strikes.append(strike)
        
        option_data = []
        
        for strike in strikes:
            # Calculate distance from ATM
            distance = abs(strike - underlying_price)
            atm_factor = np.exp(-distance / 500)
            
            # Generate realistic OI (higher near ATM)
            call_oi = int(np.random.uniform(50000, 500000) * atm_factor)
            put_oi = int(np.random.uniform(50000, 500000) * atm_factor)
            
            # Generate realistic IV (higher OTM)
            base_iv = 15 + (distance / 100)
            call_iv = base_iv + np.random.uniform(-2, 2)
            put_iv = base_iv + np.random.uniform(-2, 2)
            
            # Generate realistic LTP
            days_to_expiry = 3
            T = days_to_expiry / 365.0
            
            if strike > underlying_price:
                call_ltp = max(0.5, (strike - underlying_price) * 0.3 + np.random.uniform(5, 50))
                put_ltp = max(0.5, np.random.uniform(1, 10))
            else:
                call_ltp = max(0.5, np.random.uniform(1, 10))
                put_ltp = max(0.5, (underlying_price - strike) * 0.3 + np.random.uniform(5, 50))
            
            # Generate volume
            call_volume = int(np.random.uniform(1000, 50000) * atm_factor)
            put_volume = int(np.random.uniform(1000, 50000) * atm_factor)
            
            option_data.append({
                'strike_price': strike,
                'option_type': 'CALL',
                'oi': call_oi,
                'iv': call_iv,
                'ltp': call_ltp,
                'volume': call_volume
            })
            
            option_data.append({
                'strike_price': strike,
                'option_type': 'PUT',
                'oi': put_oi,
                'iv': put_iv,
                'ltp': put_ltp,
                'volume': put_volume
            })
        
        # Generate expiry (next Thursday)
        today = datetime.now()
        days_ahead = (3 - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        next_thursday = today + timedelta(days=days_ahead)
        expiry = next_thursday.strftime('%Y-%m-%d')
        
        return option_data, [expiry], expiry
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price"""
        defaults = {"NIFTY": 24500, "BANKNIFTY": 52000, "FINNIFTY": 22500, "MIDCPNIFTY": 12000}
        return defaults.get(symbol, 24500)
    
    def get_option_chain_data(self, symbol="NIFTY", expiry_index=0):
        """Get option chain - with demo fallback"""
        
        if not self.dhan:
            print("⚠️ Using demo data (DhanHQ not available)")
            return self.generate_demo_data(symbol)
        
        try:
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            print(f"📅 Getting expiry list from DhanHQ...")
            
            # Try to get expiries
            try:
                expiry_response = self.dhan.expiry_list(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I"
                )
            except:
                try:
                    expiry_response = self.dhan.expiry_list(
                        under_security_id=security_id,
                        under_exchange_segment=3
                    )
                except:
                    expiry_response = self.dhan.expiry_list(under_security_id=security_id)
            
            # Parse expiries
            expiries = []
            if isinstance(expiry_response, dict):
                if 'data' in expiry_response:
                    data = expiry_response['data']
                    if isinstance(data, dict) and 'expiry_list' in data:
                        expiries = data['expiry_list']
                    elif isinstance(data, list):
                        expiries = data
            else:
                expiries = expiry_response if expiry_response else []
            
            if not expiries:
                print("⚠️ No expiries from API, using demo data")
                return self.generate_demo_data(symbol)
            
            # Select expiry
            if expiry_index >= len(expiries):
                expiry_index = 0
            selected_expiry = expiries[expiry_index]
            
            print(f"✅ Expiry: {selected_expiry}")
            print(f"📊 Getting option chain...")
            
            # Get option chain
            try:
                option_response = self.dhan.option_chain(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I",
                    expiry=selected_expiry
                )
            except:
                try:
                    option_response = self.dhan.option_chain(
                        under_security_id=security_id,
                        under_exchange_segment=3,
                        expiry=selected_expiry
                    )
                except:
                    option_response = self.dhan.option_chain(
                        under_security_id=security_id,
                        expiry=selected_expiry
                    )
            
            # Parse option data
            if isinstance(option_response, dict) and 'data' in option_response:
                option_data = option_response['data']
            else:
                option_data = option_response if option_response else []
            
            if not option_data:
                print("⚠️ No option data from API, using demo data")
                return self.generate_demo_data(symbol)
            
            print(f"✅ Got {len(option_data)} contracts from DhanHQ")
            return option_data, expiries, selected_expiry
            
        except Exception as e:
            print(f"⚠️ API error: {e}, using demo data")
            return self.generate_demo_data(symbol)
    
    def parse_option_data(self, option_data, underlying_price):
        """Parse option data"""
        
        strikes_dict = {}
        
        for opt in option_data:
            try:
                strike = float(opt.get('strike_price', opt.get('strikePrice', 0)))
                if strike == 0:
                    continue
                
                if strike not in strikes_dict:
                    strikes_dict[strike] = {
                        'Strike': strike,
                        'Call_OI': 0, 'Call_IV': 0.15, 'Call_LTP': 0, 'Call_Volume': 0,
                        'Put_OI': 0, 'Put_IV': 0.15, 'Put_LTP': 0, 'Put_Volume': 0
                    }
                
                opt_type = str(opt.get('option_type', opt.get('optionType', ''))).upper()
                
                if 'CALL' in opt_type or opt_type == 'CE':
                    strikes_dict[strike]['Call_OI'] = int(opt.get('oi', opt.get('open_interest', opt.get('openInterest', 0))))
                    iv = opt.get('iv', opt.get('implied_volatility', opt.get('impliedVolatility', 15)))
                    strikes_dict[strike]['Call_IV'] = float(iv) / 100 if iv and iv > 0 else 0.15
                    strikes_dict[strike]['Call_LTP'] = float(opt.get('ltp', opt.get('last_price', opt.get('lastPrice', 0))))
                    strikes_dict[strike]['Call_Volume'] = int(opt.get('volume', opt.get('totalTradedVolume', 0)))
                
                elif 'PUT' in opt_type or opt_type == 'PE':
                    strikes_dict[strike]['Put_OI'] = int(opt.get('oi', opt.get('open_interest', opt.get('openInterest', 0))))
                    iv = opt.get('iv', opt.get('implied_volatility', opt.get('impliedVolatility', 15)))
                    strikes_dict[strike]['Put_IV'] = float(iv) / 100 if iv and iv > 0 else 0.15
                    strikes_dict[strike]['Put_LTP'] = float(opt.get('ltp', opt.get('last_price', opt.get('lastPrice', 0))))
                    strikes_dict[strike]['Put_Volume'] = int(opt.get('volume', opt.get('totalTradedVolume', 0)))
            except:
                continue
        
        return list(strikes_dict.values())
    
    def fetch_and_calculate_gex_dex(self, symbol="NIFTY", strikes_range=12, expiry_index=0):
        """Main calculation with demo fallback"""
        
        print(f"🔄 Fetching {symbol}...")
        
        underlying_price = self.get_underlying_price(symbol)
        option_data, expiries, selected_expiry = self.get_option_chain_data(symbol, expiry_index)
        parsed_data = self.parse_option_data(option_data, underlying_price)
        
        if not parsed_data:
            raise Exception("No data")
        
        df = pd.DataFrame(parsed_data)
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in range")
        
        try:
            expiry_date = datetime.strptime(str(selected_expiry), '%Y-%m-%d')
        except:
            try:
                expiry_date = datetime.strptime(str(selected_expiry), '%d-%b-%Y')
            except:
                expiry_date = datetime.now() + timedelta(days=7)
        
        days_to_expiry = max((expiry_date - datetime.now()).days, 1)
        T = days_to_expiry / 365.0
        
        df['Call_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01)), axis=1)
        df['Put_Gamma'] = df.apply(lambda r: self.bs_calc.calculate_gamma(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01)), axis=1)
        df['Call_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Call_IV'], 0.01), 'call'), axis=1)
        df['Put_Delta'] = df.apply(lambda r: self.bs_calc.calculate_delta(underlying_price, r['Strike'], T, self.risk_free_rate, max(r['Put_IV'], 0.01), 'put'), axis=1)
        
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
        
        atm_strike = df.iloc[(df['Strike'] - underlying_price).abs().argsort()[0]]['Strike']
        atm_row = df[df['Strike'] == atm_strike].iloc[0]
        
        atm_info = {
            'atm_strike': int(atm_strike),
            'atm_straddle_premium': atm_row['Call_LTP'] + atm_row['Put_LTP']
        }
        
        data_source = "DhanHQ API" if self.dhan and not self.use_demo else "Demo Data"
        print(f"✅ Complete! Source: {data_source}")
        
        return df, underlying_price, data_source, atm_info

def calculate_dual_gex_dex_flow(df, futures_ltp):
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

def detect_gamma_flip_zones(df):
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
