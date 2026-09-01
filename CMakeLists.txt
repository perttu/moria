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
#
# The --expect-* values are the ones Amiga Moria Graphics 1.1 carries. They
# are asserted here, during generation, rather than only in the test suite, so
# that a substituted or edited source is caught even in a build configured
# with BUILD_TESTING=OFF.
set(MORIA_GFX_CORR_EXPECTATIONS
    --expect-explicit 230
    --expect-extended 128
    --expect-seed 33 7
    --expect-fixup 13 20 6
    --expect-atlas 40 7)

add_custom_command(
    OUTPUT "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp"
    COMMAND "${Python3_EXECUTABLE}"
            "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_gfx_corr.py"
            "${MORIA_CORRLIST}"
            --hpp "${MORIA_GENERATED_DIR}/amiga_tiles_table.generated.hpp"
            ${MORIA_GFX_CORR_EXPECTATIONS}
    DEPENDS "${MORIA_CORRLIST}" "${CMAKE_CURRENT_SOURCE_DIR}/tools/gen_gfx_corr.py"
    COMMENT "Extracting GFX_CORR from amiga_corrlist.c"
    VERBATIM)

# The artwork, embedded as RGBA arrays so the binaries carry no loose files.
#
# --opaque because putgfx() in amiga.c copies all four bitplanes without
# consulting the mask: on the Amiga a tile's colour 0 is drawn as black, not
# as a hole. The converter still decodes the masking the files declare -- both
# atlases are mode 2 with transparentColor 0 -- it is the renderer that
# reproduces the original's indifference to it.
set(MORIA_ASSET_SOURCES "")
foreach(asset moria_gfx moria_gfxsmall moria_title)
    add_custom_command(
        OUTPUT "${MORIA_GENERATED_DIR}/${asset}.generated.cpp"
               "${MORIA_GENERATED_DIR}/${asset}.generated.hpp"
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/iff_convert.py"
                "${MORIA_ASSET_DIR}/${asset}.iff"
                --name "${asset}"
                --opaque
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

# On Linux, SDL treats a missing optional backend dependency as a hard
# configure error. Rather than making everyone install the full desktop -dev
# set before they can build at all, switch off what is genuinely absent and
# say so.
#
# Every probe re-runs on every configure, and anything switched off here is
# remembered in MORIA_AUTO_DISABLED_SDL so it can be handed back to SDL once
# its dependency appears. Without that, following the printed apt line and
# reconfiguring the same build directory would leave the cached OFF in place
# and quietly deny the full build it just promised. Options the user set
# themselves are never touched.
if(UNIX AND NOT APPLE AND NOT EMSCRIPTEN)
    find_package(PkgConfig QUIET)
    if(NOT PkgConfig_FOUND)
        message(STATUS
            "SDL: pkg-config was not found, so optional backends are detected "
            "by looking for their headers instead.")
    endif()

    # SDL option | pkg-config module | header | Debian/Ubuntu package
    set(_moria_optional_deps
        "SDL_X11_XCURSOR|xcursor|X11/Xcursor/Xcursor.h|libxcursor-dev"
        "SDL_X11_XFIXES|xfixes|X11/extensions/Xfixes.h|libxfixes-dev"
        "SDL_X11_XINPUT|xi|X11/extensions/XInput2.h|libxi-dev"
        "SDL_X11_XRANDR|xrandr|X11/extensions/Xrandr.h|libxrandr-dev"
        "SDL_X11_XSCRNSAVER|xscrnsaver|X11/extensions/scrnsaver.h|libxss-dev"
        "SDL_X11_XTEST|xtst|X11/extensions/XTest.h|libxtst-dev"
        "SDL_X11_XDBE|xext|X11/extensions/Xdbe.h|libxext-dev"
        "SDL_X11_XSHAPE|xext|X11/extensions/shape.h|libxext-dev"
        "SDL_X11_XSYNC|xext|X11/extensions/sync.h|libxext-dev"
        "SDL_WAYLAND|wayland-client|wayland-client.h|libwayland-dev")

    set(_moria_disabled_now "")
    set(_moria_missing_packages "")
    set(_moria_restored "")

    foreach(_dep IN LISTS _moria_optional_deps)
        string(REPLACE "|" ";" _parts "${_dep}")
        list(GET _parts 0 _option)
        list(GET _parts 1 _module)
        list(GET _parts 2 _header)
        list(GET _parts 3 _package)

        list(FIND MORIA_AUTO_DISABLED_SDL "${_option}" _managed)
        if(_managed EQUAL -1 AND DEFINED CACHE{${_option}})
            continue()  # the user chose this one; leave it alone
        endif()

        # Force a fresh probe: both of these cache their results.
        unset(_moria_probe_FOUND CACHE)
        unset(_moria_probe_FOUND)
        unset(_moria_probe_header CACHE)

        set(_moria_available FALSE)
        if(PkgConfig_FOUND)
            pkg_check_modules(_moria_probe QUIET "${_module}")
            if(_moria_probe_FOUND)
                set(_moria_available TRUE)
            endif()
        else()
            find_path(_moria_probe_header "${_header}")
            if(_moria_probe_header)
                set(_moria_available TRUE)
            endif()
        endif()

        if(_moria_available)
            if(NOT _managed EQUAL -1)
                # It was ours and its dependency is back: drop our cache entry
                # so SDL applies its own default again.
                unset(${_option} CACHE)
                list(APPEND _moria_restored "${_option}")
            endif()
        else()
            set(${_option} OFF CACHE BOOL "" FORCE)
            list(APPEND _moria_disabled_now "${_option}")
            list(APPEND _moria_missing_packages "${_package}")
        endif()
    endforeach()

    set(MORIA_AUTO_DISABLED_SDL "${_moria_disabled_now}" CACHE INTERNAL
        "SDL options this project switched off because their dependency was missing")

    if(_moria_restored)
        list(JOIN _moria_restored " " _moria_restored_text)
        message(STATUS "SDL: dependencies reappeared, re-enabling ${_moria_restored_text}")
    endif()
    if(_moria_missing_packages)
        list(REMOVE_DUPLICATES _moria_missing_packages)
        list(JOIN _moria_missing_packages " " _moria_missing_text)
        message(STATUS
            "SDL: building without some optional backends. For the full "
            "desktop build install: sudo apt install ${_moria_missing_text}")
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

# ---------------------------------------------------------------------------
# moria-amiga: Umoria driving the Amiga frontend
#
# Umoria is vendored untouched. Its terminal layer is the only file that talks
# to curses, and it is retargeted by three exact substitutions at build time
# (see tools/patch_ui_io.py) rather than forked, so all of its own logic --
# message combining, the "-more-" prompt, line editing -- stays upstream's.
# No gameplay source is modified. Henrik owns presentation, UMoria owns
# gameplay.
# ---------------------------------------------------------------------------
set(MORIA_UMORIA_DIR "${CMAKE_CURRENT_SOURCE_DIR}/vendored/umoria")

if(EXISTS "${MORIA_UMORIA_DIR}/src/ui_io.cpp")
    # Umoria's sources are copied into the build tree and three of them are
    # patched on the way through: ui_io.cpp to draw through the frontend,
    # dungeon.cpp to hand the reduced map over, and headers.h to admit that
    # Emscripten exists. The whole tree is copied rather than compiled in
    # place because a quoted #include always finds the file next to it -- a
    # patched headers.h has no effect unless its neighbours come along.
    # Everything not listed in the patcher is byte-identical to upstream.
    set(MORIA_UMORIA_COPY "${MORIA_GENERATED_DIR}/umoria")

    execute_process(
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/patch_umoria.py"
                --src "${MORIA_UMORIA_DIR}/src" --out "${MORIA_UMORIA_COPY}"
        RESULT_VARIABLE _moria_patch_result
        OUTPUT_VARIABLE _moria_patch_output)
    if(NOT _moria_patch_result EQUAL 0)
        message(FATAL_ERROR "could not prepare Umoria's sources: ${_moria_patch_output}")
    endif()
    string(STRIP "${_moria_patch_output}" _moria_patch_output)
    message(STATUS "Umoria: ${_moria_patch_output}")

    # Reconfigure when upstream changes, so the copies never go stale.
    file(GLOB _moria_umoria_inputs CONFIGURE_DEPENDS
         "${MORIA_UMORIA_DIR}/src/*.cpp" "${MORIA_UMORIA_DIR}/src/*.h")
    set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
                 ${_moria_umoria_inputs}
                 "${CMAKE_CURRENT_SOURCE_DIR}/tools/patch_umoria.py")

    file(GLOB MORIA_UMORIA_SOURCES "${MORIA_UMORIA_COPY}/*.cpp")

    # Everything but the entry point, so tests can link the game's state and
    # the colour policy without pulling in main().
    add_library(moria-engine STATIC
        ${MORIA_UMORIA_SOURCES}
        src/engine/amiga_colours.cpp
        src/engine/amiga_overview.cpp
        src/engine/amiga_web.cpp
        src/engine/amiga_curses.cpp
        src/engine/amiga_sprites.cpp
        "${MORIA_GENERATED_DIR}/amiga_codes.generated.hpp")

    target_include_directories(moria-engine PUBLIC
        "${MORIA_UMORIA_COPY}"
        src/engine)

    target_link_libraries(moria-engine PUBLIC moria-frontend)

    # Umoria's own warning suppressions; its 1980s string handling trips
    # modern GCC otherwise.
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
        target_compile_options(moria-engine PRIVATE
            -Wno-format-overflow -Wno-format-truncation)
    endif()

    add_executable(moria-amiga src/engine/main.cpp)
    target_link_libraries(moria-amiga PRIVATE moria-engine)

    if(EMSCRIPTEN)
        # Umoria reads keys from deep inside its call stack and a browser
        # cannot be kept waiting there. Asyncify unwinds and resumes that
        # stack around ui::delay(), so the engine keeps its structure and the
        # browser keeps its event loop.
        #
        # The data files are baked into the download, and the save directory
        # is IDBFS so a save survives closing the tab.
        set_target_properties(moria-amiga PROPERTIES SUFFIX ".html")
        target_link_options(moria-amiga PRIVATE
            -sASYNCIFY
            -sASYNCIFY_STACK_SIZE=131072
            -sALLOW_MEMORY_GROWTH=1
            -sSTACK_SIZE=1048576
            -sEXPORTED_RUNTIME_METHODS=ccall
            -sFORCE_FILESYSTEM=1
            -lidbfs.js
            "--preload-file=${MORIA_UMORIA_DIR}/data@/data"
            "--preload-file=${MORIA_UMORIA_DIR}/data/scores.dat@/scores.dat")
    endif()

    # Umoria looks for these relative to the working directory.
    file(COPY
        "${MORIA_UMORIA_DIR}/data/help.txt"
        "${MORIA_UMORIA_DIR}/data/help_wizard.txt"
        "${MORIA_UMORIA_DIR}/data/rl_help.txt"
        "${MORIA_UMORIA_DIR}/data/rl_help_wizard.txt"
        "${MORIA_UMORIA_DIR}/data/welcome.txt"
        "${MORIA_UMORIA_DIR}/data/death_tomb.txt"
        "${MORIA_UMORIA_DIR}/data/death_royal.txt"
        DESTINATION "${CMAKE_CURRENT_BINARY_DIR}/data")
    file(COPY "${MORIA_UMORIA_DIR}/data/scores.dat"
        DESTINATION "${CMAKE_CURRENT_BINARY_DIR}")
