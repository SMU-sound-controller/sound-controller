import streamlit as st
import serial
import time
import os
from music21 import converter, instrument, note, stream, tempo, pitch, duration

# --- 1. 설정 ---
# ❗ 아두이노 IDE의 '도구 > 포트'에서 확인한 실제 포트 번호로 변경
SERIAL_PORT = 'COM4' 
SERIAL_BAUD = 9600
MAX_NOTES = 100
NOTE_DURATION_MS = 300
# --- (설정 끝) ---

# --- 2. 시리얼 연결 및 헬퍼 함수 ---
@st.cache_resource
def get_serial_connection(port, baud):
    """시리얼 포트 연결을 시도하고 connection 객체를 반환합니다."""
    try:
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(0.1) 
        ser.flushInput() # 연결 시 버퍼 비우기
        return ser
    except serial.SerialException as e:
        st.error(f"'{port}'에 연결 실패: {e}")
        st.warning("1. 아두이노가 PC에 연결되었는지 확인하세요.")
        st.warning(f"2. 위 코드의 SERIAL_PORT를 올바른 포트 번호로 수정하세요.")
        st.warning(f"3. 아두이노 IDE의 시리얼 모니터가 닫혀있는지 확인하세요.")
        st.stop()

def frequency_to_music21_note(frequency, default_duration_quarters=0.25):
    """주파수를 Music21의 Note 또는 Rest 객체로 변환합니다."""
    if frequency == 0: 
        return note.Rest(quarterLength=default_duration_quarters)
    try:
        p = pitch.Pitch()
        p.frequency = frequency
        n = note.Note(p.nameWithOctave)
        n.quarterLength = default_duration_quarters
        return n
    except Exception:
        return note.Rest(quarterLength=default_duration_quarters)

@st.cache_data(ttl=60) # 60초간 MIDI 파일 캐시
def create_and_save_score_audio(frequencies, filename="score.mid"):
    """
    주파수 리스트를 받아 MIDI 파일로 저장하고 파일 경로를 반환합니다.
    (MuseScore 불필요)
    """
    if not frequencies:
        return None
    s = stream.Stream()
    s.append(tempo.MetronomeMark(number=120))
    s.append(instrument.Piano())
    note_quarter_length = 0.5 # 8분음표

    for freq in frequencies:
        m21_note_or_rest = frequency_to_music21_note(freq, note_quarter_length)
        s.append(m21_note_or_rest)
        s.append(note.Rest(quarterLength=0.25)) # 음표 사이 쉼표
    try:
        midi_path = s.write('midi', fp=filename)
        return midi_path
    except Exception as e:
        st.error(f"MIDI 파일 생성 실패: {e}")
        return None

# --- 3. (새 기능) 저장된 곡 플레이리스트 UI 업데이트 함수 ---
def update_saved_songs_ui():
    """
    st.session_state.saved_songs를 기반으로 사이드바 UI를 다시 그립니다.
    """
    saved_song_placeholder.empty() # 사이드바를 비웁니다.
    
    with saved_song_placeholder.container():
        st.session_state.save_message_placeholder = st.empty()
        
        if not st.session_state.saved_songs:
            st.write("아직 저장된 곡이 없습니다.")
            st.caption("아두이노의 조이스틱 버튼을 2초 이상 눌러 현재 곡을 저장하세요.")
        
        # 저장된 곡 목록을 순회하며 UI 생성
        for i, song_data in enumerate(st.session_state.saved_songs):
            st.subheader(song_data['name'])
            
            audio_path = create_and_save_score_audio(
                song_data['frequencies'], 
                filename=f"saved_song_{i}.mid"
            )
            
            if audio_path and os.path.exists(audio_path):
                with open(audio_path, 'rb') as f:
                    st.audio(f.read(), format='audio/midi')
            else:
                st.warning("저장된 곡의 오디오를 생성할 수 없습니다.")
            st.divider()

# --- 4. Streamlit UI 설정 ---
st.set_page_config(layout="wide")
st.title("Arduino Music Composer - Live Dashboard 🎹")

if 'saved_songs' not in st.session_state:
    st.session_state.saved_songs = []
if 'save_message_placeholder' not in st.session_state:
    st.session_state.save_message_placeholder = st.empty()

# 시리얼 연결
ser = get_serial_connection(SERIAL_PORT, SERIAL_BAUD)
st.success(f"Arduino 연결 성공! (Port: {SERIAL_PORT})")

# --- 5. UI 레이아웃 ---
st.sidebar.header("🎶 Saved Songs Playlist")
saved_song_placeholder = st.sidebar.empty() 

col1, col2, col3 = st.columns(3)
with col1:
    st.header("Current Status")
    status_placeholder = st.empty()
    segment_placeholder = st.empty()
with col2:
    st.header("Compose Info")
    octave_placeholder = st.empty()
    note_placeholder = st.empty()
with col3:
    st.header("Song Progress")
    count_placeholder = st.empty()
    progress_placeholder = st.empty()

st.divider()
st.header("Composing Note (Live Preview)")
score_audio_placeholder = st.empty() 

# '현재' 곡 데이터는 "라이브 프리뷰"에만 사용됨
current_song_frequencies = []
last_rendered_song_hash = None

