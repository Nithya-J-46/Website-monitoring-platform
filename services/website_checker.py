import requests

def check_website(url):
    try:
        response = requests.get(
            url,
            timeout=8,
            allow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/html"
            }
        )

        print("Status Code:", response.status_code)

        # Professional monitoring rule
        if response.status_code < 500:
            return "UP"
        else:
            return "DOWN"

    except requests.exceptions.RequestException:
        return "DOWN"
