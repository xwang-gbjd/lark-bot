import lark_oapi as lark
from lark_oapi.api.im.v1 import *
import requests
import json
from cachetools import TTLCache
import threading
import time

# 配置 LLM 服务的地址和 API 密钥
LLM_SERVICE_URL = "http://10.68.14.177:5001/v1/chat-messages"
LLM_API_KEY = "app-uNN7p6Eq12Nnx9wzVUIqPOuF"  # 替换为实际的 API 密钥

# 创建一个缓存，最大存储 10000 条消息，条目有效期为 1 小时
processed_messages = TTLCache(maxsize=10000, ttl=3600)  # TTL 单位为秒

# 创建一个缓存来存储用户的会话ID，设置7天过期
user_conversations = TTLCache(maxsize=10000, ttl=7*24*3600)

# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
    # 创建一个新线程来处理消息
    thread = threading.Thread(target=handle_message, args=(data,))
    thread.start()

def send_waiting_message(data: P2ImMessageReceiveV1):
    waiting_content = json.dumps({
        "zh_cn": {
            "title": "智能体思考中",
            "content": [[{
                "tag": "text",
                "text": "🤔 正在思考中，请稍候..."
            }]]
        }
    })
    
    if data.event.message.chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("post")
                .content(waiting_content)
                .build()
            )
            .build()
        )
        response = client.im.v1.chat.create(request)
    else:
        request = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(waiting_content)
                .msg_type("post")
                .build()
            )
            .build()
        )
        response = client.im.v1.message.reply(request)

def handle_message(data: P2ImMessageReceiveV1) -> None:
    message_id = data.event.message.message_id
    user_id = data.event.sender.sender_id.user_id

    # 检查消息是否已经处理
    if message_id in processed_messages:
        print(f"消息已处理，跳过: {message_id}")
        return
    processed_messages[message_id] = True  # 记录消息

    res_content = ""
    if data.event.message.message_type == "text":
        res_content = json.loads(data.event.message.content)["text"]
    else:
        res_content = "解析消息失败，请发送文本消息\nparse message failed, please send text message"

    # 创建一个事件对象用于控制定时器
    timer_event = threading.Event()
    
    # 创建定时器线程
    timer = threading.Timer(5.0, lambda: None if timer_event.is_set() else send_waiting_message(data))
    timer.start()

    try:
        # 获取现有的conversation_id，如果不存在则为空字符串
        current_conversation_id = user_conversations.get(user_id, "")
        
        # 调用 LLM 服务
        payload = {
            "query": res_content,
            "inputs": {},
            "response_mode": "blocking",
            "conversation_id": current_conversation_id,
            "user": user_id
        }

        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        llm_response = requests.post(
            LLM_SERVICE_URL,
            headers=headers,
            json=payload,
            timeout=120
        )
        # 设置事件，阻止发送等待消息
        timer_event.set()
        timer.cancel()  # 取消定时器
        
        llm_response.raise_for_status()
        response_data = llm_response.json()
        print(response_data)
        # 保存新的conversation_id
        if "conversation_id" in response_data:
            user_conversations[user_id] = response_data["conversation_id"]
        
        llm_reply = response_data.get("answer", "LLM 无法处理你的请求")
    except Exception as e:
        timer_event.set()
        timer.cancel()  # 取消定时器
        llm_reply = f"调用 LLM 服务失败: {str(e)}"

    # 将 LLM 回复作为内容
    content = json.dumps({
        "zh_cn": {
            "title": "智能体回复",
            "content": [[{
                "tag": "md",
                "text": llm_reply
            }]]
        }
    })

    if data.event.message.chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("post")
                .content(content)
                .build()
            )
            .build()
        )
        # 使用OpenAPI发送消息
        # Use send OpenAPI to send messages
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/create
        response = client.im.v1.chat.create(request)

        if not response.success():
            raise Exception(
                f"client.im.v1.chat.create failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )
    else:
        request: ReplyMessageRequest = (
            ReplyMessageRequest.builder()
            .message_id(data.event.message.message_id)
            .request_body(
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type("post")
                .build()
            )
            .build()
        )
        # 使用OpenAPI回复消息
        # Reply to messages using send OpenAPI
        # https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/reply
        response: ReplyMessageResponse = client.im.v1.message.reply(request)
        if not response.success():
            raise Exception(
                f"client.im.v1.message.reply failed, code: {response.code}, msg: {response.msg}, log_id: {response.get_log_id()}"
            )


# 注册事件回调
# Register event handler.
event_handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
    .build()
)


# 创建 LarkClient 对象，用于请求OpenAPI, 并创建 LarkWSClient 对象，用于使用长连接接收事件。
# Create LarkClient object for requesting OpenAPI, and create LarkWSClient object for receiving events using long connection.
client = lark.Client.builder().app_id(lark.APP_ID).app_secret(lark.APP_SECRET).build()
wsClient = lark.ws.Client(
    lark.APP_ID,
    lark.APP_SECRET,
    event_handler=event_handler,
    log_level=lark.LogLevel.DEBUG,
    auto_reconnect=True  # 确保启用自动重连
)


def main():
    #  启动长连接，并注册事件处理器。
    #  Start long connection and register event handler.
    wsClient.start()


if __name__ == "__main__":
    main()
