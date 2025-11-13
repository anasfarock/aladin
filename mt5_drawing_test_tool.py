"""
MT5 Chart Drawing Diagnostic Tool
Tests if chart objects can be drawn on MT5
Run this to diagnose chart drawing issues
"""

import MetaTrader5 as mt5
from datetime import datetime
import time

def test_mt5_chart_drawing(symbol="AUDUSD"):
    """Test if we can draw on MT5 charts"""
    
    print("="*60)
    print("MT5 CHART DRAWING DIAGNOSTIC")
    print("="*60)
    
    # Initialize MT5
    print("Initializing MT5...")
    initialized = mt5.initialize()
    print(f"MT5 initialization: {initialized}")
    
    # Check connection
    terminal_info = mt5.terminal_info()
    if not terminal_info:
        print("❌ MT5 terminal not connected!")
        print("\nTroubleshooting:")
        print("  1. Make sure MetaTrader 5 is OPEN and running")
        print("  2. Your MT5 must be logged in (showing account)")
        print("  3. Check if MT5 terminal shows 'Connected' status")
        print("  4. Try: mt5.shutdown() and restart the script")
        
        # Try to get more info
        try:
            last_error = mt5.last_error()
            print(f"\nLast MT5 error: {last_error}")
        except:
            pass
        
        mt5.shutdown()
        return False
    
    print("✓ MT5 terminal connected")
    try:
        # Get account info
        account_info = mt5.account_info()
        if account_info:
            print(f"  Account: {account_info.login}")
            print(f"  Server: {account_info.server}")
        else:
            print("  (Could not get account info)")
    except Exception as e:
        print(f"  Account info unavailable: {e}")
    
    # Check symbol
    print(f"\nTesting symbol: {symbol}")
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ Symbol {symbol} not found!")
        print("Available symbols must be enabled in MT5 Market Watch")
        return False
    
    print(f"✓ Symbol {symbol} found")
    print(f"  Bid: {symbol_info.bid}")
    print(f"  Ask: {symbol_info.ask}")
    
    # Get current chart
    print(f"\nGetting chart for {symbol}...")
    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 1)
        if rates is None or len(rates) == 0:
            print("⚠️  No rates available for chart")
            return False
        
        current_price = rates[0]['close']
        current_time = datetime.fromtimestamp(rates[0]['time'])
        print(f"✓ Latest M15 candle: {current_price} at {current_time}")
    except Exception as e:
        print(f"❌ Error getting rates: {e}")
        return False
    
    # Test drawing a simple horizontal line
    print(f"\nTesting horizontal line draw...")
    try:
        test_obj_name = f"TEST_HLINE_{datetime.now().strftime('%H%M%S%f')}"
        test_price = current_price + 0.001
        
        # Try with CHART_TYPE_BID
        result = mt5.chart_object_create(
            symbol,
            test_obj_name,
            mt5.OBJ_HLINE,
            mt5.CHART_TYPE_BID,
            current_time,
            test_price
        )
        
        if result:
            print(f"✓ Successfully created object: {test_obj_name}")
            
            # Try to set color
            try:
                mt5.chart_object_set_integer(
                    symbol,
                    test_obj_name,
                    mt5.OBJPROP_COLOR,
                    0xFF0000  # Red
                )
                print("✓ Successfully set object color")
            except Exception as e:
                print(f"⚠️  Could not set color: {e}")
            
            # Refresh chart
            try:
                mt5.chart_redraw(symbol)
                print("✓ Chart refreshed with mt5.chart_redraw()")
            except Exception as e:
                print(f"⚠️  Could not refresh chart: {e}")
            
            # List objects on chart
            print(f"\nObjects on chart:")
            try:
                objs = mt5.chart_get_objects(symbol, 0)
                if objs:
                    print(f"  Found {len(objs)} objects")
                    for obj in objs:
                        print(f"    - {obj}")
                else:
                    print("  No objects found on chart")
            except Exception as e:
                print(f"⚠️  Could not list objects: {e}")
            
            # Clean up
            time.sleep(2)
            try:
                mt5.chart_object_delete(symbol, mt5.CHART_TYPE_BID, test_obj_name)
                print(f"\n✓ Test object deleted")
            except Exception as e:
                print(f"⚠️  Could not delete test object: {e}")
            
            return True
        else:
            print(f"❌ Failed to create object")
            
            # Try alternate chart type
            print(f"\nTrying CHART_TYPE_STANDARD...")
            result = mt5.chart_object_create(
                symbol,
                test_obj_name,
                mt5.OBJ_HLINE,
                mt5.CHART_TYPE_STANDARD,
                current_time,
                test_price
            )
            
            if result:
                print(f"✓ Success with CHART_TYPE_STANDARD!")
                mt5.chart_object_delete(symbol, mt5.CHART_TYPE_STANDARD, test_obj_name)
                return True
            else:
                print(f"❌ Failed with CHART_TYPE_STANDARD too")
                return False
    
    except Exception as e:
        print(f"❌ Error during draw test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    symbol = input("Enter symbol (default AUDUSD): ").strip() or "AUDUSD"
    success = test_mt5_chart_drawing(symbol)
    
    print("\n" + "="*60)
    if success:
        print("✓ Chart drawing test PASSED")
        print("\nYour MT5 setup should support chart drawing.")
        print("If lines still don't appear:")
        print("  1. Check that the chart window is visible")
        print("  2. Make sure chart zoom level shows the price area")
        print("  3. Check MT5 Objects menu to see if objects exist")
    else:
        print("❌ Chart drawing test FAILED")
        print("\nRequired:")
        print("  1. MetaTrader 5 must be OPEN and RUNNING")
        print("  2. Must be LOGGED IN to your account")
        print("  3. Symbol must be added to Market Watch")
        print("  4. A chart for the symbol should be open")
    print("="*60)
    
    # Cleanup
    try:
        mt5.shutdown()
    except:
        pass