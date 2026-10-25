# ESP32 CYD Starter — ขอบเขตโปรเจกต์

ฐาน Arduino ESP32 สำหรับ CYD จอ ILI9341 320×240 มีเฉพาะ calibration, WiFi setup และนาฬิกา Home วาดด้วย TFT_eSPI โดยตรง ไม่มี LVGL, JSON, dashboard ข้อมูล หรือ API ภายนอก

## ลำดับการทำงาน
1. โหลด calibration จาก NVS; หากใช้ไม่ได้ ให้แตะวงกลม 4 มุมและบันทึกเมื่อ affine fit ผ่าน
2. เมื่อ calibration พร้อม ลอง WiFi ที่บันทึกอัตโนมัติหนึ่งครั้ง จำกัด 20 วินาที หรือให้กรอก SSID/Password ผ่านคีย์บอร์ดบนจอ
3. เข้า Home เมื่อเชื่อมสำเร็จ แสดงนาฬิกากรุงเทพ UTC+7 และปุ่ม `WiFi` / `Calibrate`
4. เชื่อมล้มเหลว/หมดเวลา/Cancel หรือ WiFi หลุด กลับฟอร์มแก้ไขโดยไม่ลบค่าดีเดิม

NTP ใช้ `pool.ntp.org` / `time.google.com` แบบไม่บล็อก ไม่รอ sync ค้างใน UI; แสดง placeholder จน epoch >= `1704067200`

## ข้อกำหนดที่คงเดิม
- ขา GPIO ตาม `README.md` และ `hardware_lib.md`; TFT rotation 3, touch canonical rotation 1
- แปลง affine/clamp ตาม canonical แล้วกลับพิกัดสำหรับ UI; calibration เก่าใช้ต่อได้
- Preferences namespace `cyd_settings`, record `cal`/`wifi` และรูปแบบ version/profile/CRC เดิมยัง compatible ไม่ต้องลบ NVS
- บันทึก calibration เมื่อผ่าน fit; บันทึก WiFi เฉพาะเชื่อมสำเร็จและข้อมูลเปลี่ยน ใช้ `WiFi.persistent(false)`
- Serial 115200 รองรับเฉพาะ `c` ลบ calibration, `w` ลบ WiFi, `t` touch diagnostics, `h` heap/stack diagnostics ไม่ log credentials

## Dependencies / Build
Dependencies ภายนอกเฉพาะ TFT_eSPI **2.5.43** และ XPT2046_Touchscreen **v1.4** ส่วน WiFi, Preferences และ SNTP/time.h มากับ Arduino ESP32

```bash
pio run -e cyd_ili9341
```

เลือก `cyd_st7789` ได้เฉพาะตรวจ build compatibility ไม่ใช่จอหลัก ไม่มี auto-detect

## ข้อจำกัดและความปลอดภัย
- WiFi 2.4GHz; คีย์บอร์ด ASCII ไม่รองรับ enterprise/captive portal
- Password แสดงจริงบนจอและเก็บ plaintext ใน NVS ไม่มี flash/NVS encryption; CRC ไม่ป้องกันการอ่านข้อมูล และ `w` ไม่ใช่ secure wipe
- ฟอนต์ Nunito Bold จาก Google Fonts ใช้ SIL OFL 1.1 ดู `assets/fonts/OFL.txt`

## การยืนยันผล
Build cyd_ili9341 และ host tests (touch mapping, saved settings, stack guard) ผ่าน ยังไม่ได้ flash หรือทดสอบบนบอร์ดจริง ต้องตรวจบนบอร์ด: calibration และ NVS หลังรีบูต, WiFi autoattempt/Cancel/timeout/loss, ทัช/คีย์บอร์ด, ปุ่ม Home และ NTP placeholder/UTC+7
