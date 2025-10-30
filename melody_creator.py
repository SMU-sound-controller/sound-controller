# 🎶 app.py (v15 - 삭제 기능 추가)
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
# JSON/사운드 함수 (v14와 동일)
# -----------------------
def load_melodies():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f).get("melodies", [])
        except json.JSONDecodeError:
            return [] 
    return []

def save_melodies(melodies):
    with open(SAVE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"melodies": melodies}, f, indent=2, ensure_ascii=False)

def generate_tone(frequency, duration, volume=0.3, sample_rate=44100, fade_ms=5):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    if frequency <= 0: return np.zeros(len(t))
    wave = np.sin(frequency * t * 2 * np.pi)
    fade_len = int(sample_rate * (fade_ms / 1000.0))
    if fade_len * 2 > len(t): fade_len = len(t) // 2
    envelope = np.ones(len(t))
    if fade_len > 0:
        envelope[:fade_len] = np.linspace(0, 1, fade_len)
        envelope[-fade_len:] = np.linspace(1, 0, fade_len)
    return (wave * envelope) * volume

def play_melody(notes, note_duration=0.3, gap_duration=0.05, sample_rate=44100):
    all_audio_segments = []
    gap_samples = int(sample_rate * gap_duration)
    silence = np.zeros(gap_samples)
    for freq in notes:
        note_wave = generate_tone(freq, duration=note_duration, sample_rate=sample_rate)
        all_audio_segments.append(note_wave)
        all_audio_segments.append(silence) 
    if not all_audio_segments: return
    full_melody = np.concatenate(all_audio_segments)
    try:
        sd.play(full_melody, sample_rate)
        sd.wait()
    except Exception as e:
        st.warning(f"오디오 재생 중 오류 발생: {e}")

# -----------------------
# 백그라운드 스레드 함수 (v14와 동일)
# -----------------------
def serial_listener(ser_instance, q):
    while True:
        if not ser_instance.is_open: break
        try:
            line = ser_instance.readline().decode('utf-8', errors='ignore').strip()
            if line: q.put(line)
        except Exception: time.sleep(0.5)

# -----------------------
# Queue 처리 함수 (v14와 동일)
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
# 시리얼 연결 + 큐 + 스레드 시작 (v14와 동일)
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
# 세션 상태 기본값 확인 (v14와 동일)
# -----------------------
if "melodies" not in st.session_state: st.session_state["melodies"] = load_melodies()
if "pending_melody" not in st.session_state: st.session_state["pending_melody"] = None
if "is_playing" not in st.session_state: st.session_state["is_playing"] = False
if "note_count" not in st.session_state: st.session_state["note_count"] = 0
if "display_num" not in st.session_state: st.session_state["display_num"] = 0
if "current_note_info" not in st.session_state: st.session_state["current_note_info"] = "아두이노 연결 대기 중..."
if "slot_1" not in st.session_state: st.session_state.slot_1 = "(비워두기)"
if "slot_2" not in st.session_state: st.session_state.slot_2 = "(비워두기)"
if "slot_3" not in st.session_state: st.session_state.slot_3 = "(비워두기)"
if "slot_4" not in st.session_state: st.session_state.slot_4 = "(비워두기)"
if "editing_melody_index" not in st.session_state:
    st.session_state.editing_melody_index = None

# -----------------------
# 큐 처리 (v14와 동일)
# -----------------------
need_to_rerun_now = process_queue(data_queue)

# -----------------------
# UI 섹션 1: 라이브 상태 (v14와 동일)
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
# UI 섹션 2: 멜로디 저장 (v14와 동일)
# -----------------------
with col2:
    st.subheader("✍️ 멜로디 저장")
    if st.session_state.get("pending_melody"):
        with st.form("save_form"):
            name = st.text_input("🎼 새 멜로디 이름:", key="pending_melody_name")
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
                st.rerun()
    else:
        st.info("아두이노에서 조이스틱 버튼을 2초 이상 길게 누르면 여기에 저장 버튼이 나타납니다.")

# -----------------------
# (✅✅✅ 수정된 기능 ✅✅✅)
# UI 섹션 3: 저장된 멜로디 (삭제 기능 추가)
# -----------------------
st.divider()
st.subheader("📂 저장된 멜로디 목록")
melodies = st.session_state["melodies"]
melody_map = {m["name"]: m["notes"] for m in melodies}

if not melodies:
    st.write("아직 저장된 멜로디가 없습니다.")
