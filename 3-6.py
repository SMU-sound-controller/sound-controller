# 🎶 app.py (v5 - 폼 버튼 클릭 버그 수정)
# 실행 명령어: streamlit run app.py

import streamlit as st
import serial
import json
import datetime
import os
import numpy as np
import sounddevice as sd
import time
import threading
import queue
from serial.tools import list_ports

# -----------------------
# 설정 부분
# -----------------------
BAUD_RATE = 9600
SAVE_FILE = 'melodies.json'

# -----------------------
# Streamlit 페이지 설정
# -----------------------
st.set_page_config(page_title="조이스틱 작곡가", page_icon="🎵", layout="centered")
st.title("🎹 조이스틱 작곡가")
st.caption("아두이노 조이스틱으로 멜로디를 만들고 PC에 저장하세요.")

# -----------------------
# JSON/사운드 함수 (변경 없음)
# -----------------------
def load_melodies():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f).get("melodies", [])
    return []

def save_melodies(melodies):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"melodies": melodies}, f, indent=2, ensure_ascii=False)

def play_tone(frequency, duration=0.3, volume=0.3, sample_rate=44100):
    if frequency <= 0: time.sleep(duration); return
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(frequency * t * 2 * np.pi)
    audio = wave * volume
    sd.play(audio, sample_rate)
    sd.wait()

def play_melody(notes, note_duration=0.3):
    for freq in notes:
        play_tone(freq, note_duration)
        time.sleep(0.05)

# -----------------------
# 백그라운드 스레드 함수 (변경 없음)
# -----------------------
def serial_listener(ser_instance, q):
    while True:
        if not ser_instance.is_open:
            break
        try:
            line = ser_instance.readline().decode('utf-8', errors='ignore').strip()
            if line:
                q.put(line)
        except Exception:
            time.sleep(0.5)

# -----------------------
# Queue 처리 함수 (변경 없음)
# -----------------------
def process_queue(q):
    rerun_needed = False
    while not q.empty():
        line = q.get() 

        if line.startswith("STATUS:"):
            parts = line.replace("STATUS:", "").split(",")
            if len(parts) >= 5:
                is_playing_str, note_count_str, display_num_str, octave, note_name = parts[:5]
                st.session_state["is_playing"] = (is_playing_str == "1")
                st.session_state["note_count"] = int(note_count_str)
                st.session_state["display_num"] = int(display_num_str)
                
                if st.session_state["is_playing"]:
                    st.session_state["current_note_info"] = f"재생 시간: {st.session_state['display_num']}초"
                else:
                    st.session_state["current_note_info"] = f"{note_name} (옥타브 {octave})"

        elif line.startswith("SAVE_SONG:") and st.session_state.get("pending_melody") is None:
            data = line.replace("SAVE_SONG:", "")
            notes = [int(n) for n in data.split(",") if n.strip().isdigit()]
            if notes:
                st.session_state["pending_melody"] = notes
                if "pending_melody_name" not in st.session_state:
                    st.session_state["pending_melody_name"] = f"멜로디_{datetime.datetime.now().strftime('%H%M%S')}"
                rerun_needed = True 

    return rerun_needed

# -----------------------
# 시리얼 연결 + 큐 + 스레드 시작 (변경 없음)
# -----------------------
@st.cache_resource
def get_serial_and_start_listener(port, rate):
    try:
        ser = serial.Serial(port, rate, timeout=0.1)
        q = queue.Queue()
        listener_thread = threading.Thread(target=serial_listener, args=(ser, q), daemon=True)
        listener_thread.start()
        return ser, q
    except Exception as e:
        return str(e)

# -----------------------
# --- 메인 코드 실행 ---
# -----------------------
ports = [p.device for p in list_ports.comports()]
if not ports:
    st.error("❌ 연결된 아두이노를 찾을 수 없습니다. 포트를 확인해주세요.")
    st.stop()

selected_port = st.selectbox("아두이노 포트를 선택하세요:", ports)
connection_result = get_serial_and_start_listener(selected_port, BAUD_RATE)

if isinstance(connection_result, str):
    st.error(f"❌ 포트 연결 실패: {connection_result}")
    st.stop()
