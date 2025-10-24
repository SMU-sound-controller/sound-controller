import streamlit as st
import serial
import time
import simpleaudio as sa
import numpy as np
from streamlit_autorefresh import st_autorefresh

# ---------------------------
# Streamlit 상태 초기화
# ---------------------------
if 'melody_stack' not in st.session_state:
    st.session_state.melody_stack = []  # 저장된 멜로디
if 'current_melody' not in st.session_state:
    st.session_state.current_melody = []
if 'lcd_message' not in st.session_state:
    st.session_state.lcd_message = ""

# ---------------------------
# Arduino 시리얼 연결
# ---------------------------
try:
    ser = serial.Serial('COM5', 9600, timeout=0.1)
except Exception as e:
    st.error(f"시리얼 연결 오류: {e}")
    st.stop()

# ---------------------------
# Arduino 데이터 읽기
# ---------------------------
def read_arduino():
    while ser.in_waiting:
        line = ser.readline().decode(errors='ignore').strip()
        if line.startswith("STATUS:"):
            parts = line[7:].split(",")
            st.session_state.lcd_message = f"Notes:{parts[1]} Oct:{parts[3]} Note:{parts[4]}"
        elif line.startswith("SAVE_SONG:"):
            notes = list(map(int, line[10:].split(",")))
            st.session_state.melody_stack.append(notes)
            st.session_state.current_melody = []  # 초기화
            st.success(f"멜로디 저장 완료! 총 {len(st.session_state.melody_stack)}곡")

# ---------------------------
# 멜로디 재생
# ---------------------------
def play_melody(melody):
    progress_bar = st.progress(0)
    for i, freq in enumerate(melody):
        if freq <= 0:
            time.sleep(0.2)
            continue
        fs = 44100
        t = 0.2
        samples = (0.5 * (np.sin(2*np.pi*np.arange(fs*t)*freq/fs))).astype(np.float32)
        sa.play_buffer((samples*32767).astype('int16'), 1, 2, fs).wait_done()
        progress_bar.progress((i+1)/len(melody))

# ---------------------------
# UI
# ---------------------------
st.title("Arduino Music Composer")

st.subheader("LCD 정보")
st.text(st.session_state.lcd_message)

st.subheader("저장된 멜로디")
for idx, melody in enumerate(st.session_state.melody_stack):
    st.write(f"Melody {idx+1} ({len(melody)} notes)")
    if st.button(f"Play Melody {idx+1}", key=f"play_{idx}"):
        play_melody(melody)

# ---------------------------
# 자동 새로고침
# ---------------------------
read_arduino()
st_autorefresh(interval=1000, limit=None, key="auto_refresh")
