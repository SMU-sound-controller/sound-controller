import streamlit as st
import serial
import time
from music21 import stream, note, instrument, tempo

# -----------------------------
# Serial 포트 설정
# -----------------------------
SERIAL_PORT = 'COM5'
BAUD_RATE = 9600

try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.1)
except Exception as e:
    st.error(f"시리얼 포트 연결 실패: {e}")

# -----------------------------
# Session 상태 초기화
# -----------------------------
if 'saved_songs' not in st.session_state:
    st.session_state.saved_songs = []

if 'status_text' not in st.session_state:
    st.session_state.status_text = ""

# -----------------------------
# UI 업데이트 함수
# -----------------------------
def update_saved_songs_ui():
    st.sidebar.subheader("Saved Songs")
    for idx, song in enumerate(st.session_state.saved_songs):
        st.sidebar.write(f"{idx+1}. {song['name']} ({len(song['frequencies'])} notes)")

update_saved_songs_ui()

st.title("Arduino Music Composer")
st.write("Arduino에서 음악 데이터를 입력받습니다...")

# -----------------------------
# 주파수를 music21 Note로 변환
# -----------------------------
def frequency_to_music21_note(freq, duration=1.0):
    if freq == 0:
        return note.Rest(quarterLength=duration)
    n = note.Note()
    n.pitch.frequency = freq
    n.quarterLength = duration
    return n

# -----------------------------
# 시리얼 데이터 처리
# -----------------------------
def process_serial_data():
    updated = False
    while ser.in_waiting > 0:
        try:
            data_line = ser.readline().decode('utf-8').strip()
        except:
            continue
        
        if not data_line:
            continue

        # --- SAVE_SONG 처리 ---
        if data_line.startswith("SAVE_SONG:"):
            raw_data = data_line[len("SAVE_SONG:"):].strip()
            if not raw_data:
                continue
            freq_str_list = [f for f in raw_data.split(',') if f.strip()]
            saved_frequencies = []
            try:
                saved_frequencies = [int(f) for f in freq_str_list]
            except ValueError:
                continue

            if saved_frequencies:
                song_name = f"Song {len(st.session_state.saved_songs) + 1}"
                st.session_state.saved_songs.append({'name': song_name, 'frequencies': saved_frequencies})
                updated = True

        # --- STATUS 처리 ---
        elif data_line.startswith("STATUS:"):
            st.session_state.status_text = data_line[len("STATUS:"):]

        # --- SONG 처리 ---
        elif data_line.startswith("SONG:"):
            st.session_state.status_text = "Live Preview: " + data_line[len("SONG:"):]

    return updated

# -----------------------------
# Streamlit 페이지 갱신
# -----------------------------
updated = process_serial_data()

st.write("상태:", st.session_state.status_text)

if updated:
    update_saved_songs_ui()

# 0.1초마다 페이지 자동 갱신
st.experimental_rerun()
