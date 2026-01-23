import os
import json
import requests
import base64
from datetime import datetime
from dotenv import load_dotenv
import operator
from typing import TypedDict, Annotated, List

# OpenAI 및 LangChain 관련 임포트
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

# 일반 OpenAI 클라이언트 (analyze_food용)
client = OpenAI(api_key=OPENAI_API_KEY)

# =========================================================
# 1. 도구(Tool) 정의 - LangChain @tool 데코레이터 사용
# =========================================================
@tool
def search_restaurants(location: str, menu_keyword: str):
    """
    특정 지역의 식당이나 메뉴를 카카오맵에서 검색합니다.
    location: 검색할 지역 (예: 강남역, 홍대)
    menu_keyword: 검색할 메뉴 (예: 샐러드, 한식)
    """
    if not KAKAO_API_KEY:
        return "Error: 카카오 API 키가 없습니다."

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    query = f"{location} {menu_keyword}".strip()
    
    try:
        response = requests.get(url, headers=headers, params={"query": query, "size": 3})
        if response.status_code == 200:
            docs = response.json().get('documents', [])
            if not docs:
                return "NOT_FOUND: 검색 결과가 없습니다."
            
            # AI가 읽기 좋게 문자열로 요약해서 반환
            results = []
            for doc in docs:
                results.append(f"이름: {doc['place_name']}, URL: {doc['place_url']}, 카테고리: {doc['category_name']}")
            return "\n".join(results)
        else:
            return f"API 호출 에러: {response.status_code}"
    except Exception as e:
        return f"검색 중 에러 발생: {e}"

# =========================================================
# 2. 식단 분석 함수 (기존 코드 유지)
# =========================================================
ANALYSIS_PROMPT = """
당신은 당뇨/다이어트 전문 영양사입니다. 입력된 음식을 분석하여 JSON으로 반환하세요.(한국어로 설명할것)
포맷: {"food_name": "...", "blood_sugar_level": "...", "summary": "...", "action_guide": "...", "alternatives": "..."}
"""

def analyze_food(text_input: str = None, image_bytes: bytes = None, user_profile: dict = None):
    messages = [{"role": "system", "content": ANALYSIS_PROMPT}]
    
    if user_profile:
        messages[0]["content"] += f"\n[사용자 정보] {user_profile}"

    user_content = []
    if text_input: user_content.append({"type": "text", "text": text_input})
    if image_bytes:
        b64_img = base64.b64encode(image_bytes).decode('utf-8')
        user_content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}})
    
    messages.append({"role": "user", "content": user_content})

    try:
        res = client.chat.completions.create(model="gpt-4o", messages=messages, max_tokens=600)
        content = res.choices[0].message.content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Analyze Error: {e}")
        return {"food_name": "Error", "blood_sugar_level": "알 수 없음", "summary": "분석 실패"}

# =========================================================
# 3. LangGraph 상태 및 노드 정의 
# =========================================================
class AgentState(TypedDict):
    messages: Annotated[List, operator.add]
    user_profile: dict
    current_time: str

# LangChain LLM 초기화
llm = ChatOpenAI(model="gpt-4o", temperature=0.7)
llm_with_tools = llm.bind_tools([search_restaurants])

