import os
import re
import csv
import copy
import queue
import argparse
import threading
import concurrent.futures
from faker import Faker
from datetime import datetime
import time

from DrissionPage import ChromiumOptions, Chromium
from temp_mails import Tempmail_io, Guerillamail_com
from helper.email.minuteinbox_com import Minuteinboxcom
from helper.email.etempmail import EtempMail
from helper.email.tempmailonline import TempMailOnline
from helper.email.gmail_imap import GmailImap
from helper.email import EmailServer

CURSOR_URL = "https://www.cursor.com/"
CURSOR_SIGNIN_URL = "https://authenticator.cursor.sh"
CURSOR_PASSWORD_URL = "https://authenticator.cursor.sh/password"
CURSOR_MAGAIC_CODE_URL = "https://authenticator.cursor.sh/magic-code"
CURSOR_SIGNUP_URL =  "https://authenticator.cursor.sh/sign-up"
CURSOR_SIGNUP_PASSWORD_URL = "https://authenticator.cursor.sh/sign-up/password"
CURSOR_EMAIL_VERIFICATION_URL = "https://authenticator.cursor.sh/email-verification"

CURSOR_SETTINGS_URL = "https://www.cursor.com/settings"

# Parameters for debugging purpose
hide_account_info = os.getenv('HIDE_ACCOUNT_INFO', 'false').lower() == 'true'
enable_register_log = True
enable_headless = os.getenv('ENABLE_HEADLESS', 'false').lower() == 'true'
enable_browser_log = os.getenv('ENABLE_BROWSER_LOG', 'true').lower() == 'true' or not enable_headless

