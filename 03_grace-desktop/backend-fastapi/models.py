"""models.py – ORM models for Grace Desktop memory system"""
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, ForeignKey,
    Integer, JSON, Boolean, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(128), default="Friend")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(256), default="New conversation")
    mode = Column(String(16), default="chat")   # chat | code
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_archived = Column(Boolean, default=False)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.timestamp")
    summaries = relationship("ConversationSummary", back_populates="conversation", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_conv_user_updated", "user_id", "updated_at"),)


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(16), nullable=False)     # user | assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    embedding = Column(JSON, nullable=True)        # sentence-transformer vector
    tokens = Column(Integer, nullable=True)        # approx token count
    meta = Column(JSON, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (Index("ix_msg_conv_ts", "conversation_id", "timestamp"),)


class ConversationSummary(Base):
    """Rolling summary to compress long conversations for context injection."""
    __tablename__ = "conversation_summaries"
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    message_count_at = Column(Integer, default=0)   # how many messages were summarized
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="summaries")
