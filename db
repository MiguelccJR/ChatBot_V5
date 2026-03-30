import streamlit as st
from supabase import create_client


def get_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


def create_test_session(tester_name: str, platform: str) -> str:
    supabase = get_supabase()
    response = (
        supabase.table("test_sessions")
        .insert({
            "tester_name": tester_name,
            "platform": platform
        })
        .execute()
    )
    return response.data[0]["id"]


def save_message_turn(
    session_id: str,
    turn_number: int,
    user_message: str,
    bot_messages: list,
    idioma: str,
    categorias_detectadas: list,
    categorias_respondibles: list
):
    supabase = get_supabase()
    (
        supabase.table("messages")
        .insert({
            "session_id": session_id,
            "turn_number": turn_number,
            "user_message": user_message,
            "bot_messages": bot_messages,
            "idioma": idioma,
            "categorias_detectadas": categorias_detectadas,
            "categorias_respondibles": categorias_respondibles
        })
        .execute()
    )


def save_feedback(session_id: str, turn_number: int, rating: str, comment: str):
    supabase = get_supabase()
    (
        supabase.table("feedback")
        .insert({
            "session_id": session_id,
            "turn_number": turn_number,
            "rating": rating,
            "comment": comment
        })
        .execute()
    )
