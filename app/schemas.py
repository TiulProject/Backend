from pydantic import BaseModel

class KakaoLoginRequest(BaseModel):
    code: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    nickname: str | None = None
    profile_completed: bool          # 추가

class CompleteProfileRequest(BaseModel):
    name: str
    nickname: str
    class_name: str