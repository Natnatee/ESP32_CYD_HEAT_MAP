#include "saved_settings.h"
#include <Preferences.h>
#include <math.h>
#include <string.h>
#include <limits>

namespace saved_settings {
namespace {
constexpr const char *NVS_NAMESPACE = "cyd_settings";
constexpr const char *CAL_KEY = "cal";
constexpr const char *WIFI_KEY = "wifi";
constexpr uint8_t VERSION = 1;
constexpr size_t CAL_SIZE = 40, WIFI_MAX_SIZE = 107;
static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559,
              "Calibration wire format requires IEEE-754 binary32");

uint32_t checksum(const uint8_t *data, size_t size) {
    uint32_t crc = 0xFFFFFFFF;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1U)));
    }
    return ~crc;
}
void put_u32(uint8_t *out, uint32_t value) {
    for (int i = 0; i < 4; ++i) out[i] = uint8_t(value >> (i * 8));
}
uint32_t get_u32(const uint8_t *in) {
    return uint32_t(in[0]) | (uint32_t(in[1]) << 8) | (uint32_t(in[2]) << 16) | (uint32_t(in[3]) << 24);
}
void put_float(uint8_t *out, float value) {
    uint32_t bits; memcpy(&bits, &value, sizeof(bits)); put_u32(out, bits);
}
float get_float(const uint8_t *in) {
    uint32_t bits = get_u32(in); float value; memcpy(&value, &bits, sizeof(value)); return value;
}
size_t read_blob(const char *key, uint8_t *out, size_t capacity) {
    Preferences prefs;
    if (!prefs.begin(NVS_NAMESPACE, true)) return 0;
    const size_t size = prefs.getBytesLength(key);
    const bool ok = size && size <= capacity && prefs.getBytes(key, out, size) == size;
    prefs.end();
    return ok ? size : 0;
}
bool write_changed(const char *key, const uint8_t *data, size_t size) {
    uint8_t previous[WIFI_MAX_SIZE];
    if (read_blob(key, previous, sizeof(previous)) == size && !memcmp(previous, data, size)) return true;
    Preferences prefs;
    if (!prefs.begin(NVS_NAMESPACE, false)) return false;
    // One committed NVS blob per record: never separate fields/SSID/password writes.
    const bool ok = prefs.putBytes(key, data, size) == size;
    prefs.end();
    return ok;
}
bool forget(const char *key) {
    Preferences prefs;
    if (!prefs.begin(NVS_NAMESPACE, false)) return false;
    const bool ok = !prefs.isKey(key) || prefs.remove(key);
    prefs.end();
    return ok;
}
bool valid_affine(const Affine &a) {
    const float fields[] = {a.ox, a.oy, a.ux, a.uy, a.vx, a.vy};
    for (float field : fields) if (!isfinite(field) || fabsf(field) > 8190) return false;
    const float det = a.ux * a.vy - a.uy * a.vx;
    if (det < 1000000 || a.ux <= 0 || a.vy <= 0 ||
        hypotf(a.ux, a.uy) < 1800 || hypotf(a.vx, a.vy) < 1800) return false;
    // Reconstructed inset corners must be plausible ADC coordinates for rotation-1 hardware.
    for (int i = 0; i < 4; ++i) {
        const float x = a.ox + ((i & 1) ? a.ux : 0) + ((i & 2) ? a.vx : 0);
        const float y = a.oy + ((i & 1) ? a.uy : 0) + ((i & 2) ? a.vy : 0);
        if (x <= 0 || x >= 4095 || y <= 0 || y >= 4095) return false;
    }
    return true;
}
bool ascii_string(const char *text, size_t maximum, size_t &length) {
    if (!text) return false;
    for (length = 0; length <= maximum; ++length) {
        const unsigned char ch = text[length];
        if (!ch) return true;
        if (ch < 32 || ch > 126) return false;
    }
    return false;
}
} // namespace

bool valid_credentials(const char *ssid, const char *password) {
    size_t ssid_length = 0, password_length = 0;
    return ascii_string(ssid, 32, ssid_length) && ssid_length &&
        ascii_string(password, 63, password_length) && (!password_length || password_length >= 8);
}
bool load_calibration(Affine &out, uint32_t profile) {
    uint8_t bytes[CAL_SIZE];
    if (read_blob(CAL_KEY, bytes, sizeof(bytes)) != CAL_SIZE || memcmp(bytes, "CYDC", 4) ||
        bytes[4] != VERSION || bytes[5] != 1 || bytes[6] || bytes[7] ||
        get_u32(bytes + 8) != profile || get_u32(bytes + 36) != checksum(bytes, 36)) return false;
    const Affine candidate = {get_float(bytes + 12), get_float(bytes + 16), get_float(bytes + 20),
        get_float(bytes + 24), get_float(bytes + 28), get_float(bytes + 32)};
    if (!valid_affine(candidate)) return false;
    out = candidate;
    return true;
}
bool save_calibration(const Affine &value, uint32_t profile) {
    if (!valid_affine(value)) return false;
    // Explicit little-endian fields, no raw struct/padding serialization.
    uint8_t bytes[CAL_SIZE]{};
    memcpy(bytes, "CYDC", 4); bytes[4] = VERSION; bytes[5] = 1; // display/touch rotation
    put_u32(bytes + 8, profile);
    const float fields[] = {value.ox, value.oy, value.ux, value.uy, value.vx, value.vy};
    for (int i = 0; i < 6; ++i) put_float(bytes + 12 + i * 4, fields[i]);
    put_u32(bytes + 36, checksum(bytes, 36));
    return write_changed(CAL_KEY, bytes, sizeof(bytes));
}
bool forget_calibration() { return forget(CAL_KEY); }

bool load_wifi(Credentials &out) {
    uint8_t bytes[WIFI_MAX_SIZE];
    const size_t size = read_blob(WIFI_KEY, bytes, sizeof(bytes));
    if (size < 13 || memcmp(bytes, "CYDW", 4) || bytes[4] != VERSION || bytes[7] ||
        bytes[5] < 1 || bytes[5] > 32 || bytes[6] > 63 ||
        (bytes[6] && bytes[6] < 8) || size != size_t(12 + bytes[5] + bytes[6]) ||
        get_u32(bytes + size - 4) != checksum(bytes, size - 4)) return false;
    Credentials candidate;
    // Reject embedded NUL as well as non-ASCII; encoded lengths must match actual values.
    for (size_t i = 8; i < size - 4; ++i) if (bytes[i] < 32 || bytes[i] > 126) return false;
    memcpy(candidate.ssid, bytes + 8, bytes[5]);
    memcpy(candidate.password, bytes + 8 + bytes[5], bytes[6]);
    if (!valid_credentials(candidate.ssid, candidate.password)) return false;
    out = candidate;
    return true;
}
bool save_wifi(const char *ssid, const char *password) {
    if (!valid_credentials(ssid, password)) return false;
    const size_t ssid_length = strlen(ssid), password_length = strlen(password);
    const size_t size = 12 + ssid_length + password_length;
    uint8_t bytes[WIFI_MAX_SIZE]{};
    memcpy(bytes, "CYDW", 4); bytes[4] = VERSION;
    bytes[5] = ssid_length; bytes[6] = password_length;
    memcpy(bytes + 8, ssid, ssid_length); memcpy(bytes + 8 + ssid_length, password, password_length);
    put_u32(bytes + size - 4, checksum(bytes, size - 4));
    return write_changed(WIFI_KEY, bytes, size);
}
bool forget_wifi() { return forget(WIFI_KEY); }
} // namespace saved_settings
