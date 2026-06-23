import requests


proxies = {
    "http": None,
    "https": None,
}

res = requests.get(api_url, timeout=30, proxies=proxies)

print("status:", res.status_code)
print("text:", res.text)