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
                # self.tab.refresh()
                # self.tab.wait(2)
                    
                # 尝试多种选择器
                email_elements = self.tab.eles("xpath=//div[contains(@class, 'email-list')]//div[contains(text(), 'Cursor')]")
                if not email_elements:
                    email_elements = self.tab.eles("xpath=//div[contains(text(), 'Cursor')]")
                if not email_elements:
                    email_elements = self.tab.eles("xpath=//*[contains(text(), 'Cursor')]")
                if email_elements:
                    print("find cursor email,click..")
                    email_elements[0].click()
                    self.tab.wait(2)
                    try:                  
                        code_element = self.tab.ele("xpath=/html/body/div[2]/table[2]/tbody/tr/td/div/table/tbody/tr/td/div/table/tbody/tr/td/table/tbody/tr[5]/td/div")
                        if code_element:
                            return {
                                "text": code_element.text
                            }
                        else:
                            print("not found code")
                    except Exception as e:
                        print(f"click email or get content error: {e}")
            except Exception as e:
                print(e)
                pass
            print("not found code,wait 5 seconds..")
            self.tab.wait(delay)

        return None

if __name__ == "__main__":
    browser = Chromium()
    email_server = Minuteinboxcom(browser)
    email = email_server.get_email_address()
    print(email)
    
