import requests
from datetime import datetime
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import socket

def check_website(host, port=80):
    try:
        socket.create_connection((host, port), timeout=5)
        return "UP"
    except:
        return "DOWN"

