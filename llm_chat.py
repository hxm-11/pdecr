import os
from fastapi import APIRouter, Body
from pydantic import BaseModel
import openai
from dotenv import load_dotenv

# 加载 .env 文件中的 OPENAI_API_KEY
load_dotenv()

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

@router.post('/llm_chat')
async def llm_chat(data: ChatRequest):
    openai.api_key = os.getenv('OPENAI_API_KEY')
    try:
        completion = openai.ChatCompletion.create(
            model='gpt-4-1106-preview',  # 可根据你的账号和额度调整此模型名
            messages=[{'role': 'user', 'content': data.message}],
            max_tokens=512,
            temperature=0.7,
        )
        reply = completion.choices[0].message.content
        return {'reply': reply}
    except Exception as e:
        return {'error': str(e)}
