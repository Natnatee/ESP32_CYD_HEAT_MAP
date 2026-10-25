#pragma once
#include <TFT_eSPI.h>
namespace map_ui {
void enter(TFT_eSPI &tft);
void tick(TFT_eSPI &tft);
void swipe(TFT_eSPI &tft, bool left);
}
