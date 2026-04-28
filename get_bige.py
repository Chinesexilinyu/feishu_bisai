import requests
import json


def get_feishu_tenant_token():
    # 替换为你的飞书应用凭证
    app_id= "cli_a965beb89978dbd5"
    app_secret= "rZRmQVDAN7YHA24aNcyj52yBtoxOwgIY"

    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"

    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers)
        result = response.json()

        if result.get("code") == 0:
            print("获取成功！")
            print(f"Tenant Access Token: {result.get('tenant_access_token')}")
            print(f"有效期 (秒): {result.get('expire')}")
            return result.get('tenant_access_token')
        else:
            print(f"获取失败，错误信息: {result}")
            return None

    except Exception as e:
        print(f"请求发生错误: {e}")
        return None


if __name__ == "__main__":
    # 执行函数
    get_feishu_tenant_token()