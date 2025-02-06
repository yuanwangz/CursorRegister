import requests

class CustomAPIManager:
    
    def __init__(self, url):
        self.api_url = url
        self.headers = {
            "Content-Type": "application/json",
        }
    
    def upload_tokens(self, tokens):
        data = {"tokens": tokens}
        response = requests.post(self.api_url, headers=self.headers, json=data)
        return response
