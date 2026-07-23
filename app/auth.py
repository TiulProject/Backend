import os
import datetime
import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database import get_db
from app.models import User

load_dotenv()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

# 보안 설정(Client Secret)을 켜두셨다면 넣어주시고, 안 쓰신다면 빈 값으로 둡니다.
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# --- 추가된 부분: 토큰에서 현재 로그인한 유저 꺼내기 ---
# tokenUrl은 실제로 호출되진 않고, /docs 화면에서 인증 UI 표시용으로만 쓰입니다.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/kakao")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
    except JWTError:
        print("🚨 [JWT Error] 토큰 디코딩 실패")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    if user_id is None:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    return user
# ----------------------------------------------------

async def get_kakao_user_info(code: str) -> dict:
    # 1. 인가 코드(code)를 이용해 토큰 받기
    token_url = "https://kauth.kakao.com/oauth/token"
    
    token_headers = {
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
    }
    
    # 카카오 공식 spec: application/x-www-form-urlencoded 포맷 데이터
    token_data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
    }
    
    # Client Secret 설정이 활성화되어 있을 경우에만 전송에 포함
    if KAKAO_CLIENT_SECRET:
        token_data["client_secret"] = KAKAO_CLIENT_SECRET

    async with httpx.AsyncClient() as client:
        # 토큰 발급 요청
        response = await client.post(token_url, headers=token_headers, data=token_data)
        
        # ❌ 토큰 발급 실패 시 카카오의 에러 본문을 터미널에 프린트
        if response.status_code != 200:
            print(f"🚨 [Kakao Token Error] Status: {response.status_code}, Body: {response.text}")
            raise HTTPException(
                status_code=400, 
                detail=f"카카오 토큰 발급 실패 (원인: {response.json().get('error_description', '알 수 없음')})"
            )
        
        token_res = response.json()
        access_token = token_res.get("access_token")

        # 2. 토큰을 이용해 사용자 정보(프로필) 가져오기
        profile_url = "https://kapi.kakao.com/v2/user/me"
        
        profile_headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8"
        }
        
        # 공식 가이드: 안전한 사용자 정보 조회를 위해 POST 권장
        profile_response = await client.post(profile_url, headers=profile_headers)
        
        # ❌ 사용자 정보 조회 실패 시 로그 출력
        if profile_response.status_code != 200:
            print(f"🚨 [Kakao Profile Error] Status: {profile_response.status_code}, Body: {profile_response.text}")
            raise HTTPException(status_code=400, detail="카카오 프로필 정보를 가져오지 못했습니다.")
            
        return profile_response.json()
    