else:
    ser, data_queue = connection_result
    st.success(f"✅ 아두이노 연결됨 ({selected_port})")

# -----------------------
# 세션 상태 기본값 확인 (변경 없음)
# -----------------------
if "melodies" not in st.session_state: st.session_state["melodies"] = load_melodies()
if "pending_melody" not in st.session_state: st.session_state["pending_melody"] = None
if "is_playing" not in st.session_state: st.session_state["is_playing"] = False
if "note_count" not in st.session_state: st.session_state["note_count"] = 0
if "display_num" not in st.session_state: st.session_state["display_num"] = 0
if "current_note_info" not in st.session_state: st.session_state["current_note_info"] = "아두이노 연결 대기 중..."

# -----------------------
# 큐 처리 (변경 없음)
# -----------------------
need_to_rerun_now = process_queue(data_queue)

# -----------------------
# UI 섹션 1: 라이브 상태 (변경 없음)
# -----------------------
col1, col2 = st.columns([1, 1])
with col1:
    st.subheader("🔴 라이브 상태")
    status_icon = "▶️" if st.session_state.get("is_playing", False) else "🎹"
    status_text = "재생 중" if st.session_state.get("is_playing", False) else "작곡 중"
    st.metric(label=f"{status_icon} 현재 상태: {status_text}",
              value=f"{st.session_state.get('note_count', 0)} 개 음 입력됨",
              delta=st.session_state.get("current_note_info", "대기 중..."),
              delta_color="off")

# -----------------------
# UI 섹션 2: 멜로디 저장 (변경 없음)
# -----------------------
with col2:
    st.subheader("✍️ 멜로디 저장")
    if st.session_state.get("pending_melody"):
        with st.form("save_form"):
            name = st.text_input(
                "🎼 새 멜로디 이름:",
                key="pending_melody_name"
            )
            submitted = st.form_submit_button("💾 저장하기")
            
            if submitted:
                melody = {
                    "name": st.session_state.pending_melody_name,
                    "notes": st.session_state["pending_melody"],
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state["melodies"].insert(0, melody)
                save_melodies(st.session_state["melodies"])
                st.success(f"✅ '{name}' 저장 완료!")
                
                st.session_state["pending_melody"] = None
                if "pending_melody_name" in st.session_state:
                    del st.session_state["pending_melody_name"]
                
                st.rerun() # 폼 제출 완료 후에는 즉시 새로고침
    else:
        st.info("아두이노에서 조이스틱 버튼을 2초 이상 길게 누르면 여기에 저장 버튼이 나타납니다.")

# -----------------------
# UI 섹션 3: 저장된 멜로디 (변경 없음)
# -----------------------
st.divider()
st.subheader("📂 저장된 멜로디 목록")
melodies = st.session_state["melodies"]

if not melodies:
    st.write("아직 저장된 멜로디가 없습니다.")
else:
    for i, melody in enumerate(melodies):
        with st.expander(f"**{melody['name']}** ({melody['created_at']})"):
            st.write(f"🎵 음 개수: {len(melody['notes'])}")
            st.bar_chart(melody["notes"], height=150)
            if st.button("▶️ PC 스피커로 재생", key=f"play_{i}"):
                with st.spinner("🔊 재생 중..."):
                    play_melody(melody["notes"])
                st.success("✅ 재생 완료!")

# -----------------------
# (✅ 핵심 수정) 새로고침 루프
# -----------------------

# 1. 'SAVE_SONG' 신호가 방금 감지됐다면(need_to_rerun_now=True),
#    즉시 새로고침해서 저장 폼을 띄웁니다.
if need_to_rerun_now:
    st.rerun()

# 2. '저장 폼'이 이미 화면에 떠 있는 상태라면(pending_melody가 None이 아님),
#    자동 새로고침을 '멈추고' 사용자의 버튼 클릭/Enter 입력을 기다립니다.
elif st.session_state.get("pending_melody") is not None:
    pass  # 폼이 활성화된 상태. 자동 새로고침 중지.

# 3. '작곡 중' 상태라면(pending_melody가 None임),
#    '라이브 상태'를 위해 0.05초마다 새로고침합니다.
else:
    time.sleep(0.05)
    st.rerun()