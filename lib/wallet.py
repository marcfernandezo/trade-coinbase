import os
from dotenv import load_dotenv
from coinbase.rest import RESTClient
import pprint

def main():
    load_dotenv()  # Load environment variables from .env file

    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    # Check if API credentials are set
    if not api_key or not api_secret:
        print("ERROR: API_KEY or API_SECRET not defined in .env")
        return

    # Initialize Coinbase REST client with API credentials
    client = RESTClient(api_key=api_key, api_secret=api_secret)

    try:
        # Retrieve all accounts associated with the API key
        accounts = client.get_accounts()
    except Exception as e:
        print(f"Error fetching accounts: {e}")
        return

    # Print the full response from the get_accounts() call
    print("Full response from get_accounts():")
    pprint.pprint(accounts)

    # Print a summarized list of each currency and its corresponding UUID
    print("\nSummary list of currencies and their UUIDs:")
    for account in accounts.accounts:
        currency = getattr(account, 'currency', 'N/A')
        uuid = getattr(account, 'uuid', 'N/A')
        print(f"Currency: {currency} | UUID: {uuid}")

if __name__ == "__main__":
    main()
