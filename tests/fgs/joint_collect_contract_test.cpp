#include "NVEncFilmGrainJointCollect.h"
#include <cassert>
#include <iostream>
using namespace fgsmodel;
int main() {
    FilmGrainCollectFrame current;
    current.width=1920;current.height=1080;current.complete=true;
    current.frameId=2;current.timestamp=80;current.epoch=7;
    for(unsigned i=0;i<3;++i)current.plane[i]={reinterpret_cast<void*>(uintptr_t(0x1000+i*0x1000)),4096,1};
    auto base=current,previous=current;previous.frameId=1;previous.timestamp=40;
    assert(film_grain_collect_base_valid(current,base));
    assert(film_grain_collect_history_valid(current,previous));
    auto broken=previous;broken.plane[1].data=nullptr;
    assert(!film_grain_collect_history_valid(current,broken)); // allocated/copied Y is insufficient
    broken=previous;broken.complete=false;assert(!film_grain_collect_history_valid(current,broken));
    broken=previous;broken.epoch++;assert(!film_grain_collect_history_valid(current,broken));
    broken=previous;broken.frameId--;assert(!film_grain_collect_history_valid(current,broken));
    broken=previous;broken.timestamp=current.timestamp;assert(!film_grain_collect_history_valid(current,broken));
    broken=previous;broken.timestamp=std::numeric_limits<int64_t>::min();assert(!film_grain_collect_history_valid(current,broken));
    broken=previous;broken.width/=2;assert(!film_grain_collect_history_valid(current,broken));
    broken=base;broken.frameId--;assert(!film_grain_collect_base_valid(current,broken));
    broken=base;broken.timestamp--;assert(!film_grain_collect_base_valid(current,broken));
    broken=base;broken.epoch++;assert(!film_grain_collect_base_valid(current,broken));
    broken=current;broken.storageShift=6;assert(film_grain_collect_layout_valid(broken));
    broken=current;broken.storageShift=1;assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.width=1919;assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.height=8194;assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.plane[0].pixelStride=2;assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.plane[1].pixelStride=2;broken.plane[2].pixelStride=2;
    assert(film_grain_collect_layout_valid(broken));
    broken.plane[1].pitchBytes=3839;assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.plane[1].data=reinterpret_cast<void*>(0x1001);assert(!film_grain_collect_layout_valid(broken));
    broken=current;broken.bitDepth=8;assert(film_grain_collect_layout_valid(broken));
    broken.storageShift=6;assert(!film_grain_collect_layout_valid(broken));
    current.frameId=std::numeric_limits<int64_t>::max();previous.frameId=current.frameId-1;
    assert(film_grain_collect_history_valid(current,previous));
    current.frameId=0;previous.frameId=std::numeric_limits<int64_t>::max();
    assert(!film_grain_collect_history_valid(current,previous));
    std::cout<<"Native joint collection rejects invalid layouts, stale bases and incomplete/reset colour history\n";
}
