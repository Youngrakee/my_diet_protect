# app.py
import streamlit as st
import requests
import pandas as pd

# BACKEND_URL = "http://localhost:8000"
BACKEND_URL = "https://my-diet-protect.onrender.com"

st.set_page_config(page_title="오늘뭐먹지.AI", layout="centered", initial_sidebar_state="collapsed")

if 'token' not in st.session_state: st.session_state['token'] = None
if 'username' not in st.session_state: st.session_state['username'] = None
if 'chat_messages' not in st.session_state: st.session_state['chat_messages'] = []

def login_page():
    st.title("🥗 오늘뭐먹지 AI")
    t1, t2 = st.tabs(["로그인", "회원가입"])
    with t1:
        u = st.text_input("ID")
        p = st.text_input("PW", type="password")
        if st.button("로그인"):
            try:
                res = requests.post(f"{BACKEND_URL}/login", data={"username":u,"password":p})
                if res.status_code == 200:
                    st.session_state['token'] = res.json()['access_token']
                    st.session_state['username'] = u
                    st.rerun()
                else: st.error("로그인 실패")
            except: st.warning("서버 연결 중입니다. 다시 한 번 눌러주세요.")
    with t2:
        nu = st.text_input("New ID")
        np = st.text_input("New PW", type="password")

        if st.button("가입"):
            if not nu or not np:
                st.warning("아이디와 비밀번호를 모두 입력해주세요.")
            else:
                res = requests.post(
                    f"{BACKEND_URL}/signup",
                    data={"username": nu, "password": np}
                )

                if res.status_code == 200:
                    st.success("가입 완료")
                elif res.status_code == 400:
                    st.error("이미 존재하는 아이디입니다.")
                else:
                    st.error("회원가입 실패")