class CursorRegister:

    def __init__(self, 
                 browser: Chromium,
                 email_server: EmailServer = None):
        self.browser = browser
        self.email_server = email_server

        self.thread_id = threading.current_thread().ident
        self.retry_times = 5

    def sign_in(self, email, password = None):
        # 检查是否已经有email_server，如果没有才创建新的临时邮箱
        if self.email_server is None:
            # 创建临时邮箱
            mail = EtempMail(self.browser)
            # mail = Minuteinboxcom(self.browser)
            # mail = TempMailOnline(self.browser)
            self.email_server = mail
            email = mail.get_email_address()
            print(f"[Register][{self.thread_id}] 使用临时邮箱: {email}")
        else:
            # 使用已存在的邮箱服务(如Gmail)
            print(f"[Register][{self.thread_id}] 使用已配置邮箱: {email}")

        # 创建新的队列，确保不会使用之前的验证码
        email_queue = queue.Queue()
        email_thread = threading.Thread(target=self._wait_for_new_message,
                                        args=(email_queue, ), 
                                        daemon=True)
        email_thread.start()

        tab = self.browser.new_tab(CURSOR_SIGNIN_URL)
        # Input email
        for retry in range(self.retry_times):
            try:
                if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Input email")
                tab.ele("xpath=//input[@name='email']").input(email, clear=True)
                tab.ele("@type=submit").click()

                # If not in password page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_PASSWORD_URL, timeout=3) and CURSOR_SIGNIN_URL in tab.url:
                    if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for email page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{self.thread_id}] Exception when handlding email page.")
                print(e)

            # In password page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_PASSWORD_URL, timeout=5):
                print(f"[Register][{self.thread_id}] Continue to password page")
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                print(f"[Register][{self.thread_id}] Timeout when inputing email address")
                return None

        # Use email sign-in code in password page
        for retry in range(self.retry_times):
            try:
                if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Input password")
                if password is None:
                    # 确认魔法码按钮存在
                    magic_code_button = tab.ele("xpath=//button[@value='magic-code']")
                    if magic_code_button:
                        magic_code_button.click()
                        print(f"[Register][{self.thread_id}] 点击了魔法码按钮，等待验证码")
                    else:
                        print(f"[Register][{self.thread_id}] 警告：未找到魔法码按钮")
                        return None
                else:
                    # 如果提供了密码，则使用密码登录
                    password_input = tab.ele("xpath=//input[@name='password']")
                    if password_input:
                        password_input.input(password, clear=True)
                        tab.ele('@type=submit').click()
                        print(f"[Register][{self.thread_id}] 使用密码登录")
                    else:
                        print(f"[Register][{self.thread_id}] 警告：未找到密码输入框")
                        return None

                # If not in verification code page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_MAGAIC_CODE_URL, timeout=3) and CURSOR_PASSWORD_URL in tab.url:
                    if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for password page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{self.thread_id}] Exception when handling password page.")
                print(e)

            # In code verification page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_MAGAIC_CODE_URL, timeout=5):
                print(f"[Register][{self.thread_id}] Continue to email code page")
                break

            if tab.wait.eles_loaded("xpath=//div[contains(text(), 'Sign up is restricted.')]", timeout=3):
                print(f"[Register][{self.thread_id}][Error] Sign up is restricted.")
                return None

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                if enable_register_log: print(f"[Register][{self.thread_id}] Timeout when inputing password")
                return None

        # Get email verification code
        try:
            verify_code = None
            message = None

            print(f"[Register][{self.thread_id}] 正在等待验证码邮件...")
            data = email_queue.get(timeout=60)
            if data is None:
                print(f"[Register][{self.thread_id}] 未收到邮件或获取邮件出错")
                return None
                
            print(f"[Register][{self.thread_id}] 收到邮件，开始提取验证码")
            
            # 尝试从text字段获取验证码
            if "text" in data:
                message = data["text"]
                print(f"[Register][{self.thread_id}] 邮件内容: {message[:100]}...")
            # 如果没有text字段，尝试从content字段获取
            elif "content" in data:
                message = data["content"]
                print(f"[Register][{self.thread_id}] 从content获取内容: {message[:100]}...")
            # 尝试从body_text字段获取
            elif "body_text" in data:
                message = data["body_text"]
                print(f"[Register][{self.thread_id}] 从body_text获取内容: {message[:100]}...")
            else:
                print(f"[Register][{self.thread_id}] 无法从邮件中获取内容，可用字段: {list(data.keys())}")
                return None
                
            # 提取验证码
            if message:
                # 首先检查是否直接是6位数字
                if message.strip().isdigit() and len(message.strip()) == 6:
                    verify_code = message.strip()
                    print(f"[Register][{self.thread_id}] 直接获取到验证码: {verify_code}")
                else:
                    # 清理内容以便正则匹配
                    clean_message = message.replace(" ", "")
                    
                    # 尝试多种正则模式
                    patterns = [
                        r'(\d{6})',  # 基本6位数字
                        r'验证码[：:]\s*(\d{6})',  # 中文格式
                        r'code[：:]*\s*(\d{6})',  # 英文format
                        r'verification[：:]*\s*(\d{6})'  # 另一种英文format
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, clean_message)
                        if match:
                            verify_code = match.group(1)
                            print(f"[Register][{self.thread_id}] 通过模式 '{pattern}' 提取到验证码: {verify_code}")
                            break
                    
                    # 如果上面的模式都没匹配到，尝试特殊格式如 "9 9 2 2 8 2"
                    if verify_code is None:
                        pattern = r'(\d\s+\d\s+\d\s+\d\s+\d\s+\d)'
                        match = re.search(pattern, message)
                        if match:
                            formatted_code = re.sub(r'\s+', '', match.group(1))
                            if formatted_code.isdigit() and len(formatted_code) == 6:
                                verify_code = formatted_code
                                print(f"[Register][{self.thread_id}] 通过特殊格式提取到验证码: {verify_code}")
            
            # 如果email_server有extract_verification_code方法，尝试使用它
            if verify_code is None and hasattr(self.email_server, 'extract_verification_code'):
                verify_code = self.email_server.extract_verification_code(message)
                if verify_code:
                    print(f"[Register][{self.thread_id}] 使用email_server提取到验证码: {verify_code}")
            
            if verify_code is None:
                print(f"[Register][{self.thread_id}] 无法从邮件中提取验证码")
                return None
                
            print(f"[Register][{self.thread_id}] 最终验证码: {verify_code}")
            
        except Exception as e:
            print(f"[Register][{self.thread_id}] 提取验证码时出错: {e}")
            return None

        # Input email verification code
        for retry in range(self.retry_times):
            try:
                if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Input email verification code")

                for idx, digit in enumerate(verify_code, start = 0):
                    tab.ele(f"xpath=//input[@data-index={idx}]").input(digit, clear=True)
                    tab.wait(0.1, 0.3)
                tab.wait(0.5, 1.5)

                if not tab.wait.url_change(CURSOR_URL, timeout=3) and CURSOR_MAGAIC_CODE_URL in tab.url:
                    if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for email code page.")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{self.thread_id}] Exception when handling email code page.")
                print(e)

            if tab.wait.url_change(CURSOR_URL, timeout=5):
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                if enable_register_log: print(f"[Register][{self.thread_id}] Timeout when inputing email verification code")
                return None

        # Get cookie
        try:
            cookies = tab.cookies().as_dict()
        except e:
            print(f"[Register][{self.thread_id}] Fail to get cookie.")
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                print(f"[Register][{self.thread_id}] Register Account Successfully.")
            else:
                print(f"[Register][{self.thread_id}] Register Account Failed.")

        if not hide_account_info:
            print(f"[Register] Cursor Email: {email}")
            print(f"[Register] Cursor Token: {token}")

        return tab

    def sign_up(self, browser):

        def _wait_for_new_email_thread(mail, queue, timeout=300):
            try:
                data = mail.wait_for_new_email(delay=1, timeout=timeout)
                queue.put(copy.deepcopy(data))
            except Exception as e:
                queue.put(None)

        fake = Faker()
        retry_times = 5
        thread_id = threading.current_thread().ident

        mail = Guerillamail_com()
        email = mail.email
        password = fake.password(length=12, special_chars=True, digits=True, upper_case=True, lower_case=True)

        email_queue = queue.Queue()
        email_thread = threading.Thread(target=_wait_for_new_email_thread,
                                        args=(mail, email_queue, ), 
                                        daemon=True)
        email_thread.start()

        tab = browser.new_tab(CURSOR_SIGNUP_URL)
        # Input email
        for retry in range(retry_times):
            try:
                if enable_register_log: print(f"[Register][{thread_id}][{retry}] Input email")
                tab.ele("xpath=//input[@name='email']").input(email, clear=True)
                tab.ele("@type=submit").click()

                # If not in password page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_SIGNUP_PASSWORD_URL, timeout=3) and CURSOR_SIGNUP_URL in tab.url:
                    if enable_register_log: print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for email page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{thread_id}] Exception when handlding email page.")
                print(e)

            # In password page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_SIGNUP_PASSWORD_URL, timeout=5):
                print(f"[Register][{thread_id}] Continue to password page")
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                print(f"[Register][{thread_id}] Timeout when inputing email address")
                if not enable_browser_log: browser.quit(force=True, del_data=True)
                return None

        # Use email sign-in code in password page
        for retry in range(retry_times):
            try:
                if enable_register_log: print(f"[Register][{thread_id}][{retry}] Input password")
                tab.ele("xpath=//input[@name='password']").input(password, clear=True)
                tab.ele('@type=submit').click()

                # If not in verification code page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_EMAIL_VERIFICATION_URL, timeout=3) and CURSOR_SIGNUP_PASSWORD_URL in tab.url:
                    if enable_register_log: print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for password page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{thread_id}] Exception when handling password page.")
                print(e)

            # In code verification page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_EMAIL_VERIFICATION_URL, timeout=5):
                print(f"[Register][{thread_id}] Continue to email code page")
                break

            if tab.wait.eles_loaded("xpath=//div[contains(text(), 'Sign up is restricted.')]", timeout=3):
                print(f"[Register][{thread_id}][Error] Sign up is restricted.")
                return None

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                if enable_register_log: print(f"[Register][{thread_id}] Timeout when inputing password")
                return None

        # Get email verification code
        try:
            data = email_queue.get(timeout=60)
            assert data is not None, "Fail to get code from email."

            verify_code = None
            if "body_text" in data:
                message_text = data["body_text"]
                message_text = message_text.replace(" ", "")
                verify_code = re.search(r'(?:\r?\n)(\d{6})(?:\r?\n)', message_text).group(1)
            elif "preview" in data:
                message_text = data["preview"]
                verify_code = re.search(r'Your verification code is (\d{6})\. This code expires', message_text).group(1)
            # Handle HTML format
            elif "content" in data:
                message_text = data["content"]
                message_text = re.sub(r"<[^>]*>", "", message_text)
                message_text = re.sub(r"&#8202;", "", message_text)
                message_text = re.sub(r"&nbsp;", "", message_text)
                message_text = re.sub(r'[\n\r\s]', "", message_text)
                verify_code = re.search(r'openbrowserwindow\.(\d{6})Thiscodeexpires', message_text).group(1)
            assert verify_code is not None, "Fail to get code from email."

        except Exception as e:
            print(f"[Register][{thread_id}] Fail to get code from email.")
            return None

        # Input email verification code
        for retry in range(retry_times):
            try:
                if enable_register_log: print(f"[Register][{thread_id}][{retry}] Input email verification code")

                for idx, digit in enumerate(verify_code, start = 0):
                    tab.ele(f"xpath=//input[@data-index={idx}]").input(digit, clear=True)
                    tab.wait(0.1, 0.3)
                tab.wait(0.5, 1.5)

                if not tab.wait.url_change(CURSOR_URL, timeout=3) and CURSOR_MAGAIC_CODE_URL in tab.url:
                    if enable_register_log: print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for email code page.")
                    self._cursor_turnstile(tab)

            except Exception as e:
                print(f"[Register][{thread_id}] Exception when handling email code page.")
                print(e)

            if tab.wait.url_change(CURSOR_URL, timeout=3):
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                if enable_register_log: print(f"[Register][{thread_id}] Timeout when inputing email verification code")
                return None

        # Get cookie
        try:
            cookies = tab.cookies().as_dict()
        except e:
            print(f"[Register][{thread_id}] Fail to get cookie.")
            if not enable_browser_log: browser.quit(force=True, del_data=True)
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                print(f"[Register][{thread_id}] Register Account Successfully.")
            else:
                print(f"[Register][{thread_id}] Register Account Failed.")

        if not hide_account_info:
            print(f"[Register] Cursor Email: {email}")
            print(f"[Register] Cursor Token: {token}")

        return {
            'username': email,
            'token': token
        }

    # tab: A tab has signed in 
    def delete_account(self, tab):
        """删除Cursor账户"""
        try:
            # 导航到设置页面
            tab.get(CURSOR_SETTINGS_URL)
            tab.wait(5)  # 改为简单地等待5秒钟
            print(f"[账户删除][{self.thread_id}] 已进入设置页面")
            
            # 1. 点击Advanced按钮展开高级选项
            advanced_button = tab.ele("xpath=//div[contains(@class, 'cursor-pointer') and contains(., 'Advanced')]")
            if advanced_button:
                advanced_button.click()
                print(f"[账户删除][{self.thread_id}] 点击Advanced按钮")
                tab.wait(2)
            else:
                print(f"[账户删除][{self.thread_id}] 未找到Advanced按钮")
                return False
                
            # 2. 点击Delete Account按钮
            delete_button = tab.ele("xpath=//button[contains(@class, 'underline') and contains(., 'Delete Account')]")
            if delete_button:
                delete_button.click()
                print(f"[账户删除][{self.thread_id}] 点击Delete Account按钮")
                tab.wait(2)
            else:
                print(f"[账户删除][{self.thread_id}] 未找到Delete Account按钮")
                return False
                
            # 3. 输入确认文本"Delete"
            confirm_input = tab.ele("xpath=//input[@placeholder=\"Type 'Delete' to confirm\"]")
            if confirm_input:
                confirm_input.input("Delete", clear=True)
                print(f"[账户删除][{self.thread_id}] 输入确认文本'Delete'")
                tab.wait(1)
            else:
                print(f"[账户删除][{self.thread_id}] 未找到确认输入框")
                return False
                
            # 4. 点击最终的Delete按钮
            final_delete_button = tab.ele("xpath=//button[contains(@class, 'bg-brand-black') and .//span[contains(text(), 'Delete')]]")
            if final_delete_button:
                # 检查按钮是否已启用 (aria-disabled="false" 或者属性不存在)
                is_disabled = final_delete_button.attr('aria-disabled') == 'true'
                if is_disabled:
                    # 尝试等待按钮启用
                    print(f"[账户删除][{self.thread_id}] 等待Delete按钮启用")
                    tab.wait(2)
                    # 再次检查
                    is_disabled = final_delete_button.attr('aria-disabled') == 'true'
                    if is_disabled:
                        print(f"[账户删除][{self.thread_id}] Delete按钮未启用，可能需要更多确认")
                        return False
                
                final_delete_button.click()
                print(f"[账户删除][{self.thread_id}] 点击最终Delete按钮")
                tab.wait(3)
                
                # 验证是否返回到登录页面或首页
                if CURSOR_SIGNIN_URL in tab.url or "sign-in" in tab.url or "cursor.com" in tab.url:
                    print(f"[账户删除][{self.thread_id}] 账户删除成功，当前URL: {tab.url}")
                    return True
                else:
                    print(f"[账户删除][{self.thread_id}] 账户可能未成功删除，当前URL: {tab.url}")
                    return False
            else:
                print(f"[账户删除][{self.thread_id}] 未找到最终Delete按钮")
                return False
                
        except Exception as e:
            print(f"[账户删除][{self.thread_id}] 删除账户过程中出现异常: {e}")
            return False

    def get_cursor_cookie(self, tab):
        try:
            cookies = tab.cookies().as_dict()
        except:
            print(f"[Register][{self.thread_id}] Fail to get cookie.")
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                print(f"[Register][{self.thread_id}] Register Account Successfully.")
            else:
                print(f"[Register][{self.thread_id}] Register Account Failed.")

        return token

    def _cursor_turnstile(self, tab, retry_times = 5):
        for retry in range(retry_times): # Retry times
            try:
                if enable_register_log: print(f"[Register][{self.thread_id}][{retry}] Passing Turnstile")
                challenge_shadow_root = tab.ele('@id=cf-turnstile').child().shadow_root
                challenge_shadow_button = challenge_shadow_root.ele("tag:iframe", timeout=30).ele("tag:body").sr("xpath=//input[@type='checkbox']")
                if challenge_shadow_button:
                    challenge_shadow_button.click()
                    break
            except:
                pass
            if retry == retry_times - 1:
                print("[Register] Timeout when passing turnstile")

    def _wait_for_new_message(self, queue, timeout=300):
        try:
            data = self.email_server.wait_for_message(delay=1, timeout=timeout)
            if data:
                # 打印邮件主题，帮助调试
                if "subject" in data:
                    print(f"email_from: {data.get('subject', '未知主题')}")
                
                # 确保text字段存在
                if "text" in data:
                    try:
                        # 处理编码问题
                        data["text"] = data["text"].encode("raw_unicode_escape").decode("utf-8")
                    except:
                        # 如果编码失败，保持原样
                        pass
                    
                    print(f"收到邮件内容: {data['text'][:100]}..." if len(data['text']) > 100 else data['text'])
                else:
                    # 如果text字段不存在，尝试从其他字段提取
                    if "content" in data:
                        data["text"] = data["content"]
                    elif "body_text" in data:
                        data["text"] = data["body_text"]
                    
                    if "text" not in data:
                        print(f"[Warning] 邮件缺少文本内容，可用字段: {list(data.keys())}")
            
            queue.put(copy.deepcopy(data))
        except Exception as e:
            print(f"[Error] 等待邮件时出错: {e}")
            queue.put(None)

