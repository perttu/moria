cmake_minimum_required(VERSION 3.16)
project(moria-amiga LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "" FORCE)
endif()

# ---------------------------------------------------------------------------
# Historical inputs
#
# Henrik Harmsen's source and the original artwork are not committed to this
# repository. Point these at your own copies; everything derived from them is
# generated into the build directory and never checked in.
# ---------------------------------------------------------------------------
set(MORIA_HISTORICAL_DIR "${CMAKE_CURRENT_SOURCE_DIR}/historical-amiga"
    CACHE PATH "Directory containing amiga_corrlist.c from Amiga Moria Graphics 1.1")
set(MORIA_ASSET_DIR "${CMAKE_CURRENT_SOURCE_DIR}/historical-assets"
    CACHE PATH "Directory containing moria_gfx.iff, moria_gfxsmall.iff, moria_title.iff")

find_package(Python3 REQUIRED COMPONENTS Interpreter)

set(MORIA_CORRLIST "${MORIA_HISTORICAL_DIR}/amiga_corrlist.c")
if(NOT EXISTS "${MORIA_CORRLIST}")
    message(FATAL_ERROR
        "amiga_corrlist.c not found at ${MORIA_CORRLIST}.\n"
        "Set -DMORIA_HISTORICAL_DIR=/path/to/the/1.1/source tree.")
endif()

foreach(asset moria_gfx moria_gfxsmall moria_title)
    if(NOT EXISTS "${MORIA_ASSET_DIR}/${asset}.iff")
        message(FATAL_ERROR
            "${asset}.iff not found in ${MORIA_ASSET_DIR}.\n"
            "Set -DMORIA_ASSET_DIR=/path/to/the/1.2/Moria directory.")
    endif()
endforeach()

set(MORIA_GENERATED_DIR "${CMAKE_CURRENT_BINARY_DIR}/generated")
file(MAKE_DIRECTORY "${MORIA_GENERATED_DIR}")

# GFX_CORR, transcribed mechanically from the original C rather than by hand.
add_custom_command(
    OUTPUT "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp"
    COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_gfx_corr.py"
            "${MORIA_CORRLIST}"
            --hpp "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp"
    DEPENDS "${MORIA_CORRLIST}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_gfx_corr.py"
    COMMENT "Extracting GFX_CORR from amiga_corrlist.c"
    VERBATIM)

# The artwork, embedded as RGBA arrays so the binaries carry no loose files.
set(MORIA_ASSET_SOURCES "")
foreach(asset moria_gfx moria_gfxsmall moria_title)
    add_custom_command(
        OUTPUT "${MORIA_GENERATED_DIR}/${asset}.generated.cpp"
               "${MORIA_GENERATED_DIR}/${asset}.generated.hpp"
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/iff_convert.py"
                "${MORIA_ASSET_DIR}/${asset}.iff"
                --name "${asset}"
                --cpp "${MORIA_GENERATED_DIR}/${asset}.generated.cpp"
                --hpp "${MORIA_GENERATED_DIR}/${asset}.generated.hpp"
        DEPENDS "${MORIA_ASSET_DIR}/${asset}.iff"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/iff_convert.py"
        COMMENT "Converting ${asset}.iff"
        VERBATIM)
    list(APPEND MORIA_ASSET_SOURCES "${MORIA_GENERATED_DIR}/${asset}.generated.cpp")
endforeach()

# ---------------------------------------------------------------------------
# SDL3, vendored so that a build needs no Homebrew, no apt and no system SDL
# ---------------------------------------------------------------------------
if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/vendored/SDL/CMakeLists.txt")
    message(FATAL_ERROR
        "vendored/SDL is empty. Run: git submodule update --init --depth 1")
endif()

set(SDL_SHARED OFF CACHE BOOL "" FORCE)
set(SDL_STATIC ON CACHE BOOL "" FORCE)
set(SDL_TEST_LIBRARY OFF CACHE BOOL "" FORCE)
set(SDL_EXAMPLES OFF CACHE BOOL "" FORCE)
set(SDL_INSTALL OFF CACHE BOOL "" FORCE)

