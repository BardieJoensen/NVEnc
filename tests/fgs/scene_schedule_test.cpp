#include "../../NVEncCore/NVEncFilmGrainScene.h"
#include <cstdlib>
#include <iostream>
#include <sstream>

static void require(bool value) { if (!value) { std::cerr << "scene schedule test failed\n"; std::exit(1); } }
int main() {
    NVEncFilmGrainSceneSchedule schedule;
    bool cut = true;
    require(schedule.consume(-1, cut) && !cut && schedule.complete());
    std::string error;
    std::istringstream input("FGS_SCENE_CUTS_V1 5\r\n0\r\n\n3\r\n");
    require(schedule.load(input, error) && schedule.frames() == 5 && schedule.cuts() == 2);
    require(!schedule.complete());
    require(schedule.isCut(0) && schedule.isCut(3) && !schedule.isCut(1));
    require(!schedule.isCut(-1) && !schedule.isCut(5));
    require(schedule.seen() == 0 && !schedule.complete()); // read-ahead cannot consume
    require(schedule.consume(0, cut) && cut);
    require(schedule.consume(1, cut) && !cut);
    require(schedule.consume(2, cut) && !cut);
    require(!schedule.complete()); // truncation
    require(schedule.consume(3, cut) && cut);
    require(schedule.consume(4, cut) && !cut && schedule.complete());
    require(!schedule.consume(5, cut)); // overrun
    require(!schedule.complete()); // a later pipeline drain cannot hide failure
    for (bool duplicate : {false, true}) {
        std::istringstream fresh("FGS_SCENE_CUTS_V1 2\n");
        require(schedule.load(fresh, error));
        if (duplicate) require(schedule.consume(0, cut));
        require(!schedule.consume(duplicate ? 0 : 1, cut));
        require(!schedule.consume(duplicate ? 1 : 0, cut) && !schedule.complete());
    }
    for (const char *invalid : {"", "5\n", "FGS_SCENE_CUTS_V1 0\n", "FGS_SCENE_CUTS_V1 -1\n",
        "FGS_SCENE_CUTS_V1 2147483648\n", "FGS_SCENE_CUTS_V1 5\n3\n3\n", "FGS_SCENE_CUTS_V1 5\n3\n2\n",
        "FGS_SCENE_CUTS_V1 5\n5\n", "FGS_SCENE_CUTS_V1 5\n-1\n", "FGS_SCENE_CUTS_V1 5\n1junk\n",
        "FGS_SCENE_CUTS_V1 5\n+1\n", "FGS_SCENE_CUTS_V1 5 \n"}) {
        std::istringstream bad(invalid);
        require(!schedule.load(bad, error) && !schedule.enabled());
    }
    std::istringstream empty("FGS_SCENE_CUTS_V1 1\n");
    require(schedule.load(empty, error) && schedule.consume(0, cut) && !cut && schedule.complete());
    std::cout << "scene schedule: PASS\n";
}