# --- 6. 초기 UI 그리기 ---
status_placeholder.metric("Status", "Initializing...")
segment_placeholder.metric("7-Segment Display", "0")
octave_placeholder.metric("Current Octave", "...")
note_placeholder.metric("Current Note", "...")
count_placeholder.metric("Stored Notes", f"0 / {MAX_NOTES}")
progress_placeholder.progress(0.0)
update_saved_songs_ui() 

# --- 7. 메인 루프 ---
while True:
    try:
        if ser.in_waiting > 0:
            data_line = ser.readline().decode('utf-8').strip()
            
            if not data_line:
                continue

            # 7-1. "STATUS:" 데이터 처리 (변경 없음)
            if data_line.startswith("STATUS:"):
                parts = data_line[len("STATUS:"):].split(',')
                if len(parts) == 5:
                    is_playing = (parts[0] == "1")
                    note_count = int(parts[1])
                    display_num = int(parts[2])
                    octave = int(parts[3])
                    note_name = parts[4]
                    
                    status_str = "▶️ Playing" if is_playing else "Compose Mode"
                    status_placeholder.metric("Status", status_str)
                    segment_label = "Playback Time (sec)" if is_playing else "Note Count"
                    segment_placeholder.metric(f"7-Segment ({segment_label})", f"{display_num}")
                    octave_placeholder.metric("Current Octave", f"{octave}")
                    note_placeholder.metric("Current Note", f"{note_name}")
                    count_placeholder.metric("Stored Notes", f"{note_count} / {MAX_NOTES}")
                    progress_placeholder.progress(note_count / MAX_NOTES if MAX_NOTES > 0 else 0)
            
            # 7-2. "SONG:" 데이터 처리 (라이브 프리뷰용, 변경 없음)
            elif data_line.startswith("SONG:"):
                freq_str_list = data_line[len("SONG:"):].split(',')
                if freq_str_list == ['']:
                    current_song_frequencies = []
                else:
                    current_song_frequencies = [int(f) for f in freq_str_list]
                
                new_song_hash = hash(tuple(current_song_frequencies))

                if new_song_hash != last_rendered_song_hash:
                    st.session_state.save_message_placeholder.empty()
                    
                    if current_song_frequencies:
                        audio_path = create_and_save_score_audio(current_song_frequencies, "current_song.mid")
                        if audio_path and os.path.exists(audio_path):
                            with open(audio_path, 'rb') as f:
                                score_audio_placeholder.audio(f.read(), format='audio/midi')
                            last_rendered_song_hash = new_song_hash
                        else:
                            score_audio_placeholder.warning("현재 곡 오디오 생성에 실패했습니다.")
                    else:
                        score_audio_placeholder.info("저장된 음표가 없습니다. 조이스틱을 눌러 음표를 추가해보세요!")
                        last_rendered_song_hash = new_song_hash
            
            # 7-3. ❗ (수정됨) "SAVE_SONG:" 신호 처리 (버그 수정 완료)
            elif data_line.startswith("SAVE_SONG:"):
                
                # 1. 아두이노가 신호와 "함께 보낸" 데이터 파싱
                freq_str_list = data_line[len("SAVE_SONG:"):].split(',')
                saved_frequencies = []
                if freq_str_list != ['']:
                    try:
                        saved_frequencies = [int(f) for f in freq_str_list]
                    except ValueError:
                        st.toast("저장 데이터 파싱 오류", icon="🔥")
                        continue # 이 신호 무시

                # 2. 파싱한 데이터가 있을 경우에만 저장
                if saved_frequencies:
                    # 3. 새 노래 데이터 생성
                    song_name = f"Song {len(st.session_state.saved_songs) + 1}"
                    new_saved_song = {
                        'name': song_name,
                        'frequencies': saved_frequencies # ❗ 파싱한 데이터를 직접 사용
                    }
                    
                    # 4. 플레이리스트에 추가
                    st.session_state.saved_songs.append(new_saved_song)
                    
                    # 5. 사이드바 UI 새로고침
                    update_saved_songs_ui()
                    
                    # 6. 사이드바에 "저장 확인" 메시지 표시
                    st.session_state.save_message_placeholder.success(f"{song_name}이(가) 저장되었습니다!", icon="✅")
                    
                    # 7. 메인 UI는 어차피 아두이노에서 빈 "SONG:" 신호가 올 것이므로
                    #    즉각적으로 "저장됨"으로 표시
                    score_audio_placeholder.info("곡이 저장되었습니다! 새 곡을 작곡해 보세요.")
                    # (다음 "SONG:" 신호가 와서 UI를 갱신할 때까지 이 메시지가 유지됨)
                else:
                    st.toast("저장할 음표가 없습니다. (신호는 왔으나 데이터가 빔)", icon="🤷")

    # (예외 처리)
    except (UnicodeDecodeError, ValueError) as e:
        st.toast(f"데이터 파싱 오류: {e}", icon="⚠️")
        time.sleep(0.1)
    except serial.SerialException:
        st.error("아두이노 연결이 끊어졌습니다! 재연결을 시도합니다...")
        ser.close()
        time.sleep(2)
        st.rerun() 
    
    time.sleep(0.01) # CPU 과부하 방지