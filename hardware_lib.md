# CYD Starter — Hardware / Libraries

## ฮาร์ดแวร์และขาเดิม
บอร์ด ESP32-2432S028 / HW-458, ESP32-WROOM-32E จอ ILI9341 แนวนอน 320×240

| อุปกรณ์ | ขา / ค่า | หมายเหตุ |
|---|---|---|
| TFT SPI (HSPI) | SCLK14 / MOSI13 / MISO12 | ILI9341, SPI 27MHz |
| TFT control | CS15 / DC2 / RST=-1 | rotation **3** |
| Backlight | GPIO21 | HIGH เปิด |
| XPT2046 SPI (VSPI) | CLK25 / MOSI32 / MISO39 | แยกบัสจาก TFT |
| Touch control | CS33 / IRQ36 | rotation **1**, pressure polling ไม่ใช้ IRQ เป็น gate |

ไม่เปลี่ยน pin map/rotation ขาทัชยังต้องยืนยันกับบอร์ดจริง GPIO36 ไม่มี pull-up ภายใน ใช้ USB จ่ายไฟเพียงพอร์ตเดียว GPIO เป็น 3.3V ดูผัง ASCII ใน `README.md`

## Libraries
| หน้าที่ | Library / รุ่น |
|---|---|
| TFT และ UI โดยตรง | TFT_eSPI **2.5.43** |
| Touch | XPT2046_Touchscreen **v1.4** |
| WiFi / NVS / NTP | WiFi / Preferences / SNTP และ time.h จาก Arduino ESP32 |

Dependencies ภายนอกมีเพียง TFT_eSPI และ XPT2046_Touchscreen ไม่มี LVGL, JSON หรือ API client สำหรับข้อมูลภายนอก

ฟอนต์ **Nunito Bold** จาก Google Fonts ฝัง ASCII 18/26px ใน `src/ui_fonts.h` เปิด `LOAD_GFXFF`; SIL Open Font License 1.1 ที่ `assets/fonts/OFL.txt` ต้นฉบับ `assets/fonts/Nunito.ttf` การสร้างใหม่ใช้ `tools/generate_ui_fonts.py` กับ Python/Pillow เฉพาะเครื่องมือพัฒนา

## พฤติกรรมฐาน
- คาลิเบรตวงกลม 4 มุม รับมุมใดก่อนก็ได้ บันทึก affine เมื่อ fit ผ่าน และโหลดข้ามขั้นตอนเมื่อบูตครั้งถัดไป
- Touch canonical rotation 1 แล้วกลับพิกัดสำหรับ TFT rotation 3 คงรูปแบบ NVS เดิม จึงใช้ calibration และ WiFi ที่บันทึกไว้ต่อได้
- WiFi 2.4GHz พร้อมคีย์บอร์ด ASCII; บันทึกเฉพาะเชื่อมสำเร็จ บูตลองค่าที่บันทึกหนึ่งครั้ง จำกัด 20 วินาที มี Cancel; ล้มเหลว/หมดเวลา/Cancel/หลุดกลับฟอร์ม
- Home มีนาฬิกาและปุ่ม `WiFi` / `Calibrate`; NTP `pool.ntp.org` / `time.google.com` ใช้กรุงเทพ UTC+7 แบบไม่บล็อก แสดง placeholder จน epoch >= `1704067200`
- Serial 115200 เฉพาะ `c/w/t/h`: ลบ calibration / ลบ WiFi / toggle touch diagnostics / heap-stack diagnostics ไม่ log credentials
- Preferences `cyd_settings` แยก `cal`/`wifi` คง version/profile/CRC เดิม **Password เห็นบนจอและเก็บ plaintext ใน NVS** ไม่มี encryption; `w` ไม่ใช่ secure wipe

## Build / ตรวจสอบ
```bash
pio run -e cyd_ili9341
```

`cyd_st7789` เป็นตัวเลือกตรวจ build compatibility เท่านั้น Build cyd_ili9341 และ host tests (touch mapping, saved settings, stack guard) ผ่าน ยังไม่ได้ flash หรือทดสอบบนบอร์ดจริง; ต้องตรวจทัช, NVS/reboot, WiFi timeout/Cancel/loss และ NTP บนบอร์ดจริง

## อ้างอิง
- https://github.com/Bodmer/TFT_eSPI
- https://github.com/PaulStoffregen/XPT2046_Touchscreen
- https://github.com/witnessmenow/ESP32-Cheap-Yellow-Display
