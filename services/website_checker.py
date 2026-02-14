import requests

def check_website(url):
    try:
        response = requests.get(
            url,
            timeout=8,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        if 200 <= response.status_code < 400:
            return "UP"
        else:
            return "DOWN"

    except:
        return "DOWN"
