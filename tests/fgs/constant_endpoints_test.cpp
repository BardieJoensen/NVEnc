#include <cstdlib>
#include <iostream>
#include <limits>
#include "NVEncFilmGrainConstantEndpoints.h"
#include "NVEncFilmGrainScaling.h"

static void require(bool condition, const char* message) {
    if (!condition) { std::cerr << message << '\n'; std::exit(1); }
}

int main() {
    NV_ENC_FILM_GRAIN_PARAMS_AV1 p{};
    p.cbMult=p.crMult=128; p.cbLumaMult=p.crLumaMult=192; p.cbOffset=p.crOffset=256;
    for (unsigned depth : {8u,10u}) for (bool restricted : {false,true}) {
        p.clipToRestrictedRange=restricted;
        const unsigned scale=1u<<(depth-8), black=restricted?16*scale:0;
        const unsigned white=restricted?235*scale:(1u<<depth)-1;
        fgsmodel::FilmGrainConstantEndpoints guard;
        guard.advance(true,depth,p);
        for (unsigned code=0;code<(1u<<depth);++code) {
            const int result=guard.observeLuma(code,code,8,8);
            require((result>=0)==(code==black || code==white),"non-endpoint source constrained");
        }
        require(guard.observed(0)==2,"endpoint observation count differs");
        const int atBlack=restricted?16:0, atWhite=restricted?235:255;
        require(guard.gain(0,atBlack)==0 && guard.gain(0,atWhite)==0,"endpoint not capped");
        require(guard.gain(0,atBlack+1)==1 && guard.gain(0,atWhite-1)==1,"neighboring source codes capped");
        require(guard.observeLuma(black,black+1,8,8)==-1,"weak native source grain treated as constant");
        require(guard.observeLuma(black,black,7,8)==-1 && guard.observeLuma(white,white,8,7)==-1,
            "undersized endpoint region accepted");
        require(guard.observeLuma(std::numeric_limits<double>::quiet_NaN(),0,8,8)==-1,
            "invalid endpoint accepted");
        require(guard.observeChroma(1,atBlack,128*scale,0,8,8),"constant colour not protected");
        require(!guard.observeChroma(2,atBlack,128*scale,.01,8,8),"weak colour grain treated as constant");
        require(!guard.observeChroma(2,atBlack,128*scale,0,7,8),"tiny colour region accepted");
        require(!guard.observeChroma(2,atBlack,128*scale+.5,0,8,8),"fractional constant native colour accepted");
        require(guard.gain(2,atBlack)==1,"luma evidence inferred colour constancy");
        require(!guard.observeChroma(2,128,128*scale,0,8,8),"non-endpoint luma admitted");
        if (restricted) require(!guard.observeChroma(2,atBlack,15*scale,0,8,8),"restricted range failure ignored");
        uint8_t values[14]={0,64,128,192,255},scalings[14]={60,48,72,32,28};
        fgsmodel::FilmGrainScalingLut before,after;
        require(before.build(values,scalings,5,depth),"input curve invalid");
        bool changed=false;
        const auto count=guard.refitCurve(0,values,scalings,5,14,changed);
        require(changed && count<=14 && after.build(values,scalings,count,depth),"endpoint refit invalid");
        unsigned a=0,b=0;
        for (unsigned code=0;code<(1u<<depth);++code) {
            require(before.lookup(code,a)&&after.lookup(code,b)&&b<=a,"endpoint curve increased native synthesis");
            if (code==black || code==white) require(b==0,"exact native endpoint still synthesizes");
        }
        for (int i=0;i<100;++i) guard.advance(false,depth,p);
        require(guard.gain(0,atBlack)==0,"stale fits released endpoint protection");
        guard.noModel();
        require(guard.gain(0,atBlack)==0 && guard.observed(0)==0,
            "missing model released endpoint state or retained current observations");
        for (int i=0;i<24;++i) guard.advance(true,depth,p);
        require(guard.gain(0,atBlack)==0,"endpoint hold ended early");
        guard.advance(true,depth,p);
        require(guard.gain(0,atBlack)==1./16,"endpoint release skipped ramp");
        auto changedLookup=p;changedLookup.cbMult=129;
        guard.advance(false,depth,changedLookup);
        require(guard.gain(1,atBlack)==1 && !guard.observeChroma(1,atBlack,128*scale,0,8,8),
            "colour protection crossed lookup domains");
        auto changedRange=p;changedRange.clipToRestrictedRange=!restricted;
        guard.advance(false,depth,changedRange);
        require(guard.gain(0,atBlack)==1,"endpoint protection crossed range domains");
        guard.advance(false,depth,p);
        guard.observeLuma(black,black,8,8);
        guard.advance(false,depth==8?10:8,p);
        require(guard.gain(0,atBlack)==1,"endpoint protection crossed depth domains");
        auto shared=p;shared.chromaScalingFromLuma=1;
        guard.advance(false,depth,shared);
        require(guard.observeLuma(black,black,8,8)==-1,
            "shared luma curve suppressed unmeasured colour grain");
        guard.reset();
        require(guard.observeLuma(black,black,8,8)==-1,"uninitialized domain used");
    }
    for (unsigned component : {0u,3u})
        require(!fgsmodel::film_grain_chroma_uses_luma_lookup(p,component),"invalid component lookup accepted");
    p.chromaScalingFromLuma=1;
    require(!fgsmodel::film_grain_chroma_uses_luma_lookup(p,1),"shared luma curve given independent colour caps");
    std::cout<<"constant endpoint guards passed\n";
}
