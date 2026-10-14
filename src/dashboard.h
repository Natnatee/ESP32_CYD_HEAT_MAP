#pragma once
#include <Arduino.h>
#include <TFT_eSPI.h>
namespace dashboard {
bool begin(TFT_eSPI &display);
void show(uint8_t page = 3);
void hide();
void next();
void touch(bool pressed, int x, int y);
void tick(uint32_t now);
}