else:
    # ❗️ i, melody를 얻기 위해 enumerate를 사용합니다
    for i, melody in enumerate(melodies):
        with st.expander(f"**{melody['name']}** ({melody['created_at']})"):
            
            if st.session_state.editing_melody_index == i:
                # --- '수정 모드' UI ---
                new_name = st.text_input(
                    "새 이름 입력:", 
                    value=melody["name"], 
                    key=f"rename_input_{i}"
                )
                
                if st.button("저장", key=f"save_rename_{i}"):
                    # 1. 시퀀서 슬롯에 있는 이름도 같이 변경
                    old_name = st.session_state.melodies[i]["name"]
                    if st.session_state.slot_1 == old_name: st.session_state.slot_1 = new_name
                    if st.session_state.slot_2 == old_name: st.session_state.slot_2 = new_name
                    if st.session_state.slot_3 == old_name: st.session_state.slot_3 = new_name
                    if st.session_state.slot_4 == old_name: st.session_state.slot_4 = new_name
                    
                    # 2. 메인 목록 및 파일 저장
                    st.session_state.melodies[i]["name"] = new_name
                    save_melodies(st.session_state.melodies)
                    st.session_state.editing_melody_index = None # 수정 모드 종료
                    st.rerun()
                
            else:
                # --- '일반 모드' UI ---
                st.write(f"🎵 음 개수: {len(melody['notes'])}")
                st.bar_chart(melody["notes"], height=150)
                
                st.write("시퀀서에 담기:")
                # ❗️ c1, c2, c3, c4 컬럼 정의
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("슬롯 1", key=f"s1_{i}", use_container_width=True):
                    st.session_state.slot_1 = melody["name"]
                    st.rerun()
                if c2.button("슬롯 2", key=f"s2_{i}", use_container_width=True):
                    st.session_state.slot_2 = melody["name"]
                    st.rerun()
                if c3.button("슬롯 3", key=f"s3_{i}", use_container_width=True):
                    st.session_state.slot_3 = melody["name"]
                    st.rerun()
                if c4.button("슬롯 4", key=f"s4_{i}", use_container_width=True):
                    st.session_state.slot_4 = melody["name"]
                    st.rerun()

                st.divider()
                
                # ❗️ c_play, c_rename, c_delete 컬럼 정의
                c_play, c_rename, c_delete = st.columns([3, 1, 1])
                
                if c_play.button("▶️ PC 스피커로 재생", key=f"play_{i}", use_container_width=True):
                    with st.spinner("🔊 재생 중..."):
                        play_melody(melody["notes"])
                    st.success("✅ 재생 완료!")

                if c_rename.button("이름 변경 ✏️", key=f"rename_{i}", use_container_width=True):
                    st.session_state.editing_melody_index = i
                    st.rerun()
                
                # (✅ 추가) 삭제 버튼 로직
                if c_delete.button("삭제 🗑️", key=f"delete_{i}", use_container_width=True, type="primary"):
                    # 1. 시퀀서 슬롯에서 삭제되는 멜로디 이름 제거
                    deleted_name = st.session_state.melodies[i]["name"]
                    if st.session_state.slot_1 == deleted_name: st.session_state.slot_1 = "(비워두기)"
                    if st.session_state.slot_2 == deleted_name: st.session_state.slot_2 = "(비워두기)"
                    if st.session_state.slot_3 == deleted_name: st.session_state.slot_3 = "(비워두기)"
                    if st.session_state.slot_4 == deleted_name: st.session_state.slot_4 = "(비워두기)"
                    
                    # 2. 메인 목록에서 멜로디 제거
                    st.session_state.melodies.pop(i)
                    
                    # 3. 변경된 목록을 파일에 덮어쓰기
                    save_melodies(st.session_state.melodies)
                    
                    st.success(f"✅ '{deleted_name}' 멜로디가 삭제되었습니다.")
                    st.rerun()

# -----------------------
# UI 섹션 4: 멜로디 시퀀서 (v14와 동일)
# -----------------------
st.divider()
st.subheader("🎶 멜로디 시퀀서 (순서 재생)")

col_slot_1, col_slot_2, col_slot_3, col_slot_4 = st.columns(4)
with col_slot_1:
    st.text_input("슬롯 1", value=st.session_state.slot_1, disabled=True, label_visibility="visible")
with col_slot_2:
    st.text_input("슬롯 2", value=st.session_state.slot_2, disabled=True, label_visibility="visible")
with col_slot_3:
    st.text_input("슬롯 3", value=st.session_state.slot_3, disabled=True, label_visibility="visible")
with col_slot_4:
    st.text_input("슬롯 4", value=st.session_state.slot_4, disabled=True, label_visibility="visible")
    
c_play, c_clear = st.columns([3, 1])

if c_play.button("▶️ 4개 슬롯 순서대로 재생하기", use_container_width=True):
    sequence_to_play = []
    slot_keys = ["slot_1", "slot_2", "slot_3", "slot_4"]
    
    for key in slot_keys:
        selected_name = st.session_state[key]
        if selected_name != "(비워두기)":
            sequence_to_play.extend(melody_map.get(selected_name, []))
    
    if sequence_to_play:
        with st.spinner("🔊 시퀀스 재생 중..."):
            play_melody(sequence_to_play)
        st.success("✅ 시퀀스 재생 완료!")
    else:
        st.warning("재생할 멜로디가 슬롯에 선택되지 않았습니다.")

if c_clear.button("🗑️ 시퀀스 비우기", use_container_width=True):
    st.session_state.slot_1 = "(비워두기)"
    st.session_state.slot_2 = "(비워두기)"
    st.session_state.slot_3 = "(비워두기)"
    st.session_state.slot_4 = "(비워두기)"
    st.rerun()

# -----------------------
# 새로고침 루프 (v14와 동일)
# -----------------------
if need_to_rerun_now:
    st.rerun()
elif st.session_state.get("pending_melody") is not None:
    pass 
elif st.session_state.get("editing_melody_index") is not None:
    pass 
else:
    time.sleep(0.05)
    st.rerun()