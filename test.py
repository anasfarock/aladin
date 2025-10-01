import MetaTrader5 as mt5

mt5.initialize()

# Check permissions
terminal = mt5.terminal_info()
account = mt5.account_info()

print(f"Terminal trade allowed: {terminal.trade_allowed}")
print(f"Account trade allowed: {account.trade_allowed}")
print(f"Expert trading allowed: {account.trade_expert}")

mt5.shutdown()