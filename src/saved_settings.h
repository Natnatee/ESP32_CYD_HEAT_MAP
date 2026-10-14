#pragma once
#include <stddef.h>
#include <stdint.h>

namespace saved_settings {
struct Affine { float ox, oy, ux, uy, vx, vy; };
struct Credentials { char ssid[33]{}; char password[64]{}; };
bool valid_credentials(const char *ssid, const char *password);
bool load_calibration(Affine &out, uint32_t profile);
bool save_calibration(const Affine &value, uint32_t profile);
bool forget_calibration();
bool load_wifi(Credentials &out);
bool save_wifi(const char *ssid, const char *password);
bool forget_wifi();
} // namespace saved_settings
