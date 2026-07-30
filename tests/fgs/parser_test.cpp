// CPU behavior tests for the AOM filmgrn1 table parser (NVEncFilmGrain).
// No GPU required.  Build and run via tests/fgs/run_cpu_tests.sh, or:
//   g++ -std=c++17 -O2 -I NVEncCore -I NVEncSDK/Common/inc
//       tests/fgs/parser_test.cpp NVEncCore/NVEncFilmGrain.cpp -o parser_test
//
// Fixtures are written to a temporary directory at startup so the test is
// self-contained.

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

#include "NVEncFilmGrain.h"

namespace {

tstring g_dir;

void writeFixture(const char *filename, const char *content) {
    const tstring p = g_dir + _T("/") + filename;
    FILE *f = fopen(p.c_str(), "w");
    assert(f != nullptr);
    fputs(content, f);
    fclose(f);
}

tstring path(const TCHAR *filename) {
    return g_dir + _T("/") + filename;
}

void expectInvalid(const TCHAR *filename, const TCHAR *expectedError) {
    tstring error;
    const auto table = NVEncFilmGrainTable::load(path(filename), false, error);
    if (table || error.find(expectedError) == tstring::npos) {
        std::cerr << "unexpected result for invalid fixture: " << filename
                  << "\nerror: " << error << "\n";
        std::abort();
    }
}

const char *const FIXTURE_VALID_INHERITED =
    "filmgrn1\n"
    "E 0 10000000 1 12345 1\n"
    "p 1 8 0 8 1 1 0 0 0 0 0 0\n"
    "sY 4 0 0 32 80 224 80 255 0\n"
    "sCb 0\n"
    "sCr 0\n"
    "cY 24 4 -2 12\n"
    "cCb 0 0 0 0 0\n"
    "cCr 0 0 0 0 0\n"
    "E 10000000 20000000 1 54321 0\n";

const char *const FIXTURE_INVALID_OVERLAP =
    "filmgrn1\n"
    "E 0 10000000 0 1 0\n"
    "E 5000000 15000000 0 2 0\n";

const char *const FIXTURE_INVALID_SCALING_ORDER =
    "filmgrn1\n"
    "E 0 10000000 1 12345 1\n"
    "p 0 8 0 8 1 1 0 0 0 0 0 0\n"
    "sY 2 100 40 90 50\n"
    "sCb 0\n"
    "sCr 0\n"
    "cY\n"
    "cCb 0\n"
    "cCr 0\n";

const char *const FIXTURE_INVALID_INHERIT_FIRST =
    "filmgrn1\n"
    "E 0 10000000 1 12345 0\n";

const char *const FIXTURE_INVALID_COUNTS =
    "filmgrn1\n"
    "E 0 10000000 1 12345 1\n"
    "p 0 8 0 8 1 1 0 0 0 0 0 0\n"
    "sY 15\n";

const char *const FIXTURE_INVALID_ASYMMETRIC_CHROMA =
    "filmgrn1\n"
    "E 0 10000000 1 12345 1\n"
    "p 0 8 0 8 0 1 0 0 0 128 192 256\n"
    "sY 1 0 20\n"
    "sCb 0\n"
    "sCr 1 0 1\n"
    "cY\n"
    "cCb 0\n"
    "cCr 0\n";

} // namespace

int main() {
    char dirTemplate[] = "/tmp/fgs-parser-test-XXXXXX";
    const char *dir = mkdtemp(dirTemplate);
    assert(dir != nullptr);
    g_dir = dir;
    writeFixture("valid-inherited.filmgrn1", FIXTURE_VALID_INHERITED);
    writeFixture("invalid-overlap.filmgrn1", FIXTURE_INVALID_OVERLAP);
    writeFixture("invalid-scaling-order.filmgrn1", FIXTURE_INVALID_SCALING_ORDER);
    writeFixture("invalid-inheritance-before-model.filmgrn1", FIXTURE_INVALID_INHERIT_FIRST);
    writeFixture("invalid-malformed-counts.filmgrn1", FIXTURE_INVALID_COUNTS);
    writeFixture("invalid-asymmetric-chroma.filmgrn1", FIXTURE_INVALID_ASYMMETRIC_CHROMA);

    tstring error;
    const auto table = NVEncFilmGrainTable::load(
        path(_T("valid-inherited.filmgrn1")), false, error);
    if (!table) {
        std::cerr << "valid fixture failed: " << error << "\n";
        return 1;
    }

    assert(table->entries().size() == 2);
    const auto& explicitModel = table->lookup(0);
    const auto& inheritedModel = table->lookup(10000000);
    assert(&table->lookup(9999999) == &explicitModel);
    assert(&table->lookup(19999999) == &inheritedModel);
    assert(&table->lookup(20000000) == &table->off());

    assert(explicitModel.startTime == 0);
    assert(explicitModel.endTime == 10000000);
    assert(explicitModel.randomSeed == 12345);
    assert(explicitModel.sourceUpdateParameters);
    assert(inheritedModel.startTime == 10000000);
    assert(inheritedModel.endTime == 20000000);
    assert(inheritedModel.randomSeed == 54321);
    assert(!inheritedModel.sourceUpdateParameters);
    assert(explicitModel.randomSeed != inheritedModel.randomSeed);

    assert(explicitModel.params.applyGrain == 1);
    assert(explicitModel.params.chromaScalingFromLuma == 1);
    assert(explicitModel.params.overlapFlag == 1);
    assert(explicitModel.params.arCoeffLag == 1);
    assert(explicitModel.params.arCoeffShiftMinus6 == 2);
    assert(explicitModel.params.grainScaleShift == 0);
    assert(explicitModel.params.grainScalingMinus8 == 0);
    assert(explicitModel.params.numYPoints == 4);
    assert(explicitModel.params.numCbPoints == 0);
    assert(explicitModel.params.numCrPoints == 0);
    assert(explicitModel.params.arCoeffsYPlus128[0] == 152);
    assert(explicitModel.params.arCoeffsYPlus128[1] == 132);
    assert(explicitModel.params.arCoeffsYPlus128[2] == 126);
    assert(explicitModel.params.arCoeffsYPlus128[3] == 140);
    assert(std::memcmp(&explicitModel.params, &inheritedModel.params,
        sizeof(explicitModel.params)) == 0);

    expectInvalid(_T("invalid-overlap.filmgrn1"), _T("overlaps"));
    expectInvalid(_T("invalid-scaling-order.filmgrn1"),
        _T("strictly increasing"));
    expectInvalid(_T("invalid-inheritance-before-model.filmgrn1"),
        _T("cannot inherit"));
    expectInvalid(_T("invalid-malformed-counts.filmgrn1"),
        _T("scaling point count must be in [0, 14]"));
    expectInvalid(_T("invalid-asymmetric-chroma.filmgrn1"),
        _T("both be zero or both be non-zero"));

    std::cout << "all filmgrn1 parser behavior tests passed\n";
    return 0;
}
