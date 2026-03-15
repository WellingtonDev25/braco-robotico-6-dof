#include <Servo.h>

// ============================
// CONFIGURAÇÕES
// ============================

// Porta digital onde o servo está conectado
int portaServo = 9;

// Ângulo que o servo deve mover
int anguloDesejado = 90;


// ============================
// OBJETO SERVO
// ============================
Servo meuServo;


// ============================
// SETUP
// ============================
void setup() {

  // Conecta o servo à porta definida
  meuServo.attach(portaServo);

  // Move para o ângulo desejado
  meuServo.write(anguloDesejado);
}


// ============================
// LOOP
// ============================
void loop() {

  // Não faz nada, apenas mantém posição

}