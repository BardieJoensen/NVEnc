// Source/base joint moments for experimental colour-grain recovery.
// CPU-only; MIT license, as NVEncFilmGrainModel.h.
// Not connected to encoder decisions. A valid mathematical fit is not evidence
// that the input moments describe grain rather than picture detail.
#pragma once
#include <array>
#include <algorithm>
#include <cmath>
#include <cstdint>

namespace fgsmodel {
constexpr unsigned FGS_JOINT_VARIABLES = 26; // 24 chroma neighbours, avgY, current chroma
using FilmGrainJointMatrix = std::array<double, FGS_JOINT_VARIABLES * FGS_JOINT_VARIABLES>;
struct FilmGrainJointMoments {
    FilmGrainJointMatrix source{};
    FilmGrainJointMatrix base{};
    FilmGrainJointMatrix sourceBase{}; // Cov(source_i, base_j), generally NOT symmetric
    uint64_t observations = 0;
    uint64_t blocks = 0;
};
struct FilmGrainJointTarget {
    bool valid = false;
    FilmGrainJointMatrix covariance{};
};
struct FilmGrainJointChromaFit {
    bool valid = false;
    std::array<double, 24> spatial{};
    double rawLumaCoefficient = 0.0;
    double templateLumaCoefficient = 0.0;
    double innovationVariance = 0.0;
    double lumaInnovationVariance = 0.0;
};

namespace joint_model_detail {
// Positive semidefinite evidence may contain a zero base or an exactly shared
// source/base component. Reject inconsistent moments; do not silently ridge
// away a negative eigenvalue in the missing-noise covariance.
template<size_t N> inline bool semidefinite(const std::array<double, N*N>& input) {
    std::array<double,N*N> lower{};
    double scale = 0.0;
    for (size_t i=0;i<N;++i) {
        if (!std::isfinite(input[i*N+i]) || input[i*N+i]<0.0) return false;
        scale=std::max(scale,input[i*N+i]);
    }
    const double tolerance=std::max(1e-12,scale*1e-9);
    for (size_t i=0;i<N;++i) for (size_t j=0;j<=i;++j) {
        double value=input[i*N+j];
        if (!std::isfinite(value) || !std::isfinite(input[j*N+i])
            || std::abs(value-input[j*N+i])>tolerance) return false;
        for(size_t k=0;k<j;++k)value-=lower[i*N+k]*lower[j*N+k];
        if(i==j) {
            if(value < -tolerance)return false;
            lower[i*N+j]=std::sqrt(std::max(0.0,value));
        } else if(lower[j*N+j]>std::sqrt(tolerance)) {
            lower[i*N+j]=value/lower[j*N+j];
        } else if(std::abs(value)>tolerance) return false;
    }
    return true;
}
} // namespace joint_model_detail

// All inputs are sums of moments from the same source-selected, detrended
// observations. Retention can differ by component: current chroma and its
// neighbours use zero, while the averaged luma can retain a source fraction.
// The two mixed terms need their own orientation when these fractions differ.
// This identity describes a LINEAR blend before native-depth rounding. For
// a rounded retained base, measure that actual base and pass zero retention;
// applying the linear identity again would double-retain and miss quantization
// effects, which are material for weak colour grain.
inline FilmGrainJointTarget film_grain_joint_target(const FilmGrainJointMoments& moments,
    const std::array<double,FGS_JOINT_VARIABLES>& retain) {
    constexpr size_t N=FGS_JOINT_VARIABLES;
    FilmGrainJointTarget result;
    if(moments.blocks<16 || moments.blocks>10000000 || moments.observations<moments.blocks
        || moments.observations>1000000000) return result;
    for(const double r:retain)if(!std::isfinite(r)||r<0.0||r>1.0)return result;
    std::array<double,4*N*N> evidence{};
    for(size_t i=0;i<N;++i) for(size_t j=0;j<N;++j) {
        const double s=moments.source[i*N+j]/moments.observations;
        const double b=moments.base[i*N+j]/moments.observations;
        const double x=moments.sourceBase[i*N+j]/moments.observations;
        const double xt=moments.sourceBase[j*N+i]/moments.observations;
        if(!std::isfinite(s)||!std::isfinite(b)||!std::isfinite(x)||!std::isfinite(xt))return result;
        evidence[i*2*N+j]=s;
        evidence[(i+N)*2*N+j+N]=b;
        evidence[i*2*N+j+N]=x;
        evidence[(j+N)*2*N+i]=x;
        result.covariance[i*N+j]=(1.0-retain[i]*retain[j])*s
            -(1.0-retain[i])*(1.0-retain[j])*b
            -retain[i]*(1.0-retain[j])*x
            -(1.0-retain[i])*retain[j]*xt;
    }
    if(!joint_model_detail::semidefinite<2*N>(evidence)
        ||!joint_model_detail::semidefinite<N>(result.covariance))return result;
    result.valid=true;
    return result;
}

// Fit chroma's spatial AR coefficients and its luma driver jointly. The driver
// coefficient is converted to AV1 template units using the *averaged* luma
// transfer power and the chroma innovation variance. Quantization, stability,
// per-intensity support and decoded/source checks must still accept the model.
inline FilmGrainJointChromaFit film_grain_fit_joint_chroma(const FilmGrainJointTarget& target,
    const double averagedLumaTemplatePower) {
    constexpr size_t N=FGS_JOINT_VARIABLES, predictors=N-1;
    FilmGrainJointChromaFit result;
    if(!target.valid||!std::isfinite(averagedLumaTemplatePower)||averagedLumaTemplatePower<=0.0
        || !joint_model_detail::semidefinite<N>(target.covariance))return result;
    const auto& c=target.covariance;
    const double energy=c[(N-1)*N+N-1], luma=c[24*N+24];
    if(energy<=1e-12||luma<=1e-12)return result;
    std::array<double,predictors*predictors> lower{};
    std::array<double,predictors> forward{},coeff{};
    double scale=0.0;
    for(size_t i=0;i<predictors;++i)scale=std::max(scale,c[i*N+i]);
    for(size_t i=0;i<predictors;++i)for(size_t j=0;j<=i;++j) {
        double v=c[i*N+j];
        for(size_t k=0;k<j;++k)v-=lower[i*predictors+k]*lower[j*predictors+k];
        if(i==j) {
            if(!std::isfinite(v)||v<=scale*1e-9)return result;
            lower[i*predictors+j]=std::sqrt(v);
        } else lower[i*predictors+j]=v/lower[j*predictors+j];
    }
    for(size_t i=0;i<predictors;++i) {
        double v=c[i*N+N-1];
        for(size_t j=0;j<i;++j)v-=lower[i*predictors+j]*forward[j];
        forward[i]=v/lower[i*predictors+i];
    }
    for(int i=int(predictors)-1;i>=0;--i) {
        double v=forward[i];
        for(size_t j=i+1;j<predictors;++j)v-=lower[j*predictors+i]*coeff[j];
        coeff[i]=v/lower[i*predictors+i];
        if(!std::isfinite(coeff[i]))return result;
    }
    double innovation=energy;
    for(size_t i=0;i<predictors;++i)innovation-=coeff[i]*c[i*N+N-1];
    // An almost deterministic colour component cannot be represented as an
    // ordinary AV1 independent innovation with a bounded coupling coefficient.
    if(!std::isfinite(innovation)||innovation<=energy*1e-6)return result;
    std::copy_n(coeff.begin(),24,result.spatial.begin());
    result.rawLumaCoefficient=coeff[24];
    result.innovationVariance=innovation;
    result.lumaInnovationVariance=luma/averagedLumaTemplatePower;
    result.templateLumaCoefficient=coeff[24]*std::sqrt(result.lumaInnovationVariance/innovation);
    result.valid=std::isfinite(result.templateLumaCoefficient);
    return result;
}
} // namespace fgsmodel
