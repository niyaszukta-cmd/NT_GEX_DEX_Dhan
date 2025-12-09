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
    """GEX/DEX Calculator using DhanHQ API"""
    
    def __init__(self, client_id=None, access_token=None, risk_free_rate=0.07):
        self.risk_free_rate = risk_free_rate
        self.bs_calc = BlackScholesCalculator()
        self.client_id = client_id
        self.access_token = access_token
        self.dhan = None
        
        if client_id and access_token:
            try:
                if DHAN_NEW:
                    dhan_context = DhanContext(client_id, access_token)
                    self.dhan = dhanhq(dhan_context)
                else:
                    self.dhan = dhanhq(client_id, access_token)
                
                print(f"✅ DhanHQ initialized")
            except Exception as e:
                print(f"❌ DhanHQ init failed: {e}")
                raise Exception(f"Failed to initialize: {str(e)}")
    
    def get_underlying_price(self, symbol="NIFTY"):
        """Get index price - use defaults"""
        defaults = {
            "NIFTY": 24500,
            "BANKNIFTY": 52000,
            "FINNIFTY": 22500,
            "MIDCPNIFTY": 12000
        }
        return defaults.get(symbol, 24500)
    
    def get_option_chain_data(self, symbol="NIFTY", expiry_index=0):
        """Get option chain from DhanHQ"""
        
        if not self.dhan:
            raise Exception("DhanHQ not initialized")
        
        try:
            security_map = {"NIFTY": 13, "BANKNIFTY": 25, "FINNIFTY": 27, "MIDCPNIFTY": 29}
            security_id = security_map.get(symbol, 13)
            
            print(f"📅 Getting expiry list...")
            
            # Get expiry list - try different methods
            try:
                # Method 1: Using string "IDX_I"
                expiry_response = self.dhan.expiry_list(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I"
                )
            except:
                try:
                    # Method 2: Using integer code
                    expiry_response = self.dhan.expiry_list(
                        under_security_id=security_id,
                        under_exchange_segment=3  # IDX_I = 3
                    )
                except:
                    # Method 3: Without exchange segment
                    expiry_response = self.dhan.expiry_list(
                        under_security_id=security_id
                    )
            
            # Parse response
            if not expiry_response:
                raise Exception("Empty expiry response")
            
            # Handle different response formats
            if isinstance(expiry_response, dict):
                if 'data' in expiry_response:
                    data = expiry_response['data']
                    if isinstance(data, dict) and 'expiry_list' in data:
                        expiries = data['expiry_list']
                    elif isinstance(data, list):
                        expiries = data
                    else:
                        expiries = []
                else:
                    expiries = []
            else:
                expiries = expiry_response
            
            if not expiries:
                raise Exception("No expiries found")
            
            # Select expiry
            if expiry_index >= len(expiries):
                expiry_index = 0
            
            selected_expiry = expiries[expiry_index]
            print(f"✅ Expiry: {selected_expiry}")
            
            # Get option chain - try different methods
            print(f"📊 Getting option chain...")
            
            try:
                # Method 1: Using string
                option_response = self.dhan.option_chain(
                    under_security_id=security_id,
                    under_exchange_segment="IDX_I",
                    expiry=selected_expiry
                )
            except:
                try:
                    # Method 2: Using integer
                    option_response = self.dhan.option_chain(
                        under_security_id=security_id,
                        under_exchange_segment=3,
                        expiry=selected_expiry
                    )
                except:
                    # Method 3: Without exchange segment
                    option_response = self.dhan.option_chain(
                        under_security_id=security_id,
                        expiry=selected_expiry
                    )
            
            # Parse option data
            if isinstance(option_response, dict) and 'data' in option_response:
                option_data = option_response['data']
            else:
                option_data = option_response
            
            if not option_data:
                raise Exception("No option data")
            
            print(f"✅ Got {len(option_data)} contracts")
            
            return option_data, expiries, selected_expiry
            
        except Exception as e:
            raise Exception(f"DhanHQ API Error: {str(e)}")
    
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
        """Main calculation"""
        
        print(f"🔄 Fetching {symbol}...")
        
        underlying_price = self.get_underlying_price(symbol)
        print(f"💰 Price: ₹{underlying_price:,.0f}")
        
        option_data, expiries, selected_expiry = self.get_option_chain_data(symbol, expiry_index)
        parsed_data = self.parse_option_data(option_data, underlying_price)
        
        if not parsed_data:
            raise Exception("No data after parsing")
        
        df = pd.DataFrame(parsed_data)
        
        df = df[
            (df['Strike'] >= underlying_price - strikes_range * 100) &
            (df['Strike'] <= underlying_price + strikes_range * 100)
        ].copy()
        
        if len(df) == 0:
            raise Exception("No strikes in range")
        
        print(f"✅ Processing {len(df)} strikes")
        
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
        
        print(f"✅ Complete!")
        
        return df, underlying_price, "DhanHQ API", atm_info

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
