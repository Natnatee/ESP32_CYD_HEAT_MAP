# CYD Starter / hardware validation

1. Build: `pio run -e cyd_ili9341`
2. หากไม่มี calibration หรือสั่ง Serial `c`: แตะจุดกลางวงกลมทั้ง 4 มุม นิ่งประมาณ 80ms แล้วปล่อย มุมไหนก่อนก็ได้ ครบและ fit ผ่านจะรอ 600ms ก่อนหน้า WiFi
3. ตรวจคีย์บอร์ด ตัวพิมพ์ใหญ่/เล็ก ตัวเลข สัญลักษณ์ Space/Del และปุ่มริมจอ ถ้าไม่ตรงใช้ `t` ดู raw/pressure/พิกัด แล้ว `c` ใหม่ ห้ามส่งภาพหรือ log ที่มี credentials
4. ต่อ WiFi 2.4GHz ลองรหัสผิด/Cancel/timeout 20 วินาที ต้องกลับฟอร์มและไม่เขียนทับค่าดีเดิม
5. เชื่อมสำเร็จต้องเข้าหน้า Home แสดง --:--:-- ระหว่างรอ NTP แล้วเป็นวันเวลา UTC+7 อัปเดตทุกวินาที แม้อินเทอร์เน็ตใช้ไม่ได้ UI ต้องไม่ค้าง
6. ปล่อยนิ้วจาก Connect ก่อนใช้ปุ่ม Home ทดสอบ WiFi กลับฟอร์ม และ Calibrate ลบเฉพาะ calibration ไม่ลบ WiFi
7. Reboot ต้องโหลด calibration และลอง WiFi ที่บันทึกหนึ่งครั้ง ปิด router ต้องกลับฟอร์ม กด Connect เพื่อลองใหม่
8. Serial `w` ลบเฉพาะ WiFi; `h` แสดง heap/stack; `t` สลับ diagnostics; `c` เริ่ม calibration ใหม่
9. Host regression: `python tools/test_touch_mapping.py` และ `python tools/test_saved_settings.py`
10. Stack guard: `python tools/check_stack_frames.py --self-test` ตรวจ main.cpp ต่อฟังก์ชันไม่เกิน 1024 bytes ไม่รับรอง runtime call depth รวม

Password แสดงบนจอและเก็บ plaintext NVS การลบด้วย w ไม่ใช่ secure wipe Host mocks ไม่แทนการทดสอบ power-cut/NVS บนบอร์ดจริง

ไม่ upload/flash/monitor โดยไม่มีคำสั่งจากผู้ใช้ ตรวจพอร์ตจริงด้วย `pio device list` ก่อนเลือกพอร์ต ห้ามเปิด monitor พร้อม upload
