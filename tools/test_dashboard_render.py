"""Build actual pinned LVGL/dashboard on host, test layout/selection/ownership.
Requires gcc/g++ and optional Pillow for .pio/host_ui/fixture-*.png previews.
All displayed prices are SYNTHETIC TEST FIXTURES, not downloaded market data.
No board connection. Generated/cache files are confined to ignored .pio/host_ui.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LVGL = ROOT / ".pio/libdeps/cyd_ili9341/lvgl"
OUT = ROOT / ".pio/host_ui"
assert (LVGL / "lvgl.h").exists(), "Run pio run -e cyd_ili9341 first"
OUT.mkdir(parents=True, exist_ok=True)


def write_if_changed(path, text):
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


write_if_changed(OUT / "Arduino.h", """#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <ctime>
#ifdef _WIN32
inline tm *localtime_r(const time_t *value, tm *out) {
    const tm *result=localtime(value); if(!result)return nullptr;
    *out=*result; return out;
}
#endif
extern uint32_t host_millis;
inline uint32_t millis() { return host_millis; }
""")
write_if_changed(OUT / "TFT_eSPI.h", """#pragma once
#include <cstdint>
#include <cassert>
struct TFT_eSPI {
    uint16_t framebuffer[320*240]{};
    int x=0,y=0,w=0,h=0,flushes=0;
    void startWrite() {} void endWrite() {}
    void setAddrWindow(int ax,int ay,int aw,int ah) {
        assert(ax>=0 && ay>=0 && ax+aw<=320 && ay+ah<=240);
        x=ax;y=ay;w=aw;h=ah;
    }
    void pushColors(uint16_t *pixels,int count,bool) {
        assert(count==w*h); ++flushes;
        for(int i=0;i<count;++i) framebuffer[(y+i/w)*320+x+i%w]=pixels[i];
    }
};
""")
harness = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <string>
#include "dashboard.cpp"
uint32_t host_millis=0;
live_data::Snapshot fixture;
namespace live_data {
void copy_snapshot(Snapshot &destination) { destination = fixture; }
bool stale(const Reading &r,Source,uint32_t) { return r.failed; }
}
void fits(const char *text,int width,bool large=false) {
    auto font=large?&lv_font_montserrat_26:&lv_font_montserrat_18;
    int actual=lv_txt_get_width(text,strlen(text),font,0,LV_TEXT_FLAG_NONE);
    if(actual>width) { fprintf(stderr,"LAYOUT OVERFLOW: %s (%d > %d)\n",text,actual,width); }
    assert(actual<=width);
}
void frame(TFT_eSPI &tft,int page,const char *variant="data") {
    dashboard::show(page);
    host_millis+=25; dashboard::tick(host_millis);
    std::string name="fixture-"+std::to_string(page)+"-"+variant+".ppm";
    auto file=fopen(name.c_str(),"wb"); assert(file);
    fprintf(file,"P6\n320 240\n255\n");
    for(auto pixel:tft.framebuffer) {
        uint8_t rgb[]={uint8_t(((pixel>>11)&31)*255/31),uint8_t(((pixel>>5)&63)*255/63),uint8_t((pixel&31)*255/31)};
        fwrite(rgb,1,3,file);
    }
    fclose(file);
}
void tap(int x,int y) {
    dashboard::touch(true,x,y);host_millis+=100;dashboard::touch(false,x,y);
}
int main() {
    fixture.worker_ok=true;
    for(int i=0;i<live_data::COUNT;++i) {
        auto &r=fixture.readings[i];r.valid=true;r.source_epoch=time(nullptr);r.available=0xFFF;
        strcpy(r.source_time,"14/10/2569 15:46");
        for(int j=0;j<12;++j)r.values[j]=41.44f+j;
        for(int j=0;j<22;++j)r.history[j]={r.source_epoch-(21-j)*86400,100.0f+j+(j%3)*3};
        r.history_count=22;
    }
    auto &weather=fixture.readings[live_data::WEATHER];
    weather.values[0]=31.5;weather.values[1]=72;weather.values[2]=36.0;weather.values[3]=3;weather.values[4]=12.0;
    fixture.readings[live_data::SET].values[0]=1575.88;
    auto &gold=fixture.readings[live_data::THAI_GOLD];gold.values[0]=65950;gold.values[1]=65750;gold.source_epoch=0;
    for(int i=0;i<22;++i)gold.history[i]={time(nullptr)-(21-i)*900,65000.0f+i*50};
    fixture.readings[live_data::THAI_OIL].source_epoch=0;
    strcpy(fixture.readings[live_data::THAI_OIL].source_time,"As of 14/10/2026");
    TFT_eSPI tft;assert(dashboard::begin(tft));
    fits("THAI MARKET",296,true);fits("THAI GOLD 96.5%",296,true);
    fits("FUEL / THB PER L",296,true);fits("BANGKOK / UTC+7",296,true);
    for(auto text:{"SET","PTT","PTG","AOT","ADVANC","CPALL","PT / PTG","Bangchak"})fits(text,98);
    for(auto text:{"Gasohol 95","Gasohol 91","Diesel B7"})fits(text,109);
    for(auto text:{"CACHED 14/10/2569 15:46","CACHED As of 14/10/2026","UNAVAILABLE / error -24","Observed SELL / since boot"})fits(text,296);
    fits("14/10 23:59",136);fits("99999",126,true);fits("1575.88",170,true);
    for(int i=0;i<5;++i)frame(tft,i);
    dashboard::show(0);tap(252,83);assert(dashboard::stock==5 && dashboard::page==0);
    tap(109,55);tap(55,69);assert(dashboard::stock==5); // Tab gaps are not hits.
    dashboard::touch(true,108,55);host_millis+=100;dashboard::touch(true,113,55);
    dashboard::touch(false,113,55);assert(dashboard::stock==5); // Crossing a tab boundary isn't a selection.
    for(int i=0;i<6;++i)assert(dashboard::selected_tab(15+(i%3)*101,45+(i/3)*31,false)==i);
    tap(80,140);assert(dashboard::page==0); // Background never navigates.
    dashboard::touch(true,280,55);host_millis+=60;dashboard::touch(true,100,55);
    dashboard::touch(false,100,55);assert(dashboard::page==1 && dashboard::stock==5);
    dashboard::show(2);tap(252,55);assert(dashboard::station==2);
    tap(109,55);assert(dashboard::station==2);
    for(int i=0;i<3;++i)assert(dashboard::selected_tab(15+i*101,45,true)==i);
    frame(tft,2);
    // One real observation, missing product, cached stamp, no fabricated lines.
    fixture.readings[live_data::THAI_GOLD].history_count=1;fixture.readings[live_data::THAI_GOLD].failed=true;
    frame(tft,1,"cached-single");
    fixture.readings[live_data::THAI_OIL].available=1<<8;frame(tft,2,"missing-products");
    for(auto &r:fixture.readings)r={};++fixture.revision;
    for(int i=0;i<5;++i)frame(tft,i,"unavailable");
    int before=tft.flushes;dashboard::hide();host_millis+=1000;dashboard::tick(host_millis);
    assert(tft.flushes==before); // Custom WiFi/calibration exclusively own TFT while hidden.
    assert(lv_mem_test()==LV_RES_OK);
    lv_mem_monitor_t monitor;lv_mem_monitor(&monitor);
    printf("PASS: actual LVGL 8.3 rendering/partial flush bounds/font widths/tab selection/swipe exclusion/setup ownership; LVGL pool max used %u bytes. Preview fixtures are not real prices.\n",unsigned(monitor.max_used));
}
'''
write_if_changed(OUT / "harness.cpp", harness)
includes = ["-I", str(OUT), "-I", str(ROOT / "src"), "-I", str(LVGL), "-DLV_CONF_INCLUDE_SIMPLE=1"]
config_time = (ROOT / "src/lv_conf.h").stat().st_mtime
sources = list((LVGL / "src").rglob("*.c"))


def compile_c(source):
    name = "_".join(source.relative_to(LVGL / "src").parts) + ".o"
    output = OUT / name
    if not output.exists() or output.stat().st_mtime < max(source.stat().st_mtime, config_time):
        subprocess.run(["gcc", "-std=c99", "-O1", *includes, "-c", str(source), "-o", str(output)], check=True, timeout=30)
    return output


with ThreadPoolExecutor(max_workers=8) as pool:
    objects = list(pool.map(compile_c, sources))
subprocess.run(["g++", "-std=c++11", "-O1", *includes, str(OUT / "harness.cpp"),
                *map(str, objects), "-o", str(OUT / "test.exe")], check=True, timeout=60)
subprocess.run([str(OUT / "test.exe")], cwd=OUT, check=True, timeout=15)
try:
    from PIL import Image
    for ppm in OUT.glob("fixture-*.ppm"):
        with Image.open(ppm) as image:
            image.save(ppm.with_suffix(".png"))
except ImportError:
    print("Pillow not installed: previews remain PPM (tests already passed).")
