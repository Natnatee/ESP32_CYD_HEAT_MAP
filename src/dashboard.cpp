#include "dashboard.h"
#include "dashboard_gesture.h"
#include "live_data.h"
#include <lvgl.h>
#include <math.h>
#include <time.h>

namespace dashboard {
namespace {
constexpr uint32_t BG = 0x080D19, PANEL = 0x141F32, MUTED = 0x8C9DB5;
constexpr uint32_t CYAN = 0x38E5F5, PINK = 0xFA4DA5, GOLD = 0xF7C859, RED = 0xFF4949;
TFT_eSPI *tft = nullptr;
lv_color_t pixels[320 * 8]; // Single 8-row RGB565 partial buffer: 5120 bytes, no full-screen sprite.
lv_disp_draw_buf_t draw_buffer;
lv_disp_drv_t display_driver;
lv_indev_drv_t input_driver;
lv_disp_t *display = nullptr;
lv_obj_t *root = nullptr;
bool active = false, input_pressed = false;
lv_point_t input_point{};
DashboardGesture gesture;
// UI thread owns this persistent snapshot; no full Snapshot temporaries on loopTask's stack.
live_data::Snapshot data;
uint8_t page = 3, stock = 0, station = 0;
uint32_t last_tick = 0, last_refresh = 0, last_age_refresh = 0;
int last_second = -2;
lv_draw_ctx_t *ctx = nullptr;
const char *const TICKERS[] = {"SET", "PTT", "PTG", "AOT", "ADVANC", "CPALL"};
const char *const STATIONS[] = {"PTT", "PT / PTG", "Bangchak"};

void flush(lv_disp_drv_t *driver, const lv_area_t *area, lv_color_t *colors) {
    // Only tick() runs LVGL, only while dashboard owns TFT. Setup never races this callback.
    if (active) {
        tft->startWrite();
        tft->setAddrWindow(area->x1, area->y1, area->x2 - area->x1 + 1, area->y2 - area->y1 + 1);
        tft->pushColors(reinterpret_cast<uint16_t *>(colors),
            (area->x2 - area->x1 + 1) * (area->y2 - area->y1 + 1), true);
        tft->endWrite();
    }
    lv_disp_flush_ready(driver);
}
void read_input(lv_indev_drv_t *, lv_indev_data_t *out) {
    out->state = active && input_pressed ? LV_INDEV_STATE_PR : LV_INDEV_STATE_REL;
    out->point = input_point;
}
void box(int x, int y, int w, int h, uint32_t fill, int radius = 10,
         uint32_t border = 0, int border_width = 0) {
    lv_draw_rect_dsc_t d; lv_draw_rect_dsc_init(&d);
    d.bg_color = lv_color_hex(fill); d.radius = radius;
    d.border_color = lv_color_hex(border); d.border_width = border_width;
    lv_area_t a = {lv_coord_t(x), lv_coord_t(y), lv_coord_t(x + w - 1), lv_coord_t(y + h - 1)};
    lv_draw_rect(ctx, &d, &a);
}
void label(const char *text, int x, int y, int width = 300, uint32_t color = 0xFFFFFF,
           bool large = false, lv_text_align_t align = LV_TEXT_ALIGN_LEFT) {
    lv_draw_label_dsc_t d; lv_draw_label_dsc_init(&d);
    d.font = large ? &lv_font_montserrat_26 : &lv_font_montserrat_18;
    d.color = lv_color_hex(color); d.align = align;
    lv_area_t a = {lv_coord_t(x), lv_coord_t(y), lv_coord_t(x + width - 1), lv_coord_t(y + (large ? 30 : 22) - 1)};
    lv_draw_label(ctx, &d, &a, text, nullptr);
}
void line(int x1, int y1, int x2, int y2, uint32_t color, int width = 1) {
    lv_draw_line_dsc_t d; lv_draw_line_dsc_init(&d);
    d.color = lv_color_hex(color); d.width = width; d.round_start = d.round_end = 1;
    lv_point_t a = {lv_coord_t(x1), lv_coord_t(y1)}, b = {lv_coord_t(x2), lv_coord_t(y2)};
    lv_draw_line(ctx, &d, &a, &b);
}
void source_stamp(const live_data::Reading &r, char *text, size_t size) {
    if (r.source_epoch) {
        tm local{}; localtime_r(&r.source_epoch, &local);
        strftime(text, size, "%d/%m %H:%M BKK", &local);
    } else snprintf(text, size, "%s", r.source_time);
}
void status(live_data::Source source, int y) {
    const auto &r = data.readings[source]; char text[48];
    uint32_t color = MUTED;
    if (!data.worker_ok) { strcpy(text, "Worker unavailable"); color = RED; }
    else if (r.failed) {
        if (r.valid) {
            char stamp[32]; source_stamp(r, stamp, sizeof(stamp));
            snprintf(text, sizeof(text), "CACHED %s", stamp);
        } else snprintf(text, sizeof(text), "UNAVAILABLE / error %d", r.error);
        color = RED;
    }
    else if (!r.valid) strcpy(text, time(nullptr) < 1704067200 ? "Waiting for NTP" : "Loading data...");
    else if (live_data::stale(r, source, millis())) {
        char stamp[32]; source_stamp(r, stamp, sizeof(stamp));
        snprintf(text, sizeof(text), "STALE %s", stamp); color = RED;
    }
    else source_stamp(r, text, sizeof(text));
    label(text, 12, y, 296, color);
}
void value(float number, bool valid, char *out, size_t size, int decimals = 2) {
    if (valid) snprintf(out, size, "%.*f", decimals, number);
    else snprintf(out, size, "--");
}
void history(const live_data::Reading &r, int y, int height, uint32_t color) {
    box(10, y, 300, height, PANEL, 8);
    if (!r.history_count) { label("No history yet", 22, y + 12, 276, MUTED); return; }
    const int left = 22, right = 298, top = y + 8, bottom = y + height - 26;
    float low = r.history[0].price, high = low;
    for (int i = 1; i < r.history_count; ++i) {
        low = fminf(low, r.history[i].price); high = fmaxf(high, r.history[i].price);
    }
    const float span = high > low ? high - low : fmaxf(1, low * 0.001f);
    if (high == low) { low -= span / 2; high += span / 2; }
    const time_t first = r.history[0].epoch, last = r.history[r.history_count - 1].epoch;
    line(left, bottom, right, bottom, 0x32425A);
    line(left, (top + bottom) / 2, right, (top + bottom) / 2, 0x243248);
    if (r.history_count == 1)
        label("1 real sample", 84, y + 9, 204, MUTED);
    else if (r.history_observed)
        label("Observed / since boot", 50, y + 2, 240, MUTED);
    int px = 0, py = 0;
    for (int i = 0; i < r.history_count; ++i) {
        int x = last > first ? left + int(double(r.history[i].epoch - first) * (right - left) / (last - first)) : left;
        int cy = bottom - int((r.history[i].price - low) * (bottom - top) / (high - low));
        if (i) line(px, py, x, cy, color, 2);
        box(x - 2, cy - 2, 5, 5, color, 2);
        px = x; py = cy;
    }
    char dates[24]; tm local{}; localtime_r(&first, &local);
    strftime(dates, sizeof(dates), page == 1 || r.history_observed ? "%d/%m %H:%M" : "%d/%m", &local);
    label(dates, left, y + height - 23, 136, MUTED);
    localtime_r(&last, &local);
    strftime(dates, sizeof(dates), page == 1 || r.history_observed ? "%d/%m %H:%M" : "%d/%m", &local);
    label(dates, right - 136, y + height - 23, 136, MUTED, false, LV_TEXT_ALIGN_RIGHT);
}
// Original vector-like seven-segment artwork, shared by clock and pump prices.
void digital(const char *text, int x, int y, int scale, uint32_t color) {
    static const uint8_t masks[] = {0x3F,0x06,0x5B,0x4F,0x66,0x6D,0x7D,0x07,0x7F,0x6F};
    const int rects[7][4] = {{2,0,8,2},{10,2,2,8},{10,12,2,8},{2,20,8,2},{0,12,2,8},{0,2,2,8},{2,10,8,2}};
    for (const char *p = text; *p; ++p) {
        if (*p == '.' || *p == ':') {
            box(x, y + 18 * scale, 2 * scale, 2 * scale, color, scale);
            if (*p == ':') box(x, y + 6 * scale, 2 * scale, 2 * scale, color, scale);
            x += 4 * scale; continue;
        }
        uint8_t mask = *p >= '0' && *p <= '9' ? masks[*p - '0'] : 0x40;
        for (int i = 0; i < 7; ++i) {
            const int *r = rects[i];
            box(x + r[0] * scale, y + r[1] * scale, r[2] * scale, r[3] * scale,
                mask & (1 << i) ? color : 0x302334, scale);
        }
        x += 15 * scale;
    }
}
void stocks() {
    label("THAI MARKET", 12, 7, 296, CYAN, true);
    for (int i = 0; i < 6; ++i) {
        const int x = 10 + (i % 3) * 101, y = 40 + (i / 3) * 31;
        box(x, y, 98, 28, i == stock ? 0x22535D : PANEL, 8, i == stock ? CYAN : PANEL, 1);
        label(TICKERS[i], x, y + 3, 98, i == stock ? CYAN : MUTED, false, LV_TEXT_ALIGN_CENTER);
    }
    auto source = static_cast<live_data::Source>(live_data::SET + stock);
    const auto &r = data.readings[source]; char text[40];
    value(r.values[0], r.valid, text, sizeof(text));
    label(text, 12, 105, 170, 0xFFFFFF, true);
    label(stock ? "THB" : "points", 204, 112, 100, CYAN, false, LV_TEXT_ALIGN_RIGHT);
    status(source, 138);
    history(r, 164, 74, CYAN);
}
void gold() {
    label("THAI GOLD 96.5%", 12, 7, 296, GOLD, true);
    // Original bullion illustration: bevelled bars, not a third-party image/logo.
    box(222, 55, 71, 34, 0xAA7423, 5);
    box(214, 47, 71, 34, GOLD, 5, 0xFFE5A0, 2);
    line(221, 54, 277, 54, 0xFFF1BE, 2);
    label("96.5", 218, 57, 65, 0x684715, false, LV_TEXT_ALIGN_CENTER);
    const auto &r = data.readings[live_data::THAI_GOLD]; char text[32];
    label("BUY", 12, 43, 55, MUTED); value(r.values[1], r.valid, text, sizeof(text), 0);
    label(text, 78, 38, 126, GOLD, true);
    label("SELL", 12, 76, 65, MUTED); value(r.values[0], r.valid, text, sizeof(text), 0);
    label(text, 78, 71, 126, 0xFFFFFF, true);
    label("THB / baht weight", 12, 102, 296, MUTED);
    status(live_data::THAI_GOLD, 125);
    label("Observed SELL / since boot", 12, 149, 296, GOLD);
    history(r, 174, 64, GOLD);
}
void oil() {
    label("FUEL / THB PER L", 12, 7, 296, CYAN, true);
    const uint32_t colors[] = {0x52BAF8, 0x72D348, 0xB8DF44};
    for (int i = 0; i < 3; ++i) {
        box(10 + 101 * i, 40, 98, 29, station == i ? 0x263C37 : PANEL, 8, colors[i], station == i ? 2 : 0);
        label(STATIONS[i], 10 + 101 * i, 45, 98, colors[i], false, LV_TEXT_ALIGN_CENTER);
    }
    // Stylized text wordmark and an original pump; these are not official station logos.
    box(12, 82, 80, 116, PANEL, 10, colors[station], 2);
    box(22, 93, 60, 35, 0x071219, 4);
    label(station == 0 ? "PTT" : station == 1 ? "PT" : "BCP", 22, 101, 60, colors[station], false, LV_TEXT_ALIGN_CENTER);
    box(26, 145, 47, 35, colors[station], 5);
    line(77, 137, 88, 150, MUTED, 3); line(88, 150, 88, 183, MUTED, 3);
    line(88, 183, 75, 183, MUTED, 3);
    const auto &r = data.readings[live_data::THAI_OIL];
    const char *products[] = {"Gasohol 95", "Gasohol 91", "E20", "Diesel B7"};
    for (int i = 0; i < 4; ++i) {
        const int y = 77 + i * 33, index = station * 4 + i;
        box(103, y, 207, 31, PANEL, 6);
        label(products[i], 109, y + 5, 109, MUTED);
        char price[16]; value(r.values[index], r.valid && (r.available & (1U << index)), price, sizeof(price));
        digital(price, 229, y + 4, 1, RED);
    }
    status(live_data::THAI_OIL, 211);
}
const char *condition(int code) {
    if (code == 0) return "Clear sky";
    if (code <= 3) return "Cloudy";
    if (code == 45 || code == 48) return "Fog";
    if (code >= 95) return "Thunderstorm";
    if (code >= 71 && code <= 77) return "Snow";
    if (code >= 51 && code <= 57) return "Drizzle";
    if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return "Rain";
    return "Other weather";
}
void weather() {
    label("BANGKOK", 12, 7, 296, CYAN, true);
    const auto &r = data.readings[live_data::WEATHER]; char text[40];
    box(12, 44, 296, 92, PANEL, 14);
    box(247, 61, 34, 34, GOLD, 17);
    box(226, 81, 66, 23, 0xCCDBEF, 12);
    if (r.valid) snprintf(text, sizeof(text), "%.1f C", r.values[0]); else strcpy(text, "-- C");
    label(text, 26, 57, 194, 0xFFFFFF, true);
    label(r.valid ? condition(int(r.values[3])) : "--", 26, 98, 210, CYAN);
    if (r.valid) snprintf(text, sizeof(text), "Feels %.1f C", r.values[2]); else strcpy(text, "Feels -- C");
    label(text, 12, 144, 296, 0xFFFFFF, true);
    box(12, 179, 142, 30, PANEL, 8); box(163, 179, 145, 30, PANEL, 8);
    if (r.valid) snprintf(text, sizeof(text), "RH %.0f%%", r.values[1]); else strcpy(text, "RH --%");
    label(text, 22, 184, 125, CYAN);
    if (r.valid) snprintf(text, sizeof(text), "%.1f km/h", r.values[4]); else strcpy(text, "-- km/h");
    label(text, 173, 184, 130, CYAN);
    status(live_data::WEATHER, 215);
}
void clock() {
    label("BANGKOK / UTC+7", 12, 7, 296, PINK, true);
    for (int y = 43; y < 191; y += 7) line(12, y, 307, y, 0x19243C);
    box(10, 43, 300, 147, BG, 14, PINK, 2);
    // Scan lines confined to the clock face, with neon segments over them.
    for (int y = 49; y < 185; y += 7) line(18, y, 300, y, 0x142137);
    time_t now = time(nullptr); tm local{}; char text[48];
    const bool valid = now >= 1704067200;
    if (valid) { localtime_r(&now, &local); strftime(text, sizeof(text), "%H:%M", &local); }
    else strcpy(text, "--:--");
    digital(text, 30, 58, 4, CYAN);
    if (valid) strftime(text, sizeof(text), "%a %d %b %Y", &local); else strcpy(text, "Waiting for NTP");
    label(text, 18, 159, 284, MUTED, false, LV_TEXT_ALIGN_CENTER);
    if (valid) snprintf(text, sizeof(text), "%02d seconds", local.tm_sec); else strcpy(text, "-- seconds");
    label(text, 12, 204, 296, PINK, true, LV_TEXT_ALIGN_CENTER);
}
void draw(lv_event_t *event) {
    ctx = lv_event_get_draw_ctx(event);
    box(0, 0, 320, 240, BG, 0);
    if (page == 0) stocks(); else if (page == 1) gold(); else if (page == 2) oil();
    else if (page == 3) weather(); else clock();
}
int selected_tab(int x, int y, bool oil_tab) {
    const int relative_x = x - 10, relative_y = y - 40;
    if (relative_x < 0 || relative_x >= 300 || relative_y < 0) return -1;
    if (relative_x % 101 >= 98) return -1;
    if (oil_tab) return relative_y < 29 ? relative_x / 101 : -1;
    if (relative_y >= 59 || relative_y % 31 >= 28) return -1;
    return (relative_y / 31) * 3 + relative_x / 101;
}
void change_page(int direction) {
    page = (page + 5 + direction) % 5;
    lv_obj_invalidate(root);
}
} // namespace
bool begin(TFT_eSPI &screen) {
    if (root) return true;
    tft = &screen; lv_init();
    lv_disp_draw_buf_init(&draw_buffer, pixels, nullptr, 320 * 8);
    lv_disp_drv_init(&display_driver);
    display_driver.hor_res = 320; display_driver.ver_res = 240;
    display_driver.flush_cb = flush; display_driver.draw_buf = &draw_buffer;
    display = lv_disp_drv_register(&display_driver);
    if (!display) return false;
    root = lv_disp_get_scr_act(display);
    lv_obj_remove_style_all(root);
    lv_obj_clear_flag(root, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_event_cb(root, draw, LV_EVENT_DRAW_MAIN, nullptr);
    lv_indev_drv_init(&input_driver); input_driver.type = LV_INDEV_TYPE_POINTER;
    input_driver.read_cb = read_input; input_driver.disp = display;
    lv_indev_drv_register(&input_driver);
    last_tick = millis();
    return true;
}
void show(uint8_t selected) {
    if (!root) return;
    page = selected % 5; active = true; gesture = {}; input_pressed = false;
    last_tick = millis();
    live_data::copy_snapshot(data); last_refresh = millis();
    last_second = -2; lv_obj_invalidate(root);
}
void hide() { active = false; input_pressed = false; gesture = {}; }
void next() { if (active) change_page(1); }
void touch(bool pressed, int x, int y) {
    if (!active) return;
    input_pressed = pressed; input_point = {lv_coord_t(x), lv_coord_t(y)};
    const auto action = gesture.update(pressed, x, y, millis());
    if (action == DashboardGesture::LEFT) change_page(1);
    else if (action == DashboardGesture::RIGHT) change_page(-1);
    else if (action == DashboardGesture::TAP) {
        if (page == 0 || page == 2) {
            const int start = selected_tab(gesture.start_x, gesture.start_y, page == 2);
            const int end = selected_tab(gesture.end_x, gesture.end_y, page == 2);
            if (start >= 0 && start == end) {
                if (page == 0) stock = end; else station = end;
                lv_obj_invalidate(root);
            }
        }
    }
}
void tick(uint32_t now) {
    if (!active || !root) return;
    lv_tick_inc(now - last_tick); last_tick = now;
    if (now - last_refresh >= 250) {
        last_refresh = now;
        // Main-thread-only snapshot and drawing; worker has no LVGL/TFT access.
        const uint32_t revision = data.revision;
        live_data::copy_snapshot(data);
        int second = int(time(nullptr));
        if (revision != data.revision || (page == 4 && second != last_second) || now - last_age_refresh >= 60000) {
            last_second = second; last_age_refresh = now; lv_obj_invalidate(root);
        }
    }
    lv_timer_handler();
}
} // namespace dashboard