def register_pipeline(options):

    try:
        # Maybe fail to open the browser
        browser = Chromium(options)
    except Exception as e:
        print(e)
        return None

    register = CursorRegister(browser)    
    #email_address = register.email_server.get_email_address()
        
    #account_infos = sign_in(browser)
    tab_signin = register.sign_in("email_address")
    token = register.get_cursor_cookie(tab_signin)

    register.browser.quit(force=True, del_data=True)

    #if not hide_account_info:
    #    print(f"[Register] Cursor Email: {"email"}")
    #    print(f"[Register] Cursor Token: {token}")

    return {
        "token": token
    }

def gmail_account_cycle(gmail_email, gmail_app_password, api_url=None):
    """
    Gmail账户循环流程：登录->删除账户->重新登录->获取token传入API
    
    参数:
        gmail_email: Gmail邮箱地址
        gmail_app_password: Gmail应用密码(App Password)
        api_url: 可选，API地址用于上传token
    """
    print(f"[Gmail循环] 开始处理Gmail账户: {gmail_email}")

    options = ChromiumOptions()
    options.auto_port()
    options.new_env()
    # 添加turnstilePatch扩展
    options.add_extension("turnstilePatch")

    # 设置headless模式
    if enable_headless: 
        from platform import platform
        if platform == "linux" or platform == "linux2":
            platformIdentifier = "X11; Linux x86_64"
        elif platform == "darwin":
            platformIdentifier = "Macintosh; Intel Mac OS X 10_15_7"
        elif platform == "win32":
            platformIdentifier = "Windows NT 10.0; Win64; x64"
        # 设置Chrome版本
        chrome_version = "130.0.0.0"        
        options.set_user_agent(f"Mozilla/5.0 ({platformIdentifier}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36")
        options.headless()

    try:
        # 打开浏览器
        browser = Chromium(options)
        print(f"[Gmail循环] 浏览器已启动")
        
        # 暂停几秒，确保时间差足够区分新旧邮件
        print(f"[Gmail循环] 暂停5秒，确保能够区分新旧邮件")
        time.sleep(5)
        
        # 创建Gmail IMAP客户端
        gmail_client = GmailImap(gmail_email, gmail_app_password)
        print(f"[Gmail循环] Gmail IMAP客户端已创建")
        
        # 创建注册器，并确保先设置email_server
        register = CursorRegister(browser)
        register.email_server = gmail_client  # 设置邮箱服务
        
        # 第一步：使用Gmail账号登录
        print(f"[Gmail循环] 开始使用Gmail登录")
        # 确认邮箱服务已正确设置
        print(f"[Gmail循环] 使用邮箱: {gmail_email}")
        print(f"[Gmail循环] 邮箱服务类型: {type(register.email_server).__name__}")
        
        tab = register.sign_in(gmail_email)
        if not tab:
            print(f"[Gmail循环] 登录失败")
            browser.quit(force=True, del_data=True)
            return None
        
        # 获取首次登录的token以供检查
        first_token = register.get_cursor_cookie(tab)
        if not first_token:
            print(f"[Gmail循环] 首次登录获取token失败")
            browser.quit(force=True, del_data=True)
            return None
            
        print(f"[Gmail循环] 登录成功，首次token: {first_token[:10]}..., 准备删除账户")
        
        # 第二步：删除账户
        delete_success = register.delete_account(tab)
        if not delete_success:
            print(f"[Gmail循环] 删除账户失败")
            browser.quit(force=True, del_data=True)
            return None
        
        print(f"[Gmail循环] 账户删除成功，准备重新登录")
        
        # 暂停几秒，确保删除操作完全生效
        print(f"[Gmail循环] 暂停10秒等待删除操作完全生效")
        time.sleep(10)
        
        # 第三步：重新登录 - 确保再次使用同一个邮箱客户端
        # 重置邮箱客户端以确保能获取新邮件
        print(f"[Gmail循环] 重新创建Gmail IMAP客户端")
        gmail_client = GmailImap(gmail_email, gmail_app_password)
        register.email_server = gmail_client
        
        tab = register.sign_in(gmail_email)
        if not tab:
            print(f"[Gmail循环] 重新登录失败")
            browser.quit(force=True, del_data=True)
            return None
        
        # 获取token
        token = register.get_cursor_cookie(tab)
        if not token:
            print(f"[Gmail循环] 获取token失败")
            browser.quit(force=True, del_data=True)
            return None
            
        # 验证token是否变化，确认是新的注册
        if token == first_token:
            print(f"[Gmail循环] 警告：重新登录获取的token与首次相同，可能账户未真正删除")
        else:
            print(f"[Gmail循环] 成功获取到新token: {token[:10]}...")
        
        print(f"[Gmail循环] 成功获取到token")
        # 如果提供了API地址，则上传token
        if api_url:
            from tokenManager.custom_api_manager import CustomAPIManager
            custom_api = CustomAPIManager(api_url)
            response = custom_api.upload_tokens(token)
            print(f'[Custom-API] 上传Token。状态码: {response.status_code}, 响应: {response.json()}')
        
        # 关闭浏览器
        browser.quit(force=True, del_data=True)
        
        result = {
            "email": gmail_email,
            "token": token
        }
        
        # 保存结果到文件
        formatted_date = datetime.now().strftime("%Y-%m-%d")
        csv_file = f"./gmail_output_{formatted_date}.csv"
        
        with open(csv_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=["email", "token"])
            writer.writerow(result)
            
        return result
        
    except Exception as e:
        print(f"[Gmail循环] 执行过程中出现异常: {e}")
        try:
            browser.quit(force=True, del_data=True)
        except:
            pass
        return None

