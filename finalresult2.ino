#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <math.h> 

LiquidCrystal_I2C lcd(0x27, 16, 2);

// --- 핀 번호 정의 ---
#define JOY_X A0
#define JOY_Y A1
#define JOY_SW 8          
#define PLAY_BUTTON_PIN 0 
#define BUZZER_PIN 2

// --- 7세그먼트 핀 설정 ---
const int segmentPins[] = {3, 4, 5, 6, 7, 11, 12, 13}; 
const int digitPins[] = {A3, A2, 10, 9}; 

const byte digitPatterns[10] = {
  B0111111, // 0
  B0000110, // 1
  B1011011, // 2
  B1001111, // 3
  B1100110, // 4
  B1101101, // 5
  B1111101, // 6
  B0000111, // 7
  B1111111, // 8
  B1101111  // 9
};

// --- 곡 저장 및 상태 변수 ---
#define MAX_NOTES 100
#define NOTE_DURATION 300
int songNotes[MAX_NOTES];
int noteCount = 0;
bool isPlaying = false;
int octave = 4;
int noteIndex = 0;

// --- 재생 관련 변수 ---
unsigned long playbackStartTime = 0;
int currentPlayIndex = 0;
unsigned long lastNotePlayTime = 0;

// --- 7세그먼트 표시 관련 변수 ---
int numberToDisplay = 0; 
unsigned long lastDisplayUpdateTime = 0;
const int displayRefreshInterval = 2; 
int currentDigit = 0;

// 음계 주파수 및 이름
int notes[] = {262, 294, 330, 349, 392, 440, 494};
String noteNames[] = {"Do", "Re", "Mi", "Fa", "So", "La", "Si"};

// 버튼 누름 시간 감지를 위한 변수
unsigned long joySwPressTime = 0;
bool isJoySwPressed = false;

// --- Python UI 통신용 변수 ---
unsigned long lastSerialSendTime = 0;
unsigned long lastSongSendTime = 0;   
const int SONG_SEND_INTERVAL = 3000; 

// --- ❗ (수정됨) 옥타브 변경 delay() 제거용 변수 ---
unsigned long lastJoyYMoveTime = 0;
const int joyYDelay = 200; // 200ms 반복 딜레이
bool joyYCentered = true; // 조이스틱이 중앙에 있는지 여부


