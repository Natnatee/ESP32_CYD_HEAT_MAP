"""Run actual bounded fetch function with pinned ArduinoJson and network mocks."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'src/map_data.cpp').read_text()
fetch = source[source.index('bool fetch_batch('):source.index('void worker(void *)')]
headers = ROOT/'.pio/libdeps/cyd_ili9341/ArduinoJson/src'
harness = r'''
#include "map_decode.h"
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <string>
#include <cstring>
using std::min;
using String=std::string;
// Replace Arduino's fixed-decimal constructor in the extracted function below.
std::string coordinate(float value, int precision) {
 char s[32]; snprintf(s,sizeof(s),"%.*f",precision,value); return s;
}
uint32_t clock_ms=0;
uint32_t millis() { return clock_ms; }
long fake_time(void*) { return 1792944900; }
#define time fake_time
constexpr unsigned BATCH=thailand::COUNT;
constexpr int WL_CONNECTED=3, MALLOC_CAP_8BIT=0;
const char *API_ROOTS="trusted roots";
struct { int status() { return WL_CONNECTED; } } WiFi;
struct { unsigned getFreeHeap() { return 150000; } } ESP;
unsigned heap_caps_get_largest_free_block(int) { return 100000; }
int xPortGetCoreID() { return 0; }
unsigned uxTaskGetStackHighWaterMark(void*) { return 8000; }
void vTaskDelay(unsigned ms) { clock_ms+=ms; }
#define pdMS_TO_TICKS(x) (x)
struct { template<class... T> void printf(const char*,T...) {} } Serial;
char response[16384];
map_data::Snapshot candidate[2]{};
using map_data::decode_batch;
using map_data::Snapshot;
unsigned connects=0, errors=0, requests=0;
bool begun=false, ended=false;
int status_code=200, size_override=-2;
std::string body, requested_url;
size_t position=0;
struct WiFiClient {
 int available() { return int(body.size()-position); }
 size_t readBytes(char *dst,size_t n) {
  n=min(n,body.size()-position); memcpy(dst,body.data()+position,n); position+=n; return n;
 }
};
struct WiFiClientSecure:WiFiClient {
 bool trusted=false;
 void setCACert(const char *roots) { assert(roots==API_ROOTS); trusted=true; }
 void setHandshakeTimeout(int n) { assert(n==20); }
 void setTimeout(int n) { assert(n==8); }
 int connect() { assert(begun && trusted); ++connects; return 1; }
 int lastError(char*,size_t) { ++errors; return 48; }
};
struct HTTPClient {
 WiFiClientSecure *client=nullptr;
 void useHTTP10(bool value) { assert(value); }
 void setConnectTimeout(int n) { assert(n==8000); }
 void setTimeout(int n) { assert(n==8000); }
 void setReuse(bool value) { assert(!value); }
 bool begin(WiFiClientSecure &tls,const String &url) {
  client=&tls; begun=true; ended=false; requested_url=url; position=0; return true;
 }
 void addHeader(const char*,const char*) {}
 int GET() { ++requests; client->connect(); return status_code; }
 int getSize() { return size_override==-2 ? int(body.size()) : size_override; }
 WiFiClient *getStreamPtr() { return client; }
 bool connected() { return position<body.size(); }
 void end() { ended=true; begun=false; }
};
'''
main = r'''
std::string payload(bool pm) {
 std::string s="[";
 for(unsigned i=0;i<thailand::COUNT;++i) {
  if(i) s+=',';
  s+=pm ? R"({"latitude":13.75,"longitude":100.5,"generationtime_ms":0.1,"utc_offset_seconds":0,"timezone":"GMT","timezone_abbreviation":"GMT","elevation":10,"current_units":{"time":"unixtime","interval":"seconds","pm2_5":"μg/m³"},"current":{"time":1792944900,"interval":3600,"pm2_5":12.4}})" :
   R"({"latitude":13.75,"longitude":100.5,"generationtime_ms":0.1,"utc_offset_seconds":0,"timezone":"GMT","timezone_abbreviation":"GMT","elevation":10,"current_units":{"time":"unixtime","interval":"seconds","temperature_2m":"°C"},"current":{"time":1792944900,"interval":900,"temperature_2m":26.2}})";
 }
 return s+']';
}
int main() {
 DynamicJsonDocument doc(16384);
 for(unsigned page=0;page<2;++page) {
  body=payload(page); assert(body.size()>6500 && body.size()<sizeof(response));
  assert(fetch_batch(page,0,doc));
  assert(connects==page+1 && requests==page+1 && errors==0 && ended);
  assert(!candidate[page].valid && candidate[page].values[24]>0);
  auto a=requested_url.find("latitude=")+9, b=requested_url.find('&',a);
  assert(std::count(requested_url.begin()+a,requested_url.begin()+b,',')==24);
 }
 body=std::string(16384,' '); assert(!fetch_batch(0,0,doc) && ended);
 body=payload(false); size_override=int(body.size())+1;
 assert(!fetch_batch(0,0,doc) && ended); // truncated response
 size_override=-1; assert(fetch_batch(0,0,doc)); // bounded unknown length
 body=std::string(17000,' '); assert(!fetch_batch(0,0,doc) && ended);
 size_override=-2; status_code=-1; body.clear();
 assert(!fetch_batch(0,0,doc) && errors==1 && ended);
 status_code=429; assert(!fetch_batch(0,0,doc) && errors==1 && ended);
 puts("PASS: actual fetch single validated TLS per GET, full URLs/25-point payloads, bounded body/truncation/HTTP/TLS failures");
}
'''
fetch = fetch.replace('String(thailand::LOCATIONS[i].lat,3)', 'coordinate(thailand::LOCATIONS[i].lat,3)')
fetch = fetch.replace('String(thailand::LOCATIONS[i].lon,3)', 'coordinate(thailand::LOCATIONS[i].lon,3)')
with tempfile.TemporaryDirectory(prefix='cyd-fetch-') as folder:
    d = Path(folder)
    (d/'test.cpp').write_text(harness+fetch+main, encoding='utf-8')
    subprocess.run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror', '-I', str(ROOT/'src'), '-I', str(headers), str(d/'test.cpp'), '-o', str(d/'test.exe')], check=True, timeout=45)
    subprocess.run([str(d/'test.exe')], check=True, timeout=10)