else()
    message(STATUS
        "vendored/umoria is empty; building the frontend only. "
        "Run: git submodule update --init --depth 1")
endif()

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

    # The keyboard mapping. A command character that cannot be typed is
    # invisible in every screenshot test.
    add_executable(key-test tests/key_test.cpp)
    target_link_libraries(key-test PRIVATE moria-frontend)
    add_test(NAME keys COMMAND key-test)

    # Pixels, not exit codes. This renders every deterministic screen and
    # compares it: the title against moria_title.iff itself, specific dungeon
    # cells against the atlas tile that belongs at that screen position, and
    # each whole screen against a reviewed golden hash.
    add_test(NAME pixel-screens
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/tests/compare_screens.py"
                     --binary "$<TARGET_FILE:amiga-gfx-test>"
                     --assets "${MORIA_ASSET_DIR}"
                     --workdir "${CMAKE_CURRENT_BINARY_DIR}/screens"
                     --golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_screens.json")

    # The goldens are deliberately not generated automatically: they are a
    # record of screens somebody looked at. Regenerate with
    #     cmake --build <dir> --target update-screen-goldens
    # and review the rendered BMPs in <dir>/screens before committing.
    add_custom_target(update-screen-goldens
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tests/compare_screens.py"
                --binary "$<TARGET_FILE:amiga-gfx-test>"
                --assets "${MORIA_ASSET_DIR}"
                --workdir "${CMAKE_CURRENT_BINARY_DIR}/screens"
                --golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_screens.json"
                --update
        DEPENDS amiga-gfx-test
        COMMENT "Rendering the deterministic screens and rewriting the goldens"
        VERBATIM)

    # Does it come up at all? Cheap, and it catches the failures the pixel
    # tests never see: a binary that will not start, an argument that is
    # silently accepted, a window that opens at the wrong size, or a build
    # that only works against the dummy video driver.
    add_test(NAME smoke-start
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/tests/build_and_start.py"
                     --binary "$<TARGET_FILE:amiga-gfx-test>"
                     --assets "${MORIA_ASSET_DIR}")

    # The same checks starting from cmake --fresh. Off by default because it
    # rebuilds SDL from scratch; turn it on in CI or before a release.
    option(MORIA_TEST_CLEAN_BUILD
           "Add a test that configures and builds the project from scratch" OFF)
    if(MORIA_TEST_CLEAN_BUILD)
        add_test(NAME build-from-clean
                 COMMAND "${Python3_EXECUTABLE}"
                         "${CMAKE_CURRENT_SOURCE_DIR}/tests/build_and_start.py"
                         --source "${CMAKE_CURRENT_SOURCE_DIR}"
                         --historical "${MORIA_HISTORICAL_DIR}"
                         --assets "${MORIA_ASSET_DIR}")
        set_tests_properties(build-from-clean PROPERTIES TIMEOUT 1800)
    endif()

    # Does the browser build actually run? Point this at an Emscripten build
    # directory and the test loads it in headless Chrome, compares the canvas
    # against moria_title.iff, and presses Space to prove input reaches the
    # game. It cannot be part of the native build, because the WebAssembly
    # output comes from a separate emcmake configure.
    set(MORIA_WEB_BUILD_DIR "" CACHE PATH
        "An Emscripten build directory, to add the browser smoke test")
    if(MORIA_WEB_BUILD_DIR)
        add_test(NAME web-smoke
                 COMMAND "${Python3_EXECUTABLE}"
                         "${CMAKE_CURRENT_SOURCE_DIR}/tests/web_smoke.py"
                         --build-web "${MORIA_WEB_BUILD_DIR}"
                         --assets "${MORIA_ASSET_DIR}"
                         --golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_screens.json"
                         --game-golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_game_screens.json")
        set_tests_properties(web-smoke PROPERTIES TIMEOUT 900)
    endif()

    # Umoria actually driving the frontend: the real game is run through
    # character creation into the town with a fixed seed, and the screen it
    # produces is checked -- including that every drawn cell of the viewport
    # is a tile from the atlas rather than a character from the font.
    if(TARGET moria-engine)
        # Henrik's colour scheme, against the values Amiga.doc and Update.doc
        # state. Most of these cannot be seen in a screenshot: an undamaged
        # character with no drained stats is correctly drawn all in white.
        add_executable(colour-test tests/colour_test.cpp)
        target_link_libraries(colour-test PRIVATE moria-engine)
        add_test(NAME colours COMMAND colour-test)

        # Henrik's extended display codes. Losing one is invisible in a
        # screenshot -- the game still draws something -- so they are checked
        # by name.
        add_executable(sprite-test tests/sprite_test.cpp)
        target_link_libraries(sprite-test PRIVATE moria-engine)
        add_test(NAME sprites COMMAND sprite-test)
    endif()

    if(TARGET moria-amiga)
        add_test(NAME game-screens
                 COMMAND "${Python3_EXECUTABLE}"
                         "${CMAKE_CURRENT_SOURCE_DIR}/tests/game_screens.py"
                         --binary "$<TARGET_FILE:moria-amiga>"
                         --assets "${MORIA_ASSET_DIR}"
                         --workdir "${CMAKE_CURRENT_BINARY_DIR}/game-screens"
                         --golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_game_screens.json")
        set_tests_properties(game-screens PROPERTIES TIMEOUT 300)

        add_custom_target(update-game-goldens
            COMMAND "${Python3_EXECUTABLE}"
                    "${CMAKE_CURRENT_SOURCE_DIR}/tests/game_screens.py"
                    --binary "$<TARGET_FILE:moria-amiga>"
                    --assets "${MORIA_ASSET_DIR}"
                    --workdir "${CMAKE_CURRENT_BINARY_DIR}/game-screens"
                    --golden "${CMAKE_CURRENT_SOURCE_DIR}/tests/golden_game_screens.json"
                    --update
            DEPENDS moria-amiga
            COMMENT "Rendering the real game's screens and rewriting the goldens"
            VERBATIM)
    endif()

    add_test(NAME tool-iff-convert
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_iff_convert.py")
    add_test(NAME tool-gen-font
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_gen_font.py")
    add_test(NAME tool-gen-gfx-corr
             COMMAND "${Python3_EXECUTABLE}"
                     "${CMAKE_CURRENT_SOURCE_DIR}/tests/test_gen_gfx_corr.py"
                     --corrlist "${MORIA_CORRLIST}")
endif()
