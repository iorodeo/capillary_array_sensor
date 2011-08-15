#include <Streaming.h>
#include <avr/pgmspace.h>

#define SI A0
#define CLK A1
#define AIN A6

// defines for setting and clearing register bits
#ifndef cbi
#define cbi(sfr, bit) (_SFR_BYTE(sfr) &= ~_BV(bit))
#endif
#ifndef sbi
#define sbi(sfr, bit) (_SFR_BYTE(sfr) |= _BV(bit))
#endif

//#define INTEGTIME 2 

void setup() {
    // set prescale to 16
    sbi(ADCSRA,ADPS2) ;
    cbi(ADCSRA,ADPS1) ;
    cbi(ADCSRA,ADPS0) ;

    // Setup serial communications
    Serial.begin(115200);

    // Set pinModes
    pinMode(SI,OUTPUT);
    pinMode(CLK,OUTPUT);

    // Set clock and si lines low
    digitalWrite(SI,LOW);
    digitalWrite(CLK,LOW);
    
}

void loop() {
    static uint16_t buffer[768];
    readArray(buffer);
    while (Serial.available() > 0) {
        byte cmd = Serial.read();
        if (cmd == 'x') {
            sendArray(buffer);
        }
    }
}


void sendArray(uint16_t *buffer) {
    uint16_t cnt = 0;
    while (cnt < 768) {
        for (int i=0;i<30;i++) { 
            Serial << _DEC(buffer[cnt]) << " ";
            cnt++;
            if (cnt >= 768) break;
        }
        Serial << endl;
    }
    Serial << endl;
}


void readArray(uint16_t *buffer) {

    for (uint8_t j=0; j<2; j++) {
        // Start cycle
        digitalWrite(CLK,HIGH);
        digitalWrite(CLK,LOW);
        digitalWrite(SI,HIGH);

        // Take reading
        for (int i=0; i<770; i++) {
            digitalWrite(CLK,HIGH);
            if (i==0) {
                digitalWrite(SI,LOW);
            }
            else {
            }
            digitalWrite(CLK,LOW);
            if (i < 768) {
                buffer[i] = analogRead(AIN);
            }
        }
    }
}

