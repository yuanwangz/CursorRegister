import time
from DrissionPage import Chromium

class TempMailOnline:

    TEMPMAILONLINE_URL = "https://tempmailonline.co"

    def __init__(self, browser: Chromium):
        self.tab = browser.new_tab(self.TEMPMAILONLINE_URL)

    def get_email_address(self):
        email_address = None
        self.tab.ele("xpath=/html/body/div[2]/main/main/section[1]/div/div/div/div/div[1]/div/button[1]", timeout=5).click()
        self.tab.wait(2)
        for _ in range(5):
            try:
                email = self.tab.ele("xpath=/html/body/div[2]/main/main/section[1]/div/div/div/div/div[1]/div/p", timeout=5).text
                if email != "" and email != "Please wait..":
                    email_address = email
                    break
            except Exception as e:
                print(e)
                pass

        if email_address is None:
            print("[tempmailonline.co] Fail to get email address")
            return None
        
        return email_address
        
    def wait_for_message(self, delay=5, timeout=90):
        start_time = time.time()
        email_click_flag = False
        while time.time() - start_time <= timeout:
            try:
                # self.tab.refresh()
                self.tab.wait(2)
                email_elements = self.tab.eles("css=section span.text-gray-700")
                for element in email_elements:
                    if "Cursor" in element.text:
                        print("email_from:", element.text)
                        self.tab.ele("xpath=//button[contains(text(),'详情')]", timeout=5).click()
                        email_click_flag = True
                        break
                if email_click_flag:
                    # self.tab.wait(2)
                    print("click email success")
                    
                    code_element = self.tab.ele("xpath=/html/body/div[2]/main/main/section[2]/div/div/div")
                    # print("code_element:", repr(code_element.text))
                    if code_element:
                        return {
                            "text": code_element.text
                        }
            except Exception as e:
                print(e)
                pass
            # print("not found code, wait 5 seconds..")
            self.tab.wait(delay)

        return None

if __name__ == "__main__":
    browser = Chromium()
    email_server = TempMailOnline(browser)
    email = email_server.get_email_address()
    print(email)
    message = email_server.wait_for_message().get("text", None)
    import re
    verify_code = re.search(r'(\d{6})', message).group(1)
    print(verify_code)
    
