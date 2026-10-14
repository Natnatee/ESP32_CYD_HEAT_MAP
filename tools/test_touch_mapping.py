"""Host regression tests for the actual firmware fit/map and keyboard geometry.

Requires Python and g++; no ESP32, external Python packages or credentials.
Build artifacts live in a temporary directory.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "src/main.cpp").read_text(encoding="utf-8")


def function(name):
    match = re.search(r"^(?:bool|int|KeyRect|const char \*)\s*" + name + r"\([^\n]*\) \{", SOURCE, re.M)
    assert match, f"Function not found: {name}"
    start = SOURCE.index("{", match.start())
    depth = 1
    end = start + 1
    while depth:
        if SOURCE[end] == "{":
            depth += 1
        elif SOURCE[end] == "}":
            depth -= 1
        end += 1
    return SOURCE[match.start():end]


constants = []
for name in ("CORNER_X", "CORNER_Y", "TARGET_SPAN_X", "TARGET_SPAN_Y"):
    match = re.search(r"^constexpr int " + name + r"(?:\[\])? = .*?;", SOURCE, re.M)
    assert match
    constants.append(match.group())

harness = r'''
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
using std::min;
using std::isfinite;
struct SerialStub {
    template<typename... Args> void printf(const char *format, Args... args) { std::printf(format, args...); }
} Serial;
struct Calibration { float ox, oy, ux, uy, vx, vy; bool valid; } calibration{};
float corner_raw_x[4]{}, corner_raw_y[4]{};
bool symbols=false, uppercase=false;
unsigned int symbol_page=0;
constexpr int KEYBOARD_Y=121, KEY_ROW_STEP=31, KEY_H=29;
struct KeyRect { int x,y,w,h; };
constexpr int TOUCH_RAW_MIN=200, TOUCH_RAW_MAX=3900;
constexpr int RAW_CORNER_LOW=1125, RAW_CORNER_HIGH=2975;
template<typename T> T constrain(T v, T lo, T hi) { return std::min(std::max(v,lo),hi); }
'''
harness += "\n".join(constants) + "\n"
harness += "\n".join(function(name) for name in ("fit_calibration", "map_touch", "raw_corner", "keyboard_row", "keyboard_key", "inside"))
harness += r'''
// Synthetic ADC model, including cross-axis skew. These are not hardware measurements.
float raw_x(float x, float y) { return 300 + 10*x + 0.1f*y; }
float raw_y(float x, float y) { return 200 + 0.2f*x + 14*y; }
void check_pixel(int expected_x, int expected_y) {
    int x=-1,y=-1;
    assert(map_touch(lroundf(raw_x(expected_x,expected_y)), lroundf(raw_y(expected_x,expected_y)),x,y));
    assert(x==expected_x && y==expected_y);
}
int main() {
    // Fill by physical corner identity in arbitrary order, not a sequential assignment.
    for (int i : {2,0,3,1}) {
        corner_raw_x[i]=raw_x(CORNER_X[i],CORNER_Y[i]);
        corner_raw_y[i]=raw_y(CORNER_X[i],CORNER_Y[i]);
        assert(raw_corner(lroundf(corner_raw_x[i]),lroundf(corner_raw_y[i]))==i);
    }
    assert(raw_corner(2000,2000)==-1);
    assert(fit_calibration());
    for (int i=0;i<4;++i) check_pixel(CORNER_X[i],CORNER_Y[i]);
    for (int y : {0,1,120,238,239}) for (int x : {0,1,160,318,319}) check_pixel(x,y);
    int x,y;
    // Old +-12px rejection dropped these otherwise valid ADC samples.
    assert(map_touch(lroundf(raw_x(-20,120)),lroundf(raw_y(-20,120)),x,y) && x==0);
    assert(map_touch(lroundf(raw_x(339,120)),lroundf(raw_y(339,120)),x,y) && x==319);
    assert(map_touch(lroundf(raw_x(160,-14)),lroundf(raw_y(160,-14)),x,y) && y==0);
    assert(map_touch(lroundf(raw_x(160,253)),lroundf(raw_y(160,253)),x,y) && y==239);
    assert(!map_touch(0,2000,x,y));
    assert(!map_touch(4095,2000,x,y));
    int rectangles=0;
    for (int mode=0;mode<4;++mode) {
        symbols=mode>=2; uppercase=mode==1; symbol_page=mode==3;
        for(int row=0;row<3;++row) for(int col=0;col<int(strlen(keyboard_row(row)));++col) {
            KeyRect r=keyboard_key(row,col);
            assert(r.x>=0 && r.x+r.w<=320 && r.y+r.h<=240);
            for(int py : {r.y,r.y+r.h-1}) for(int px : {r.x,r.x+r.w-1}) {
                check_pixel(px,py);
                assert(map_touch(lroundf(raw_x(px,py)),lroundf(raw_y(px,py)),x,y));
                assert(inside(x,y,r.x,r.y,r.w,r.h));
            }
            ++rectangles;
        }
    }
    // An inconsistent fourth corner must not unlock the calibration gate.
    corner_raw_x[2]+=500;
    assert(!fit_calibration());
    for(int i=0;i<4;++i) { corner_raw_x[i]=500; corner_raw_y[i]=500; }
    assert(!fit_calibration());
    calibration.valid=false;
    assert(!map_touch(2000,2000,x,y));
    std::printf("PASS: circle centers, skew fit, screen-edge extrapolation/clamp, %d key rectangles, invalid fits.\n",rectangles);
}
'''
with tempfile.TemporaryDirectory(prefix="cyd-touch-test-") as folder:
    source = Path(folder) / "test.cpp"
    executable = Path(folder) / "test.exe"
    source.write_text(harness, encoding="utf-8")
    subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", str(source), "-o", str(executable)], check=True, timeout=30)
    subprocess.run([str(executable)], check=True, timeout=10)
