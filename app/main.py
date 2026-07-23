from fastapi import FastAPI, Depends, HTTPException  # 1. HTTPException 추가
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import engine, Base, get_db
from app.models import User
from app.schemas import KakaoLoginRequest, TokenResponse
# 2. auth.py에 정의되어 있던 카카오 환경변수 값들을 여기서도 쓸 수 있게 임포트합니다.
from app.auth import get_kakao_user_info, create_access_token, KAKAO_REST_API_KEY, KAKAO_REDIRECT_URI

from app.auth import get_kakao_user_info, create_access_token, get_current_user  # get_current_user 추가
from app.schemas import KakaoLoginRequest, TokenResponse, CompleteProfileRequest  # CompleteProfileRequest 추가

# 서버가 시작할 때 SQLite 테이블 자동 생성 (Supabase 도입 전 로컬 개발용)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Tiul English Voca Platform API")

# 로컬 개발 서버 포트 허용 (Vite+React 기본 포트인 5173 포함)
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Tiul Voca Platform Backend is running!"}

# 3. 주소 일관성을 위해 /api/v1/을 붙여 정돈합니다.
@app.get("/api/v1/auth/kakao/url")
def get_kakao_auth_url():
    """
    프론트엔드에게 카카오 로그인 시작 URL을 제공합니다.
    모든 키값은 백엔드에서만 안전하게 관리됩니다.
    """
    if not KAKAO_REST_API_KEY or not KAKAO_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="카카오 설정(환경변수)이 누락되었습니다.")
        
    # 백엔드가 가진 진짜 키들로 카카오 인증 주소 조립
    url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={KAKAO_REST_API_KEY}"
        f"&redirect_uri={KAKAO_REDIRECT_URI}"
        f"&response_type=code"
    )
    
    return {"url": url}

@app.post("/api/v1/auth/kakao", response_model=TokenResponse)
async def kakao_login(payload: KakaoLoginRequest, db: Session = Depends(get_db)):
    kakao_info = await get_kakao_user_info(payload.code)
    
    kakao_id = str(kakao_info.get("id"))
    properties = kakao_info.get("properties", {})
    nickname = properties.get("nickname", "학습자")

    # 기존 유저 확인 및 가입 처리
    user = db.query(User).filter(User.kakao_id == kakao_id).first()
    if not user:
        # 처음 로그인하는 사용자 → profile_completed = False 상태로 생성
        user = User(kakao_id=kakao_id, nickname=nickname, profile_completed=False)
        db.add(user)
        db.commit()
        db.refresh(user)

    access_token = create_access_token(data={"sub": user.kakao_id, "user_id": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        nickname=user.nickname,
        profile_completed=user.profile_completed,   # 추가된 부분
    )

@app.post("/api/v1/users/me/complete-profile")
def complete_profile(
    payload: CompleteProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.name = payload.name
    current_user.nickname = payload.nickname
    current_user.class_name = payload.class_name
    current_user.profile_completed = True
    db.commit()
    db.refresh(current_user)

    return {"message": "회원가입이 완료되었습니다.", "profile_completed": True}