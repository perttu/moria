// Shared declaration for the artwork converted out of the original IFF files
// by tools/iff_convert.py. The generated headers include this one so that
// several of them can be pulled into the same translation unit.
#pragma once

namespace moria::assets {

struct Image {
    int width;
    int height;
    const unsigned char *rgba;  // width * height * 4, byte order R,G,B,A
};

}  // namespace moria::assets
