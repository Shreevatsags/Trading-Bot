# Trading-Bot
This Python-based trading bot is designed for Binance Futures Testnet (USDT-M). It allows users to place MARKET, LIMIT, and TWAP orders safely without risking real funds. The bot interacts with Binance’s official API and demonstrates automated order placement, logging, and error handling.

# Features

Order Types Supported

MARKET: Executes immediately at the current Testnet price.

LIMIT: Places an order at a specified price, pending execution.

TWAP (Time-Weighted Average Price): Splits a large order into multiple MARKET slices executed at regular intervals.

Server Time Synchronization

Automatically calculates the time offset between local machine and Binance server to prevent timestamp errors.

Input Validation

Validates quantity, price, slices, and intervals.

Ensures minimum notional requirement (≥ 100 USDT) is met automatically for orders.

Logging and Monitoring

Logs all API requests, responses, and errors.

Supports console output and rotating log files (trading_bot.log) for detailed tracking.

Error Handling and Retry Mechanism

Handles HTTP errors, invalid parameters, and internal server errors gracefully.

Optional retry logic for network issues or temporary server failures.

Command-Line Interface (CLI)

Accepts user input for symbol, order side, type, quantity, price, slices, and intervals.

Example commands:

python main.py --symbol BTCUSDT --side BUY --ordertype MARKET --quantity 0.001
python main.py --symbol BTCUSDT --side SELL --ordertype LIMIT --quantity 0.002 --price 30000
python main.py --symbol BTCUSDT --side BUY --ordertype TWAP --quantity 0.01 --slices 5 --interval 10


Testnet-Safe

Designed for Binance Testnet to experiment with automated trading strategies without real money.

# Installation

Clone the repository:

git clone https://github.com/Shreevatsags/Trading-Bot.git
cd Trading-Bot


Create a virtual environment and activate it:

python -m venv venv
# Windows
venv\Scripts\activate
# Linux / MacOS
source venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Create a .env file in the root directory:

API_KEY=your_testnet_api_key
API_SECRET=your_testnet_api_secret

# Usage
1️⃣ MARKET Order
python main.py --symbol BTCUSDT --side BUY --ordertype MARKET --quantity 0.001

2️⃣ LIMIT Order
python main.py --symbol BTCUSDT --side SELL --ordertype LIMIT --quantity 0.002 --price 30000

3️⃣ TWAP Order
python main.py --symbol BTCUSDT --side BUY --ordertype TWAP --quantity 0.01 --slices 5 --interval 10

# Example Console Output

2025-10-02 12:10:00,123 [INFO] Server time offset: 25 ms
2025-10-02 12:10:00,124 [INFO] Placing order: BTCUSDT BUY MARKET qty=0.001
2025-10-02 12:10:01,456 [INFO] Order response: {'orderId': 12345678, 'symbol': 'BTCUSDT', 'status': 'FILLED', 'side': 'BUY', 'type': 'MARKET', 'executedQty': '0.001', 'avgPrice': '29875.00'}
--- ORDER RESULT ---
{'orderId': 12345678, 'symbol': 'BTCUSDT', 'status': 'FILLED', 'side': 'BUY', 'type': 'MARKET', 'executedQty': '0.001', 'avgPrice': '29875.00'}

# Dependencies

Python 3.11+

requests

python-dotenv

argparse

logging

Notes

Works only on Binance Futures Testnet — safe for testing strategies without real funds.

Ensure quantity × price ≥ 100 USDT to meet Binance’s minimum notional requirements.

Logs are stored in trading_bot.log for review.
