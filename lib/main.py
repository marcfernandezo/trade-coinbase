import os
import time
from dotenv import load_dotenv
from coinbase.rest import RESTClient
import uuid

MIN_PRICE_CHANGE_24_HRS = 3  # Minimum 24-hour price change percentage to consider buying
TARGET_PERCENTAGE_PROFIT = 0.06  # Target profit percentage to set sell limit orders

def safe_float_convert(value):
    """Safely convert a value to float. Return None if conversion fails."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return None

def main():
    load_dotenv()  # Load environment variables from .env file
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    # Initialize Coinbase REST client with API credentials
    rest_client = RESTClient(api_key=api_key, api_secret=api_secret, verbose=False)

    # Get the USDC wallet ID from environment variables
    wallet_id_usdc = str(os.getenv("USDC_WALLET_ID"))
    
    # Retrieve all currently open sell orders
    active_orders = rest_client.list_orders(order_side="SELL", order_status=["OPEN"])
    
    # Extract product IDs of assets currently being sold
    products_being_selled = []
    for order in active_orders['orders']:
        products_being_selled.append(order['product_id'])
    
    # Fetch all spot products and filter those with a 24h price increase above threshold and not already being sold
    to_buy = []
    spot_products = rest_client.get_products(product_type="SPOT")
    for spot_product in spot_products["products"]:
        price_change_raw = getattr(spot_product, 'price_percentage_change_24h', None)
        price_change = safe_float_convert(price_change_raw)
        if price_change is None:
            continue  # Skip products without a valid price change
        
        product_id = str(spot_product.product_id)
        # Consider only products trading against USDC with significant positive price change and not currently selling
        if product_id.endswith('USDC') and price_change > MIN_PRICE_CHANGE_24_HRS and product_id not in products_being_selled:
            to_buy.append(spot_product)
    
    # Get total available USDC balance
    total_balance = float(rest_client.get_account(wallet_id_usdc)['account']['available_balance']['value'])
    valid_amount = False

    number_of_products_to_buy = len(to_buy)
    if number_of_products_to_buy == 0:
        print("No products meet the buying criteria.")
        return  # Exit if no products to buy

    # Calculate how much USDC to allocate to each product, leaving a 2% buffer
    to_spend_on_each_product = (total_balance / number_of_products_to_buy) * 0.98
    print(f"Total balance: {total_balance}, products to buy: {number_of_products_to_buy}, spending per product: {to_spend_on_each_product}")
    
    # Ensure the amount allocated to each product is greater than 1 USDC; reduce product count if not
    while not valid_amount and number_of_products_to_buy > 0:
        if to_spend_on_each_product > 1:
            valid_amount = True
        else:
            number_of_products_to_buy -= 1
        if number_of_products_to_buy == 0:
            print("Insufficient balance to distribute among products.")
            return
        to_spend_on_each_product = (total_balance / number_of_products_to_buy)

    # Place buy orders for the selected products
    for product in to_buy[:number_of_products_to_buy]:
        # Refresh USDC balance before each purchase
        usdc_balance = float(rest_client.get_account(wallet_id_usdc)['account']['available_balance']['value'])
        
        # Gather product details needed for order
        product_id = product.product_id
        price = float(product.price)
        quote_increment = float(product.quote_increment)
        quote_min_size = float(product.quote_min_size)
        order_id = str(uuid.uuid4())
        
        # Calculate purchase size rounded to 2 decimals, adding increment to avoid precision issues
        quote_size = round((to_spend_on_each_product + quote_increment), 2)
        
        # Skip if current USDC balance is insufficient for intended purchase size
        if quote_size > usdc_balance:
            print(f'Skipping product: {product_id}. Quote size {quote_size} exceeds balance {usdc_balance}')
            continue
        
        # Place market buy order with a unique client order ID
        rest_client.market_order_buy(client_order_id=order_id, product_id=product_id, quote_size=str(quote_size))
        time.sleep(5)  # Wait for order execution
        
        # Place a sell limit order to take profit based on target percentage
        sell_limit_product(rest_client=rest_client, product_id=product_id, buy_price=price)
        time.sleep(2)

def sell_limit_product(rest_client: RESTClient, product_id: str, buy_price: float):
    """Place a limit sell order with Good-Till-Canceled (GTC) based on the target profit percentage."""
    client_order_id = str(uuid.uuid4())
    base_currency = product_id.split("-")[0]
    
    # Retrieve detailed product info
    product = rest_client.get_product(product_id=product_id)
    
    min_base_size = product['base_min_size']
    
    # Find the wallet for the base currency to determine available asset quantity
    wallets = rest_client.get_accounts()
    product_wallet = None
    for wallet in wallets['accounts']:
        if wallet['currency'] == base_currency:
            product_wallet = wallet
            break

    if product_wallet is None:
        print(f"No wallet found for currency: {base_currency}")
        return

    quantity_of_asset = round(float(product_wallet['available_balance']['value']), 4)
   
    # Calculate limit sell price to achieve target profit
    limit_price = round(buy_price * (1 + TARGET_PERCENTAGE_PROFIT), 4)
    
    # Check if available asset quantity meets minimum order size
    if quantity_of_asset < float(min_base_size):
        print(f"Insufficient asset quantity to place sell order. Available: {quantity_of_asset}, Minimum required: {min_base_size}")
        return
    
    # Place a limit sell order with GTC time-in-force
    rest_client.limit_order_gtc_sell(
        client_order_id=client_order_id,
        product_id=product_id,
        base_size=str(quantity_of_asset),
        limit_price=str(limit_price)
    )

if __name__ == "__main__":
    main()
