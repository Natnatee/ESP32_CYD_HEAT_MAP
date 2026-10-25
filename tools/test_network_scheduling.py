"""Host regression for actual worker creation and scheduler compatibility guards.
Does not emulate ESP-IDF SMP or prove hardware watchdog recovery.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'src/map_data.cpp').read_text()
guard = source[source.index('#if configUSE_PREEMPTION'):source.index('namespace map_data')]
begin = source[source.index('bool begin() {'):source.index('void diagnostics()')]
assert 'xTaskCreatePinnedToCore' not in source
assert 'setInsecure' not in source
assert 'tls.setCACert(API_ROOTS)' in source
assert 'tls.setHandshakeTimeout(20)' in source
assert 'tls.setTimeout(8);' in source
assert 'tls.connect(' not in source and 'hostByName(' not in source
assert source.count('http.GET()') == 1
assert source.index('if (status<0)') < source.index('tls.lastError(')
assert 'constexpr unsigned BATCH=thailand::COUNT;' in source
assert 'char response[16384];' in source
assert 'tls.lastError(error,sizeof(error))' in source
assert 'http.setConnectTimeout(8000)' in source
assert 'http.setTimeout(8000)' in source
assert 'esp_task_wdt' not in source
harness = r'''
#include <cassert>
constexpr unsigned tskIDLE_PRIORITY=0;
constexpr int pdPASS=1;
void *worker_handle=nullptr;
void worker(void *) {}
int calls=0;
bool fail=false;
int xTaskCreate(void (*fn)(void *),const char *,unsigned stack,void *arg,
                unsigned priority,void **handle) {
    ++calls;
    assert(fn==worker && stack==12288 && arg==nullptr);
    assert(priority==tskIDLE_PRIORITY);
    if (fail) return 0;
    *handle=reinterpret_cast<void *>(1);
    return pdPASS;
}
'''
main = r'''
int main() {
    fail=true; assert(!begin() && calls==1 && !worker_handle);
    fail=false; assert(begin() && calls==2 && worker_handle);
    assert(begin() && calls==2);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / 'worker.cpp'
    exe = Path(tmp) / 'worker.exe'
    cpp.write_text(guard + harness + begin + main)
    flags = ['-DconfigUSE_PREEMPTION=1', '-DconfigUSE_TIME_SLICING=1',
             '-DconfigIDLE_SHOULD_YIELD=0']
    subprocess.run(['g++', '-std=c++17', *flags, str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
    for index, bad in enumerate(['-DconfigUSE_PREEMPTION=0',
                                 '-DconfigUSE_TIME_SLICING=0',
                                 '-DconfigIDLE_SHOULD_YIELD=1']):
        incompatible = flags.copy()
        incompatible[index] = bad
        result = subprocess.run(['g++', '-std=c++17', *incompatible,
                                 '-fsyntax-only', str(cpp)], capture_output=True, text=True)
        assert result.returncode != 0 and 'Map TLS worker requires' in result.stderr
print('PASS: actual worker creation, scheduler guards, TLS/watchdog policy')

# Compile the actual worker loop with deterministic network/time mocks.
worker = source[source.index('void worker(void *) {'):source.index(chr(10)+'}'+chr(10)+'}'+chr(10)+'bool begin()')+2]
mock = r"""
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
using std::min;
uint32_t clock_ms=0;
uint32_t millis() { return clock_ms; }
long time(void*) { return 1800000000; }
constexpr int WL_CONNECTED=3;
struct { int status() { return WL_CONNECTED; } } WiFi;
struct DynamicJsonDocument { DynamicJsonDocument(int) {} int capacity() { return 8192; } };
struct Snapshot { uint32_t model_time=0, received_at=0, revision=0; bool valid=false, failed=false; };
Snapshot candidate[2], published[2];
namespace thailand { constexpr unsigned COUNT=25; }
constexpr unsigned BATCH=25, REFRESH_MS=3600000;
int lock;
#define portENTER_CRITICAL(x) ((void)(x))
#define portEXIT_CRITICAL(x) ((void)(x))
#define pdMS_TO_TICKS(x) (x)
struct { template<class... T> void printf(const char*,T...) {} } Serial;
unsigned calls[2][5]{}, first_fail=0, second_try=0;
bool simulate_failure=true;
unsigned order[3]{}, request_count=0;
bool fetch_batch(unsigned p,unsigned b,DynamicJsonDocument&) {
 ++calls[p][b/5];
 assert(request_count<3); order[request_count++]=p;
 if(!simulate_failure && p==1) assert(published[0].valid); // publish page 0 first
 if(simulate_failure && p==0 && b==0 && calls[p][0]==1) { first_fail=clock_ms; return false; }
 if(p==0 && b==0) second_try=clock_ms;
 candidate[p].model_time=1800000000;
 return true;
}
void vTaskDelay(unsigned ms) { clock_ms+=ms; if(clock_ms>15000) throw 1; }
"""
main = r"""
int main() {
 try { worker(nullptr); } catch(int) {}
 assert(published[0].valid && published[1].valid);
 assert(calls[0][0]==2 && calls[1][0]==1);
 for(unsigned p=0;p<2;++p) for(unsigned b=0;b<5;++b)
   assert(calls[p][b]==(b==0 ? (p==0 ? 2u : 1u) : 0u));
 assert(second_try-first_fail>=1000);
 // Healthy refresh: exactly two requests; no partial publish or later batch.
 clock_ms=0; request_count=0; simulate_failure=false;
 for(unsigned p=0;p<2;++p) {
   candidate[p]=Snapshot{}; published[p]=Snapshot{};
   for(auto &n:calls[p]) n=0;
 }
 try { worker(nullptr); } catch(int) {}
 assert(request_count==2 && order[0]==0 && order[1]==1);
 assert(published[0].valid && published[1].valid);
}
"""
with tempfile.TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'retry.cpp'; exe=Path(tmp)/'retry.exe'
    cpp.write_text(mock+worker+main)
    subprocess.run(['g++','-std=c++11',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
print('PASS: actual worker batch retry/backoff, independent pages, no successful batch reload')
