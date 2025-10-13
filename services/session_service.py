"""
Session Management Service for Chat Context Persistence

This service handles session management with UUID generation and chat context storage
for the Cambridge School textbook system.
"""

import uuid
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from threading import Lock
import logging

from models.rags.rag_models import ChatMessage

logger = logging.getLogger(__name__)

class SessionService:
    """
    Production-grade session management service with in-memory storage.
    
    Features:
    - UUID generation for new sessions
    - Chat history persistence per session
    - Session expiration (24 hours)
    - Thread-safe operations
    - Memory-efficient storage
    """
    
    def __init__(self, session_timeout_hours: int = 24):
        self.session_timeout_hours = session_timeout_hours
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        
        # Cleanup expired sessions periodically
        self._last_cleanup = time.time()
        self._cleanup_interval = 3600  # 1 hour
        
    def create_session(self, collection_name: str) -> str:
        """
        Create a new session with a unique UUID.
        
        Args:
            collection_name: The collection name for this session
            
        Returns:
            str: New session UUID
        """
        session_id = str(uuid.uuid4())
        current_time = time.time()
        
        with self._lock:
            self._sessions[session_id] = {
                'id': session_id,
                'collection_name': collection_name,
                'chat_history': [],
                'created_at': current_time,
                'last_accessed': current_time,
                'message_count': 0
            }
            
        logger.info(f"Created new session {session_id} for collection {collection_name}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session data by ID.
        
        Args:
            session_id: The session UUID
            
        Returns:
            Dict containing session data or None if not found/expired
        """
        if not session_id:
            return None
            
        current_time = time.time()
        
        with self._lock:
            # Cleanup expired sessions if needed
            if current_time - self._last_cleanup > self._cleanup_interval:
                self._cleanup_expired_sessions()
                
            session = self._sessions.get(session_id)
            if session:
                # Check if session is expired
                if current_time - session['last_accessed'] > (self.session_timeout_hours * 3600):
                    logger.info(f"Session {session_id} expired, removing")
                    del self._sessions[session_id]
                    return None
                    
                # Update last accessed time
                session['last_accessed'] = current_time
                return session
                
        return None
    
    def add_message_to_session(self, session_id: str, message: ChatMessage) -> bool:
        """
        Add a message to the session's chat history.
        
        Args:
            session_id: The session UUID
            message: The ChatMessage to add
            
        Returns:
            bool: True if successful, False if session not found
        """
        if not session_id:
            return False
            
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                # Add message to history
                session['chat_history'].append(message.dict())
                session['message_count'] += 1
                session['last_accessed'] = time.time()
                
                # Keep only last 50 messages to prevent memory issues
                if len(session['chat_history']) > 50:
                    session['chat_history'] = session['chat_history'][-50:]
                    
                logger.debug(f"Added message to session {session_id}, total messages: {session['message_count']}")
                return True
                
        return False
    
    def get_chat_history(self, session_id: str) -> List[ChatMessage]:
        """
        Get chat history for a session.
        
        Args:
            session_id: The session UUID
            
        Returns:
            List of ChatMessage objects
        """
        session = self.get_session(session_id)
        if session and session['chat_history']:
            try:
                return [ChatMessage(**msg) for msg in session['chat_history']]
            except Exception as e:
                logger.error(f"Error parsing chat history for session {session_id}: {e}")
                return []
        return []
    
    def update_session_collection(self, session_id: str, collection_name: str) -> bool:
        """
        Update the collection name for a session.
        
        Args:
            session_id: The session UUID
            collection_name: New collection name
            
        Returns:
            bool: True if successful, False if session not found
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session['collection_name'] = collection_name
                session['last_accessed'] = time.time()
                return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and its data.
        
        Args:
            session_id: The session UUID
            
        Returns:
            bool: True if deleted, False if not found
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Deleted session {session_id}")
                return True
        return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """
        Get statistics about active sessions.
        
        Returns:
            Dict with session statistics
        """
        with self._lock:
            current_time = time.time()
            active_sessions = 0
            total_messages = 0
            
            for session in self._sessions.values():
                if current_time - session['last_accessed'] <= (self.session_timeout_hours * 3600):
                    active_sessions += 1
                    total_messages += session['message_count']
                    
            return {
                'active_sessions': active_sessions,
                'total_sessions': len(self._sessions),
                'total_messages': total_messages,
                'session_timeout_hours': self.session_timeout_hours
            }
    
    def _cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, session in self._sessions.items():
            if current_time - session['last_accessed'] > (self.session_timeout_hours * 3600):
                expired_sessions.append(session_id)
                
        for session_id in expired_sessions:
            del self._sessions[session_id]
            logger.info(f"Cleaned up expired session {session_id}")
            
        self._last_cleanup = current_time

# Global session service instance
session_service = SessionService()
