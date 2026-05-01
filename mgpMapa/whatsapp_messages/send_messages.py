import requests

url = "https://graph.facebook.com/v22.0/523539340842961/messages"

headers = {
    "Authorization": "Bearer EAAMQSMOnEykBRfN4eBE8vE1BCqR7h2XZBNsjIcK4Xw4yJ6WbznZCtQpXZBKwltRGAItX8LHM7dEpI2MoUiGJi9icpk0VGHeFMLstQD13KYyXcc2VPZAlpm3aHnCO44Yzk6HB7mMDQt7ZBo4PG6DBeASqV7tMm28nzlH2oBnCCzZCthWeGwI0bBK7kuN0IJNCCIDIz03EkrbU11TsGmDPJRnUHrpEE2RMh6wBZA2P8Rc5rZCL8OeAxgQFbyd79A8oyjgNRLC6I9WbvaMoZAmrwPcCg7OdU",
    "Content-Type": "application/json"
}

payload = {
    "messaging_product": "whatsapp",  # ← fix here
    "to": "351967592167",
    "type": "text",
    "text": {
        "body": "Olá! Esta é uma mensagem de teste."
    }
}

response = requests.post(url, headers=headers, json=payload)

print("Status:", response.status_code)
print("Response:", response.text)