"""
Project Setup Script
Creates necessary folders and verifies installation
"""

import os
import sys

def create_directories():
    """Create necessary project directories"""
    directories = ['results', 'logs']
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"✓ Created directory: {directory}/")
        else:
            print(f"✓ Directory exists: {directory}/")

def check_dependencies():
    """Check if required packages are installed"""
    required = {
        'MetaTrader5': 'MetaTrader5',
        'pandas': 'pandas',
        'numpy': 'numpy'
    }
    
    missing = []
    
    for package, import_name in required.items():
        try:
            __import__(import_name)
            print(f"✓ {package} installed")
        except ImportError:
            print(f"✗ {package} NOT installed")
            missing.append(package)
    
    return missing

def create_readme_files():
    """Create README files in subdirectories"""
    results_readme = """# Results Folder

Backtest results are saved here automatically.
This folder is ignored by Git.
"""
    
    logs_readme = """# Logs Folder

Trading logs can be saved here.
This folder is ignored by Git.
"""
    
    if not os.path.exists('results/README.md'):
        with open('results/README.md', 'w') as f:
            f.write(results_readme)
        print("✓ Created results/README.md")
    
    if not os.path.exists('logs/README.md'):
        with open('logs/README.md', 'w') as f:
            f.write(logs_readme)
        print("✓ Created logs/README.md")

def main():
    print("="*60)
    print("ICT FIBONACCI TRADING BOT - SETUP")
    print("="*60)
    print()
    
    # Create directories
    print("1. Creating project directories...")
    create_directories()
    print()
    
    # Create README files
    print("2. Creating documentation...")
    create_readme_files()
    print()
    
    # Check dependencies
    print("3. Checking dependencies...")
    missing = check_dependencies()
    print()
    
    if missing:
        print("⚠ Missing packages detected!")
        print()
        print("Install missing packages with:")
        print(f"  pip install {' '.join(missing)}")
        print()
    else:
        print("✓ All dependencies installed!")
        print()
    
    # Summary
    print("="*60)
    print("SETUP COMPLETE")
    print("="*60)
    print()
    print("Project structure:")
    print("  ├── config.py")
    print("  ├── indicators.py")
    print("  ├── fibonacci.py")
    print("  ├── trend_analysis.py")
    print("  ├── mt5_handler.py")
    print("  ├── risk_management.py")
    print("  ├── live_trading.py")
    print("  ├── backtest.py")
    print("  ├── main.py")
    print("  ├── find_symbol.py")
    print("  ├── results/          (backtest results)")
    print("  └── logs/             (trading logs)")
    print()
    print("Next steps:")
    print("  1. Run: python find_symbol.py  (find correct symbol name)")
    print("  2. Edit config.py with your settings")
    print("  3. Enable AutoTrading in MT5")
    print("  4. Run: python main.py --backtest  (test first)")
    print("  5. Run: python main.py --live  (when ready)")
    print()

if __name__ == '__main__':
    main()