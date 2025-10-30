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

// 음계 주파수 및 이름
int notes[] = {262, 294, 330, 349, 392, 440, 494};
String noteNames[] = {"Do", "Re", "Mi", "Fa", "So", "La", "Si"};

// 버튼 누름 시간 감지를 위한 변수
unsigned long joySwPressTime = 0;
bool isJoySwPressed = false;

// --- Python UI 통신용 변수 ---
unsigned long lastSerialSendTime = 0;

// --- 옥타브 변경 delay() 제거용 변수 ---
unsigned long lastJoyYMoveTime = 0;
const int joyYDelay = 200;
bool joyYCentered = true;

void setup() {
  Serial.begin(9600); 
  
  lcd.init();
  lcd.backlight();
  pinMode(JOY_SW, INPUT_PULLUP);
  pinMode(PLAY_BUTTON_PIN, INPUT_PULLUP);
  pinMode(BUZZER_PIN, OUTPUT);
  lcd.print("Music Composer");
  lcd.setCursor(0, 1);
  lcd.print("Select Note...");
}



void loop() {

  // --- 재생/정지 버튼 처리 ---
  if (digitalRead(PLAY_BUTTON_PIN) == LOW) {
    delay(200); 
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

  } else {
    /***** 작곡 모드 *****/
    int joyY = analogRead(JOY_Y);
    unsigned long currentTimeForJoy = millis();

    if (joyY < 100 && octave < 7 && (joyYCentered || (currentTimeForJoy - lastJoyYMoveTime > joyYDelay))) {
      octave++;
      lastJoyYMoveTime = currentTimeForJoy;
      joyYCentered = false;
    } else if (joyY > 900 && octave > 1 && (joyYCentered || (currentTimeForJoy - lastJoyYMoveTime > joyYDelay))) {
      octave--;
      lastJoyYMoveTime = currentTimeForJoy;
      joyYCentered = false;
    } else if (joyY >= 400 && joyY <= 600) { 
      joyYCentered = true;
    }

    int joyX = analogRead(JOY_X);
    noteIndex = map(joyX, 0, 1023, 0, 6);
    int currentFrequency = notes[noteIndex] * pow(2, octave - 4);

    String displayInfo = "Oct:" + String(octave) + " " + noteNames[noteIndex];
    lcd.setCursor(0, 1);
    lcd.print(displayInfo + "        ");
    lcd.setCursor(13, 0);
    lcd.print(noteCount);
    lcd.print("/");
    lcd.print(MAX_NOTES);

    if (digitalRead(JOY_SW) == LOW) {
      if (!isJoySwPressed) {
        isJoySwPressed = true;
        joySwPressTime = millis();
      }
      
      if (millis() - joySwPressTime > 2000) { 
        if (noteCount > 0) { 
          Serial.print("SAVE_SONG:");
          for (int i = 0; i < noteCount; i++) {
            Serial.print(songNotes[i]);
            if (i < noteCount - 1) {
              Serial.print(",");
            }
          }
          Serial.println();
          Serial.flush();
        }
        noteCount = 0;
        lcd.clear();
        lcd.print("Song Saved&Cleared!");
        tone(BUZZER_PIN, 150, 500);
        delay(1000);
        lcd.clear();
        lcd.print("Music Composer");
        isJoySwPressed = false;
        while(digitalRead(JOY_SW) == LOW) {} 
      }
    } else {
      if (isJoySwPressed) { 
        if (noteCount < MAX_NOTES) {
          songNotes[noteCount] = currentFrequency;
          noteCount++;
          tone(BUZZER_PIN, currentFrequency, 200);
        } else {
          lcd.setCursor(0,1);
          lcd.print("Memory Full!      ");
          tone(BUZZER_PIN, 200, 200);
          delay(1000);
        }
        isJoySwPressed = false;
      }
    }
  }

  // --- Python UI로 데이터 전송 ---
  sendSerialData();
}


void sendSerialData() {
  if (millis() - lastSerialSendTime >= 100) {
    lastSerialSendTime = millis();
    Serial.print("STATUS:");
    Serial.print(isPlaying ? "1" : "0");
    Serial.print(",");
    Serial.print(noteCount);
    Serial.print(",");
    Serial.print(",");
    Serial.print(octave);
    Serial.print(",");
    Serial.print(noteNames[noteIndex]);
    Serial.println();
  }
}