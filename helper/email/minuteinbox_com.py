import time
from DrissionPage import Chromium

class Minuteinboxcom:

    MINUTEINBOX_COM_URL = "https://www.minuteinbox.com/"

    def __init__(self, browser: Chromium):
        self.tab = browser.new_tab(self.MINUTEINBOX_COM_URL)

    def get_email_address(self):
        email_address = None

        for _ in range(5):
            try:
                self.tab.refresh()
                self.tab.wait(2)
                email = self.tab.ele("xpath=//span[@id='email']", timeout=5).text
                if email != "":
                    email_address = email
                    break
            except Exception as e:
                print(e)
                pass

        if email_address is None:
            print("[minuteinbox.com] Fail to get email address")
            return None
        
        return email_address
        
    def wait_for_message(self, delay=5, timeout=60):
        start_time = time.time()

        while time.time() - start_time <= timeout:
            try:
                self.tab.refresh()
                email_elements = self.tab.eles("css=tr > td.from")
                for element in email_elements:
                    print("email_from:", element.text)
                    if "Cursor" in element.text:
                        try:
                            element.click()
                        except Exception as e:
                            print("click email error,try scroll and js click:", e)
                            self.tab.run_js("arguments[0].scrollIntoView();", element)
                            self.tab.run_js("arguments[0].click();", element)
                        break
                print("click email success")
                self.tab.wait(2)
                code_element = self.tab.ele("xpath=//div[@class='base-layout-root']")
                if code_element:
                    return {
                        "text": code_element.text
                    }
            except Exception as e:
                print(e)
                pass
            print("not found code, wait 5 seconds..")
            self.tab.wait(delay)

        return None

if __name__ == "__main__":
    browser = Chromium()
    email_server = Minuteinboxcom(browser)
    email = email_server.get_email_address()
    print(email)
    
