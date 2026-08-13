import asyncio
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings

async def test():
    llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    google_api_key=settings.GEMINI_API_KEY,
)
    response = await llm.ainvoke("Say hello")
    print(response.content)

asyncio.run(test())