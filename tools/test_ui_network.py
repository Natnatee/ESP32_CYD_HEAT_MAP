"""Execute real map UI with a recording TFT stub and reconnect policy on host."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TFT = r'''
#pragma once
#include <stdint.h>
#include <cassert>
#include <algorithm>
#include <string>
#include <vector>
#include <time.h>
inline tm *host_localtime(const time_t *value, tm *out) { *out=*localtime(value); return out; }
#define localtime_r host_localtime
extern time_t epoch;
inline time_t host_time(time_t*) { return epoch; }
#define time host_time
using std::min;
extern uint32_t clock_ms;
inline uint32_t millis() { return clock_ms; }
constexpr int TFT_WHITE=65535,TFT_BLACK=0,TFT_YELLOW=65504,TFT_CYAN=2047,TL_DATUM=0;
struct TFT_eSPI {
 int clears=0, rows=0, writes=0;
 std::vector<std::string> strings;
 void setTextColor(int,int) {} void setSwapBytes(bool) {}
 void setFreeFont(void*) {} void setTextDatum(int) {} void setTextSize(int) {}
 void drawString(const char* s,int x,int y,int) {
  assert(x>=190 && x+int(std::string(s).size())*6<=320 && y+8<=240);
  strings.push_back(s);
  for (const char *p=s; *p; ++p) assert(*p>=32 && *p<=126);
  ++writes;
 }
 void fillRect(int,int,int,int,int) { ++writes; }
 void fillScreen(int) { ++clears; }
 void drawFastVLine(int,int,int,int) { ++writes; }
 void pushImage(int x,int y,int w,int h,uint16_t*) { assert(x>=0 && y>=0 && x+w<=190 && y+h<=240); ++rows; }
};
'''
SOURCE = r'''
#include "map_ui.h"
#include "map_data.h"
#include "reconnect_policy.h"
#include <cassert>
#include <cstdio>
uint32_t clock_ms=0;
time_t epoch=0;
bool online=true;
#include <WiFi.h>
FakeWiFi WiFi;
map_data::Snapshot current{};
namespace map_data {
bool begin() { return true; }
bool snapshot(unsigned, Snapshot &out) { out=current; return out.valid; }
}
int main() {
 ReconnectPolicy p;
 assert(p.tick(0,true)==p.NONE);
 assert(p.tick(1,false)==p.START);
 assert(p.tick(20000,false)==p.NONE);
 assert(p.tick(20001,false)==p.STOP);
 assert(p.tick(25000,false)==p.NONE);
 assert(p.tick(25001,false)==p.START);
 assert(p.tick(45001,false)==p.STOP);
 assert(p.wait_ms==10000);
 assert(p.tick(45002,true)==p.NONE);
 assert(!p.active && !p.waiting && p.failures==0);
 p.reset();
 uint32_t start=0xfffffff0u;
 assert(p.tick(start,false)==p.START);
 assert(p.tick(start+19999u,false)==p.NONE);
 assert(p.tick(start+20000u,false)==p.STOP);
 for (unsigned i=0;i<10;++i) {
   start+=200000;
   assert(p.tick(start,false)==p.START);
   assert(p.tick(start+20000,false)==p.STOP);
   assert(p.wait_ms<=80000);
 }
 TFT_eSPI tft;
 map_ui::enter(tft);
 for(int i=0;i<60;++i) map_ui::tick(tft);
 assert(tft.clears==1 && tft.rows==thailand::HEIGHT);
 int writes=tft.writes, rows=tft.rows;
 for(int i=0;i<10;++i) { clock_ms+=1000; map_ui::tick(tft); }
 assert(tft.writes==writes && tft.rows==rows); // no continuous redraw
 current.failed=true; ++current.revision;
 clock_ms+=1000; map_ui::tick(tft);
 assert(tft.rows==rows && tft.writes>writes); // retry text, no map redraw
 online=false; clock_ms+=1000; map_ui::tick(tft);
 writes=tft.writes;
 clock_ms+=1000; map_ui::tick(tft);
 assert(tft.writes==writes && tft.rows==rows && tft.clears==1);
 current.valid=true; current.model_time=1792944900; current.received_at=clock_ms;
 epoch=1792944900;
 ++current.revision;
 for(auto &v:current.values) v=25;
 clock_ms+=1000; map_ui::tick(tft);
 for(int i=0;i<60;++i) map_ui::tick(tft);
 assert(tft.rows==rows+thailand::HEIGHT);
 rows=tft.rows;
 map_ui::swipe(tft,true);
 for(int i=0;i<60;++i) map_ui::tick(tft);
 assert(tft.rows==rows+thailand::HEIGHT && tft.clears==1);
 writes=tft.writes; rows=tft.rows;
 map_ui::swipe(tft,true); map_ui::tick(tft);
 assert(tft.rows==rows && tft.writes==writes); // same selection is a no-op
 assert(std::find(tft.strings.begin(),tft.strings.end(),"Bangkok UTC+7")!=tft.strings.end());
 assert(std::find(tft.strings.begin(),tft.strings.end(),"Fetched 0 m ago")!=tft.strings.end());
 assert(std::find(tft.strings.begin(),tft.strings.end(),"Min 25.0")!=tft.strings.end());
 assert(std::find(tft.strings.begin(),tft.strings.end(),"Temperature")!=tft.strings.end());
 assert(std::find(tft.strings.begin(),tft.strings.end(),"PM2.5")!=tft.strings.end());
 assert(std::find(tft.strings.begin(),tft.strings.end(),"OFFLINE / STALE")!=tft.strings.end());
 puts("PASS: actual UI redraw/selection/offline and bounded reconnect/backoff/wrap");
}
'''
with tempfile.TemporaryDirectory(prefix='cyd-ui-') as folder:
    d = Path(folder)
    (d/'TFT_eSPI.h').write_text(TFT)
    (d/'WiFi.h').write_text('#pragma once\nextern bool online;\nconstexpr int WL_CONNECTED=3;\nstruct FakeWiFi { int status() { return online ? WL_CONNECTED : 0; } };\nextern FakeWiFi WiFi;\n')
    (d/'test.cpp').write_text(SOURCE)
    subprocess.run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror', '-I', str(d), '-I', str(ROOT/'src'), str(d/'test.cpp'), str(ROOT/'src/map_ui.cpp'), '-o', str(d/'test.exe')], check=True)
    subprocess.run([str(d/'test.exe')], check=True)

main = (ROOT/'src/main.cpp').read_text()
home = main.split('if (screen == Screen::HOME) {', 1)[1].split('} else if (connecting)', 1)[0]
assert 'show_gate' not in home and 'save_wifi' not in home
assert 'inside(gesture_x' not in main
print('PASS: home reconnect cannot open setup/write NVS; removed bottom hitboxes')