def register_cursor(number, max_workers):

    options = ChromiumOptions()
    options.auto_port()
    options.new_env()
    # Use turnstilePatch from https://github.com/TheFalloutOf76/CDP-bug-MouseEvent-.screenX-.screenY-patcher
    options.add_extension("turnstilePatch")

    # If fail to pass the cloudflare in headless mode, try to align the user agent with your real browser
    if enable_headless: 
        from platform import platform
        if platform == "linux" or platform == "linux2":
            platformIdentifier = "X11; Linux x86_64"
        elif platform == "darwin":
            platformIdentifier = "Macintosh; Intel Mac OS X 10_15_7"
        elif platform == "win32":
            platformIdentifier = "Windows NT 10.0; Win64; x64"
        # Please align version with your Chrome
        chrome_version = "130.0.0.0"        
        options.set_user_agent(f"Mozilla/5.0 ({platformIdentifier}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36")
        options.headless()

    # Run the code using multithreading
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(register_pipeline, copy.deepcopy(options)) for _ in range(number)]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                results.append(result)

    results = [result for result in results if result["token"] is not None]

    if len(results) > 0:
        formatted_date = datetime.now().strftime("%Y-%m-%d")

        csv_file = f"./output_{formatted_date}.csv"
        token_file = f"./token_{formatted_date}.csv"

        fieldnames = results[0].keys()
        # Write username, token into a csv file
        with open(csv_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writerows(results)
        # Only write token to csv file, without header
        tokens = [{'token': row['token']} for row in results]
        with open(token_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=['token'])
            writer.writerows(tokens)

    return results

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Cursor Registor')
    parser.add_argument('--number', type=int, default=2, help="How many account you want")
    parser.add_argument('--max_workers', type=int, default=1, help="How many workers in multithreading")
    
    # The parameters with name starts with oneapi are used to uploead the cookie token to one-api, new-api, chat-api server.
    parser.add_argument('--oneapi', action='store_true', help='Enable One-API or not')
    parser.add_argument('--oneapi_url', type=str, required=False, help='URL link for One-API website')
    parser.add_argument('--oneapi_token', type=str, required=False, help='Token for One-API website')
    parser.add_argument('--oneapi_channel_url', type=str, required=False, help='Base url for One-API channel')
    
    parser.add_argument('--custom-api', action='store_true', help='Enable Custom-API or not')
    parser.add_argument('--api_url', type=str, required=False, help='URL link for Custom-API website')
    
    # 添加Gmail账户循环相关参数
    parser.add_argument('--gmail-cycle', action='store_true', help='启用Gmail账户循环流程')
    parser.add_argument('--gmail-email', type=str, help='Gmail邮箱地址')
    parser.add_argument('--gmail-password', type=str, help='Gmail应用密码(App Password)')

    args = parser.parse_args()
    number = args.number
    max_workers = args.max_workers
    use_oneapi = args.oneapi
    oneapi_url = args.oneapi_url
    oneapi_token = args.oneapi_token
    oneapi_channel_url = args.oneapi_channel_url

    use_custom_api = args.custom_api
    api_url = args.api_url
    
    # Gmail账户循环流程选项
    use_gmail_cycle = args.gmail_cycle
    gmail_email = args.gmail_email
    gmail_password = args.gmail_password

    # 如果启用Gmail账户循环
    if use_gmail_cycle:
        if not gmail_email or not gmail_password:
            print("[错误] 必须提供Gmail邮箱地址和应用密码")
        else:
            print(f"[Gmail循环] 开始Gmail账户循环流程")
            result = gmail_account_cycle(gmail_email, gmail_password, api_url if use_custom_api else None)
            if result:
                print(f"[Gmail循环] 流程成功完成")
            else:
                print(f"[Gmail循环] 流程执行失败")
    # 否则使用常规注册流程
    else:
        print(f"[Register] Start to register {number} accounts in {max_workers} threads")
        account_infos = register_cursor(number, max_workers)
        tokens = list(set([row['token'] for row in account_infos]))
        print(f"[Register] Register {len(tokens)} accounts successfully")
        
        if use_oneapi and len(account_infos) > 0:
            from tokenManager.oneapi_manager import OneAPIManager
            from tokenManager.cursor import Cursor
            oneapi = OneAPIManager(oneapi_url, oneapi_token)

            # Send request by batch to avoid "Too many SQL variables" error in SQLite.
            # If you use MySQL, better to set the batch_size as len(tokens)
            batch_size = 10
            for idx, i in enumerate(range(0, len(tokens), batch_size), start=1):
                batch = tokens[i:i + batch_size]
                response = oneapi.add_channel("Cursor",
                                            oneapi_channel_url,
                                            '\n'.join(batch),
                                            Cursor.models)
                print(f'[OneAPI] Add Channel Request For Batch {idx}. Status Code: {response.status_code}, Response Body: {response.json()}')
        elif use_custom_api and len(account_infos) > 0:
            from tokenManager.custom_api_manager import CustomAPIManager
            custom_api = CustomAPIManager(api_url)
            for token in tokens:
                response = custom_api.upload_tokens(token)
                print(f'[Custom-API] Upload Token. Status Code: {response.status_code}, Response Body: {response.json()}')
            print(f"[Custom-API] Upload {len(tokens)} tokens successfully")
