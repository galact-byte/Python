import requests

# ======= 配置 =======
API_URL = "xxxx"
API_KEY = "xxxxx"  # ← 可以改成你自己的

# ======= 主函数 =======
def chat_with_model(prompt: str):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": "gemini-2.5-flash",  # 如果接口不支持可删掉
        "messages": [
            {"role": "system", "content": "你是一个有帮助的AI助手"},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500
    }

    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=60)
        response.raise_for_status()
        res_json = response.json()

        # 不同平台返回结构可能略不同
        if "choices" in res_json:
            content = res_json["choices"][0]["message"]["content"]
        elif "output" in res_json:
            content = res_json["output"]
        else:
            content = str(res_json)

        return content.strip()

    except requests.exceptions.RequestException as e:
        return f"❌ 请求出错：{e}"
    except Exception as e:
        return f"⚠️ 解析出错：{e}"

# ======= 运行部分 =======
if __name__ == "__main__":
    print("💬 连接到模型接口成功，输入内容开始对话（输入 exit 退出）")
    while True:
        user_input = input("你：")
        if user_input.strip().lower() in {"exit", "quit"}:
            print("👋 再见！")
            break
        reply = chat_with_model(user_input)
        print("AI：", reply)
