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
import sys

# Safe print function to handle encoding errors
def safe_print(*args, **kwargs):
    """
    A print function that handles encoding errors safely.
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Try to encode to ASCII with replace for error characters
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                try:
                    # Replace non-ASCII characters with their ASCII approximation or '?'
                    new_args.append(arg.encode('ascii', 'replace').decode('ascii'))
                except:
                    new_args.append("<non-ASCII text>")
            else:
                new_args.append(str(arg))
        
        try:
            print(*new_args, **kwargs)
        except:
            print("<Error printing message>")

# 设置控制台编码为UTF-8，增强跨平台兼容性
if sys.platform == 'win32':
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleCP(65001)  # 设置控制台输入代码页为UTF-8
        k.SetConsoleOutputCP(65001)  # 设置控制台输出代码页为UTF-8
    except:
        # 如果上面的方法失败，尝试使用环境变量
        os.environ['PYTHONIOENCODING'] = 'utf-8'

from DrissionPage import ChromiumOptions, Chromium
from temp_mails import Tempmail_io, Guerillamail_com
from helper.email.minuteinbox_com import Minuteinboxcom
from helper.email.etempmail import EtempMail
from helper.email.tempmailonline import TempMailOnline
from helper.email.universal_imap import UniversalImap
from helper.email import EmailServer
from helper.email.imap import Imap

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
            safe_print(f"[Register][{self.thread_id}] Using temporary email: {email}")
        else:
            # 使用已存在的邮箱服务(如Gmail)
            safe_print(f"[Register][{self.thread_id}] Using configured email: {email}")

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
                if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Input email")
                tab.ele("xpath=//input[@name='email']").input(email, clear=True)
                tab.ele("@type=submit").click()

                # If not in password page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_PASSWORD_URL, timeout=3) and CURSOR_SIGNIN_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for email page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{self.thread_id}] Exception when handlding email page.")
                safe_print(e)

            # In password page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_PASSWORD_URL, timeout=5):
                safe_print(f"[Register][{self.thread_id}] Continue to password page")
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                safe_print(f"[Register][{self.thread_id}] Timeout when inputing email address")
                return None

        # Use email sign-in code in password page
        for retry in range(self.retry_times):
            try:
                if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Input password")
                if password is None:
                    # 确认魔法码按钮存在
                    magic_code_button = tab.ele("xpath=//button[@value='magic-code']")
                    if magic_code_button:
                        magic_code_button.click()
                        safe_print(f"[Register][{self.thread_id}] Clicked magic code button, waiting for verification code")
                    else:
                        safe_print(f"[Register][{self.thread_id}] Warning: Magic code button not found")
                        # return None
                else:
                    # 如果提供了密码，则使用密码登录
                    password_input = tab.ele("xpath=//input[@name='password']")
                    if password_input:
                        password_input.input(password, clear=True)
                        tab.ele('@type=submit').click()
                        safe_print(f"[Register][{self.thread_id}] Using password to login")
                    else:
                        safe_print(f"[Register][{self.thread_id}] Warning: Password input field not found")
                        return None

                # If not in verification code page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_MAGAIC_CODE_URL, timeout=3) and CURSOR_PASSWORD_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for password page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{self.thread_id}] Exception when handling password page.")
                safe_print(e)

            # In code verification page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_MAGAIC_CODE_URL, timeout=5):
                safe_print(f"[Register][{self.thread_id}] Continue to email code page")
                break

            if tab.wait.eles_loaded("xpath=//div[contains(text(), 'Sign up is restricted.')]", timeout=3):
                safe_print(f"[Register][{self.thread_id}][Error] Sign up is restricted.")
                return None

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                if enable_register_log: safe_print(f"[Register][{self.thread_id}] Timeout when inputing password")
                return None

        # Get email verification code
        try:
            verify_code = None
            message = None

            safe_print(f"[Register][{self.thread_id}] Waiting for verification email...")
            data = email_queue.get(timeout=90)
            if data is None:
                safe_print(f"[Register][{self.thread_id}] Email not received or error occurred")
                return None
                
            safe_print(f"[Register][{self.thread_id}] Email received, extracting verification code")
            
            # 尝试从text字段获取验证码
            if "text" in data:
                message = data["text"]
                safe_print(f"[Register][{self.thread_id}] Email content: {message[:100]}...")
            # 如果没有text字段，尝试从content字段获取
            elif "content" in data:
                message = data["content"]
                safe_print(f"[Register][{self.thread_id}] Content from content field: {message[:100]}...")
            # 尝试从body_text字段获取
            elif "body_text" in data:
                message = data["body_text"]
                safe_print(f"[Register][{self.thread_id}] Content from body_text field: {message[:100]}...")
            else:
                safe_print(f"[Register][{self.thread_id}] Unable to get content from email, available fields: {list(data.keys())}")
                return None
                
            # 提取验证码
            if message:
                # 首先检查是否直接是6位数字
                if message.strip().isdigit() and len(message.strip()) == 6:
                    verify_code = message.strip()
                    safe_print(f"[Register][{self.thread_id}] Directly got verification code: {verify_code}")
                else:
                    # 清理内容以便正则匹配
                    clean_message = message.replace(" ", "")
                    
                    # 尝试多种正则模式
                    patterns = [
                        r'(\d{6})',  # 基本6位数字
                        r'verification code[：:]*\s*(\d{6})',  # 英文格式1
                        r'code[：:]*\s*(\d{6})',  # 英文格式2
                        r'verification[：:]*\s*(\d{6})'  # 英文格式3
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, clean_message)
                        if match:
                            verify_code = match.group(1)
                            safe_print(f"[Register][{self.thread_id}] Extracted code via pattern '{pattern}': {verify_code}")
                            break
                    
                    # 如果上面的模式都没匹配到，尝试特殊格式如 "9 9 2 2 8 2"
                    if verify_code is None:
                        pattern = r'(\d\s+\d\s+\d\s+\d\s+\d\s+\d)'
                        match = re.search(pattern, message)
                        if match:
                            formatted_code = re.sub(r'\s+', '', match.group(1))
                            if formatted_code.isdigit() and len(formatted_code) == 6:
                                verify_code = formatted_code
                                safe_print(f"[Register][{self.thread_id}] Extracted code via special format: {verify_code}")
            
            # 如果email_server有extract_verification_code方法，尝试使用它
            if verify_code is None and hasattr(self.email_server, 'extract_verification_code'):
                verify_code = self.email_server.extract_verification_code(message)
                if verify_code:
                    safe_print(f"[Register][{self.thread_id}] Using email_server to extract code: {verify_code}")
            
            if verify_code is None:
                safe_print(f"[Register][{self.thread_id}] Unable to extract verification code from email")
                return None
                
            safe_print(f"[Register][{self.thread_id}] Final verification code: {verify_code}")
            
        except Exception as e:
            safe_print(f"[Register][{self.thread_id}] Error extracting verification code: {e}")
            return None

        # Input email verification code
        for retry in range(self.retry_times):
            try:
                if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Input email verification code")

                for idx, digit in enumerate(verify_code, start = 0):
                    tab.ele(f"xpath=//input[@data-index={idx}]").input(digit, clear=True)
                    tab.wait(0.1, 0.3)
                tab.wait(0.5, 1.5)

                if not tab.wait.url_change(CURSOR_URL, timeout=3) and CURSOR_MAGAIC_CODE_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Try pass Turnstile for email code page.")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{self.thread_id}] Exception when handling email code page.")
                safe_print(e)

            if tab.wait.url_change(CURSOR_URL, timeout=5):
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == self.retry_times - 1:
                if enable_register_log: safe_print(f"[Register][{self.thread_id}] Timeout when inputing email verification code")
                return None

        # Get cookie
        try:
            cookies = tab.cookies().as_dict()
        except e:
            safe_print(f"[Register][{self.thread_id}] Fail to get cookie.")
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                safe_print(f"[Register][{self.thread_id}] Register Account Successfully.")
            else:
                safe_print(f"[Register][{self.thread_id}] Register Account Failed.")

        if not hide_account_info:
            safe_print(f"[Register] Cursor Email: {email}")
            safe_print(f"[Register] Cursor Token: {token}")

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
                if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Input email")
                tab.ele("xpath=//input[@name='email']").input(email, clear=True)
                tab.ele("@type=submit").click()

                # If not in password page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_SIGNUP_PASSWORD_URL, timeout=3) and CURSOR_SIGNUP_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for email page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{thread_id}] Exception when handlding email page.")
                safe_print(e)

            # In password page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_SIGNUP_PASSWORD_URL, timeout=5):
                safe_print(f"[Register][{thread_id}] Continue to password page")
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                safe_print(f"[Register][{thread_id}] Timeout when inputing email address")
                if not enable_browser_log: browser.quit(force=True, del_data=True)
                return None

        # Use email sign-in code in password page
        for retry in range(retry_times):
            try:
                if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Input password")
                tab.ele("xpath=//input[@name='password']").input(password, clear=True)
                tab.ele('@type=submit').click()

                # If not in verification code page, try pass turnstile page
                if not tab.wait.url_change(CURSOR_EMAIL_VERIFICATION_URL, timeout=3) and CURSOR_SIGNUP_PASSWORD_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for password page")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{thread_id}] Exception when handling password page.")
                safe_print(e)

            # In code verification page or data is validated, continue to next page
            if tab.wait.url_change(CURSOR_EMAIL_VERIFICATION_URL, timeout=5):
                safe_print(f"[Register][{thread_id}] Continue to email code page")
                break

            if tab.wait.eles_loaded("xpath=//div[contains(text(), 'Sign up is restricted.')]", timeout=3):
                safe_print(f"[Register][{thread_id}][Error] Sign up is restricted.")
                return None

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                if enable_register_log: safe_print(f"[Register][{thread_id}] Timeout when inputing password")
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
            safe_print(f"[Register][{thread_id}] Fail to get code from email.")
            return None

        # Input email verification code
        for retry in range(retry_times):
            try:
                if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Input email verification code")

                for idx, digit in enumerate(verify_code, start = 0):
                    tab.ele(f"xpath=//input[@data-index={idx}]").input(digit, clear=True)
                    tab.wait(0.1, 0.3)
                tab.wait(0.5, 1.5)

                if not tab.wait.url_change(CURSOR_URL, timeout=3) and CURSOR_MAGAIC_CODE_URL in tab.url:
                    if enable_register_log: safe_print(f"[Register][{thread_id}][{retry}] Try pass Turnstile for email code page.")
                    self._cursor_turnstile(tab)

            except Exception as e:
                safe_print(f"[Register][{thread_id}] Exception when handling email code page.")
                safe_print(e)

            if tab.wait.url_change(CURSOR_URL, timeout=3):
                break

            tab.refresh()
            # Kill the function since time out 
            if retry == retry_times - 1:
                if enable_register_log: safe_print(f"[Register][{thread_id}] Timeout when inputing email verification code")
                return None

        # Get cookie
        try:
            cookies = tab.cookies().as_dict()
        except e:
            safe_print(f"[Register][{thread_id}] Fail to get cookie.")
            if not enable_browser_log: browser.quit(force=True, del_data=True)
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                safe_print(f"[Register][{thread_id}] Register Account Successfully.")
            else:
                safe_print(f"[Register][{thread_id}] Register Account Failed.")

        if not hide_account_info:
            safe_print(f"[Register] Cursor Email: {email}")
            safe_print(f"[Register] Cursor Token: {token}")

        return {
            'username': email,
            'token': token
        }

    # tab: A tab has signed in 
    def delete_account(self, tab):
        """Delete Cursor account"""
        try:
            # 导航到设置页面
            tab.get(CURSOR_SETTINGS_URL)
            tab.wait(5)  # Wait for page to load
            safe_print(f"[Account Delete][{self.thread_id}] Entered settings page")
            
            # 1. 点击Advanced按钮展开高级选项
            advanced_button = tab.ele("xpath=//div[contains(@class, 'cursor-pointer') and contains(., 'Advanced')]")
            if advanced_button:
                advanced_button.click()
                safe_print(f"[Account Delete][{self.thread_id}] Clicked Advanced button")
                tab.wait(2)
            else:
                safe_print(f"[Account Delete][{self.thread_id}] Advanced button not found")
                return False
                
            # 2. 点击Delete Account按钮
            delete_button = tab.ele("xpath=//button[contains(@class, 'underline') and contains(., 'Delete Account')]")
            if delete_button:
                delete_button.click()
                safe_print(f"[Account Delete][{self.thread_id}] Clicked Delete Account button")
                tab.wait(2)
            else:
                safe_print(f"[Account Delete][{self.thread_id}] Delete Account button not found")
                return False
                
            # 3. 输入确认文本"Delete"
            confirm_input = tab.ele("xpath=//input[@placeholder=\"Type 'Delete' to confirm\"]")
            if confirm_input:
                # 确保输入框是可交互的
                tab.wait(2)  # 等待输入框完全加载
                try:
                    # 先清空输入框
                    confirm_input.clear()
                    tab.wait(0.5)
                    # 逐字符输入以确保稳定性
                    for char in "Delete":
                        confirm_input.input(char, clear=False)
                        tab.wait(0.1)
                    
                    # 验证输入内容
                    input_value = confirm_input.attr('value')
                    if input_value != "Delete":
                        safe_print(f"[Account Delete][{self.thread_id}] Input verification failed. Expected 'Delete', got '{input_value}'")
                        # 重试一次
                        confirm_input.clear()
                        tab.wait(0.5)
                        confirm_input.input("Delete", clear=True)
                        tab.wait(1)
                    
                    safe_print(f"[Account Delete][{self.thread_id}] Entered confirmation text 'Delete'")
                except Exception as e:
                    safe_print(f"[Account Delete][{self.thread_id}] Error during input: {e}")
                    return False
            else:
                safe_print(f"[Account Delete][{self.thread_id}] Confirmation input field not found")
                return False
                
            # 4. 点击最终的Delete按钮
            final_delete_button = tab.ele("xpath=//button[contains(@class, 'bg-brand-black') and .//span[contains(text(), 'Delete')]]")
            if final_delete_button:
                # 检查按钮是否已启用 (aria-disabled="false" 或者属性不存在)
                is_disabled = final_delete_button.attr('aria-disabled') == 'true'
                if is_disabled:
                    # 尝试等待按钮启用
                    safe_print(f"[Account Delete][{self.thread_id}] Waiting for Delete button to be enabled")
                    tab.wait(2)
                    # 再次检查
                    is_disabled = final_delete_button.attr('aria-disabled') == 'true'
                    if is_disabled:
                        safe_print(f"[Account Delete][{self.thread_id}] Delete button is disabled, more confirmation may be needed")
                        return False
                
                final_delete_button.click()
                safe_print(f"[Account Delete][{self.thread_id}] Clicked final Delete button")
                tab.wait(5)  # 等待处理完成
                
                # 验证是否返回到登录页面或首页
                if CURSOR_SIGNIN_URL in tab.url or "sign-in" in tab.url or "cursor.com" in tab.url:
                    safe_print(f"[Account Delete][{self.thread_id}] Account deleted successfully, current URL: {tab.url}")
                    return True
                else:
                    safe_print(f"[Account Delete][{self.thread_id}] Account may not have been deleted, current URL: {tab.url}")
                    return False
            else:
                safe_print(f"[Account Delete][{self.thread_id}] Final Delete button not found")
                return False
                
        except Exception as e:
            safe_print(f"[Account Delete][{self.thread_id}] Exception during account deletion: {e}")
            return False

    def get_cursor_cookie(self, tab):
        try:
            cookies = tab.cookies().as_dict()
        except:
            safe_print(f"[Register][{self.thread_id}] Fail to get cookie.")
            return None

        token = cookies.get('WorkosCursorSessionToken', None)
        if enable_register_log:
            if token is not None:
                safe_print(f"[Register][{self.thread_id}] Register Account Successfully.")
            else:
                safe_print(f"[Register][{self.thread_id}] Register Account Failed.")

        return token

    def _cursor_turnstile(self, tab, retry_times = 5):
        for retry in range(retry_times): # Retry times
            try:
                if enable_register_log: safe_print(f"[Register][{self.thread_id}][{retry}] Passing Turnstile")
                challenge_shadow_root = tab.ele('@id=cf-turnstile').child().shadow_root
                challenge_shadow_button = challenge_shadow_root.ele("tag:iframe", timeout=30).ele("tag:body").sr("xpath=//input[@type='checkbox']")
                if challenge_shadow_button:
                    challenge_shadow_button.click()
                    break
            except:
                pass
            if retry == retry_times - 1:
                safe_print("[Register] Timeout when passing turnstile")

    def _wait_for_new_message(self, queue, timeout=300):
        try:
            data = self.email_server.wait_for_new_message(delay=1, timeout=timeout)
            if data:
                # 打印邮件主题，帮助调试
                if "subject" in data:
                    safe_print(f"Email subject: {data.get('subject', 'Unknown Subject')}")
                
                # 确保text字段存在
                if "text" in data:
                    try:
                        # 处理编码问题
                        data["text"] = data["text"].encode("raw_unicode_escape").decode("utf-8")
                    except:
                        # 如果编码失败，保持原样
                        pass
                    
                    safe_print(f"Email content received: {data['text'][:100]}..." if len(data['text']) > 100 else data['text'])
                else:
                    # 如果text字段不存在，尝试从其他字段提取
                    if "content" in data:
                        data["text"] = data["content"]
                    elif "body_text" in data:
                        data["text"] = data["body_text"]
                    
                    if "text" not in data:
                        safe_print(f"[Warning] Email missing text content, available fields: {list(data.keys())}")
            
            queue.put(copy.deepcopy(data))
        except Exception as e:
            safe_print(f"[Error] Error waiting for email: {e}")
            queue.put(None)

def register_pipeline(options):

    try:
        # Maybe fail to open the browser
        browser = Chromium(options)
    except Exception as e:
        safe_print(e)
        return None

    register = CursorRegister(browser)    
    #email_address = register.email_server.get_email_address()
        
    #account_infos = sign_in(browser)
    tab_signin = register.sign_in("email_address")
    token = register.get_cursor_cookie(tab_signin)

    register.browser.quit(force=True, del_data=True)

    #if not hide_account_info:
    #    safe_print(f"[Register] Cursor Email: {"email"}")
    #    safe_print(f"[Register] Cursor Token: {token}")

    return {
        "token": token
    }

def universal_email_cycle(email, app_password, api_url=None):
    """
    Universal email account cycle flow: login -> delete account -> re-login -> get token -> send to API
    支持多种邮箱服务商，如Gmail, QQ邮箱, 163邮箱等
    
    Parameters:
        email: 邮箱地址
        app_password: 邮箱应用密码
        api_url: Optional, API URL to upload token
    """
    domain = email.split('@')[-1].lower() if '@' in email else "unknown"
    safe_print(f"[Email Cycle] Starting to process email account: {email} (domain: {domain})")

    options = ChromiumOptions()
    options.auto_port()
    options.new_env()
    # Add turnstilePatch extension
    options.add_extension("turnstilePatch")

    # Set headless mode
    if enable_headless: 
        from platform import platform
        if platform == "linux" or platform == "linux2":
            platformIdentifier = "X11; Linux x86_64"
        elif platform == "darwin":
            platformIdentifier = "Macintosh; Intel Mac OS X 10_15_7"
        elif platform == "win32":
            platformIdentifier = "Windows NT 10.0; Win64; x64"
        # Set Chrome version
        chrome_version = "130.0.0.0"        
        options.set_user_agent(f"Mozilla/5.0 ({platformIdentifier}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36")
        options.headless()

    try:
        # Open browser
        browser = Chromium(options)
        safe_print(f"[Email Cycle] Browser launched")
        
        # Pause to ensure time difference for distinguishing old vs new emails
        safe_print(f"[Email Cycle] Pausing for 5 seconds to ensure we can distinguish new emails")
        time.sleep(5)
        
        # 创建通用IMAP客户端
        # email_client = UniversalImap(email, app_password)
        email_client = Imap(email, app_password)
        safe_print(f"[Email Cycle] Universal IMAP client created for {domain}")
        
        # Create register and set email server
        register = CursorRegister(browser)
        register.email_server = email_client
        
        # Step 1: Login with email account
        safe_print(f"[Email Cycle] Starting email login")
        # Confirm email service is set correctly
        safe_print(f"[Email Cycle] Using email: {email}")
        safe_print(f"[Email Cycle] Email service type: {type(register.email_server).__name__}")
        
        tab = register.sign_in(email)
        if not tab:
            safe_print(f"[Email Cycle] Login failed")
            browser.quit(force=True, del_data=True)
            return None
        
        # Get first login token for verification
        first_token = register.get_cursor_cookie(tab)
        if not first_token:
            safe_print(f"[Email Cycle] Failed to get token from first login")
            browser.quit(force=True, del_data=True)
            return None
            
        safe_print(f"[Email Cycle] Login successful, first token: {first_token[:10]}..., preparing to delete account")
        
        # Step 2: Delete account
        delete_success = register.delete_account(tab)
        if not delete_success:
            safe_print(f"[Email Cycle] Account deletion failed")
            browser.quit(force=True, del_data=True)
            return None
        
        safe_print(f"[Email Cycle] Account deleted successfully, preparing to login again")
        
        # Pause to ensure deletion is fully processed
        safe_print(f"[Email Cycle] Pausing 10 seconds to ensure deletion is complete")
        time.sleep(10)
        
        # Step 3: Re-login with the same email client
        # Reset email client to ensure we get new emails
        safe_print(f"[Email Cycle] Creating new Universal IMAP client")
        # email_client = UniversalImap(email, app_password)
        email_client = Imap(email, app_password)
        register.email_server = email_client
        
        tab = register.sign_in(email)
        if not tab:
            safe_print(f"[Email Cycle] Re-login failed")
            browser.quit(force=True, del_data=True)
            return None
        
        # Get token
        token = register.get_cursor_cookie(tab)
        if not token:
            safe_print(f"[Email Cycle] Failed to get token")
            browser.quit(force=True, del_data=True)
            return None
            
        # Verify token has changed, confirming new registration
        if token == first_token:
            safe_print(f"[Email Cycle] Warning: Re-login token is identical to first token, account may not have been deleted")
        else:
            safe_print(f"[Email Cycle] Successfully obtained new token: {token[:10]}...")
        
        safe_print(f"[Email Cycle] Successfully obtained token")
        # Upload token to API if provided
        if api_url:
            try:
                from tokenManager.custom_api_manager import CustomAPIManager
                custom_api = CustomAPIManager(api_url)
                response = custom_api.upload_tokens(token,email,app_password)
                
                # Safely get response content
                try:
                    if response.content and len(response.content.strip()) > 0:
                        response_json = response.json()
                        safe_print(f'[Custom-API] Upload token. Status code: {response.status_code}, Response: {response_json}')
                    else:
                        safe_print(f'[Custom-API] Upload token. Status code: {response.status_code}, Response is empty')
                except Exception as e:
                    safe_print(f'[Custom-API] Upload token. Status code: {response.status_code}, Unable to parse response: {str(response.content)[:100]}')
                    safe_print(f'[Custom-API] Response parsing error: {e}')
            except Exception as e:
                safe_print(f'[Custom-API] Error uploading token: {e}')
                # Continue execution without interrupting the flow
        
        # Close browser
        browser.quit(force=True, del_data=True)
        
        result = {
            "email": email,
            "token": token
        }
        
        # Save results to file
        formatted_date = datetime.now().strftime("%Y-%m-%d")
        csv_file = f"./email_output_{formatted_date}.csv"
        
        with open(csv_file, 'a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=["email", "token"])
            writer.writerow(result)
            
        return result
        
    except Exception as e:
        safe_print(f"[Email Cycle] Exception during execution: {e}")
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
    
    # 邮箱循环命令
    parser.add_argument('--email-cycle',action='store_true', help='使用邮箱账户循环注册')
    parser.add_argument('--email', type=str, required=True, help='邮箱地址')
    parser.add_argument('--password', type=str, required=True, help='邮箱应用密码')
    parser.add_argument('--api', type=str, help='上传token的API URL')
    
    args = parser.parse_args()
    number = args.number
    max_workers = args.max_workers
    use_oneapi = args.oneapi
    oneapi_url = args.oneapi_url
    oneapi_token = args.oneapi_token
    oneapi_channel_url = args.oneapi_channel_url

    use_custom_api = args.custom_api
    api_url = args.api_url
    
    # Email循环流程选项
    use_email_cycle = args.email_cycle
    email_account = args.email
    email_password = args.password

    # 如果启用Email账户循环
    if use_email_cycle:
        if not email_account or not email_password:
            safe_print("[Error] Email address and app password are required")
        else:
            safe_print(f"[Email Cycle] Starting Email account cycle flow")
            result = universal_email_cycle(email_account, email_password, api_url if use_custom_api else None)
            if result:
                safe_print(f"[Email Cycle] Flow completed successfully")
            else:
                safe_print(f"[Email Cycle] Flow execution failed")
    # 否则使用常规注册流程
    else:
        safe_print(f"[Register] Start to register {number} accounts in {max_workers} threads")
        account_infos = register_cursor(number, max_workers)
        tokens = list(set([row['token'] for row in account_infos]))
        safe_print(f"[Register] Register {len(tokens)} accounts successfully")
        
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
                safe_print(f'[OneAPI] Add Channel Request For Batch {idx}. Status Code: {response.status_code}, Response Body: {response.json()}')
        elif use_custom_api and len(account_infos) > 0:
            from tokenManager.custom_api_manager import CustomAPIManager
            custom_api = CustomAPIManager(api_url)
            for token in tokens:
                response = custom_api.upload_tokens(token,'','')
                safe_print(f'[Custom-API] Upload Token. Status Code: {response.status_code}, Response Body: {response.json()}')
            safe_print(f"[Custom-API] Upload {len(tokens)} tokens successfully")