void setup() {
  Serial.begin(9600); 
  
  lcd.init();
  lcd.backlight();
  pinMode(JOY_SW, INPUT_PULLUP);
  pinMode(PLAY_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  
  for (int i = 0; i < 8; i++) {
    pinMode(segmentPins[i], OUTPUT);
  }
  
  for (int i = 0; i < 4; i++) {
    pinMode(digitPins[i], OUTPUT);
    digitalWrite(digitPins[i], LOW);
  }

  lcd.print("Music Composer");
  lcd.setCursor(0, 1);
  lcd.print("Select Note...");
}

// 7세그먼트 숫자 표시
void updateSevenSegment() {
  digitalWrite(digitPins[currentDigit], LOW);
  currentDigit++;
  if (currentDigit > 3) {
    currentDigit = 0;
  }
  int tempNumber = numberToDisplay;
  int digitValue;
  if (currentDigit == 0) digitValue = tempNumber % 10;
  else if (currentDigit == 1) digitValue = (tempNumber / 10) % 10;
  else if (currentDigit == 2) digitValue = (tempNumber / 100) % 10;
  else digitValue = (tempNumber / 1000) % 10;

  if (tempNumber < 10 && currentDigit > 0) return;
  if (tempNumber < 100 && currentDigit > 1) return;
  if (tempNumber < 1000 && currentDigit > 2) return;
  byte pattern = digitPatterns[digitValue];
  for (int i = 0; i < 7; i++) {
    if (bitRead(pattern, i) == 0) {
      digitalWrite(segmentPins[i], HIGH);
    } else {
      digitalWrite(segmentPins[i], LOW);
    }
  }
  digitalWrite(digitPins[currentDigit], HIGH);
}


void loop() {
  // --- 7세그먼트 업데이트 ---
  if (millis() - lastDisplayUpdateTime >= displayRefreshInterval) {
    lastDisplayUpdateTime = millis();
    updateSevenSegment();
  }

  // --- 재생/정지 버튼 처리 ---
  if (digitalRead(PLAY_BUTTON_PIN) == LOW) {
    delay(200); // (짧은 딜레이라 버튼 입력에 큰 영향 없음)
    isPlaying = !isPlaying;
    
    if (isPlaying) {
      if (noteCount > 0) {
        playbackStartTime = millis();
        currentPlayIndex = 0;
        lastNotePlayTime = 0;
        lcd.clear();
        lcd.print("Now Playing...");
        lcd.setCursor(0, 1);
        lcd.print(noteCount);
        lcd.print(" Notes");
      } else {
        isPlaying = false;
      }
    } else {
      noTone(BUZZER_PIN);
      lcd.clear();
      lcd.print("Music Composer");
    }
  }

  if (isPlaying) {
    /***** 재생 모드 *****/
    unsigned long currentTime = millis();
    if (currentTime - lastNotePlayTime >= (NOTE_DURATION + 50)) {
      if (currentPlayIndex < noteCount) {
        tone(BUZZER_PIN, songNotes[currentPlayIndex]);
        lastNotePlayTime = currentTime;
        currentPlayIndex++;
      } else { 
        isPlaying = false;
        noTone(BUZZER_PIN);
        lcd.clear();
        lcd.print("Play Finished!");
        delay(1000);
        lcd.clear();
        lcd.print("Music Composer");
      }
    }
    if (currentTime - lastNotePlayTime >= NOTE_DURATION) {
      noTone(BUZZER_PIN);
    }
    int elapsedSeconds = (millis() - playbackStartTime) / 1000;
    numberToDisplay = elapsedSeconds;

  } else {
    /***** 작곡 모드 *****/
    
    // --- ❗ (수정됨) delay(200)을 제거하여 버튼 입력을 놓치지 않도록 수정 ---
    int joyY = analogRead(JOY_Y);
    unsigned long currentTimeForJoy = millis(); // 현재 시간

    // 조이스틱을 위로 밀었고, (중앙에 있었거나 || 200ms가 지났다면)
    if (joyY < 100 && octave < 7 && (joyYCentered || (currentTimeForJoy - lastJoyYMoveTime > joyYDelay))) {
      octave++;
      lastJoyYMoveTime = currentTimeForJoy; // 마지막 변경 시간 기록
      joyYCentered = false; // 중앙이 아님
    }
    // 조이스틱을 아래로 밀었고, (중앙에 있었거나 || 200ms가 지났다면)
    else if (joyY > 900 && octave > 1 && (joyYCentered || (currentTimeForJoy - lastJoyYMoveTime > joyYDelay))) {
      octave--;
      lastJoyYMoveTime = currentTimeForJoy; // 마지막 변경 시간 기록
      joyYCentered = false; // 중앙이 아님
    }
    // 조이스틱이 중앙(400~600)으로 돌아왔다면
    else if (joyY >= 400 && joyY <= 600) { 
      joyYCentered = true; // 중앙임
    }
    // --- (수정 끝) ---

    int joyX = analogRead(JOY_X);
    noteIndex = map(joyX, 0, 1023, 0, 6);
    int currentFrequency = notes[noteIndex] * pow(2, octave - 4);

    String displayInfo = "Oct:" + String(octave) + " " + noteNames[noteIndex];
    lcd.setCursor(0, 1);
    lcd.print(displayInfo + "      ");
    lcd.setCursor(13, 0);
    lcd.print(noteCount);
    lcd.print("/");
    lcd.print(MAX_NOTES);
    
    numberToDisplay = noteCount;

    // --- 조이스틱 버튼 처리 (변경 없음) ---
    if (digitalRead(JOY_SW) == LOW) {
      if (!isJoySwPressed) {
        isJoySwPressed = true;
        joySwPressTime = millis();
      }
      
      // 2초 이상 길게 누르면 (곡 저장 신호 전송)
      if (millis() - joySwPressTime > 2000) { 
        if (noteCount > 0) { 
          Serial.print("SAVE_SONG:"); // 1. Save signal
          for (int i = 0; i < noteCount; i++) { // 2. Save data
            Serial.print(songNotes[i]);
            if (i < noteCount - 1) {
              Serial.print(",");
            }
          }
          Serial.println(); // 3. End of line
          Serial.flush(); // 4. Wait for send
        }
        
        noteCount = 0; // 5. 데이터를 보낸 "후"에 초기화
        lcd.clear();
        lcd.print("Song Saved&Cleared!");
        tone(BUZZER_PIN, 150, 500);
        delay(1000);
        lcd.clear();
        lcd.print("Music Composer");
        isJoySwPressed = false;
        while(digitalRead(JOY_SW) == LOW) {} 
      }
    } else { // 버튼이 (LOW가 아님) HIGH일 때
      if (isJoySwPressed) { // ❗❗❗ "짧게 누름" (녹음) 로직 ❗❗❗
        // (isJoySwPressed가 true라는 것은, 방금 전까지 LOW였다는 뜻)
        
        if (noteCount < MAX_NOTES) {
          songNotes[noteCount] = currentFrequency;
          noteCount++; // 👈 이 부분이 실행되어야 합니다!
          tone(BUZZER_PIN, currentFrequency, 200);
        } else {
          lcd.setCursor(0,1);
          lcd.print("Memory Full!      ");
          tone(BUZZER_PIN, 200, 200);
          delay(1000);
        }
        isJoySwPressed = false; // 플래그 리셋
      }
    }
  }

  // --- Python UI로 데이터 전송 ---
  sendSerialData();
}


// --------------------------------------------------------
// Python UI로 데이터를 전송하기 위한 함수들 (변경 없음)
// --------------------------------------------------------

void sendFullSongData() {
  if (!isPlaying && millis() - lastSongSendTime >= SONG_SEND_INTERVAL) {
    lastSongSendTime = millis();
    Serial.print("SONG:"); // "라이브 프리뷰"용 데이터
    for (int i = 0; i < noteCount; i++) {
      Serial.print(songNotes[i]);
      if (i < noteCount - 1) {
        Serial.print(",");
      }
    }
    Serial.println(); 
  }
}

void sendSerialData() {
  if (millis() - lastSerialSendTime >= 100) {
    lastSerialSendTime = millis();
    Serial.print("STATUS:"); // "현재 상태"용 데이터
    Serial.print(isPlaying ? "1" : "0");
    Serial.print(",");
    Serial.print(noteCount);
    Serial.print(",");
    Serial.print(numberToDisplay);
    Serial.print(",");
    Serial.print(octave);
    Serial.print(",");
    Serial.print(noteNames[noteIndex]);
    Serial.println();
  }
  sendFullSongData();
}