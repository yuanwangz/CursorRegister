#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
邮箱调试工具：获取指定邮箱的未读邮件数量和最近一封未读邮件的详细信息
"""

import argparse
import time
import imaplib
import email
from email.policy import default
import sys
import re
import json
from datetime import datetime

# 邮箱服务配置，根据域名映射到对应的IMAP服务器
EMAIL_SERVER_CONFIG = {
    # 常见邮箱服务的IMAP服务器配置
    "gmail.com": {"imap_server": "imap.gmail.com", "port": 993},
    "qq.com": {"imap_server": "imap.qq.com", "port": 993},
    "vip.qq.com": {"imap_server": "imap.qq.com", "port": 993},
    "foxmail.com": {"imap_server": "imap.qq.com", "port": 993},
    "163.com": {"imap_server": "imap.163.com", "port": 993},
    "126.com": {"imap_server": "imap.126.com", "port": 993},
    "outlook.com": {"imap_server": "outlook.office365.com", "port": 993},
    "hotmail.com": {"imap_server": "outlook.office365.com", "port": 993},
    "yahoo.com": {"imap_server": "imap.mail.yahoo.com", "port": 993},
    # 可以根据需求添加更多邮箱服务商配置
}

# 默认IMAP服务器配置
DEFAULT_IMAP_CONFIG = {"imap_server": "imap.gmail.com", "port": 993}


def safe_print(*args, **kwargs):
    """
    处理编码错误的安全打印函数
    """
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # 尝试将非ASCII字符替换为ASCII近似值
        new_args = []
        for arg in args:
            if isinstance(arg, str):
                try:
                    new_args.append(arg.encode('ascii', 'replace').decode('ascii'))
                except:
                    new_args.append("<non-ASCII text>")
            else:
                new_args.append(str(arg))
        
        try:
            print(*new_args, **kwargs)
        except:
            print("<打印信息出错>")


def extract_domain(email_address):
    """从邮箱地址中提取域名部分"""
    if '@' in email_address:
        return email_address.split('@')[-1].lower()
    return "gmail.com"  # 默认域名


def get_server_config(domain):
    """根据域名获取对应的IMAP服务器配置"""
    return EMAIL_SERVER_CONFIG.get(domain, DEFAULT_IMAP_CONFIG)


def get_email_body(msg):
    """提取邮件正文内容"""
    content = ""
    if msg.is_multipart():
        # 处理多部分邮件
        for part in msg.get_payload():
            if part.get_content_type() == 'text/plain':
                try:
                    content += part.get_payload(decode=True).decode('utf-8', errors='ignore')
                except:
                    content += part.get_payload(decode=True).decode('latin-1', errors='ignore')
    else:
        # 处理单部分邮件
        try:
            content = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
        except:
            content = msg.get_payload(decode=True).decode('latin-1', errors='ignore')
    
    return content


def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='邮箱调试工具：获取未读邮件数量和最新未读邮件详情')
    parser.add_argument('-e', '--email', required=True, help='邮箱地址')
    parser.add_argument('-p', '--password', required=True, help='邮箱密码或应用密码')
    parser.add_argument('-f', '--folder', default='INBOX', help='要检查的邮件文件夹 (默认: INBOX)')
    parser.add_argument('-j', '--json', action='store_true', help='以JSON格式输出结果')
    args = parser.parse_args()

    email_address = args.email
    password = args.password
    folder = args.folder

    # 获取IMAP服务器配置
    domain = extract_domain(email_address)
    server_config = get_server_config(domain)
    
    imap_server = server_config["imap_server"]
    port = server_config["port"]
    
    safe_print(f"连接到IMAP服务器: {imap_server}:{port}, 邮箱: {email_address}")
    
    try:
        # 连接到IMAP服务器
        mail = imaplib.IMAP4_SSL(imap_server, port)
        mail.login(email_address, password)
        safe_print(f"登录成功")
        
        # 选择邮件文件夹
        result, data = mail.select(folder)
        if result != 'OK':
            safe_print(f"选择文件夹 '{folder}' 失败: {data}")
            mail.logout()
            sys.exit(1)
            
        # 获取未读邮件数量
        result, data = mail.search(None, 'UNSEEN')
        unseen_emails = data[0].split()
        unseen_count = len(unseen_emails)
        
        email_info = {
            "邮箱": email_address,
            "IMAP服务器": imap_server,
            "未读邮件数量": unseen_count,
            "最新未读邮件": None
        }
        
        if unseen_count > 0:
            # 获取最新的未读邮件
            latest_id = unseen_emails[-1]
            result, data = mail.fetch(latest_id, '(RFC822)')
            
            if result == 'OK':
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email, policy=default)
                
                # 提取邮件信息
                sender = msg.get('From', '')
                subject = msg.get('Subject', '')
                date = msg.get('Date', '')
                to = msg.get('To', '')
                content = get_email_body(msg)
                
                # 获取邮件ID和UID
                email_id = latest_id.decode('utf-8')
                result, data = mail.fetch(latest_id, '(UID)')
                uid = None
                if result == 'OK' and data[0]:
                    uid_match = re.search(r'UID (\d+)', data[0].decode('utf-8'))
                    if uid_match:
                        uid = uid_match.group(1)
                
                latest_email = {
                    "ID": email_id,
                    "UID": uid,
                    "发件人": sender,
                    "收件人": to,
                    "主题": subject,
                    "日期": date,
                    "内容长度": len(content),
                    "内容预览": content[:200] + ('...' if len(content) > 200 else '')
                }
                
                email_info["最新未读邮件"] = latest_email
        
        # 输出结果
        if args.json:
            print(json.dumps(email_info, ensure_ascii=False, indent=2))
        else:
            safe_print("-" * 50)
            safe_print(f"邮箱: {email_address}")
            safe_print(f"IMAP服务器: {imap_server}")
            safe_print(f"未读邮件数量: {unseen_count}")
            
            if email_info["最新未读邮件"]:
                latest = email_info["最新未读邮件"]
                safe_print("\n最新未读邮件详情:")
                safe_print(f"ID: {latest['ID']}, UID: {latest['UID']}")
                safe_print(f"发件人: {latest['发件人']}")
                safe_print(f"收件人: {latest['收件人']}")
                safe_print(f"主题: {latest['主题']}")
                safe_print(f"日期: {latest['日期']}")
                safe_print(f"内容长度: {latest['内容长度']} 字符")
                safe_print("\n内容预览:")
                safe_print("-" * 50)
                safe_print(latest['内容预览'])
                safe_print("-" * 50)
            else:
                safe_print("\n没有未读邮件")
            
        # 退出
        mail.close()
        mail.logout()
        
    except imaplib.IMAP4.error as e:
        safe_print(f"IMAP错误: {e}")
        sys.exit(1)
    except Exception as e:
        safe_print(f"发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 