import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, ForeignKey, SmallInteger, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship
from app.database import Base, engine

# --- [SQLite / PostgreSQL 호환을 위한 크로스 플랫폼 타입 정의] ---
class GUID(TypeDecorator):
    """플랫폼 독립적인 UUID 타입 지원 (PostgreSQL은 UUID, SQLite는 CHAR(32))"""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid.UUID):
                return value.hex
            return uuid.UUID(value).hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value

# JSONB 호환을 위한 폴백 설정
from sqlalchemy import JSON
JSON_TYPE = JSON().with_variant(JSONB, "postgresql")
# ------------------------------------------------------------------

class User(Base):
    """1. users: 카카오 로그인 사용자"""
    __tablename__ = "users"

    id = Column(GUID, primary_key=True, default=uuid.uuid4)
    kakao_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)                        # 추가: 실명
    nickname = Column(String, nullable=True)
    class_name = Column(String, nullable=True)                  # 추가: 반
    profile_completed = Column(Boolean, default=False)          # 추가: 회원가입 완료 여부
    profile_image = Column(Text, nullable=True)
    role = Column(String, default="student")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 관계 설정
    user_words = relationship("UserWord", back_populates="user", cascade="all, delete-orphan")
    study_sessions = relationship("StudySession", back_populates="user", cascade="all, delete-orphan")
    test_histories = relationship("TestHistory", back_populates="user", cascade="all, delete-orphan")

class Word(Base):
    """2. words: 단어 마스터"""
    __tablename__ = "words"

    id = Column(Integer, primary_key=True, autoincrement=True)  # BIGSERIAL 매핑
    word = Column(String, nullable=False)
    meaning = Column(Text, nullable=False)
    word_type = Column(String, nullable=True)  # noun, verb, adjective, adverb, phrase
    forms = Column(JSON_TYPE, default=dict)   # JSONB 호환 포맷
    example = Column(Text, nullable=True)
    example_kr = Column(Text, nullable=True)
    difficulty = Column(SmallInteger, nullable=True)
    source = Column(String, nullable=True)     # TOEIC, Daily, Business, MiddleSchool
    level = Column(SmallInteger, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 관계 설정
    user_words = relationship("UserWord", back_populates="word", cascade="all, delete-orphan")
    session_words = relationship("StudySessionWord", back_populates="word", cascade="all, delete-orphan")
    test_histories = relationship("TestHistory", back_populates="word", cascade="all, delete-orphan")


class UserWord(Base):
    """3. user_words: 유저별 누적 학습 상태 및 에이징"""
    __tablename__ = "user_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    
    correct_count = Column(Integer, default=0)
    wrong_count = Column(Integer, default=0)
    
    last_studied_at = Column(DateTime, nullable=True)
    next_review_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="user_words")
    word = relationship("Word", back_populates="user_words")

    # 복합 유니크 제약 및 인덱스 반영
    __table_args__ = (
        UniqueConstraint('user_id', 'word_id', name='_user_word_uc'),
        Index('ix_user_words_user_id', 'user_id'),
        Index('ix_user_words_word_id', 'word_id'),
    )


class StudySession(Base):
    """4. study_sessions: 오늘 공부 마스터 기록"""
    __tablename__ = "study_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    study_date = Column(Date, default=datetime.date.today)
    total_words = Column(Integer, default=0)
    completed_words = Column(Integer, default=0)
    completed = Column(Boolean, default=False)
    
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="study_sessions")
    session_words = relationship("StudySessionWord", back_populates="session", cascade="all, delete-orphan")
    test_histories = relationship("TestHistory", back_populates="session", cascade="all, delete-orphan")

    # 인덱스 추천 반영
    __table_args__ = (
        Index('ix_study_sessions_user_id_study_date', 'user_id', 'study_date'),
    )


class StudySessionWord(Base):
    """5. study_session_words: 오늘 세션에 배정된 단어 (순서 보장)"""
    __tablename__ = "study_session_words"

    id = Column(Integer, primary_key=True, autoincrement=True)
    study_session_id = Column(Integer, ForeignKey("study_sessions.id", ondelete="CASCADE"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    
    order_no = Column(SmallInteger, nullable=False)
    completed = Column(Boolean, default=False)
    completed_at = Column(DateTime, nullable=True)

    # 관계 설정
    session = relationship("StudySession", back_populates="session_words")
    word = relationship("Word", back_populates="session_words")


class TestHistory(Base):
    """6. test_history: 시험 상세 결과 이력"""
    __tablename__ = "test_histories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    word_id = Column(Integer, ForeignKey("words.id", ondelete="CASCADE"), nullable=False)
    study_session_id = Column(Integer, ForeignKey("study_sessions.id", ondelete="SET NULL"), nullable=True)
    
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=False)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    user = relationship("User", back_populates="test_histories")
    word = relationship("Word", back_populates="test_histories")
    session = relationship("StudySession", back_populates="test_histories")

    # 인덱스 추천 반영
    __table_args__ = (
        Index('ix_test_histories_user_id', 'user_id'),
        Index('ix_test_histories_word_id', 'word_id'),
    )

# --- [Word 단독 인덱스 별도 적용] ---
Index('ix_words_word', Word.word)
Index('ix_words_word_type', Word.word_type)
Index('ix_words_source', Word.source)