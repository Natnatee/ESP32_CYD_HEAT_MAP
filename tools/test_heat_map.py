"""Host tests: actual interpolation, mask, colors, gesture classification; no board."""
from pathlib import Path
import subprocess
import tempfile

import json

ROOT=Path(__file__).resolve().parents[1]
header=ROOT/'src/thailand_mask.h'
before=header.read_bytes()
subprocess.run(['python',str(ROOT/'tools/generate_thailand.py')],check=True)
assert header.read_bytes()==before, 'Offline asset must reproduce exactly'
feature=json.loads((ROOT/'assets/map/thailand.geojson').read_text())
assert feature['properties']['ADM0_A3']=='THA'
assert feature['geometry']['type']=='MultiPolygon'
source=r'''
#include "map_math.h"
#include <cassert>
#include <cstdio>
int main() {
    assert(thailand::WIDTH==148 && thailand::HEIGHT==230);
    assert(fabsf(float(thailand::WIDTH)/thailand::HEIGHT-112.f/174)<0.002);
    float values[thailand::COUNT];
    for (auto &v:values) v=25;
    assert(fabsf(heat_map::interpolate(14,101,values)-25)<0.001);
    for (unsigned i=0;i<thailand::COUNT;++i) values[i]=float(i);
    for (unsigned i=0;i<thailand::COUNT;++i)
        assert(heat_map::interpolate(thailand::LOCATIONS[i].lat,thailand::LOCATIONS[i].lon,values)==float(i));
    for (auto &v:values) v=NAN;
    assert(isnan(heat_map::interpolate(14,101,values)));
    values[0]=3;
    assert(fabsf(heat_map::interpolate(14,101,values)-3)<0.001);
    assert(!thailand::contains_pixel(-1,0));
    assert(!thailand::contains_pixel(thailand::WIDTH,0));
    auto inside=[](float lat,float lon) { return thailand::contains_pixel(
        int((lon-thailand::WEST)*thailand::WIDTH/(thailand::EAST-thailand::WEST)),
        int((thailand::NORTH-lat)*thailand::HEIGHT/(thailand::NORTH-thailand::SOUTH))); };
    assert(inside(13.75,100.5)); // Bangkok
    assert(inside(18.8,99)); // northern interior
    assert(inside(6.4,101.3)); // southern interior
    assert(!inside(12,103)); // Gulf
    assert(!inside(18,97.2)); // Myanmar
    assert(heat_map::color(-100,false)==heat_map::color(10,false));
    assert(heat_map::color(999,true)==heat_map::color(100,true));
    assert(heat_map::color(NAN,true)==0x4208);
    using G=heat_map::Gesture;
    assert(heat_map::gesture(-60,10,60,400)==G::LEFT);
    assert(heat_map::gesture(60,10,60,400)==G::RIGHT);
    assert(heat_map::gesture(2,3,3,200)==G::TAP);
    assert(heat_map::gesture(2,3,60,200)==G::NONE); // dragged back, not tap
    assert(heat_map::gesture(40,60,60,400)==G::NONE);
    assert(heat_map::gesture(60,0,60,1600)==G::NONE);
    puts("PASS: heat map math, clipping, colors and swipe/tap");
}
'''
with tempfile.TemporaryDirectory(prefix='cyd-map-') as d:
    d=Path(d)
    (d/'test.cpp').write_text(source)
    subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-Werror','-I',str(ROOT/'src'),str(d/'test.cpp'),'-o',str(d/'test.exe')],check=True)
    subprocess.run([str(d/'test.exe')],check=True)
