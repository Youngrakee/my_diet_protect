# main.py
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel

from database import SessionLocal, init_db, FoodLog, User, HealthLog
from ai_service import analyze_food, chat_with_nutritionist
import uvicorn

def ensure_demo_user():
    db = SessionLocal()
    try:
        demo_user = db.query(User).filter(User.username == "demo").first()
        if not demo_user:
            demo_pw = pwd_context.hash("demo1234")
            new_user = User(
                username="demo", 
                hashed_password=demo_pw,
                gender="남성",
                age=35,
                height=175.0,
                weight=75.0,
                diabetes_type="제2형 당뇨",
                activity_level="보통 (가벼운 운동)",
                health_goal="혈당 안정"
            )
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            # 샘플 기록 추가
            sample_logs = [
                FoodLog(
                    food_description="현미밥과 고등어 구이",
                    blood_sugar_impact="낮음",
                    carbs_ratio=45, protein_ratio=35, fat_ratio=20,
                    summary="균형 잡힌 한식 식단입니다. 단백질과 식이섬유가 풍부하여 혈당 상승이 완만합니다.",
                    action_guide="식후 10분 정도 가벼운 스트레칭을 추천합니다.",
                    detailed_action_guide="고등어의 오메가-3와 현미의 식이섬유가 혈당 안정을 돕습니다. 식후 물 한 잔을 마셔주세요.",
                    owner_id=new_user.id
                ),
                FoodLog(
                    food_description="제육덮밥",
                    blood_sugar_impact="높음",
                    carbs_ratio=60, protein_ratio=20, fat_ratio=20,
                    summary="탄수화물과 당분 함량이 높은 식단입니다.",
                    action_guide="식후 20분 이상 빠른 걸음으로 산책하세요.",
                    detailed_action_guide="양념의 설탕과 흰쌀밥이 혈당을 빠르게 올릴 수 있습니다. 다음 식사때는 채소를 먼저 드시는 '거꾸로 식사법'을 권장합니다.",
                    owner_id=new_user.id
                )
            ]
            db.add_all(sample_logs)
            db.commit()
            print("Successfully created demo user and sample data.")
    finally:
        db.close()

# --- 설정 ---
SECRET_KEY = "SECRET_KEY_TEST"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 600

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI()
init_db()
ensure_demo_user()

# [UPDATE] 프로필 데이터 검증 모델 (구조 확장)
class UserProfileUpdate(BaseModel):
    # 기본 정보
    gender: str
    age: int
    height: float
    weight: float
    
    # 건강 상태
    diabetes_type: str
    fasting_sugar: Optional[int] = None
    hba1c: Optional[float] = None
    
    # 생활 패턴 & 목표
    activity_level: str
    health_goal: str


class HealthLogCreate(BaseModel):
    sugar_level: int
    note: Optional[str] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None: raise HTTPException(status_code=401)
    except JWTError:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.username == username).first()
    if user is None: raise HTTPException(status_code=401)
    return user

# --- Auth Endpoints ---
@app.post("/signup")
def signup(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if user: raise HTTPException(status_code=400, detail="User exists")
    hashed_pw = pwd_context.hash(form_data.password)
    new_user = User(username=form_data.username, hashed_password=hashed_pw)
    db.add(new_user)
    db.commit()
    return {"msg": "Created"}

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401)
    token = jwt.encode({"sub": user.username, "exp": datetime.utcnow() + timedelta(minutes=600)}, SECRET_KEY, algorithm=ALGORITHM)
    return {"access_token": token, "token_type": "bearer"}

# --- Feature Endpoints ---
@app.post("/analyze")
async def analyze_endpoint(
    text: str = Form(None), file: UploadFile = File(None),
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    img_bytes = await file.read() if file else None
    profile = {
        "diabetes_type": user.diabetes_type, "health_goal": user.health_goal,
        "age": user.age, "gender": user.gender
    }
    
    result = analyze_food(text, img_bytes, profile)
    
    log = FoodLog(
        input_type="image" if file else "text",
        food_description=result.get("food_name", text or "Unknown"),
        blood_sugar_impact=result.get("blood_sugar_impact"),
        carbs_ratio=result.get("carbs_ratio"),
        protein_ratio=result.get("protein_ratio"),
        fat_ratio=result.get("fat_ratio"),
        summary=result.get("summary"),
        action_guide=result.get("action_guide"),
        detailed_action_guide=result.get("detailed_action_guide"),
        alternatives=result.get("alternatives"),
        owner_id=user.id
    )
    db.add(log)
    db.commit()
    return result

@app.get("/history")
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # [NEW] 유저 정보 주입
):
    # [NEW] owner_id가 현재 유저인 것만 필터링
    logs = db.query(FoodLog).filter(FoodLog.owner_id == current_user.id)\
            .order_by(FoodLog.created_at.desc()).limit(10).all()
    return logs


# [UPDATE] 5. 내 프로필 조회
@app.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    return {
        "username": current_user.username,
        "gender": current_user.gender,
        "age": current_user.age,
        "height": current_user.height,
        "weight": current_user.weight,
        "diabetes_type": current_user.diabetes_type,
        "fasting_sugar": current_user.fasting_sugar,
        "hba1c": current_user.hba1c,
        "activity_level": current_user.activity_level,
        "health_goal": current_user.health_goal,
    }

# [UPDATE] 6. 내 프로필 수정
@app.put("/profile")
def update_profile(
    profile: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 하나씩 매핑 (실무에서는 Mapper 라이브러리 등을 쓰기도 함)
    current_user.gender = profile.gender
    current_user.age = profile.age
    current_user.height = profile.height
    current_user.weight = profile.weight
    
    current_user.diabetes_type = profile.diabetes_type
    current_user.fasting_sugar = profile.fasting_sugar
    current_user.hba1c = profile.hba1c
    
    current_user.activity_level = profile.activity_level
    current_user.health_goal = profile.health_goal
    
    db.commit()
    return {"msg": "Profile updated successfully"}

@app.post("/health/sugar")
def log_sugar(log: HealthLogCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.add(HealthLog(sugar_level=log.sugar_level, note=log.note, owner_id=user.id))
    db.commit()
    return {"msg": "Logged"}

@app.get("/health/sugar")
def get_sugar_logs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(HealthLog).filter(HealthLog.owner_id == user.id).order_by(HealthLog.created_at.desc()).limit(20).all()

@app.post("/chat")
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    print(f"💬 [Chat] New message from {user.username}")
    profile = {"diabetes_type": user.diabetes_type, "health_goal": user.health_goal}
    
    # 최근 24시간 기록
    recent = db.query(FoodLog).filter(FoodLog.owner_id == user.id).order_by(FoodLog.created_at.desc()).limit(5).all()
    logs = [{"time": l.created_at.strftime("%H:%M"), "desc": l.food_description} for l in recent]
    
    hist = [{"role": m.role, "content": m.content} for m in req.messages]
    
    try:
        reply = chat_with_nutritionist(profile, logs, hist)
        print(f"✅ [Chat] Reply generated for {user.username}")
        return {"reply": reply}
    except Exception as e:
        print(f"❌ [Chat] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)