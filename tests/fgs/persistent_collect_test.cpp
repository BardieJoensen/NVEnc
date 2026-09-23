#include "NVEncFilmGrainPersistentCollect.h"
#include <cassert>
#include <iostream>
using namespace fgsmodel;
int main() {
    FilmGrainCollectFrame current;
    current.width=1920;current.height=1080;current.complete=true;
    current.frameId=7;current.timestamp=280;current.epoch=9;
    for (unsigned c=0;c<3;++c)
        current.plane[c]={reinterpret_cast<void*>(uintptr_t(0x1000+c*0x1000)),4096,1};
    FilmGrainPersistentHistory history;
    for (int h=0;h<7;++h) {
        history.source[h]=current;history.source[h].frameId=h;history.source[h].timestamp=h*40;
    }
    assert(film_grain_persistent_history_valid(current,history));
    for (unsigned h=0;h<7;++h) {
        auto bad=history;bad.source[h].complete=false;
        assert(!film_grain_persistent_history_valid(current,bad));
        bad=history;bad.source[h].epoch++;
        assert(!film_grain_persistent_history_valid(current,bad));
        bad=history;bad.source[h].frameId++;
        assert(!film_grain_persistent_history_valid(current,bad));
        bad=history;bad.source[h].timestamp=280;
        assert(!film_grain_persistent_history_valid(current,bad));
        bad=history;bad.source[h].plane[2].data=nullptr;
        assert(!film_grain_persistent_history_valid(current,bad));
        bad=history;bad.source[h].bitDepth=8;
        assert(!film_grain_persistent_history_valid(current,bad));
    }
    current.frameId=std::numeric_limits<int64_t>::max();
    for (unsigned h=0;h<7;++h) history.source[h].frameId=current.frameId-7+h;
    assert(film_grain_persistent_history_valid(current,history));
    current.frameId=0;assert(!film_grain_persistent_history_valid(current,history));
    FilmGrainPersistentResult row;row.samples=4096;
    for (auto& v:row.mean) v=128;
    for (auto& v:row.covariance) v=64;
    const FilmGrainPersistentLimits limits{.02,.125,.125,.5,.8};
    assert(film_grain_persistent_result_detail(row,limits).withinLimits);
    row.changedSamples=4097;
    assert(!film_grain_persistent_result_detail(row,limits).valid);
    row.changedSamples=0;row.reasons=0;row.reserved=1;
    assert(!film_grain_persistent_result_detail(row,limits).valid);
    row.reserved=0;row.reasons=FGS_COLLECT_HISTORY;
    assert(!film_grain_persistent_result_detail(row,limits).valid);
    row.reasons=0;row.covariance[10]=-7.89491928622356e-16;
    assert(!film_grain_persistent_result_detail(row,limits).valid); // Fix collection, not the PSD guard.
    std::cout<<"Persistent detail requires all seven adjacent, same-epoch native histories\n";
}
