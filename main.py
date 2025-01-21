import lark_oapi as lark
from lark_oapi.api.im.v1 import *
import requests
import json
from cachetools import TTLCache

# 配置 LLM 服务的地址和 API 密钥
LLM_SERVICE_URL = "http://10.68.14.177:5001/v1/chat-messages"
LLM_API_KEY = "app-uNN7p6Eq12Nnx9wzVUIqPOuF"  # 替换为实际的 API 密钥

# 创建一个缓存，最大存储 10000 条消息，条目有效期为 1 小时
processed_messages = TTLCache(maxsize=10000, ttl=3600)  # TTL 单位为秒

# 注册接收消息事件，处理接收到的消息。
# Register event handler to handle received messages.
# https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/reference/im-v1/message/events/receive
def do_p2_im_message_receive_v1(data: P2ImMessageReceiveV1) -> None:
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

    # 调用 LLM 服务
    try:
        # 构建请求体
        payload = {
            "query": res_content,
            "inputs": {},  # 可选的变量值
            "response_mode": "blocking",  # 使用阻塞模式
            "conversation_id": "",  # 如需保持会话上下文，可填入实际会话ID
            "user": user_id  # 用于标识用户，可替换为动态用户ID
        }

        # 发送请求
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json"
        }
        llm_response = requests.post(
            LLM_SERVICE_URL,
            headers=headers,
            json=payload,
            timeout=120  # 超时时间
        )
        llm_response.raise_for_status()  # 如果响应状态码不为 2xx，将引发异常
        response_data = llm_response.json()
        llm_reply = response_data.get("answer", "LLM 无法处理你的请求")
    except Exception as e:
        llm_reply = f"调用 LLM 服务失败: {str(e)}"

    # 将 LLM 回复作为内容
    content = json.dumps({
        "text": f"机器人回复：\n{llm_reply}"
    })

    if data.event.message.chat_type == "p2p":
        request = (
            CreateMessageRequest.builder()
            .receive_id_type("chat_id")
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(data.event.message.chat_id)
                .msg_type("text")
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
                .msg_type("text")
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
)


def main():
    #  启动长连接，并注册事件处理器。
    #  Start long connection and register event handler.
    wsClient.start()


if __name__ == "__main__":
    main()
