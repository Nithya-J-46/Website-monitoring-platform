import requests
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check_website(url):
    try:
        response = requests.get(url, timeout=10, verify=False)
        if response.status_code == 200:
            return "UP"
        return "DOWN"
    except Exception:
        return "DOWN"
