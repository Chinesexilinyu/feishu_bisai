#!/usr/bin/env python3
"""命令行交互入口，无需手动输入curl命令"""

import sys
import requests
import json
from typing import Dict

API_BASE = "http://localhost:8000"

def print_banner():
    print("=" * 70)
    print("🔥 Agent身份与权限系统 命令行交互工具 v2.0")
    print("=" * 70)

def print_main_menu():
    print("\n📋 功能菜单：")
    print("1. 📊 生成番茄小说数据分析报告（完整Agent协作流程）")
    print("2. 🔍 生成包含指定小说网络热度的分析报告")
    print("3. 🔒 测试越权访问拦截功能")
    print("4. 📝 查询审计日志（按Trace ID）")
    print("5. ℹ️  查看当前Agent权限配置说明")
    print("6. ❌ 退出程序")
    print("-" * 70)

def print_agent_permissions():
    """打印Agent权限配置说明"""
    print("\n📋 三个Agent的职责与权限说明：")
    print("\n🤖 文档助手Agent (doc-assistant) | 角色：协调者")
    print("✅ 权限：生成报告、委托其他Agent、读写飞书文档")
    print("❌ 禁止：直接读取内部多维表格、访问外部网络")
    print("-" * 50)
    print("\n🤖 企业数据Agent (data-agent) | 角色：数据访问者")
    print("✅ 权限：读取/写入飞书多维表格、通讯录、日历等内部数据")
    print("❌ 禁止：访问外部网络、委托其他Agent、直接写入飞书文档")
    print("-" * 50)
    print("\n🤖 外部检索Agent (web-agent) | 角色：外部检索者")
    print("✅ 权限：网络搜索、网页抓取公开信息")
    print("❌ 禁止：访问任何内部资源、委托其他Agent")
    print("-" * 70)

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

def query_audit_log(trace_id: str) -> Dict:
    """查询审计日志"""
    url = f"{API_BASE}/api/audit/trace/{trace_id}"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except Exception as e:
        return {"success": False, "error": str(e), "code": 500}

def main():
    print_banner()
    print("💡 提示：直接输入自然语言指令即可执行，输入 'help' 查看功能列表，输入 'exit' 退出")
    print("=" * 70)
    
    # 默认用户信息
    user_info = {
        "user_id": "user-001",
        "user_name": "张三",
        "user_role": "admin"
    }
    
    while True:
        try:
            user_input = input("\n请输入指令：").strip()
        except KeyboardInterrupt:
            print("\n再见！")
            sys.exit(0)
        
        if not user_input:
            continue
        
        user_input_lower = user_input.lower()
        
        if user_input_lower in ["exit", "quit", "q"]:
            print("再见！")
            sys.exit(0)
        
        if user_input_lower == "help":
            print("\n📋 支持的指令示例：")
            print("• 帮我生成番茄小说数据分析报告")
            print("• 帮我生成包含都市风云网络热度的分析报告")
            print("• 测试越权访问内部数据")
            print("• 查询审计日志 6916afe8-cd84-4bf9-aeb5-3c7b1cc4ecdc")
            print("• 查看Agent权限说明")
            print("• help 显示帮助信息")
            print("• exit 退出程序")
            continue
        
        if "查看权限" in user_input or "agent权限" in user_input:
            print_agent_permissions()
            continue
        
        if "查询审计日志" in user_input or "trace id" in user_input_lower:
            # 提取Trace ID
            import re
            trace_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', user_input, re.IGNORECASE)
            if trace_match:
                trace_id = trace_match.group(1)
                print(f"\n📝 正在查询Trace ID: {trace_id} 的审计日志...")
                result = query_audit_log(trace_id)
            else:
                trace_id = input("请输入Trace ID：").strip()
                if trace_id:
                    result = query_audit_log(trace_id)
                else:
                    print("❌ 未检测到Trace ID！")
                    continue
        
        elif "越权" in user_input or "测试访问内部" in user_input or "尝试读取表格" in user_input:
            print("\n🔒 正在执行越权访问测试...")
            result = call_unauthorized_test()
        
        else:
            # 自然语言指令直接执行
            print(f"\n🚀 正在执行指令：{user_input}")
            result = call_nl_api(**user_info, instruction=user_input)
        
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
