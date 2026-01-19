# ai_service.py
import base64
import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime # [NEW] 시간 확인용

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
KAKAO_API_KEY = os.getenv("KAKAO_API_KEY")

# --- 1. 카카오 API 검색 함수 ---
def search_places_kakao(query: str, location: str = ""):
    print(f"🚀 [Tool] 카카오 검색 실행: {location} {query}")
    
    if not KAKAO_API_KEY:
        return json.dumps({"error": "KAKAO_API_KEY Missing"})

    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    search_query = f"{location} {query}".strip()
    
    try:
        response = requests.get(url, headers=headers, params={"query": search_query, "size": 5, "sort": "accuracy"})
        if response.status_code == 200:
            documents = response.json().get('documents', [])
            if not documents:
                return json.dumps({"info": "검색 결과 없음"})
            
            results = []
            for doc in documents:
                results.append({
                    "name": doc['place_name'],
                    "address": doc['road_address_name'],
                    "url": doc['place_url'], # 카카오맵 링크
                    "category": doc['category_name']
                })
            return json.dumps(results, ensure_ascii=False)
        else:
            return json.dumps({"error": f"API Error {response.status_code}"})
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- 2. OpenAI 도구 정의 ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_restaurants",
            "description": "식당, 맛집 추천 요청 시 실제 장소를 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "검색할 지역 이름 (예: 강남역, 완정역)",
                    },
                    "menu_keyword": {
                        "type": "string",
                        "description": "검색할 메뉴 키워드 (구체적인 메뉴명보다는 '카테고리' 권장)",
                    },
                },
                "required": ["location", "menu_keyword"],
            },
        },
    }
]

# --- 3. 식단 분석 함수 (이미지/텍스트) ---
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

# --- 4. 챗봇 함수 (맛집 검색 포함) ---
def chat_with_nutritionist(user_profile: dict, recent_logs: list, chat_history: list):

    # 1. 현재 시간 (Default 기준점)
    now = datetime.now()
    current_time_str = now.strftime("%H시 %M분")

    # 2. 최근 식사 기록을 텍스트로 명확하게 정리
    if recent_logs:
        history_text = "\n".join([f"- {log['time']} 섭취: {log['desc']}" for log in recent_logs])
    else:
        history_text = "최근 기록 없음"

    # 2. 컨텍스트 구성
    context_text = f"""
    [시스템 정보]
    - 현재 서버 시간: {current_time_str}
    [사용자 프로필]
    - 당뇨 상태: {user_profile.get('diabetes_type', '정보 없음')}
    - 목표: {user_profile.get('health_goal', '건강 관리')}
    
    [최근 식사 기록 (매우 중요)]
    {history_text}
    """
    
     # 3. 시스템 프롬프트 (★ 시간대 로직 + 다양성 로직 + 검색 로직 통합 ★)
    system_prompt = f"""
    당신은 센스 있고 현실적인 AI 영양사 '오늘뭐먹지.ai'입니다.
    
    [Step 1: 시간대 및 의도 파악 (우선순위 1위)]
    1. **사용자의 발화(의도)**를 최우선으로 따르세요. (예: 낮 12시라도 "야식 추천해줘"라면 야식 규칙 적용)
    2. 언급이 없으면 [현재 시간]({current_time_str})을 기준으로 판단하세요.
    
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
    """


    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": context_text}
    ]
    messages.extend(chat_history)

    print("🤖 [AI] 식사 기록 분석 및 메뉴 선정 중...")

    # 1차 호출
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.7
    )
    
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    if tool_calls:
        # 도구 사용 요청 처리
        messages.append(response_message) # 대화 내역에 추가

        for tool_call in tool_calls:
            args = json.loads(tool_call.function.arguments)
            print(f"🛠️ [AI 검색어] {args.get('location')} + {args.get('menu_keyword')}")
            
            # 카카오 API 실행
            search_result = search_places_kakao(
                query=args.get("menu_keyword"),
                location=args.get("location")
            )
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": search_result
            })

        # 2차 호출 (결과를 보고 답변 생성)
        second_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.7
        )
        return second_response.choices[0].message.content

    else:
        # 도구 사용 안 함 (위치 정보 없을 때 등)
        return response_message.content