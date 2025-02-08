import time
from DrissionPage import Chromium

class EtempMail:

    ETEMPMAIL_URL = "https://etempmail.com"

    def __init__(self, browser: Chromium):
        self.tab = browser.new_tab(self.ETEMPMAIL_URL)

    def get_email_address(self):
        email_address = None
        self.tab.ele("xpath=//button[@id='deleteEmailAddress']", timeout=5).click()

        for _ in range(5):
            try:
                self.tab.refresh()
                self.tab.wait(5)
                email = self.tab.ele("xpath=//input[@id='tempEmailAddress']", timeout=5).value
                if email != "" and email != "Please wait..":
                    email_address = email
                    break
            except Exception as e:
                print(e)
                pass

        if email_address is None:
            print("[etempmail.com] Fail to get email address")
            return None
        
        return email_address
        
    def wait_for_message(self, delay=5, timeout=90):
        start_time = time.time()
        email_click_flag = False
        while time.time() - start_time <= timeout:
            try:
                # self.tab.refresh()
                self.tab.wait(2)
                email_elements = self.tab.eles("css=.mail-open td")
                for element in email_elements:
                    if "Cursor" in element.text:
                        print("email_from:", element.text)
                        element.click(by_js=True)
                        email_click_flag = True
                        break
                if email_click_flag:
                    # self.tab.wait(2)
                    print("click email success")
                    
                    code_element = self.tab.ele("css=body")
                   
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
    email_server = EtempMail(browser)
    email = email_server.get_email_address()
    print(email)
    message = email_server.wait_for_message().get("text", None)
    import re
    verify_code = re.search(r'(\d{6})', message).group(1)
    print(verify_code)
    
