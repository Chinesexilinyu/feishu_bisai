#!/usr/bin/env python3
"""命令行交互入口，无需手动输入curl命令"""

import sys
import requests
import json
from typing import Dict

API_BASE = "http://localhost:8000"

def print_banner():
    print("=" * 60)
    print("🔥 Agent身份与权限系统 命令行交互工具")
    print("=" * 60)
    print("支持的指令示例：")
    print("1. 帮我生成番茄小说数据分析报告")
    print("2. 帮我生成报告，包含都市风云的网络热度和评论信息")
    print("3. 测试越权访问：尝试让外部Agent读取内部数据")
    print("4. 输入 exit 退出程序")
    print("=" * 60)

def call_nl_api(user_id: str, user_name: str, user_role: str, instruction: str) -> Dict:
    """调用自然语言执行接口"""
    url = f"{API_BASE}/api/nl-execute"
    payload = {
        "user_id": user_id,
        "user_name": user_name,
        "user_role": user_role,
        "instruction": instruction
    }
    try:
        response = requests.post(url, json=payload, timeout=60)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e), "code": 500}

def call_unauthorized_test() -> Dict:
    """调用越权测试接口"""
    url = f"{API_BASE}/api/try-access-internal"
    try:
        response = requests.post(url, timeout=30)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e), "code": 500}

def main():
    print_banner()
    
    # 默认用户信息
    user_info = {
        "user_id": "user-001",
        "user_name": "张三",
        "user_role": "admin"
    }
    
    while True:
        try:
            instruction = input("\n请输入指令：").strip()
        except KeyboardInterrupt:
            print("\n再见！")
            sys.exit(0)
        
        if not instruction:
            continue
        
        if instruction.lower() in ["exit", "quit", "q"]:
            print("再见！")
            sys.exit(0)
        
        if "越权" in instruction or "测试访问内部" in instruction or "尝试读取表格" in instruction:
            print("\n🔍 正在执行越权访问测试...")
            result = call_unauthorized_test()
        else:
            print(f"\n🚀 正在执行指令：{instruction}")
            result = call_nl_api(**user_info, instruction=instruction)
        
        # 打印结果
        print("\n📌 执行结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        if result.get("success"):
            if "report_url" in result.get("data", {}):
                print(f"\n✅ 报告生成成功！访问地址：{result['data']['report_url']}")
            print("\n✅ 执行成功！")
        else:
            print(f"\n❌ 执行失败：{result.get('error', '未知错误')}")
            print(f"错误码：{result.get('code')}")
        
        if result.get("trace_id"):
            print(f"Trace ID：{result['trace_id']}，可用于查询审计日志")

if __name__ == "__main__":
    main()