# On Linux, SDL treats a missing optional X11 extension as a hard configure
# error. Rather than making everyone install the full desktop -dev set before
# they can build at all, switch off what is genuinely absent and say so. A
# machine with the packages installed still gets the full-featured build.
if(UNIX AND NOT APPLE AND NOT EMSCRIPTEN)
    find_package(PkgConfig QUIET)
    set(MORIA_MISSING_X11 "")
    if(PkgConfig_FOUND)
        # SDL option <-> pkg-config module <-> Debian/Ubuntu package
        set(_moria_x11_deps
            "SDL_X11_XCURSOR:xcursor:libxcursor-dev"
            "SDL_X11_XFIXES:xfixes:libxfixes-dev"
            "SDL_X11_XINPUT:xi:libxi-dev"
            "SDL_X11_XRANDR:xrandr:libxrandr-dev"
            "SDL_X11_XSCRNSAVER:xscrnsaver:libxss-dev"
            "SDL_X11_XTEST:xtst:libxtst-dev"
            "SDL_X11_XDBE:xext:libxext-dev"
            "SDL_X11_XSHAPE:xext:libxext-dev"
            "SDL_X11_XSYNC:xext:libxext-dev")
        foreach(_dep IN LISTS _moria_x11_deps)
            string(REPLACE ":" ";" _parts "${_dep}")
            list(GET _parts 0 _option)
            list(GET _parts 1 _module)
            list(GET _parts 2 _package)
            pkg_check_modules(_moria_probe QUIET "${_module}")
            if(NOT _moria_probe_FOUND)
                set(${_option} OFF CACHE BOOL "" FORCE)
                list(APPEND MORIA_MISSING_X11 "${_package}")
            endif()
        endforeach()

        pkg_check_modules(_moria_wayland QUIET wayland-client)
        if(NOT _moria_wayland_FOUND)
            set(SDL_WAYLAND OFF CACHE BOOL "" FORCE)
        endif()
    endif()

    if(MORIA_MISSING_X11)
        list(JOIN MORIA_MISSING_X11 " " _moria_missing_text)
        message(STATUS
            "SDL: building without some X11 extensions. For the full desktop "
            "build install: sudo apt install ${_moria_missing_text}")
    endif()
endif()

add_subdirectory(vendored/SDL EXCLUDE_FROM_ALL)

if(TARGET SDL3::SDL3-static)
    set(MORIA_SDL_TARGET SDL3::SDL3-static)
else()
    set(MORIA_SDL_TARGET SDL3::SDL3)
endif()

# ---------------------------------------------------------------------------
# The frontend
# ---------------------------------------------------------------------------
add_library(moria-frontend STATIC
    src/frontend/amiga_frontend.cpp
    src/frontend/amiga_tiles.cpp
    "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp"
    ${MORIA_ASSET_SOURCES})

target_include_directories(moria-frontend PUBLIC
    src/frontend
    "${MORIA_GENERATED_DIR}")

target_link_libraries(moria-frontend PUBLIC ${MORIA_SDL_TARGET})

# The tile table has no SDL in it, so tests can link it on its own.
add_library(moria-tiles STATIC
    src/frontend/amiga_tiles.cpp
    "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp")
target_include_directories(moria-tiles PUBLIC
    src/frontend
    "${MORIA_GENERATED_DIR}")

# ---------------------------------------------------------------------------
# amiga-gfx-test: the frontend with no engine behind it
# ---------------------------------------------------------------------------
add_executable(amiga-gfx-test src/tools/gfx_test_main.cpp)
target_link_libraries(amiga-gfx-test PRIVATE moria-frontend)

if(EMSCRIPTEN)
    set(CMAKE_EXECUTABLE_SUFFIX ".html")
    set_target_properties(amiga-gfx-test PROPERTIES SUFFIX ".html")
    target_link_options(amiga-gfx-test PRIVATE
        -sALLOW_MEMORY_GROWTH=1
        -sSTACK_SIZE=1048576)
endif()

if(APPLE)
    set_target_properties(amiga-gfx-test PROPERTIES
        XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC YES)
endif()

# ---------------------------------------------------------------------------
# Tests
#
# For a preservation port the useful tests are "does this still look like the
# Amiga", not conventional unit tests. Two kinds live here: the GFX_CORR table
# assertions, and 640x200 screenshots of deterministic screens.
# ---------------------------------------------------------------------------
include(CTest)
if(BUILD_TESTING)
    add_executable(gfx-corr-test tests/gfx_corr_test.cpp)
    target_link_libraries(gfx-corr-test PRIVATE moria-tiles)
    add_test(NAME gfx-corr COMMAND gfx-corr-test)

    add_test(NAME screenshot-title
             COMMAND amiga-gfx-test --headless --screen title
                     --screenshot "${CMAKE_CURRENT_BINARY_DIR}/shot-title.bmp")
    add_test(NAME screenshot-tiles
             COMMAND amiga-gfx-test --headless --screen tiles
                     --screenshot "${CMAKE_CURRENT_BINARY_DIR}/shot-tiles.bmp")
    add_test(NAME screenshot-dungeon
             COMMAND amiga-gfx-test --headless --screen dungeon
                     --screenshot "${CMAKE_CURRENT_BINARY_DIR}/shot-dungeon.bmp")
    add_test(NAME screenshot-overview
             COMMAND amiga-gfx-test --headless --screen overview
                     --screenshot "${CMAKE_CURRENT_BINARY_DIR}/shot-overview.bmp")
endif()