def chatbot_node(state: AgentState):
    """메인 챗봇 노드"""
    profile = state["user_profile"]
    now = state["current_time"]
    
    system_msg = f"""
    당신은 센스 있고 현실적인 AI 영양사 '오늘뭐먹지.ai'입니다.
    현재 시간: {now}
    사용자 정보: [당뇨: {profile.get('diabetes_type', '정보 없음')}, 목표: {profile.get('health_goal', '건강 관리')}]
    
    [Step 1: 시간대 및 의도 파악 (우선순위 1위)]
    1. **사용자의 발화(의도)**를 최우선으로 따르세요. (예: 낮 12시라도 "야식 추천해줘"라면 야식 규칙 적용)
    2. 언급이 없으면 [현재 시간]을 기준으로 판단하세요.
    
    [Step 2: 메뉴 선정 규칙 (샐러드 봇 금지!)]
    - **아침**: 뇌를 깨우는 가벼운 탄수화물+단백질 (그릭요거트, 오트밀, 샌드위치).
    - **점심/저녁 (식사 시간)**: 
       👉 **무조건 샐러드만 추천하지 마세요! 맛있는 음식을 원합니다.**
       - 한식: 비빔밥(현미), 생선구이 정식, 쌈밥, 순두부찌개, 추어탕, 샤브샤브.
       - 일식: 회덮밥, 초밥(밥 적게), 맑은 지리탕.
       - 고기: 오리고기, 보쌈/수육, 닭백숙.
       - *직전 끼니가 면/빵이었다면 한식 정식을 우선 추천하세요.*
    - **야식/심야 (21시 이후)**:
       👉 **여기서는 '식사 메뉴' 추천을 멈추세요.**
       - 🚨 경고: 비빔밥, 국밥, 정식 등은 혈당/수면에 치명적입니다. 절대 추천하지 마세요.
       - 추천: 따뜻한 우유/두유, 연두부, 오이/당근 스틱, 삶은 계란, 토마토.

    [Step 3: 검색 키워드 선정 및 도구 사용]
    1. 사용자가 장소를 말하면 `search_restaurants` 도구를 실행하세요.
    2. **키워드 선정 주의**: 검색 결과가 잘 나오도록 **상위 카테고리**를 사용하세요.
       - (X) '완정역 연어 스테이크' -> (O) '완정역 생선구이' 또는 '완정역 일식'
       - (X) '강남역 곤약 떡볶이' -> (O) '강남역 키토' 또는 '강남역 샐러드'
    3. 야식 질문에는 식당 검색보다는 '편의점 메뉴'나 '집에서 먹을 메뉴'를 제안하는 게 나을 수 있습니다.
    
    [Step 4: 예외 처리]
    - 도구 결과가 "NOT_FOUND"라면 솔직하게 말하고, 주변에 있을 법한 다른 건강 메뉴(예: 서브웨이, 국밥집 등)를 대안으로 제시하세요.
    - 도구 결과의 URL을 `[식당명](URL)` 형태로 링크를 거세요.
    """
    
    messages = [SystemMessage(content=system_msg)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def tool_node(state: AgentState):
    """도구 실행 노드"""
    last_message = state["messages"][-1]
    if not last_message.tool_calls:
        return {}

    results = []
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "search_restaurants":
            print(f"🛠️ [LangGraph] 도구 실행: {tool_call['args']}")
            res = search_restaurants.invoke(tool_call["args"])
            results.append(ToolMessage(tool_call_id=tool_call["id"], content=str(res)))
            
    return {"messages": results}

def safety_check_node(state: AgentState):
    """(Self-Correction) 당뇨 환자 안전 검사 노드"""
    last_message = state["messages"][-1]
    profile = state["user_profile"]
    
    # 툴 호출이나 시스템 메시지면 건너뜀
    if not isinstance(last_message, AIMessage) or last_message.tool_calls:
        return {}

    # 당뇨 환자일 때만 엄격하게 검사 (Self-Correction 동작)
    if "당뇨" in str(profile.get('diabetes_type')):
        checker_llm = ChatOpenAI(model="gpt-4o", temperature=0)
        check_prompt = f"""
        사용자는 '{profile.get('diabetes_type')}' 환자입니다.
        AI 답변: "{last_message.content}"
        
        이 답변이 고당분/고탄수화물(비빔밥, 국밥, 짜장면, 케이크 등)을 '야식'으로 추천하거나,
        혈당에 치명적인 음식을 '강력 추천'하고 있다면 "DANGER: [이유]"를 출력하세요.
        안전하다면 "SAFE"를 출력하세요.
        """
        check_res = checker_llm.invoke([HumanMessage(content=check_prompt)])
        
        if check_res.content.startswith("DANGER"):
            print(f"🚨 [LangGraph] 안전 검사 실패: {check_res.content}")
            correction_msg = f"잠깐! 사용자는 당뇨 환자야. 방금 추천은 위험해. ({check_res.content}) 내용을 반영해서 더 안전한 메뉴로 다시 대답해."
            return {"messages": [HumanMessage(content=correction_msg, name="safety_guard")]}
            
    return {}

# =========================================================
# 4. 그래프 구성 (Workflow)
# =========================================================
workflow = StateGraph(AgentState)

workflow.add_node("chatbot", chatbot_node)
workflow.add_node("tools", tool_node)
workflow.add_node("safety_check", safety_check_node)

workflow.set_entry_point("chatbot")

def route_tools(state: AgentState):
    if state["messages"][-1].tool_calls:
        return "tools"
    return "safety_check"

workflow.add_conditional_edges("chatbot", route_tools, {"tools": "tools", "safety_check": "safety_check"})
workflow.add_edge("tools", "chatbot")

def route_safety(state: AgentState):
    last_message = state["messages"][-1]
    if isinstance(last_message, HumanMessage) and last_message.name == "safety_guard":
        return "chatbot" # 다시 생성해!
    return END

workflow.add_conditional_edges("safety_check", route_safety, {"chatbot": "chatbot", END: END})

app_graph = workflow.compile()

# =========================================================
# 5. 외부 호출용 Wrapper 함수
# =========================================================
def chat_with_nutritionist(user_profile: dict, recent_logs: list, chat_history: list):
    
    now_str = datetime.now().strftime("%H시 %M분")
    
    # 메시지 변환 (Dict -> LangChain Message)
    lc_messages = []
    for msg in chat_history:
        if msg["role"] == "user": lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant": lc_messages.append(AIMessage(content=msg["content"]))
            
    # 최근 기록 주입 (마지막 유저 메시지에 컨텍스트로 붙임)
    if recent_logs:
        log_text = "\n".join([f"- {l['time']} {l['desc']}" for l in recent_logs])
        if lc_messages and isinstance(lc_messages[-1], HumanMessage):
             lc_messages[-1].content += f"\n\n[참고: 최근 식사 기록]\n{log_text}"
    
    inputs = {
        "messages": lc_messages,
        "user_profile": user_profile,
        "current_time": now_str
    }
    
    # 그래프 실행
    result = app_graph.invoke(inputs)
    return result["messages"][-1].content