def main_app():
    
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    with st.sidebar:
        st.write(f"Hello, **{st.session_state['username']}**")
        if st.button("로그아웃"):
            st.session_state['token'] = None
            st.rerun()

    st.title("🥗 오늘뭐먹지 AI")
    tabs = st.tabs(["🍽️ 식단 분석", "📅 기록", "👤 내 정보", "🤖 AI 영양사"])

    # 1. 분석
    with tabs[0]:
        mode = st.radio("입력", ["사진", "텍스트"], horizontal=True)
        f, t = None, None
        if mode == "사진": f = st.file_uploader("이미지", type=["jpg","png"])
        else: t = st.text_area("내용")
        
        if st.button("분석 시작"):
            with st.spinner("AI 분석 중..."):
                files = {"file": (f.name, f.getvalue(), f.type)} if f else {}
                data = {"text": t} if t else {}
                try:
                    res = requests.post(f"{BACKEND_URL}/analyze", files=files, data=data, headers=headers)
                    if res.status_code == 200:
                        r = res.json()
                        st.success("완료!")
                        st.markdown(f"### {r['food_name']} ({r['blood_sugar_level']})")
                        st.info(r['summary'])
                        st.write(f"👉 {r['action_guide']}")
                    else: st.error("실패")
                except Exception as e: st.error(f"에러: {e}")

    # 2. 기록
    with tabs[1]:
        if st.button("새로고침"): st.rerun()
        try:
            res = requests.get(f"{BACKEND_URL}/history", headers=headers, timeout=10)

            # st.write("DEBUG status:", res.status_code)
            if res.status_code != 200:
                st.write("DEBUG body:", res.text)   # 401/500/HTML 에러 확인용

            if res.status_code == 200:
                data = res.json()
                if not data:
                    st.info("저장된 식단 기록이 없습니다. 먼저 식단을 분석/저장해 주세요 ")
                else:
                    df = pd.DataFrame(data)
                    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%m-%d %H:%M")
                    st.dataframe(df[["created_at","food_description","blood_sugar_impact","summary"]],
                                width="stretch", hide_index=True)
            elif res.status_code == 401:
                st.error("401: 로그인/토큰 문제입니다. 다시 로그인 해주세요.")
            else:
                st.error(f"서버 오류: {res.status_code}")
        except Exception as e:
          st.error(f"데이터 로드 실패: {type(e).__name__} - {e}")

    # 3. 프로필 
    with tabs[2]:
        st.header("👤 상세 프로필 설정")
        st.info("정확한 정보를 입력할수록 AI 분석이 정교해집니다.")

        # 1. 프로필 정보 불러오기
        try:
            profile_res = requests.get(f"{BACKEND_URL}/profile", headers=headers)
            if profile_res.status_code == 200:
                p_data = profile_res.json() # profile_data 줄임

                with st.form("profile_form"):
                    
                    # --- 섹션 1: 기본 정보 ---
                    st.subheader("1. 기본 정보")
                    col1, col2 = st.columns(2)
                    with col1:
                        gender = st.selectbox("성별", ["남성", "여성"], 
                                              index=0 if p_data.get('gender') == "남성" else 1)
                        height = st.number_input("키 (cm)", value=p_data.get('height') or 170)
                    with col2:
                        age = st.number_input("나이", value=p_data.get('age') or 30)
                        weight = st.number_input("몸무게 (kg)", value=p_data.get('weight') or 70)
                    
                    st.divider()

                    # --- 섹션 2: 건강 상태 ---
                    st.subheader("2. 건강 상태")
                    
                    # 당뇨 상태 옵션
                    diabetes_opts = ["해당 없음", "당뇨 전단계", "제2형 당뇨", "제1형 당뇨"]
                    current_dia = p_data.get('diabetes_type')
                    dia_index = diabetes_opts.index(current_dia) if current_dia in diabetes_opts else 0
                    
                    diabetes_type = st.radio("현재 당뇨 상태", diabetes_opts, index=dia_index, horizontal=True)

                    col3, col4 = st.columns(2)
                    with col3:
                        fasting_sugar = st.number_input("공복 혈당 (선택)", value=p_data.get('fasting_sugar') or 0, help="모르면 0으로 두세요")
                    with col4:
                        hba1c = st.number_input("당화혈색소 HbA1c (선택)", value=p_data.get('hba1c') or 0.0, step=0.1, help="모르면 0으로 두세요")

                    st.divider()

                    # --- 섹션 3: 생활 패턴 및 목표 ---
                    st.subheader("3. 생활 패턴 및 목표")
                    
                    # 활동 수준
                    act_opts = ["활동 적음 (앉아서 일함)", "보통 (가벼운 운동)", "활동 많음 (육체 노동/운동함)"]
                    current_act = p_data.get('activity_level')
                    act_index = act_opts.index(current_act) if current_act in act_opts else 1
                    activity_level = st.selectbox("평소 활동량", act_opts, index=act_index)
                    
                    # 목표
                    goal_opts = ["체중 감량", "혈당 안정", "현재 유지", "근육 증가"]
                    current_goal = p_data.get('health_goal')
                    goal_index = goal_opts.index(current_goal) if current_goal in goal_opts else 1
                    health_goal = st.selectbox("관리 목표", goal_opts, index=goal_index)

                    st.divider()
                    
                    # 저장 버튼
                    if st.form_submit_button("💾 정보 저장하기"):
                        update_data = {
                            "gender": gender,
                            "age": int(age),
                            "height": float(height),
                            "weight": float(weight),
                            "diabetes_type": diabetes_type,
                            "fasting_sugar": int(fasting_sugar) if fasting_sugar > 0 else None,
                            "hba1c": float(hba1c) if hba1c > 0 else None,
                            "activity_level": activity_level,
                            "health_goal": health_goal
                        }
                        
                        res = requests.put(f"{BACKEND_URL}/profile", json=update_data, headers=headers)
                        if res.status_code == 200:
                            st.success("프로필이 성공적으로 업데이트되었습니다!")
                            st.rerun()
                        else:
                            st.error(f"업데이트 실패: {res.text}")

            else:
                st.error("프로필을 불러올 수 없습니다.")
        except Exception as e:
            st.error(f"시스템 오류: {e}")

    # 4. 채팅
    with tabs[3]:
        if not st.session_state.chat_messages:
            st.session_state.chat_messages.append({"role":"assistant", "content":"안녕하세요! 맛집 추천이나 식단 고민이 있으신가요?"})
        
        for m in st.session_state.chat_messages:
            st.chat_message(m["role"]).write(m["content"])
            
        if prompt := st.chat_input("메시지 입력 (예: 강남역 맛집 추천해줘)"):
            st.chat_message("user").write(prompt)
            st.session_state.chat_messages.append({"role":"user", "content":prompt})
            
            with st.chat_message("assistant"):
                try:
                    res = requests.post(f"{BACKEND_URL}/chat", json={"messages":st.session_state.chat_messages}, headers=headers)
                    reply = res.json()['reply']
                    st.write(reply)
                    st.session_state.chat_messages.append({"role":"assistant", "content":reply})
                except: st.error("통신 에러")

if st.session_state['token']: main_app()
else: login_page()