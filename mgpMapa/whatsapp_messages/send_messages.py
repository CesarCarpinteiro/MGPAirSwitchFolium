import requests
import json

url = "https://graph.facebook.com/v22.0/523539340842961/messages"

headers = {
    "Authorization": "Bearer EAAMQSMOnEykBRdd5EFQ5HFCrncxKwKrEXO6ubSXuOoXIX1OXtgopkTz0sTVEVCpyF198I0O5lO1Mia0B4pm811tOYuT0ZCWw83bV7YI6eUfQcyv9S3lvysRvtUXw2H1GygRMncZAovzEE6rhO3XeY1YZCgm3bPZC5QjmuZC2S3ZC8sBZC8AOi540BEAWZAxX0CrvDpguoQUjkW7LmQytLEHALSV00OxZASDlDsfIn9XpjBAkMGtSEr832OtUv7Phs4cmBptn5asBD3srAgcBt2wjF4YU3",
    "Content-Type": "application/json"
}

payload = {
    "messaging_product": "test",
    "to": "351967592167",
    "type": "template",
    "template": {
        "name": "hello_world",
        "language": { "code": "en_US" }
    }
}

response = requests.post(url, headers=headers, json=payload)

print("Status:", response.status_code)
print("Response:", response.text)