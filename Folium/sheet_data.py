import requests
import pandas as pd

# Replace with your API key and Spreadsheet ID
API_KEY = 'AIzaSyCqcu1jOFY61rRhqA7bfRVF2jGQfN1e5So'
SPREADSHEET_ID = '1nZ-PFt1k25BJoYSKUUP8VTHnD1ZwGAAH7yK6QShY3LA'
RANGE_NAME = 'Sheet1'

# URL for the Google Sheets API
url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{RANGE_NAME}?key={API_KEY}"

# Fetch the data
response = requests.get(url)
data = response.json()

if 'values' in data:
    # Use the first row as column headers
    values = data['values']
    df = pd.DataFrame(values[1:], columns=values[0])  # Skip first row for data, use it for headers

    # Save DataFrame to CSV
    df.to_csv('google_sheet_data.csv', index=False)
    print("Data saved to google_sheet_data.csv")
else:
    print('No data found or an error occurred:', data)