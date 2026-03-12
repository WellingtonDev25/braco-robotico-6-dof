#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

//Adafruit PWM Servo Driver Library    instalar biblioteca 
Adafruit_PWMServoDriver pca = Adafruit_PWMServoDriver(0x40);

// Ajuste fino conforme seus servos
#define SERVO_MIN  150
#define SERVO_MAX  600

const int canais[] = {1, 2, 3, 4, 5, 6};
const int totalServos = sizeof(canais) / sizeof(canais[0]);

// Posições iniciais de cada canal
const int posicoesIniciais[] = {74, 24, 180, 77, 128, 116};

String bufferSerial = "";

uint16_t anguloParaPulso(int angulo) {
  angulo = constrain(angulo, 0, 180);
  return map(angulo, 0, 180, SERVO_MIN, SERVO_MAX);
}

bool canalValido(int canal) {
  for (int i = 0; i < totalServos; i++) {
    if (canais[i] == canal) return true;
  }
  return false;
}

void moverServo(int canal, int angulo) {
  uint16_t pulso = anguloParaPulso(angulo);
  pca.setPWM(canal, 0, pulso);
}

void centralizarTodos() {
  for (int i = 0; i < totalServos; i++) {
    moverServo(canais[i], 90);
    delay(150);
  }
}

void irParaPosicaoInicial() {
  for (int i = 0; i < totalServos; i++) {
    moverServo(canais[i], posicoesIniciais[i]);
    delay(150);
  }
}

void processarComando(String cmd) {
  cmd.trim();

  if (cmd.length() == 0) return;

  // Comando especial
  if (cmd == "CENTER") {
    centralizarTodos();
    Serial.println("OK:CENTER");
    return;
  }

  // Novo comando: volta para posição inicial
  if (cmd == "HOME") {
    irParaPosicaoInicial();
    Serial.println("OK:HOME");
    return;
  }

  // Formato esperado: canal,angulo
  int virgula = cmd.indexOf(',');

  if (virgula == -1) {
    Serial.println("ERRO:FORMATO");
    return;
  }

  String sCanal = cmd.substring(0, virgula);
  String sAngulo = cmd.substring(virgula + 1);

  int canal = sCanal.toInt();
  int angulo = sAngulo.toInt();

  if (!canalValido(canal)) {
    Serial.println("ERRO:CANAL_INVALIDO");
    return;
  }

  if (angulo < 0 || angulo > 180) {
    Serial.println("ERRO:ANGULO_INVALIDO");
    return;
  }

  moverServo(canal, angulo);

  Serial.print("OK:");
  Serial.print(canal);
  Serial.print(",");
  Serial.println(angulo);
}

void setup() {
  Serial.begin(115200);

  pca.begin();
  pca.setPWMFreq(50);
  delay(500);

  // Vai para a posição inicial ao ligar
  irParaPosicaoInicial();

  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      processarComando(bufferSerial);
      bufferSerial = "";
    } else {
      bufferSerial += c;
    }
  }
}