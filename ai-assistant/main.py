import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from vector_store import top_k_similar

# 加载环境变量
load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY1"),
    base_url=os.getenv("OPENAI_BASE_URL1")
)

knowledge_texts = []
knowledge_vectors = []


def build_vector_store():
    global knowledge_texts, knowledge_vectors

    if os.path.exists("vector_store.json"):
        print("检测到已有向量缓存，正在加载...")
        with open("vector_store.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        knowledge_texts = data["texts"]
        knowledge_vectors = data["vectors"]
        print("向量加载完成")
        return

    with open("knowledge.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    knowledge_texts = [line.strip() for line in lines if line.strip()]
    knowledge_vectors = []
    print("正在生成知识库向量。。。")
    for text in knowledge_texts:
        embedding = get_embedding(text)
        knowledge_vectors.append(embedding)
    print("知识库向量生成完成，正在保存...")

    with open("vector_store.json", "w", encoding="utf-8") as f:
        json.dump({
            "texts": knowledge_texts,
            "vectors": knowledge_vectors
        }, f, ensure_ascii=False)

    print("向量已缓存到本地")


# 初始化对话历史
def init_conversation():
    return [
        {"role": "system",
         "content": "你是一个专业的AI助手。"
         },
    ]


conversation_history = init_conversation()


def chat_with_model(message):
    global conversation_history

    # 检索知识
    retrieve_text = retrieve_knowledge(message)

    print("检索结果:", retrieve_text)

    # if retrieve_text:
    #     enhanced_message = f"""
    #     你必须只根据下面提供的知识回答问题。如果知识中没有相关内容，请回答：无法从知识库中找到答案。
    #     以下是相关知识:
    #     {retrieve_text}
    #
    #     请根据提供的知识，回答问题：
    #     {message}
    #     """
    # else:
    #     enhanced_message = message
    enhanced_message = f"""
    你必须只根据下面提供的知识回答问题。如果知识中没有相关内容，请回答：无法从知识库中找到答案。
    以下是相关知识:
    {retrieve_text}     
    请根据提供的知识，回答问题：
    {message}
    """

    # 添加用户输入
    conversation_history.append({"role": "user", "content": enhanced_message})

    response = client.chat.completions.create(
        model="deepseek-chat",
        # messages=[
        #     {"role": "system", "content": "你是一个专业的AI助手。"},
        #     {"role": "user", "content": message}
        # ],
        messages=conversation_history,
        temperature=0.7,
    )

    reply = response.choices[0].message.content

    conversation_history.append({"role": "assistant", "content": reply})

    return reply


def save_conversation():
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"conversation_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(conversation_history, f, ensure_ascii=False, indent=4)
    print(f"保存对话到文件：{filename}")


# def retrieve_knowledge(query):
#     with open("knowledge.txt", "r", encoding="utf-8") as f:
#         lines = f.readlines()
#     # 简单关键词匹配
#     relevant_lines = []
#
#     keywords = query.replace("?", "").replace("？", "").split("是谁")
#     for line in lines:
#         for word in keywords:
#             if word.strip() and word.strip() in line:
#                 relevant_lines.append(line.strip())
#     return "\n".join(relevant_lines)
def retrieve_knowledge(query):
    query_vec = get_embedding(query)

    top_texts = top_k_similar(
        query_vec,
        knowledge_vectors,
        knowledge_texts,
        k=3
    )

    return "\n".join(top_texts)


def get_embedding(text):
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


if __name__ == "__main__":
    print("AI已启动（输入 /exit 退出，/clear 清空, /save 保存）")
    build_vector_store()
    while True:
        user_input = input("你：")

        if user_input == "/exit":
            print("再见！")
            break
        elif user_input == "/clear":
            conversation_history = init_conversation()
            print("上下文已清空")
            continue
        elif user_input == "/save":
            save_conversation()
            continue
        elif user_input == "/help":
            print("可用命令：/exit 退出，/clear 清空, /save 保存")
        elif user_input == "/reset":
            conversation_history = init_conversation()
            print("对话已重置")

        reply = chat_with_model(user_input)
        print("AI：", reply)
