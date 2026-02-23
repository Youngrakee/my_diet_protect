import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from database import SessionLocal, init_db, FoodLog, User, HealthLog
from ai_service import analyze_food, chat_with_nutritionist

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(16))
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

init_db()

# --- Password Context ---
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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

ensure_demo_user()

# --- Helpers ---
def get_db():
    db = SessionLocal()
    try:
        return db
    finally:
        pass # Handle closing in a teardown function

@app.teardown_appcontext
def shutdown_session(exception=None):
    pass # SessionLocal is handled manually or we can use a middleware/decorator

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('index.html', username=session.get('username'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = SessionLocal()
        user = db.query(User).filter(User.username == username).first()
        db.close()
        
        if user and (check_password_hash(user.hashed_password, password) or (username == "demo" and password == "demo1234")):
            # Note: The database currently uses bcrypt via passlib, but main.py uses pwd_context
            # I should be careful with password verification logic if I change it.
            # Let's check how main.py does it.
            
            # For now, let's use the same logic as main.py (FastAPI) which is bcrypt
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            
            if user and pwd_context.verify(password, user.hashed_password):
                session['user_id'] = user.id
                session['username'] = user.username
                return redirect(url_for('index'))
            
        flash('아이디 또는 비밀번호가 올바르지 않습니다.')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        db = SessionLocal()
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            db.close()
            flash('이미 존재하는 아이디입니다.')
            return redirect(url_for('signup'))
        
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        hashed_pw = pwd_context.hash(password)
        
        new_user = User(username=username, hashed_password=hashed_pw)
        db.add(new_user)
        db.commit()
        db.close()
        
        flash('회원가입이 완료되었습니다. 로그인해 주세요.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    db = SessionLocal()
    user = db.query(User).filter(User.id == session['user_id']).first()
    
    if request.method == 'POST':
        user.gender = request.form.get('gender')
        user.age = int(request.form.get('age', 0))
        user.height = float(request.form.get('height', 0))
        user.weight = float(request.form.get('weight', 0))
        user.diabetes_type = request.form.get('diabetes_type')
        user.fasting_sugar = int(request.form.get('fasting_sugar', 0)) or None
        user.hba1c = float(request.form.get('hba1c', 0)) or None
        user.activity_level = request.form.get('activity_level')
        user.health_goal = request.form.get('health_goal')
        
        db.commit()
        db.close()
        flash('프로필이 업데이트되었습니다.')
        return redirect(url_for('index'))
    
    user_data = {
        "gender": user.gender,
        "age": user.age,
        "height": user.height,
        "weight": user.weight,
        "diabetes_type": user.diabetes_type,
        "fasting_sugar": user.fasting_sugar,
        "hba1c": user.hba1c,
        "activity_level": user.activity_level,
        "health_goal": user.health_goal
    }
    db.close()
    return render_template('profile.html', user=user_data)

@app.route('/profile_data')
@login_required
def profile_data():
    db = SessionLocal()
    user = db.query(User).filter(User.id == session['user_id']).first()
    data = {
        "gender": user.gender,
        "age": user.age
    }
    db.close()
    return jsonify(data)

@app.route('/api/health/sugar', methods=['GET', 'POST'])
@login_required
def health_sugar():
    db = SessionLocal()
    if request.method == 'POST':
        data = request.json
        new_log = HealthLog(
            sugar_level=data.get('sugar_level'),
            note=data.get('note'),
            owner_id=session['user_id']
        )
        db.add(new_log)
        db.commit()
        db.close()
        return jsonify({"msg": "Logged"})
    
    logs = db.query(HealthLog).filter(HealthLog.owner_id == session['user_id'])\
             .order_by(HealthLog.created_at.desc()).limit(20).all()
    result = [{
        "created_at": log.created_at.strftime("%m-%d %H:%M"),
        "sugar_level": log.sugar_level,
        "note": log.note
    } for log in logs]
    db.close()
    return jsonify(result)

@app.route('/api/analyze', methods=['POST'])
@login_required
def analyze():
    text = request.form.get('text')
    file = request.files.get('file')
    
    image_filename = None
    if file:
        image_filename = f"{secrets.token_hex(8)}_{secure_filename(file.filename)}"
        file.seek(0) # Reset before saving if needed, but analyze_food might have read it
        # Actually file.read() was called above, so we need to handle it.
        # Let's fix the file reading logic to allow both analyze and save.
    
    # Let's re-read image_bytes if file exists
    if file:
        file.seek(0)
        img_bytes = file.read()
        file.seek(0)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], image_filename))
    
    db = SessionLocal()
    user = db.query(User).filter(User.id == session['user_id']).first()
    
    profile = {
        "diabetes_type": user.diabetes_type, 
        "health_goal": user.health_goal,
        "age": user.age, 
        "gender": user.gender
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
        image_path=image_filename,
        owner_id=user.id
    )
    db.add(log)
    db.commit()
    db.close()
    
    return jsonify(result)

@app.route('/api/history')
@login_required
def history():
    db = SessionLocal()
    logs = db.query(FoodLog).filter(FoodLog.owner_id == session['user_id'])\
             .order_by(FoodLog.created_at.desc()).limit(10).all()
    
    result = []
    for log in logs:
        result.append({
            "created_at": log.created_at.strftime("%m-%d %H:%M"),
            "food_description": log.food_description,
            "blood_sugar_impact": log.blood_sugar_impact,
            "carbs_ratio": log.carbs_ratio,
            "protein_ratio": log.protein_ratio,
            "fat_ratio": log.fat_ratio,
            "summary": log.summary,
            "detailed_action_guide": log.detailed_action_guide,
            "image_path": log.image_path
        })
    db.close()
    return jsonify(result)

@app.route('/api/chat', methods=['POST'])
@login_required
def chat():
    data = request.json
    messages = data.get('messages', [])
    
    db = SessionLocal()
    user = db.query(User).filter(User.id == session['user_id']).first()
    
    profile = {
        "diabetes_type": user.diabetes_type or "정보 없음", 
        "health_goal": user.health_goal or "일반 건강 관리"
    }
    
    recent = db.query(FoodLog).filter(FoodLog.owner_id == user.id).order_by(FoodLog.created_at.desc()).limit(5).all()
    logs = [{"time": l.created_at.strftime("%H:%M"), "desc": l.food_description} for l in recent]
    db.close()
    
    try:
        reply = chat_with_nutritionist(profile, logs, messages)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
