## 1. 프로젝트 소개 
- 현실적인 직장인 및 당뇨 환자의 생활 패턴에 맞춰, 음식 추천과 혈당 관리 식단 분석을 AI 기반으로 제공하는 당뇨/다이어트 관리 웹 서비스입니다.


## 2. 기획 배경
- 병원에서 당뇨 환자에게 제공되는 표준 식단 가이드북을 접하면서, 실제 직장인의 생활 패턴과는 다소 동떨어진 식단이 제시되고 있다는 점을 느꼈습니다.  
- 이에 따라, 직장인도 일상 속에서 부담 없이 혈당 관리를 할 수 있는 서비스를 만들고자 본 프로젝트를 기획하게 되었습니다.


## 3. 주요 기능
- 회원가입 / 로그인
- 건강 정보 입력
- 식단 분석 (텍스트/이미지)
- 메뉴 추천
- 위치 기반 식당 추천

## 4. 서비스 흐름
- 사용자는 웹 서비스에 접속하여 회원가입 및 로그인을 진행합니다.
- 이후 개인 헬스 데이터(선택)를 입력할 수 있습니다.
- 입력된 정보를 바탕으로 식단 분석, 메뉴 추천, 식사 기록 관리 기능을 이용할 수 있습니다.


## 5. 기술 스택
- Frontend: Streamlit
- Backend: FastAPI
- AI: OpenAI GPT-4o
- Database: SQLite
- ORM: SQLAlchemy
- External API: Kakao Map API

## 6. 시스템 구조 
- Frontend(Streamlit)는 사용자 입력 및 결과 시각화를 담당합니다.
- Backend(FastAPI)는 인증, 데이터 처리, AI 요청을 포함한 비즈니스 로직을 담당합니다.
- AI(OpenAI GPT-4o)는 식단 분석 및 메뉴 추천을 수행합니다.
- Database(SQLite)는 사용자 정보, 식단 기록, 건강 데이터를 저장합니다.

## 7. 실행 방법 
- 로컬 실행 방법
    ### Backend
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    pip install -r requirements.txt
    py main.py
    ### Frontend
    streamlit run app.py
- 환경 변수 설정
- OPENAI_API_KEY, OPENAI_API_KEY

## 8. 배포 정보 
- Backend: Render를 통해 FastAPI 서버 배포
- Frontend: Streamlit Cloud를 통해 웹 UI 배포
- 프론트엔드와 백엔드를 분리하여 배포하고, 외부에서도 서비스 테스트가 가능하도록 구성하였습니다.
- Frontend URL : https://mydietprotect-yje9dfmzdul4i5a4fsmcjg.streamlit.app/
- Backend URL : https://my-diet-protect.onrender.com


## 9. 트러블슈팅 & 배운 점 
- 가상환경 생성 시 Python 버전을 명시하지 않아 Python 3.14 환경에서 개발을 시작하였고,
  FastAPI 및 일부 라이브러리와의 호환성 문제로 실행 오류가 발생했습니다.
  이후 Python 3.12 환경으로 가상환경을 재구성하여 문제를 해결했습니다.

- 회원가입 기능 테스트 중 passlib에서 사용하는 bcrypt 라이브러리가
  내부 보안 테스트 과정에서 예외를 발생시키는 이슈를 겪었습니다.
  문제를 해결하기 위해 bcrypt 버전을 3.2.0으로 조정하여 정상 동작하도록 수정했습니다.

- AI 식단 분석 결과가 기대한 형식으로 출력되지 않는 문제가 있어,
  시스템 프롬프트를 3~4차례 수정하며
  응답 포맷(JSON 고정)과 출력 안정성을 개선했습니다.


## 10. 향후 개선 방향 
- 가상환경 생성 시 Python 버전을 명시하지 않아 Python 3.14 환경에서 개발을 시작하였고,
  FastAPI 및 일부 라이브러리와의 호환성 문제로 실행 오류가 발생했습니다.
  이후 Python 3.12 환경으로 가상환경을 재구성하여 문제를 해결했습니다.

- 회원가입 기능 테스트 중 passlib에서 사용하는 bcrypt 라이브러리가
  내부 보안 테스트 과정에서 예외를 발생시키는 이슈를 겪었습니다.
  원인을 분석한 결과 라이브러리 버전 간 호환성 문제임을 확인했고,
  bcrypt 버전을 3.2.0으로 조정하여 정상 동작하도록 수정했습니다.

- AI 식단 분석 결과가 기대한 형식으로 출력되지 않는 문제가 있어,
  시스템 프롬프트를 3~4차례 수정하며
  응답 포맷(JSON 고정)과 출력 안정성을 개선했습니다.