# ESP32 CYD Starter

ฐานเฟิร์มแวร์สำหรับ ESP32-2432S028 / HW-458 จอ ILI9341 แนวนอน 320×240 ใช้ TFT_eSPI วาด UI โดยตรง ไม่มี LVGL, JSON หรือการเรียก API ข้อมูลภายนอก

## การใช้งาน
- เมื่อไม่มี calibration ที่ใช้ได้ ให้แตะจุดกลางวงกลมทั้ง 4 มุม มุมใดก่อนก็ได้ แตะนิ่งแล้วปล่อย บันทึกลง NVS เมื่อ fit ผ่าน; บูตถัดไปข้ามขั้นตอนนี้
- หน้า WiFi มีช่อง SSID/Password และคีย์บอร์ด QWERTY พร้อมตัวเลข/สัญลักษณ์, Space และ Del รองรับ ASCII
- ใช้ WiFi **2.4GHz** บันทึก credentials เฉพาะเมื่อเชื่อมสำเร็จ บูตจะลองค่าที่บันทึกอัตโนมัติหนึ่งครั้ง จำกัด 20 วินาที ยกเลิกด้วย Cancel ได้
- เชื่อมไม่สำเร็จ/หมดเวลา/Cancel หรือ WiFi หลุด จะกลับฟอร์มแก้ไข โดยไม่ลบค่าที่บันทึกไว้
- หน้า Home แสดงนาฬิกา NTP กรุงเทพ UTC+7 พร้อมปุ่ม `WiFi` กลับฟอร์ม และ `Calibrate` เริ่มคาลิเบรตใหม่
- NTP ใช้ `pool.ntp.org` และ `time.google.com` แบบไม่บล็อก UI แสดง placeholder จน epoch >= `1704067200`

## Hardware / Pin Map
มองจากด้านหลัง พอร์ต USB อยู่ด้านบน รูปแสดงตำแหน่งส่วนประกอบโดยประมาณ ไม่ใช่ลำดับขาของคอนเนกเตอร์

```text
       Micro USB     USB-C
    +--------------------------+
    |      ESP32-2432S028       |
    |                          |-- SPEAK (ไม่ใช้)
    | microSD                  |
    | (ไม่ใช้)   TFT ภายใน     |
    |          CLK14 MOSI13    |
    |          MISO12 CS15 DC2 |
    |          BL21 RST=-1     |
    | RGB LED                  |
    | (ไม่ใช้) Touch ภายใน     |
    |          CLK25 MOSI32    |
    |          MISO39 CS33     |
    |          IRQ36          |
    |       ESP32-WROOM   BOOT |
    |       เสาอากาศ      RESET|
    +--------------------------+
```

คงขาเดิม: TFT rotation **3**, touch rotation **1**; affine ใช้พิกัด canonical เดิมแล้วกลับพิกัดก่อนส่ง UI จึงใช้ calibration/NVS เดิมได้ ไม่ต้องลบข้อมูล ขาทัชยังต้องยืนยันบนบอร์ดจริง อ่าน pressure แบบ polling ไม่ใช้ IRQ เป็น gate

ใช้สาย USB ส่งข้อมูลได้ จ่ายไฟผ่าน USB เพียงพอร์ตเดียว GPIO เป็น 3.3V ห้ามป้อน 5V เข้า GPIO

## Build
ติดตั้ง PlatformIO แล้วรันจาก root:

```bash
pio run -e cyd_ili9341
```

`cyd_ili9341` เป็นค่าหลัก; `pio run -e cyd_st7789` มีไว้ตรวจ build compatibility เท่านั้น ไม่ใช่การตรวจพบชนิดจออัตโนมัติ

Dependencies ภายนอกมีเพียง **TFT_eSPI 2.5.43** และ **XPT2046_Touchscreen v1.4**; WiFi, Preferences และ SNTP/time.h มากับ Arduino ESP32

## Serial (115200 baud)
| คำสั่ง | หน้าที่ |
|---|---|
| `c` | ลบเฉพาะ calibration แล้วเริ่มใหม่ ไม่ลบ WiFi |
| `w` | ลบเฉพาะ WiFi ที่บันทึก แล้วกลับฟอร์มเมื่อ calibration พร้อม |
| `t` | เปิด/ปิด touch diagnostics |
| `h` | ดู heap/stack diagnostics |

รองรับเฉพาะ `c/w/t/h` ไม่ log credentials

## NVS / ความปลอดภัย
- Preferences namespace `cyd_settings` แยก record `cal`/`wifi` รูปแบบ version/profile/CRC เดิมยังเข้ากันได้ CRC ตรวจข้อมูลเสีย ไม่ใช่การเข้ารหัส
- Calibration บันทึกเมื่อผ่านการตรวจ; WiFi บันทึกเมื่อเชื่อมสำเร็จและข้อมูลเปลี่ยน ไม่เขียนทับค่าดีเมื่อเชื่อมล้มเหลว/Cancel/หลุด
- **Password มองเห็นบนจอ และ NVS เก็บ plaintext** ไม่เปิด flash/NVS encryption ผู้เข้าถึง flash อาจกู้รหัสได้ `w` ไม่ใช่ secure wipe

## รายการตรวจบนบอร์ด
ตรวจคาลิเบรต/รีบูต, ปุ่มและคีย์บอร์ดริมจอ, saved WiFi autoattempt/Cancel/timeout 20 วินาที, WiFi หลุดกลับฟอร์ม, placeholder ก่อน NTP และเวลา UTC+7 รวมถึงปุ่ม Home ทั้งสองปุ่ม

Build `cyd_ili9341` ผ่าน: Flash 814,301 bytes (62.1%), static RAM 47,072 bytes (14.4%) ทดสอบ host touch mapping, saved settings และ stack guard ผ่าน ยังไม่ได้ flash หรือทดสอบบนบอร์ดจริง

## Fonts / License
UI ใช้ **Nunito Bold** จาก Google Fonts ภายใต้ **SIL Open Font License 1.1** ดู `assets/fonts/OFL.txt` และต้นฉบับ `assets/fonts/Nunito.ttf` ฝัง ASCII bitmap 18/26px ใน `src/ui_fonts.h` ไม่ดาวน์โหลดขณะรัน

สร้างฟอนต์ใหม่ด้วย `python tools/generate_ui_fonts.py` (ต้องมี Pillow เฉพาะขั้นตอนสร้างฟอนต์ ไม่ใช่ dependency ของ firmware build)
