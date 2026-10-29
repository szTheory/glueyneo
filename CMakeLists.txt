cmake_minimum_required(VERSION 3.20)

# release-please owns the only project version. Keep this parsing before
# project() so CMake's installed package version uses the manifest value.
set(GLUEYNEO_RELEASE_MANIFEST "${CMAKE_CURRENT_LIST_DIR}/.release-please-manifest.json")
if(NOT EXISTS "${GLUEYNEO_RELEASE_MANIFEST}")
  message(FATAL_ERROR "release-please manifest is missing: ${GLUEYNEO_RELEASE_MANIFEST}")
endif()
file(READ "${GLUEYNEO_RELEASE_MANIFEST}" GLUEYNEO_RELEASE_MANIFEST_JSON)
string(JSON GLUEYNEO_RELEASE_MANIFEST_LENGTH ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       LENGTH "${GLUEYNEO_RELEASE_MANIFEST_JSON}")
if(GLUEYNEO_RELEASE_JSON_ERROR OR NOT GLUEYNEO_RELEASE_MANIFEST_LENGTH EQUAL 1)
  message(FATAL_ERROR "release-please manifest must be a valid object containing only the root package")
endif()
string(JSON GLUEYNEO_RELEASE_MANIFEST_PACKAGE ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       MEMBER "${GLUEYNEO_RELEASE_MANIFEST_JSON}" 0)
if(GLUEYNEO_RELEASE_JSON_ERROR OR NOT GLUEYNEO_RELEASE_MANIFEST_PACKAGE STREQUAL ".")
  message(FATAL_ERROR "release-please manifest must define exactly the root package key '.'")
endif()
string(JSON GLUEYNEO_PROJECT_VERSION ERROR_VARIABLE GLUEYNEO_RELEASE_JSON_ERROR
       GET "${GLUEYNEO_RELEASE_MANIFEST_JSON}" ".")
if(GLUEYNEO_RELEASE_JSON_ERROR OR
   NOT GLUEYNEO_PROJECT_VERSION MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+(-[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?(\\+[0-9A-Za-z]+([.-][0-9A-Za-z]+)*)?$")
  message(FATAL_ERROR "release-please manifest root version must be valid semantic version text")
endif()

project(Glueyneo VERSION "${GLUEYNEO_PROJECT_VERSION}" LANGUAGES C)
include(CTest)
include(GNUInstallDirs)
include(CMakePackageConfigHelpers)

# ZIP handling is isolated to the standalone importer. These exact upstream
# zlib 1.3.2 inflater/CRC sources are pinned at da607da739fa6047df13e66a2af6b8bec7c2a498.
add_library(glueyneo_mvs_zlib STATIC
  third_party/zlib/adler32.c
  third_party/zlib/crc32.c
  third_party/zlib/inflate.c
  third_party/zlib/inffast.c
  third_party/zlib/inftrees.c
  third_party/zlib/zutil.c
)
target_include_directories(glueyneo_mvs_zlib PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/zlib)
target_compile_features(glueyneo_mvs_zlib PRIVATE c_std_17)
set_target_properties(glueyneo_mvs_zlib PROPERTIES C_STANDARD 17
  C_STANDARD_REQUIRED YES C_EXTENSIONS NO POSITION_INDEPENDENT_CODE ON)

option(GLUEYNEO_BUILD_TESTS "Build SDK tests and the headless diagnostic" ${BUILD_TESTING})
option(GLUEYNEO_YM2610_ADMISSION "Build the separate private ymfm YM2610 admission tests" ${GLUEYNEO_BUILD_TESTS})
option(GLUEYNEO_MVS_INPUT_OBSERVATIONS "Enable bounded local libretro input/video observations" OFF)
option(GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
  "Build a separate Libretro core with bounded continuation observations" OFF)
option(GLUEYNEO_CPU_EXPERIMENT "Build the private CPU acceptance experiment" OFF)
option(GLUEYNEO_OWNED_CPU_EXPERIMENT "Build the private owned MC68000 experiment" OFF)
option(GLUEYNEO_PRE_SHIP_HISTORY_CHECK "Register the pre-ship history allowlist CTest (needs full branch history)" OFF)
set(GLUEYNEO_HISTORY_BASE "origin/main" CACHE STRING
    "Base ref for the pre-ship history allowlist CTest (the pull request base; fetch it first)")
set(GLUEYNEO_SDK_SANITIZER "NONE" CACHE STRING
    "SDK-only instrumentation: NONE, ADDRESS_UNDEFINED, or THREAD")
set_property(CACHE GLUEYNEO_SDK_SANITIZER PROPERTY STRINGS
             NONE ADDRESS_UNDEFINED THREAD)
if(NOT GLUEYNEO_SDK_SANITIZER MATCHES "^(NONE|ADDRESS_UNDEFINED|THREAD)$")
  message(FATAL_ERROR "Unknown SDK sanitizer mode: ${GLUEYNEO_SDK_SANITIZER}")
endif()

# The admitted YM2610 is part of the MVS runtime even without admission tests.
enable_language(CXX)

set(GLUEYNEO_SDK_SANITIZER_FLAGS "")
set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS "")
set(GLUEYNEO_SDK_SANITIZER_RUNTIME_LINK_FLAG "")
if(GLUEYNEO_SDK_SANITIZER STREQUAL "ADDRESS_UNDEFINED")
  include(CheckCCompilerFlag)
  include(CheckCXXCompilerFlag)
  include(CheckLinkerFlag)
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=address,undefined")
  check_c_compiler_flag("-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_COMPILE)
  check_linker_flag(C "-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_LINK)
  check_cxx_compiler_flag("-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_CXX_COMPILE)
  check_linker_flag(CXX "-fsanitize=address,undefined"
    GLUEYNEO_SDK_HAS_ASAN_UBSAN_CXX_LINK)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  if(NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_COMPILE OR
     NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_LINK OR
     NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_CXX_COMPILE OR
     NOT GLUEYNEO_SDK_HAS_ASAN_UBSAN_CXX_LINK)
    message(FATAL_ERROR
      "SDK_SANITIZER_UNSUPPORTED: selected C or C++ compiler/linker lacks ASan+UBSan")
  endif()
  set(GLUEYNEO_SDK_SANITIZER_FLAGS
      -fsanitize=address,undefined -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS
      -fsanitize=address,undefined -fno-omit-frame-pointer
      -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_RUNTIME_LINK_FLAG "-fsanitize=address,undefined")
elseif(GLUEYNEO_SDK_SANITIZER STREQUAL "THREAD")
  include(CheckCCompilerFlag)
  include(CheckCXXCompilerFlag)
  include(CheckLinkerFlag)
  set(CMAKE_REQUIRED_LINK_OPTIONS "-fsanitize=thread")
  check_c_compiler_flag("-fsanitize=thread"
    GLUEYNEO_SDK_HAS_TSAN_COMPILE)
  check_linker_flag(C "-fsanitize=thread" GLUEYNEO_SDK_HAS_TSAN_LINK)
  check_cxx_compiler_flag("-fsanitize=thread"
    GLUEYNEO_SDK_HAS_TSAN_CXX_COMPILE)
  check_linker_flag(CXX "-fsanitize=thread" GLUEYNEO_SDK_HAS_TSAN_CXX_LINK)
  unset(CMAKE_REQUIRED_LINK_OPTIONS)
  if(NOT GLUEYNEO_SDK_HAS_TSAN_COMPILE OR NOT GLUEYNEO_SDK_HAS_TSAN_LINK OR
     NOT GLUEYNEO_SDK_HAS_TSAN_CXX_COMPILE OR NOT GLUEYNEO_SDK_HAS_TSAN_CXX_LINK)
    message(FATAL_ERROR
      "SDK_SANITIZER_UNSUPPORTED: selected C or C++ compiler/linker lacks TSan")
  endif()
  set(GLUEYNEO_SDK_SANITIZER_FLAGS
      -fsanitize=thread -fno-omit-frame-pointer -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_LINK_FLAGS
      -fsanitize=thread -fno-omit-frame-pointer -fno-sanitize-recover=all)
  set(GLUEYNEO_SDK_SANITIZER_RUNTIME_LINK_FLAG "-fsanitize=thread")
endif()

function(glueyneo_apply_sdk_sanitizer target)
  if(GLUEYNEO_SDK_SANITIZER_FLAGS)
    target_compile_options(${target} PRIVATE ${GLUEYNEO_SDK_SANITIZER_FLAGS})
    get_target_property(target_type ${target} TYPE)
    if(target_type STREQUAL "STATIC_LIBRARY")
      target_link_options(${target} INTERFACE ${GLUEYNEO_SDK_SANITIZER_RUNTIME_LINK_FLAG})
    else()
      target_link_options(${target} PRIVATE ${GLUEYNEO_SDK_SANITIZER_LINK_FLAGS})
    endif()
  endif()
endfunction()

glueyneo_apply_sdk_sanitizer(glueyneo_mvs_zlib)
if(NOT GLUEYNEO_SDK_SANITIZER STREQUAL "NONE")
  set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
endif()

if(GLUEYNEO_CPU_EXPERIMENT AND GLUEYNEO_OWNED_CPU_EXPERIMENT)
  message(FATAL_ERROR "Select one whole CPU backend experiment per build directory")
endif()

set(GLUEYNEO_RUNTIME_SOURCES
  src/instance.c
  src/mvs/mvs_bus.c
  src/mvs/mvs_protocol.c
  src/chips/z80_candidate.c
  experiments/owned_cpu/cpu.c
  src/chips/ym2610_candidate.cpp
  third_party/ymfm/src/ymfm_opn.cpp
  third_party/ymfm/src/ymfm_adpcm.cpp
  third_party/ymfm/src/ymfm_ssg.cpp
)

function(glueyneo_configure_runtime_ym target)
  target_compile_features(${target} PRIVATE cxx_std_14)
  set_target_properties(${target} PROPERTIES CXX_STANDARD 14
    CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO
    CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
  target_include_directories(${target} SYSTEM PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/ymfm/src)
  target_compile_definitions(${target} PRIVATE GLUEYNEO_YM2610_CANDIDATE_INTERNAL)
  if(GLUEYNEO_SDK_SANITIZER STREQUAL "THREAD" AND NOT MSVC)
    # The real per-tick chip workload exceeded the unchanged TSan time bound
    # at -O0. Clang's TSan usage recommends -O1 or higher; retain full
    # instrumentation and debug info, optimizing only this C++ dependency.
    target_compile_options(${target} PRIVATE "$<$<COMPILE_LANGUAGE:CXX>:-O1>")
  endif()
  # C-only installed consumers cannot infer the private C++ runtime from their
  # enabled languages. Keep its link requirement on static archives only.
  get_target_property(_runtime_type ${target} TYPE)
  if(_runtime_type STREQUAL "STATIC_LIBRARY")
    if("stdc++" IN_LIST CMAKE_CXX_IMPLICIT_LINK_LIBRARIES)
      # Includes GNU/Clang MinGW: WIN32 is true there, UNIX is false.
      target_link_libraries(${target} INTERFACE "$<$<LINK_LANGUAGE:C>:stdc++>")
    elseif("c++" IN_LIST CMAKE_CXX_IMPLICIT_LINK_LIBRARIES OR APPLE)
      target_link_libraries(${target} INTERFACE "$<$<LINK_LANGUAGE:C>:c++>")
    elseif(UNIX)
      target_link_libraries(${target} INTERFACE "$<$<LINK_LANGUAGE:C>:stdc++>")
    endif()
  endif()
endfunction()

add_library(glueyneo ${GLUEYNEO_RUNTIME_SOURCES})
add_library(Glueyneo::glueyneo ALIAS glueyneo)
target_compile_features(glueyneo PRIVATE c_std_17)
set_target_properties(glueyneo PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  POSITION_INDEPENDENT_CODE ON
  C_VISIBILITY_PRESET hidden
)
target_include_directories(glueyneo
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
)
target_include_directories(glueyneo SYSTEM PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
)
if(BUILD_SHARED_LIBS)
  target_compile_definitions(glueyneo
    PUBLIC GLUEYNEO_SHARED
    PRIVATE GLUEYNEO_BUILDING
  )
endif()
if(MSVC)
  target_compile_options(glueyneo PRIVATE /W4 "$<$<COMPILE_LANGUAGE:C>:/WX>")
else()
  target_compile_options(glueyneo PRIVATE -Wall -Wextra -Wpedantic "$<$<COMPILE_LANGUAGE:C>:-Werror>")
endif()
glueyneo_configure_runtime_ym(glueyneo)
glueyneo_apply_sdk_sanitizer(glueyneo)

# A static copy of the production runtime (no test hooks) for binaries that
# must not depend on a shared libglueyneo: the Libretro core, which frontends
# load from their own cores directory without our rpath, and tools that call
# private symbols the shared library hides. Static builds reuse glueyneo.
if(BUILD_SHARED_LIBS)
  add_library(glueyneo_runtime_static STATIC ${GLUEYNEO_RUNTIME_SOURCES})
  target_compile_features(glueyneo_runtime_static PRIVATE c_std_17)
  set_target_properties(glueyneo_runtime_static PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    POSITION_INDEPENDENT_CODE ON
    C_VISIBILITY_PRESET hidden
  )
  target_include_directories(glueyneo_runtime_static
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
  )
  target_include_directories(glueyneo_runtime_static SYSTEM PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
  )
  if(MSVC)
    target_compile_options(glueyneo_runtime_static PRIVATE /W4 "$<$<COMPILE_LANGUAGE:C>:/WX>")
  else()
    target_compile_options(glueyneo_runtime_static PRIVATE
      -Wall -Wextra -Wpedantic "$<$<COMPILE_LANGUAGE:C>:-Werror>")
  endif()
  glueyneo_configure_runtime_ym(glueyneo_runtime_static)
  glueyneo_apply_sdk_sanitizer(glueyneo_runtime_static)
else()
  add_library(glueyneo_runtime_static ALIAS glueyneo)
endif()

# The frontend adapter owns the Libretro ABI boundary; machine behavior and
# deterministic frame buffers remain in the native C library, linked
# statically so the installed core is a single self-contained module.
add_library(glueyneo_libretro SHARED src/libretro/libretro_core.c)
target_compile_features(glueyneo_libretro PRIVATE c_std_17)
target_compile_definitions(glueyneo_libretro PRIVATE
  $<$<BOOL:${GLUEYNEO_MVS_INPUT_OBSERVATIONS}>:GLUEYNEO_MVS_INPUT_OBSERVATIONS>)
set_target_properties(glueyneo_libretro PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
  C_VISIBILITY_PRESET hidden
  OUTPUT_NAME glueyneo_libretro
  PREFIX ""
)
target_include_directories(glueyneo_libretro PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/libretro
)
target_link_libraries(glueyneo_libretro PRIVATE glueyneo_runtime_static)
install(TARGETS glueyneo_libretro
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}/libretro"
  RUNTIME DESTINATION "${CMAKE_INSTALL_LIBDIR}/libretro"
)
if(MSVC)
  target_compile_options(glueyneo_libretro PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo_libretro PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
glueyneo_apply_sdk_sanitizer(glueyneo_libretro)

# A private opt-in core exposes bounded save/load continuation observations for
# the pinned frontend smoke. The installed production core above stays clean.
if(GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS)
  add_library(glueyneo_libretro_observed SHARED src/libretro/libretro_core.c)
  target_compile_features(glueyneo_libretro_observed PRIVATE c_std_17)
  target_compile_definitions(glueyneo_libretro_observed PRIVATE
    GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
    GLUEYNEO_MVS_INPUT_OBSERVATIONS)
  set_target_properties(glueyneo_libretro_observed PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    C_VISIBILITY_PRESET hidden
    OUTPUT_NAME glueyneo_libretro_observed
    PREFIX ""
  )
  target_include_directories(glueyneo_libretro_observed PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/libretro
  )
  target_link_libraries(glueyneo_libretro_observed PRIVATE glueyneo_runtime_static)
  if(MSVC)
    target_compile_options(glueyneo_libretro_observed PRIVATE /W4 /WX)
  else()
    target_compile_options(glueyneo_libretro_observed PRIVATE
      -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(glueyneo_libretro_observed)
endif()

# Source identity belongs to the checkout, independently of the C compiler.
# An offline source archive without Git retains the explicit unknown identity.
execute_process(
  COMMAND git rev-parse --short=12 HEAD
  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
  RESULT_VARIABLE GLUEYNEO_SOURCE_REVISION_RESULT
  OUTPUT_VARIABLE GLUEYNEO_SOURCE_REVISION
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET
)
if(NOT GLUEYNEO_SOURCE_REVISION_RESULT EQUAL 0 OR NOT GLUEYNEO_SOURCE_REVISION)
  set(GLUEYNEO_SOURCE_REVISION "unknown")
endif()

add_executable(glueyneo-diagnostic tools/diagnostic/main.c tests/sdk/guest_fixture.c)
target_include_directories(glueyneo-diagnostic PRIVATE tests/sdk)
target_compile_features(glueyneo-diagnostic PRIVATE c_std_17)
set_target_properties(glueyneo-diagnostic PROPERTIES
  C_STANDARD 17
  C_STANDARD_REQUIRED YES
  C_EXTENSIONS NO
)
target_link_libraries(glueyneo-diagnostic PRIVATE Glueyneo::glueyneo)
target_compile_definitions(glueyneo-diagnostic PRIVATE
  GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
  GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
  GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
  GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
)
if(MSVC)
  target_compile_options(glueyneo-diagnostic PRIVATE /W4 /WX)
else()
  target_compile_options(glueyneo-diagnostic PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
glueyneo_apply_sdk_sanitizer(glueyneo-diagnostic)

if(APPLE)
  set_target_properties(glueyneo-diagnostic PROPERTIES
    INSTALL_RPATH "@loader_path/../${CMAKE_INSTALL_LIBDIR}"
  )
elseif(UNIX)
  set_target_properties(glueyneo-diagnostic PROPERTIES
    INSTALL_RPATH "$ORIGIN/../${CMAKE_INSTALL_LIBDIR}"
  )
endif()

set(GLUEYNEO_DIAGNOSTIC_FIXTURE
  "${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin")
add_custom_command(
  OUTPUT "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  COMMAND $<TARGET_FILE:glueyneo-diagnostic> --write-fixture
          "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DEPENDS glueyneo-diagnostic
  VERBATIM
)
add_custom_target(glueyneo-original-fixture ALL
  DEPENDS "${GLUEYNEO_DIAGNOSTIC_FIXTURE}")

install(TARGETS glueyneo
  EXPORT GlueyneoTargets
  ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
  INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(TARGETS glueyneo-diagnostic
  RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
)
if(GLUEYNEO_YM2610_ADMISSION)
  add_library(glueyneo_ym2610_candidate
    src/chips/ym2610_candidate.cpp
    third_party/ymfm/src/ymfm_opn.cpp
    third_party/ymfm/src/ymfm_adpcm.cpp
    third_party/ymfm/src/ymfm_ssg.cpp
  )
  add_library(Glueyneo::ym2610_candidate ALIAS glueyneo_ym2610_candidate)
  target_compile_features(glueyneo_ym2610_candidate PUBLIC c_std_17 PRIVATE cxx_std_14)
  set_target_properties(glueyneo_ym2610_candidate PROPERTIES
    EXPORT_NAME ym2610_candidate
    CXX_STANDARD 14
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES
    POSITION_INDEPENDENT_CODE ON
  )
  target_include_directories(glueyneo_ym2610_candidate
    PUBLIC
      $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/src/chips>
      $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}/glueyneo/private>
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/third_party/ymfm/src
  )
  target_compile_definitions(glueyneo_ym2610_candidate
    PUBLIC GLUEYNEO_YM2610_TEST_HOOKS
    PRIVATE GLUEYNEO_YM2610_CANDIDATE_BUILD
  )
  if(BUILD_SHARED_LIBS AND WIN32)
    target_compile_definitions(glueyneo_ym2610_candidate
      INTERFACE GLUEYNEO_YM2610_CANDIDATE_SHARED
    )
  endif()
  if(APPLE)
    target_link_libraries(glueyneo_ym2610_candidate INTERFACE
      "$<$<LINK_LANGUAGE:C>:c++>"
    )
  elseif(UNIX)
    target_link_libraries(glueyneo_ym2610_candidate INTERFACE
      "$<$<LINK_LANGUAGE:C>:stdc++>"
    )
  endif()
  if(MSVC)
    target_compile_options(glueyneo_ym2610_candidate PRIVATE /W4)
  else()
    target_compile_options(glueyneo_ym2610_candidate PRIVATE -Wall -Wextra -Wpedantic)
  endif()
  install(TARGETS glueyneo_ym2610_candidate
    EXPORT GlueyneoTargets
    ARCHIVE DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    LIBRARY DESTINATION "${CMAKE_INSTALL_LIBDIR}"
    RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}"
    INCLUDES DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
  )
  install(FILES src/chips/ym2610_candidate.h
    DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}/glueyneo/private"
  )
endif()
install(DIRECTORY include/glueyneo
  DESTINATION "${CMAKE_INSTALL_INCLUDEDIR}"
)
install(FILES LICENSE DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo")
install(FILES third_party/ymfm/LICENSE third_party/ymfm/NOTICE.md
  DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo/ymfm")
install(FILES third_party/libretro/libretro.h third_party/libretro/NOTICE.md
  DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo/libretro")
install(FILES third_party/chips/NOTICE.md
  DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo/chips")
install(FILES third_party/zlib/LICENSE
  DESTINATION "${CMAKE_INSTALL_DATADIR}/licenses/Glueyneo/zlib")
install(FILES "${GLUEYNEO_DIAGNOSTIC_FIXTURE}"
  DESTINATION "${CMAKE_INSTALL_DATADIR}/glueyneo")

set(GLUEYNEO_CMAKE_INSTALL_DIR "${CMAKE_INSTALL_LIBDIR}/cmake/Glueyneo")
configure_package_config_file(
  cmake/GlueyneoConfig.cmake.in
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfig.cmake"
  INSTALL_DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)
write_basic_package_version_file(
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfigVersion.cmake"
  VERSION "${PROJECT_VERSION}"
  COMPATIBILITY SameMajorVersion
)
install(EXPORT GlueyneoTargets
  FILE GlueyneoTargets.cmake
  NAMESPACE Glueyneo::
  DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)
install(FILES
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfig.cmake"
  "${CMAKE_CURRENT_BINARY_DIR}/GlueyneoConfigVersion.cmake"
  DESTINATION "${GLUEYNEO_CMAKE_INSTALL_DIR}"
)

if(GLUEYNEO_BUILD_TESTS)
  enable_testing()
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  # Bind the process exchange runner to the exact source and dependency bytes
  # present when this SDK configuration is generated. The Python supervisor
  # recomputes this value before accepting any child result.
  set(_glueyneo_state_identity_roots
    src
    include/glueyneo
    tests/sdk
    tests/fixture
    third_party/chips
    third_party/ymfm/src
  )
  set(_glueyneo_state_identity_files)
  foreach(_root IN LISTS _glueyneo_state_identity_roots)
    file(GLOB_RECURSE _root_files
      LIST_DIRECTORIES false
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.c"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.h"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.cpp"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.hpp"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.py"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.json"
      "${CMAKE_CURRENT_SOURCE_DIR}/${_root}/*.md"
    )
    list(APPEND _glueyneo_state_identity_files ${_root_files})
  endforeach()
  list(APPEND _glueyneo_state_identity_files
    "${CMAKE_CURRENT_SOURCE_DIR}/CMakeLists.txt"
    "${CMAKE_CURRENT_SOURCE_DIR}/CMakePresets.json"
    "${CMAKE_CURRENT_SOURCE_DIR}/third_party/ymfm/NOTICE.md"
  )
  list(REMOVE_DUPLICATES _glueyneo_state_identity_files)
  list(SORT _glueyneo_state_identity_files)
  set(_glueyneo_state_identity_material "")
  foreach(_identity_file IN LISTS _glueyneo_state_identity_files)
    file(SHA256 "${_identity_file}" _identity_file_sha256)
    file(RELATIVE_PATH _identity_relative "${CMAKE_CURRENT_SOURCE_DIR}"
      "${_identity_file}")
    string(APPEND _glueyneo_state_identity_material
      "${_identity_relative}:${_identity_file_sha256}\n")
  endforeach()
  string(SHA256 GLUEYNEO_SOURCE_CONTENT_ID
    "${_glueyneo_state_identity_material}")
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    ${_glueyneo_state_identity_files})
  if(NOT WIN32)
    find_package(Threads REQUIRED)
  endif()
  add_library(glueyneo_test STATIC ${GLUEYNEO_RUNTIME_SOURCES})
  target_compile_features(glueyneo_test PRIVATE c_std_17)
  set_target_properties(glueyneo_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
    C_VISIBILITY_PRESET hidden
  )
  target_include_directories(glueyneo_test
    PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include
    PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/src
      ${CMAKE_CURRENT_SOURCE_DIR}/experiments/owned_cpu
  )
  target_include_directories(glueyneo_test SYSTEM PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
  )
  target_compile_definitions(glueyneo_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    Z80_CANDIDATE_TEST_HOOKS
    OWNED_CPU_TEST_HOOKS
  )
  if(MSVC)
    target_compile_options(glueyneo_test PRIVATE /W4 "$<$<COMPILE_LANGUAGE:C>:/WX>")
  else()
    target_compile_options(glueyneo_test PRIVATE -Wall -Wextra -Wpedantic "$<$<COMPILE_LANGUAGE:C>:-Werror>")
  endif()
  glueyneo_configure_runtime_ym(glueyneo_test)
  glueyneo_apply_sdk_sanitizer(glueyneo_test)

  add_library(glueyneo_unity STATIC third_party/unity/src/unity.c)
  target_include_directories(glueyneo_unity PUBLIC third_party/unity/src)
  target_compile_features(glueyneo_unity PRIVATE c_std_17)
  set_target_properties(glueyneo_unity PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  glueyneo_apply_sdk_sanitizer(glueyneo_unity)

  if(GLUEYNEO_YM2610_ADMISSION)
    add_executable(ym2610_admission_test tests/chips/test_ym2610.c)
    target_include_directories(ym2610_admission_test PRIVATE src/chips)
    target_compile_features(ym2610_admission_test PRIVATE c_std_17)
    set_target_properties(ym2610_admission_test PROPERTIES
      C_STANDARD 17
      C_STANDARD_REQUIRED YES
      C_EXTENSIONS NO
    )
    target_compile_definitions(ym2610_admission_test PRIVATE GLUEYNEO_YM2610_TEST_HOOKS)
    target_link_libraries(ym2610_admission_test PRIVATE
      glueyneo_ym2610_candidate glueyneo_unity
    )
    if(MSVC)
      target_compile_options(ym2610_admission_test PRIVATE /W4 /WX)
    else()
      target_compile_options(ym2610_admission_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
    glueyneo_apply_sdk_sanitizer(ym2610_admission_test)
    add_test(NAME ym2610_admission
      COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/chips/check_ym2610.py"
              test --binary $<TARGET_FILE:ym2610_admission_test>
              --report "${CMAKE_CURRENT_BINARY_DIR}/ym2610-admission/ym2610-admission.json")
    set_tests_properties(ym2610_admission PROPERTIES LABELS "ym2610-admission" TIMEOUT 180)
  endif()

  add_executable(public_guest_test
    tests/fixture/test_public_guest.c
    tests/fixture/public_guest.c
  )
  target_include_directories(public_guest_test PRIVATE tests/fixture)
  target_compile_features(public_guest_test PRIVATE c_std_17)
  set_target_properties(public_guest_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(public_guest_test PRIVATE glueyneo glueyneo_unity)
  if(MSVC)
    target_compile_options(public_guest_test PRIVATE /W4 /WX)
  else()
    target_compile_options(public_guest_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(public_guest_test)
  set(GLUEYNEO_PUBLIC_FIXTURE
      "${CMAKE_CURRENT_BINARY_DIR}/public-playable.bin")
  add_custom_command(
    OUTPUT "${GLUEYNEO_PUBLIC_FIXTURE}"
    COMMAND $<TARGET_FILE:public_guest_test> --write-fixture
            "${GLUEYNEO_PUBLIC_FIXTURE}"
    DEPENDS public_guest_test tests/fixture/public_guest.c
    VERBATIM
  )
  add_custom_target(glueyneo-public-fixture ALL
    DEPENDS "${GLUEYNEO_PUBLIC_FIXTURE}")
  add_test(NAME public_guest_contract
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}")
  add_test(NAME public_guest_trace
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" trace)
  add_test(NAME public_guest_negative_left
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" negative-left)
  add_test(NAME public_guest_negative_none
    COMMAND public_guest_test "${GLUEYNEO_PUBLIC_FIXTURE}" negative-none)
  set_tests_properties(public_guest_contract public_guest_trace
    public_guest_negative_left public_guest_negative_none PROPERTIES
    LABELS "public-fixture;native-tracer")

  add_executable(public_sound_test
    tests/fixture/test_public_sound_guest.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(public_sound_test PRIVATE tests/fixture)
  target_compile_features(public_sound_test PRIVATE c_std_17)
  set_target_properties(public_sound_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(public_sound_test PRIVATE glueyneo glueyneo_unity)
  if(MSVC)
    target_compile_options(public_sound_test PRIVATE /W4 /WX)
  else()
    target_compile_options(public_sound_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(public_sound_test)
  set(GLUEYNEO_PUBLIC_SOUND_FIXTURE
      "${CMAKE_CURRENT_BINARY_DIR}/public-sound-mvs.bin")
  add_custom_command(
    OUTPUT "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}"
    COMMAND $<TARGET_FILE:public_sound_test> --write-fixture
            "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}"
    DEPENDS public_sound_test tests/fixture/public_sound_guest.c
    VERBATIM
  )
  add_custom_target(glueyneo-public-sound-fixture ALL
    DEPENDS "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}")
  add_test(NAME public_sound_fixture
    COMMAND public_sound_test "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}")
  set_tests_properties(public_sound_fixture PROPERTIES
    LABELS "public-fixture;mvs-audio-contract" TIMEOUT 180)

  add_executable(sound_consumer_reference tests/consumers/sound_consumer.c
    tests/fixture/public_sound_guest.c)
  target_link_libraries(sound_consumer_reference PRIVATE Glueyneo::glueyneo)
  set_target_properties(sound_consumer_reference PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  if(MSVC)
    target_compile_options(sound_consumer_reference PRIVATE /W4 /WX)
  else()
    target_compile_options(sound_consumer_reference PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sound_consumer_reference)
  add_dependencies(sound_consumer_reference glueyneo-public-sound-fixture)
  set(GLUEYNEO_SOUND_REFERENCE "${CMAKE_CURRENT_BINARY_DIR}/public-sound-reference.trace")
  add_test(NAME sdk_sound_reference COMMAND sound_consumer_reference
    "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}" --trace "${GLUEYNEO_SOUND_REFERENCE}")
  set_tests_properties(sdk_sound_reference PROPERTIES
    FIXTURES_SETUP sdk_sound_reference LABELS "public-fixture;mvs-audio-contract" TIMEOUT 30)

  add_executable(libretro_callback_test
    tests/libretro/callback_harness.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(libretro_callback_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/libretro
  )
  target_compile_features(libretro_callback_test PRIVATE c_std_17)
  set_target_properties(libretro_callback_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(libretro_callback_test PRIVATE
    glueyneo_libretro Glueyneo::glueyneo ${CMAKE_DL_LIBS}
  )
  # libretro.h marks RETRO_API dllexport on Windows unless the consumer asks for dllimport.
  target_compile_definitions(libretro_callback_test PRIVATE $<$<PLATFORM_ID:Windows>:RARCH_DLL_IMPORT>)
  if(MSVC)
    target_compile_options(libretro_callback_test PRIVATE /W4 /WX)
  else()
    target_compile_options(libretro_callback_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(libretro_callback_test)
  add_dependencies(libretro_callback_test glueyneo-public-fixture)
  add_dependencies(libretro_callback_test glueyneo-public-sound-fixture)
  add_test(NAME libretro_callback
    COMMAND libretro_callback_test "${GLUEYNEO_PUBLIC_FIXTURE}")
  set_tests_properties(libretro_callback PROPERTIES LABELS "libretro;callback-contract")
  add_test(NAME libretro_audio_contract
    COMMAND libretro_callback_test --sound "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}")
  set_tests_properties(libretro_audio_contract PROPERTIES
    LABELS "libretro;mvs-audio-contract" TIMEOUT 180)

  add_executable(libretro_frontend_observer_test
    tests/libretro/callback_harness.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
    src/libretro/libretro_core.c
  )
  target_include_directories(libretro_frontend_observer_test PRIVATE
    src tests/sdk tests/fixture third_party/libretro third_party/chips
  )
  target_compile_features(libretro_frontend_observer_test PRIVATE c_std_17)
  target_compile_definitions(libretro_frontend_observer_test PRIVATE
    GLUEYNEO_LIBRETRO_CONTINUATION_OBSERVATIONS
  )
  set_target_properties(libretro_frontend_observer_test PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(libretro_frontend_observer_test PRIVATE
    glueyneo_test glueyneo_unity ${CMAKE_DL_LIBS})
  if(MSVC)
    target_compile_options(libretro_frontend_observer_test PRIVATE /W4 /WX)
  else()
    target_compile_options(libretro_frontend_observer_test PRIVATE
      -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(libretro_frontend_observer_test)
  add_dependencies(libretro_frontend_observer_test glueyneo-public-sound-fixture)

  add_executable(libretro_frontend_production_test
    tests/libretro/callback_harness.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
    src/libretro/libretro_core.c
  )
  target_include_directories(libretro_frontend_production_test PRIVATE
    src tests/sdk tests/fixture third_party/libretro third_party/chips
  )
  target_compile_features(libretro_frontend_production_test PRIVATE c_std_17)
  set_target_properties(libretro_frontend_production_test PROPERTIES
    C_STANDARD 17 C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(libretro_frontend_production_test PRIVATE
    glueyneo_test glueyneo_unity ${CMAKE_DL_LIBS})
  if(MSVC)
    target_compile_options(libretro_frontend_production_test PRIVATE /W4 /WX)
  else()
    target_compile_options(libretro_frontend_production_test PRIVATE
      -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(libretro_frontend_production_test)
  add_dependencies(libretro_frontend_production_test glueyneo-public-sound-fixture)

  set(GLUEYNEO_PUBLIC_SAVE_FIXTURE
      "${CMAKE_CURRENT_BINARY_DIR}/public-save.gnmv")
  add_custom_command(
    OUTPUT "${GLUEYNEO_PUBLIC_SAVE_FIXTURE}"
    COMMAND $<TARGET_FILE:libretro_callback_test> --write-save-fixture
            "${GLUEYNEO_PUBLIC_SAVE_FIXTURE}"
    DEPENDS libretro_callback_test tests/fixture/public_save_guest.c
            tests/fixture/public_sound_guest.c
    VERBATIM
  )
  add_custom_target(glueyneo-public-save-fixture ALL
    DEPENDS "${GLUEYNEO_PUBLIC_SAVE_FIXTURE}")
  add_test(NAME libretro_mvs_state_contract
    COMMAND libretro_callback_test --mvs-state "${GLUEYNEO_PUBLIC_SAVE_FIXTURE}")
  set_tests_properties(libretro_mvs_state_contract PROPERTIES
    LABELS "libretro;mvs-state-contract;public-fixture" TIMEOUT 180)
  add_test(NAME libretro_mvs_save_ram_contract
    COMMAND libretro_callback_test --mvs-save-ram
            "${GLUEYNEO_PUBLIC_SAVE_FIXTURE}")
  set_tests_properties(libretro_mvs_save_ram_contract PROPERTIES
    LABELS "libretro;mvs-save-ram-contract;public-fixture" TIMEOUT 180)

  # Compile the production adapter against the test runtime so state and SRAM
  # failure hooks exercise the real callback boundary without adding a
  # production failpoint ABI.
  add_executable(libretro_mvs_state_safety_test
    tests/libretro/state_safety.c
    tests/sdk/save_fixture.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
    src/libretro/libretro_core.c
  )
  target_include_directories(libretro_mvs_state_safety_test PRIVATE
    src tests/sdk tests/fixture third_party/libretro third_party/chips
  )
  target_compile_features(libretro_mvs_state_safety_test PRIVATE c_std_17)
  target_compile_definitions(libretro_mvs_state_safety_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
  )
  set_target_properties(libretro_mvs_state_safety_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(libretro_mvs_state_safety_test PRIVATE
    glueyneo_test glueyneo_unity ${CMAKE_DL_LIBS}
  )
  if(MSVC)
    target_compile_options(libretro_mvs_state_safety_test PRIVATE /W4 /WX /UNDEBUG)
  else()
    target_compile_options(libretro_mvs_state_safety_test PRIVATE
      -Wall -Wextra -Wpedantic -Werror -UNDEBUG
    )
  endif()
  glueyneo_apply_sdk_sanitizer(libretro_mvs_state_safety_test)
  add_test(NAME libretro_mvs_state_rejection
    COMMAND libretro_mvs_state_safety_test --state-rejection)
  add_test(NAME libretro_mvs_retention
    COMMAND libretro_mvs_state_safety_test --retention)
  set_tests_properties(libretro_mvs_state_rejection libretro_mvs_retention
    PROPERTIES LABELS "libretro;mvs-state-safety" TIMEOUT 180)

  add_library(mvs_import_lib STATIC tools/mvs/mvs_import.c)
  target_compile_definitions(mvs_import_lib PRIVATE MVS_IMPORT_NO_MAIN)
  target_compile_features(mvs_import_lib PRIVATE c_std_17)
  set_target_properties(mvs_import_lib PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_include_directories(mvs_import_lib PRIVATE third_party/zlib)
  target_link_libraries(mvs_import_lib PRIVATE glueyneo_mvs_zlib)
  if(MSVC)
    target_compile_options(mvs_import_lib PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_import_lib PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_import_lib)

  add_executable(mvs_importer tools/mvs/mvs_import.c)
  target_compile_features(mvs_importer PRIVATE c_std_17)
  set_target_properties(mvs_importer PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_include_directories(mvs_importer PRIVATE third_party/zlib)
  target_link_libraries(mvs_importer PRIVATE glueyneo_mvs_zlib)
  if(MSVC)
    target_compile_options(mvs_importer PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_importer PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_importer)

  add_executable(mvs_test tests/mvs/test_mvs.c)
  target_sources(mvs_test PRIVATE tests/fixture/public_guest.c)
  target_include_directories(mvs_test PRIVATE
    src third_party/libretro third_party/zlib third_party/chips)
  target_compile_features(mvs_test PRIVATE c_std_17)
  target_compile_definitions(mvs_test PRIVATE GLUEYNEO_SDK_TEST_HOOKS
    $<$<BOOL:${GLUEYNEO_MVS_INPUT_OBSERVATIONS}>:GLUEYNEO_MVS_INPUT_OBSERVATIONS>)
  set_target_properties(mvs_test PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_test PRIVATE
    glueyneo_test glueyneo_unity mvs_import_lib glueyneo_libretro
    ${CMAKE_DL_LIBS})
  if(MSVC)
    target_compile_options(mvs_test PRIVATE /W4 /WX /UNDEBUG)
  else()
    target_compile_options(mvs_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_test)
  # Compile an instrumented adapter directly with the private test runtime;
  # the ordinary installed core retains the default-OFF diagnostic contract.
  add_executable(mvs_observations_test tests/mvs/test_mvs.c
    tests/fixture/public_guest.c src/libretro/libretro_core.c)
  target_include_directories(mvs_observations_test PRIVATE
    src third_party/libretro third_party/zlib third_party/chips)
  target_compile_features(mvs_observations_test PRIVATE c_std_17)
  target_compile_definitions(mvs_observations_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS GLUEYNEO_MVS_INPUT_OBSERVATIONS)
  set_target_properties(mvs_observations_test PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_observations_test PRIVATE
    glueyneo_test glueyneo_unity mvs_import_lib ${CMAKE_DL_LIBS})
  if(MSVC)
    target_compile_options(mvs_observations_test PRIVATE /W4 /WX /UNDEBUG)
  else()
    target_compile_options(mvs_observations_test PRIVATE -Wall -Wextra -Wpedantic -Werror -UNDEBUG)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_observations_test)
  add_test(NAME mvs_input_observations
    COMMAND mvs_observations_test --input-observations)
  set_tests_properties(mvs_input_observations PROPERTIES LABELS "mvs;libretro" TIMEOUT 180)
  add_test(NAME mvs_synthetic_trace COMMAND mvs_test)
  set_tests_properties(mvs_synthetic_trace PROPERTIES
    LABELS "mvs;importer;guest;libretro" TIMEOUT 60)
  add_test(NAME mvs_media_contract COMMAND mvs_test --media-contract)
  add_test(NAME mvs_import_contract
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer>
            --failure-driver $<TARGET_FILE:mvs_failure_driver> --mode positive)
  # Keep the full 3,600-frame guest run in ordinary integration coverage. Its
  # sanitizer-instrumented -O0 workload exceeds the existing 120-second child
  # bound; shorter guest, input and maximum-bound rejection checks remain in
  # mvs_import_contract under ASan/UBSan.
  if(GLUEYNEO_SDK_SANITIZER STREQUAL "NONE")
    set(_GLUEYNEO_MAX_HORIZON_CTEST_TIMEOUT 180)
    if(MSVC)
      # A Windows Debug runner previously reached the 120-second child bound
      # before completing the fixed 3,600-frame boundary case.
      set(_GLUEYNEO_MAX_HORIZON_CTEST_TIMEOUT 300)
    endif()
    add_test(NAME mvs_import_max_horizon
      COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
              --importer $<TARGET_FILE:mvs_importer> --mode maximum-horizon)
    set_tests_properties(mvs_import_max_horizon PROPERTIES
      LABELS "mvs;resource-boundary" TIMEOUT ${_GLUEYNEO_MAX_HORIZON_CTEST_TIMEOUT})
  endif()
  add_test(NAME mvs_failure_diagnostics
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer>
            --failure-driver $<TARGET_FILE:mvs_failure_driver> --mode failure)
  add_test(NAME mvs_import_mutation
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer> --mode mutation)
  add_test(NAME mvs_callback_contract COMMAND mvs_test --callback-contract)
  add_test(NAME mvs_boot_checkpoint COMMAND mvs_test --boot-checkpoint)
  add_test(NAME mvs_attract_predicate COMMAND mvs_test --attract-predicate)
  # Preserve every board assertion in bounded semantic partitions. The legacy
  # --board-behavior CLI still executes all six groups for direct callers.
  add_test(NAME mvs_board_behavior COMMAND mvs_test --board-core)
  add_test(NAME mvs_board_io COMMAND mvs_test --board-io)
  add_test(NAME mvs_board_calendar COMMAND mvs_test --board-calendar)
  add_test(NAME mvs_board_sound COMMAND mvs_test --board-sound)
  add_test(NAME mvs_board_cartridge COMMAND mvs_test --board-cartridge)
  add_test(NAME mvs_board_video COMMAND mvs_test --board-video)
  set_tests_properties(mvs_media_contract mvs_import_contract mvs_failure_diagnostics
    mvs_import_mutation
    mvs_callback_contract mvs_boot_checkpoint mvs_attract_predicate
    mvs_board_behavior mvs_board_io mvs_board_calendar mvs_board_sound
    mvs_board_cartridge mvs_board_video
    PROPERTIES LABELS "mvs" TIMEOUT 180)

  add_executable(mvs_import_fuzz tests/mvs/fuzz_import.c)
  target_compile_features(mvs_import_fuzz PRIVATE c_std_17)
  target_link_libraries(mvs_import_fuzz PRIVATE mvs_import_lib Glueyneo::glueyneo)
  add_dependencies(mvs_import_fuzz glueyneo-public-sound-fixture)
  if(MSVC)
    target_compile_options(mvs_import_fuzz PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_import_fuzz PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_import_fuzz)
  add_dependencies(mvs_test mvs_import_fuzz)
  add_test(NAME mvs_import_fuzz_corpus
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/mvs/test_mvs_qualification.py
            --importer $<TARGET_FILE:mvs_importer> --fuzzer $<TARGET_FILE:mvs_import_fuzz>
            --mode fuzz)
  set_tests_properties(mvs_import_fuzz_corpus PROPERTIES
    LABELS "mvs;fuzz" TIMEOUT 180)
  add_test(NAME mvs_audio_call_corpus COMMAND mvs_import_fuzz
    --audio-calls "${GLUEYNEO_PUBLIC_SOUND_FIXTURE}")
  set_tests_properties(mvs_audio_call_corpus PROPERTIES
    LABELS "mvs-audio-contract;fuzz" TIMEOUT 60)

  # mvs_qualify reads the private fetch trace, which a shared libglueyneo
  # hides, so it links the static runtime copy in every build mode.
  add_executable(mvs_qualify tools/mvs/mvs_qualify.c)
  target_include_directories(mvs_qualify PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include)
  target_compile_features(mvs_qualify PRIVATE c_std_17)
  set_target_properties(mvs_qualify PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_qualify PRIVATE glueyneo_runtime_static)
  if(MSVC)
    target_compile_options(mvs_qualify PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_qualify PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_qualify)

  add_executable(mvs_failure_driver
    tests/mvs/qualification_failure_driver.c tools/mvs/mvs_qualify.c)
  target_include_directories(mvs_failure_driver PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
    ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_compile_features(mvs_failure_driver PRIVATE c_std_17)
  target_compile_definitions(mvs_failure_driver PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS GN_MVS_QUALIFY_NO_MAIN)
  set_target_properties(mvs_failure_driver PROPERTIES C_STANDARD 17
    C_STANDARD_REQUIRED YES C_EXTENSIONS NO)
  target_link_libraries(mvs_failure_driver PRIVATE glueyneo_test)
  if(MSVC)
    target_compile_options(mvs_failure_driver PRIVATE /W4 /WX)
  else()
    target_compile_options(mvs_failure_driver PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(mvs_failure_driver)

  add_executable(sdk_diagnostic tests/sdk/test_sdk.c tests/sdk/guest_fixture.c)
  target_include_directories(sdk_diagnostic PRIVATE tests/sdk src)
  target_compile_features(sdk_diagnostic PRIVATE c_std_17)
  set_target_properties(sdk_diagnostic PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_diagnostic PRIVATE
    glueyneo_test glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_diagnostic PRIVATE Threads::Threads)
  endif()
  target_compile_definitions(sdk_diagnostic PRIVATE GLUEYNEO_SDK_TEST_HOOKS)
  target_compile_definitions(sdk_diagnostic PRIVATE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_diagnostic PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_diagnostic PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_diagnostic)

  add_executable(sdk_state_test
    tests/sdk/test_state.c
    tests/fuzz/state_mutation.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_state_test PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_state_test PRIVATE c_std_17)
  set_target_properties(sdk_state_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_state_test PRIVATE glueyneo_test glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_state_test PRIVATE Threads::Threads)
  endif()
  target_compile_definitions(sdk_state_test PRIVATE GLUEYNEO_SDK_TEST_HOOKS)
  target_compile_definitions(sdk_state_test PRIVATE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_state_test PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_state_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_state_test)

  add_executable(sdk_state_mutation
    tests/sdk/test_state.c
    tests/fuzz/state_mutation.c
    tests/fuzz/state_oom.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_state_mutation PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_state_mutation PRIVATE c_std_17)
  set_target_properties(sdk_state_mutation PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_state_mutation PRIVATE glueyneo_test glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_state_mutation PRIVATE Threads::Threads)
  endif()
  target_compile_definitions(sdk_state_mutation PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    GLUEYNEO_STATE_MUTATION_EXECUTABLE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_state_mutation PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_state_mutation PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_state_mutation)

  add_executable(sdk_state_process
    tests/sdk/state_process.c
    tests/sdk/guest_fixture.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_state_process PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_state_process PRIVATE c_std_17)
  set_target_properties(sdk_state_process PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_state_process PRIVATE glueyneo_test glueyneo_unity)
  target_compile_definitions(sdk_state_process PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_SOURCE_CONTENT_ID="${GLUEYNEO_SOURCE_CONTENT_ID}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_state_process PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_state_process PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_state_process)
  add_test(NAME libretro_frontend_observer
    COMMAND ${Python3_EXECUTABLE}
      ${CMAKE_CURRENT_SOURCE_DIR}/tests/libretro/frontend_observer_test.py
      --harness $<TARGET_FILE:libretro_frontend_observer_test>
      --production $<TARGET_FILE:libretro_frontend_production_test>
      --witness $<TARGET_FILE:sdk_state_process>
      --bundle ${GLUEYNEO_PUBLIC_SOUND_FIXTURE})
  set_tests_properties(libretro_frontend_observer PROPERTIES
    LABELS "libretro;continuation;state" TIMEOUT 180)

  add_executable(sdk_save_process
    tests/sdk/save_process.c
    tests/sdk/save_host.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_save_process PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_save_process PRIVATE c_std_17)
  set_target_properties(sdk_save_process PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_save_process PRIVATE glueyneo_test glueyneo_unity)
  target_compile_definitions(sdk_save_process PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_SOURCE_CONTENT_ID="${GLUEYNEO_SOURCE_CONTENT_ID}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_save_process PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_save_process PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_save_process)

  add_executable(sdk_save_test
    tests/sdk/test_save.c
    tests/sdk/save_fixture.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_save_test PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_save_test PRIVATE c_std_17)
  set_target_properties(sdk_save_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_save_test PRIVATE glueyneo_test glueyneo_unity)
  target_compile_definitions(sdk_save_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_save_test PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_save_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_save_test)

  add_executable(sdk_save_lifecycle_test
    tests/sdk/test_save_lifecycle.c
    tests/sdk/save_fixture.c
    tests/fixture/public_save_guest.c
    tests/fixture/public_sound_guest.c
  )
  target_include_directories(sdk_save_lifecycle_test PRIVATE
    tests/sdk src tests/fixture third_party/chips
  )
  target_compile_features(sdk_save_lifecycle_test PRIVATE c_std_17)
  set_target_properties(sdk_save_lifecycle_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_save_lifecycle_test PRIVATE
    glueyneo_test glueyneo_unity
  )
  target_compile_definitions(sdk_save_lifecycle_test PRIVATE
    GLUEYNEO_SDK_TEST_HOOKS
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_save_lifecycle_test PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_save_lifecycle_test PRIVATE
      -Wall -Wextra -Wpedantic -Werror
    )
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_save_lifecycle_test)

  # Keep the candidate's direct conformance tests alongside its private runtime link.
  add_executable(z80_admission_test
    tests/chips/test_z80.c
    src/chips/z80_candidate.c
  )
  target_include_directories(z80_admission_test PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src/chips
  )
  # The pinned upstream header carries its implementation; keep its warnings out of /WX and -Werror.
  target_include_directories(z80_admission_test SYSTEM PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
  )
  target_compile_features(z80_admission_test PRIVATE c_std_17)
  target_compile_definitions(z80_admission_test PRIVATE Z80_CANDIDATE_TEST_HOOKS=1)
  set_target_properties(z80_admission_test PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(z80_admission_test PRIVATE glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(z80_admission_test PRIVATE Threads::Threads)
  endif()
  if(MSVC)
    target_compile_options(z80_admission_test PRIVATE /W4 /WX /external:W0
      "/external:I${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips")
  else()
    target_compile_options(z80_admission_test PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(z80_admission_test)
  add_test(NAME z80_admission_contract COMMAND z80_admission_test)
  set_tests_properties(z80_admission_contract PROPERTIES LABELS "z80-admission")
  foreach(z80_mutation IN ITEMS cycle bus irq continuation instance)
    add_test(NAME "z80_admission_mutation_${z80_mutation}"
      COMMAND z80_admission_test "--mutation=${z80_mutation}")
    set_tests_properties("z80_admission_mutation_${z80_mutation}" PROPERTIES
      WILL_FAIL TRUE
      LABELS "z80-admission;z80-mutation"
    )
  endforeach()

  add_executable(sdk_mutation
    tests/fuzz/sdk_mutation.c
    tests/sdk/guest_fixture.c
  )
  target_include_directories(sdk_mutation PRIVATE tests/sdk)
  target_compile_features(sdk_mutation PRIVATE c_std_17)
  set_target_properties(sdk_mutation PROPERTIES
    C_STANDARD 17
    C_STANDARD_REQUIRED YES
    C_EXTENSIONS NO
  )
  target_link_libraries(sdk_mutation PRIVATE glueyneo glueyneo_unity)
  if(NOT WIN32)
    target_link_libraries(sdk_mutation PRIVATE Threads::Threads)
  endif()
  target_compile_definitions(sdk_mutation PRIVATE
    GLUEYNEO_SOURCE_REVISION="${GLUEYNEO_SOURCE_REVISION}"
    GLUEYNEO_CONFIGURATION="${CMAKE_BUILD_TYPE}"
    GLUEYNEO_COMPILER_ID="${CMAKE_C_COMPILER_ID}"
    GLUEYNEO_COMPILER_VERSION="${CMAKE_C_COMPILER_VERSION}"
    GLUEYNEO_SANITIZER="${GLUEYNEO_SDK_SANITIZER}"
  )
  if(MSVC)
    target_compile_options(sdk_mutation PRIVATE /W4 /WX)
  else()
    target_compile_options(sdk_mutation PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  glueyneo_apply_sdk_sanitizer(sdk_mutation)
  add_test(NAME sdk_diagnostic COMMAND sdk_diagnostic diagnostic)
  set_tests_properties(sdk_diagnostic PROPERTIES LABELS "sdk-contract;sdk-diagnostic")
  add_test(NAME sdk_state_tracer COMMAND sdk_diagnostic state-tracer)
  set_tests_properties(sdk_state_tracer PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_identity COMMAND sdk_diagnostic state-identity)
  set_tests_properties(sdk_state_identity PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_ym COMMAND sdk_diagnostic state-ym)
  set_tests_properties(sdk_state_ym PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_machine COMMAND sdk_diagnostic state-machine)
  set_tests_properties(sdk_state_machine PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_continuation COMMAND sdk_state_test continuation)
  set_tests_properties(sdk_state_continuation PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_controls
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/state_controls.py
            $<TARGET_FILE:sdk_state_test>)
  set_tests_properties(sdk_state_controls PROPERTIES
    LABELS "sdk-state;sdk-controls"
    TIMEOUT 300
  )
  add_test(NAME sdk_state_isolation COMMAND sdk_state_test isolation)
  set_tests_properties(sdk_state_isolation PROPERTIES
    LABELS "sdk-state;sdk-isolation"
    TIMEOUT 180
  )
  add_test(NAME sdk_state_repeat COMMAND sdk_state_test repeat)
  set_tests_properties(sdk_state_repeat PROPERTIES
    LABELS "sdk-state"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_hostile
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/fuzz/verify_state_controls.py
            $<TARGET_FILE:sdk_state_mutation>)
  set_tests_properties(sdk_state_hostile PROPERTIES
    LABELS "sdk-state;hostile"
    TIMEOUT 120
  )
  add_test(NAME sdk_state_oom COMMAND sdk_state_mutation oom)
  set_tests_properties(sdk_state_oom PROPERTIES
    LABELS "sdk-state;oom"
    TIMEOUT 60
  )
  add_test(NAME sdk_state_process
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_state_exchange.py
            --mode process --runner $<TARGET_FILE:sdk_state_process>)
  set_tests_properties(sdk_state_process PROPERTIES
    LABELS "sdk-state;process-exchange"
    TIMEOUT 300
    PROCESSORS 2
  )
  if(APPLE)
    add_test(NAME sdk_save_process
      COMMAND ${Python3_EXECUTABLE}
              ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_save_process.py
              --mode process --runner $<TARGET_FILE:sdk_save_process>)
  else()
    # The reference file-commit protocol is Darwin-specific. Keep a portable
    # executable stub in every build and report the process test as skipped.
    add_test(NAME sdk_save_process COMMAND $<TARGET_FILE:sdk_save_process>)
    set_tests_properties(sdk_save_process PROPERTIES SKIP_RETURN_CODE 77)
  endif()
  set_tests_properties(sdk_save_process PROPERTIES
    LABELS "sdk-save;process-exchange"
    TIMEOUT 60
    PROCESSORS 1
    RESOURCE_LOCK sdk_save_single_process
  )
  if(APPLE)
    add_test(NAME sdk_save_host_faults
      COMMAND ${Python3_EXECUTABLE}
              ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_save_process.py
              --mode host-faults --runner $<TARGET_FILE:sdk_save_process>)
  else()
    add_test(NAME sdk_save_host_faults COMMAND $<TARGET_FILE:sdk_save_process>
             --mode host-faults)
    set_tests_properties(sdk_save_host_faults PROPERTIES SKIP_RETURN_CODE 77)
  endif()
  set_tests_properties(sdk_save_host_faults PROPERTIES
    LABELS "sdk-save;host-faults"
    TIMEOUT 60
    PROCESSORS 1
    RESOURCE_LOCK sdk_save_single_process
  )
  if(APPLE)
    add_test(NAME sdk_save_recovery
      COMMAND ${Python3_EXECUTABLE}
              ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_save_process.py
              --mode recovery --runner $<TARGET_FILE:sdk_save_process>)
  else()
    add_test(NAME sdk_save_recovery COMMAND $<TARGET_FILE:sdk_save_process>
             --mode recovery)
    set_tests_properties(sdk_save_recovery PROPERTIES SKIP_RETURN_CODE 77)
  endif()
  set_tests_properties(sdk_save_recovery PROPERTIES
    LABELS "sdk-save;recovery"
    TIMEOUT 60
    PROCESSORS 1
    RESOURCE_LOCK sdk_save_single_process
  )
  if(APPLE)
    add_test(NAME sdk_save_barriers
      COMMAND ${Python3_EXECUTABLE}
              ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_save_process.py
              --mode barriers --runner $<TARGET_FILE:sdk_save_process>)
  else()
    add_test(NAME sdk_save_barriers COMMAND $<TARGET_FILE:sdk_save_process>
             --mode barriers)
    set_tests_properties(sdk_save_barriers PROPERTIES SKIP_RETURN_CODE 77)
  endif()
  set_tests_properties(sdk_save_barriers PROPERTIES
    LABELS "sdk-save;barriers"
    TIMEOUT 60
    PROCESSORS 1
    RESOURCE_LOCK sdk_save_single_process
  )
  add_test(NAME sdk_save_api COMMAND sdk_save_test api)
  set_tests_properties(sdk_save_api PROPERTIES
    LABELS "sdk-save"
    TIMEOUT 60
    PROCESSORS 1
  )
  if(GLUEYNEO_SDK_SANITIZER STREQUAL "ADDRESS_UNDEFINED")
    set(SDK_SAVE_CONTROL_TIMEOUT_SECONDS 90)
    set(SDK_SAVE_CONTROL_TEST_TIMEOUT_SECONDS 180)
  else()
    set(SDK_SAVE_CONTROL_TIMEOUT_SECONDS 30)
    set(SDK_SAVE_CONTROL_TEST_TIMEOUT_SECONDS 60)
  endif()
  add_test(NAME sdk_save_receipts
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/save_controls.py
            --mode receipts --runner $<TARGET_FILE:sdk_save_test>
            --timeout ${SDK_SAVE_CONTROL_TIMEOUT_SECONDS}
  )
  set_tests_properties(sdk_save_receipts PROPERTIES
    LABELS "sdk-save"
    TIMEOUT ${SDK_SAVE_CONTROL_TEST_TIMEOUT_SECONDS}
    PROCESSORS 1
  )
  add_test(NAME sdk_save_lifecycle
    COMMAND sdk_save_lifecycle_test lifecycle
  )
  set_tests_properties(sdk_save_lifecycle PROPERTIES
    LABELS "sdk-save"
    TIMEOUT ${SDK_SAVE_CONTROL_TEST_TIMEOUT_SECONDS}
    PROCESSORS 1
  )
  add_test(NAME sdk_save_registration
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_save_registration.py
  )
  set_tests_properties(sdk_save_registration PROPERTIES
    LABELS "sdk-save"
    TIMEOUT 60
    PROCESSORS 1
  )
  set(SDK_STATE_DEBUG_RUNNER
    "${CMAKE_SOURCE_DIR}/build/sdk-debug/sdk_state_process${CMAKE_EXECUTABLE_SUFFIX}")
  set(SDK_STATE_RELEASE_RUNNER
    "${CMAKE_SOURCE_DIR}/build/sdk-release/sdk_state_process${CMAKE_EXECUTABLE_SUFFIX}")
  if(EXISTS "${SDK_STATE_DEBUG_RUNNER}" AND EXISTS "${SDK_STATE_RELEASE_RUNNER}" AND
     NOT SDK_STATE_DEBUG_RUNNER STREQUAL SDK_STATE_RELEASE_RUNNER)
    add_test(NAME sdk_state_exchange
      COMMAND ${Python3_EXECUTABLE}
              ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/test_state_exchange.py
              --mode exchange
              --debug-runner "${SDK_STATE_DEBUG_RUNNER}"
              --release-runner "${SDK_STATE_RELEASE_RUNNER}")
    set_tests_properties(sdk_state_exchange PROPERTIES
      LABELS "sdk-state;process-exchange"
      TIMEOUT 600
      PROCESSORS 2
      DEPENDS sdk_state_process
    )
  endif()
  add_test(NAME sdk_state_registration
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/cmake/test_state_test_metadata.py)
  set_tests_properties(sdk_state_registration PROPERTIES
    LABELS "sdk-state-metadata"
    TIMEOUT 15
  )
  add_test(NAME sdk_lifecycle COMMAND sdk_diagnostic lifecycle)
  set_tests_properties(sdk_lifecycle PROPERTIES LABELS "sdk-contract;sdk-lifecycle")
  add_test(NAME sdk_media COMMAND sdk_diagnostic media)
  set_tests_properties(sdk_media PROPERTIES LABELS "sdk-contract;sdk-media")
  add_test(NAME sdk_faults COMMAND sdk_diagnostic faults)
  set_tests_properties(sdk_faults PROPERTIES LABELS "sdk-contract;sdk-faults")
  add_test(NAME sdk_run COMMAND sdk_diagnostic run)
  set_tests_properties(sdk_run PROPERTIES LABELS "sdk-contract;sdk-run")
  add_test(NAME sdk_mutation_media COMMAND sdk_mutation --media)
  add_test(NAME sdk_mutation_sequence COMMAND sdk_mutation --sequence)
  add_test(NAME sdk_mutation_minimizer
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/fuzz/minimize.py
            --self-test)
  add_test(NAME sdk_state_minimizer
    COMMAND ${Python3_EXECUTABLE} ${CMAKE_CURRENT_SOURCE_DIR}/tests/fuzz/minimize.py
            --self-test --state)
  set_tests_properties(sdk_mutation_media sdk_mutation_sequence
    sdk_mutation_minimizer sdk_state_minimizer
    PROPERTIES LABELS "sdk-hostile;sdk-mutation" TIMEOUT 180)
  add_test(NAME sdk_controls
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --controls
            $<TARGET_FILE:sdk_diagnostic> $<TARGET_FILE:glueyneo-diagnostic>)
  set_tests_properties(sdk_controls PROPERTIES LABELS "sdk-controls")
  add_test(NAME sdk_isolation
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --isolation
            $<TARGET_FILE:sdk_diagnostic>
            $<IF:$<STREQUAL:${GLUEYNEO_SDK_SANITIZER},THREAD>,60,30>)
  add_test(NAME sdk_cold
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/sdk/controls.py --cold
            $<TARGET_FILE:sdk_diagnostic>)
  set_tests_properties(sdk_isolation sdk_cold PROPERTIES
    LABELS "sdk-isolation" TIMEOUT 180)

  # Keep the runtime source closure explicit, then inspect both source and the
  # linked target for ambient host services used by the native core.
  set(SDK_HOST_CLOSURE_SCRIPT "${CMAKE_CURRENT_BINARY_DIR}/sdk-host-closure.cmake")
  set(SDK_RUNTIME_ABSOLUTE_SOURCES)
  foreach(runtime_source IN LISTS GLUEYNEO_RUNTIME_SOURCES)
    list(APPEND SDK_RUNTIME_ABSOLUTE_SOURCES
      "${CMAKE_CURRENT_SOURCE_DIR}/${runtime_source}")
  endforeach()
  if(WIN32)
    find_program(GLUEYNEO_SDK_DUMPBIN NAMES dumpbin REQUIRED)
  endif()
  set(SDK_HOST_CLOSURE_CONTENT [=[
set(_sdk_sources "@SDK_RUNTIME_ABSOLUTE_SOURCES@")
set(_sdk_library "$<TARGET_FILE:glueyneo>")
set(_sdk_nm "@CMAKE_NM@")
set(_sdk_windows "@WIN32@")
set(_sdk_dumpbin "@GLUEYNEO_SDK_DUMPBIN@")
set(_sdk_host_names "fopen|freopen|fread|fwrite|remove|rename|open|close|read|write|time|clock|gettimeofday|socket|connect|accept|system|fork|execve|pthread_create|pthread_mutex_lock|CreateFileA|CreateFileW|ReadFile|WriteFile|DeleteFileA|DeleteFileW|MoveFileA|MoveFileW|GetSystemTime|GetSystemTimeAsFileTime|GetSystemTimePreciseAsFileTime|GetTickCount|GetTickCount64|QueryPerformanceCounter|QueryPerformanceFrequency|timeGetTime|GetEnvironmentVariableA|GetEnvironmentVariableW|WSAStartup|closesocket|getaddrinfo|send|recv|bind|listen|CreateThread|_beginthread|_beginthreadex|CreateMutexA|CreateMutexW|WaitForSingleObject|WaitForMultipleObjects|EnterCriticalSection|AcquireSRWLockExclusive|AcquireSRWLockShared|Sleep|SleepEx|SwitchToThread")
# Immutable ymfm source is audited by its exact pinned-byte/license gate.
# Owned C++ distinguishes member expressions from global host calls. All
# compiled objects remain subject to the forbidden-symbol checks below.
execute_process(COMMAND "@Python3_EXECUTABLE@"
  "@CMAKE_CURRENT_SOURCE_DIR@/tests/tools/check_runtime_host.py"
  --root "@CMAKE_CURRENT_SOURCE_DIR@" --names "${_sdk_host_names}" ${_sdk_sources}
  RESULT_VARIABLE _sdk_source_result)
if(NOT _sdk_source_result EQUAL 0)
  message(FATAL_ERROR "Runtime host-call source/provenance audit failed")
endif()
if(_sdk_windows)
  # /SYMBOLS exposes each COFF object's external definitions and references in
  # the static archive. /GL objects lack this table and must fail qualification.
  # https://learn.microsoft.com/en-us/cpp/build/reference/symbols
  # Checked 2026-10-06; retain the source closure as a separate control.
  execute_process(COMMAND ${_sdk_dumpbin} /SYMBOLS "${_sdk_library}"
    RESULT_VARIABLE _sdk_dumpbin_result OUTPUT_VARIABLE _sdk_symbols
    ERROR_VARIABLE _sdk_dumpbin_error)
  if(NOT _sdk_dumpbin_result EQUAL 0)
    message(FATAL_ERROR "Could not inspect runtime COFF symbols: ${_sdk_dumpbin_error}")
  endif()
  if(NOT _sdk_symbols MATCHES "File Type:[ \t]+(LIBRARY|COFF OBJECT)" OR
     NOT _sdk_symbols MATCHES "COFF SYMBOL TABLE")
    message(FATAL_ERROR "Runtime inspector produced no recognizable COFF symbol table")
  endif()
  string(REGEX MATCHALL "COFF SYMBOL TABLE" _sdk_coff_tables "${_sdk_symbols}")
  list(LENGTH _sdk_coff_tables _sdk_coff_table_count)
  list(LENGTH _sdk_sources _sdk_source_count)
  if(NOT _sdk_coff_table_count EQUAL _sdk_source_count)
    message(FATAL_ERROR "Runtime inspector omitted one or more runtime object symbol tables")
  endif()
  string(REPLACE "\r" "" _sdk_symbols "${_sdk_symbols}")
  string(REPLACE "\n" ";" _sdk_symbol_lines "${_sdk_symbols}")
  set(_sdk_external_count 0)
  string(REGEX REPLACE "\\|_beginthread" "|beginthread"
    _sdk_windows_host_names "${_sdk_host_names}")
  foreach(_sdk_line IN LISTS _sdk_symbol_lines)
    if(_sdk_line MATCHES "[ \t](WeakExternal|External)[ \t]+\\|")
      if(NOT _sdk_line MATCHES "^[ \t]*[0-9A-Fa-f]+[ \t]+[0-9A-Fa-f]+[ \t]+(UNDEF|ABS|DEBUG|SECT[0-9A-Fa-f]+)[ \t]+[^|]*[ \t](WeakExternal|External)[ \t]+\\|[ \t]+([^ \t]+)")
        message(FATAL_ERROR "Runtime inspector produced an unrecognizable external COFF symbol row")
      endif()
      set(_sdk_symbol "${CMAKE_MATCH_3}")
      math(EXPR _sdk_external_count "${_sdk_external_count} + 1")
      # Handle imported and x86-decorated C symbols before matching exact names.
      string(REGEX REPLACE "^__imp_" "" _sdk_symbol "${_sdk_symbol}")
      string(REGEX REPLACE "^_+" "" _sdk_symbol "${_sdk_symbol}")
      string(REGEX REPLACE "@[0-9]+$" "" _sdk_symbol "${_sdk_symbol}")
      if(_sdk_symbol MATCHES "^(${_sdk_windows_host_names})$")
        message(FATAL_ERROR "Ambient host symbol found in runtime: ${_sdk_symbol}")
      endif()
      if(_sdk_symbol MATCHES "^gn_test_")
        message(FATAL_ERROR "Private test hook leaked into public runtime: ${_sdk_symbol}")
      endif()
    endif()
  endforeach()
  if(_sdk_external_count EQUAL 0)
    message(FATAL_ERROR "Runtime inspector produced no external COFF symbols")
  endif()
else()
execute_process(COMMAND "${_sdk_nm}" -u "${_sdk_library}"
  RESULT_VARIABLE _sdk_nm_result OUTPUT_VARIABLE _sdk_symbols ERROR_VARIABLE _sdk_nm_error)
if(NOT _sdk_nm_result EQUAL 0)
  message(FATAL_ERROR "Could not inspect runtime symbols: ${_sdk_nm_error}")
endif()
if(_sdk_symbols MATCHES "(^|[^A-Za-z0-9_])_?(fopen|freopen|fread|fwrite|remove|rename|open|close|read|write|time|clock|gettimeofday|socket|connect|accept|system|fork|execve|pthread_create|pthread_mutex_lock)($|[^A-Za-z0-9_])")
  message(FATAL_ERROR "Ambient host symbol found in runtime: ${_sdk_symbols}")
endif()
execute_process(COMMAND "${_sdk_nm}" -g "${_sdk_library}"
  RESULT_VARIABLE _sdk_global_nm_result OUTPUT_VARIABLE _sdk_global_symbols
  ERROR_VARIABLE _sdk_global_nm_error)
if(NOT _sdk_global_nm_result EQUAL 0)
  message(FATAL_ERROR "Could not inspect runtime exports: ${_sdk_global_nm_error}")
endif()
if(_sdk_global_symbols MATCHES "gn_test_")
  message(FATAL_ERROR "Private test hook leaked into public runtime: ${_sdk_global_symbols}")
endif()
endif()
message(STATUS "SDK runtime host-call closure passed for ${_sdk_library}")
]=])
  string(CONFIGURE "${SDK_HOST_CLOSURE_CONTENT}" SDK_HOST_CLOSURE_CONTENT @ONLY)
  file(GENERATE OUTPUT "${SDK_HOST_CLOSURE_SCRIPT}" CONTENT "${SDK_HOST_CLOSURE_CONTENT}")
  add_test(NAME sdk_host_closure COMMAND ${CMAKE_COMMAND} -P "${SDK_HOST_CLOSURE_SCRIPT}")
  set_tests_properties(sdk_host_closure PROPERTIES LABELS "sdk-lifecycle;sdk-capabilities")
  add_test(NAME sdk_fixture_write
    COMMAND glueyneo-diagnostic --write-fixture
            ${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin)
  set_tests_properties(sdk_fixture_write PROPERTIES
    FIXTURES_SETUP sdk_fixture_a
    LABELS "sdk-provenance"
  )
  add_test(NAME sdk_provenance
    COMMAND glueyneo-diagnostic --check-fixture
            ${CMAKE_CURRENT_BINARY_DIR}/diagnostic-original-a.bin)
  set_tests_properties(sdk_provenance PROPERTIES
    FIXTURES_REQUIRED sdk_fixture_a
    LABELS "sdk-provenance"
  )

  set(GLUEYNEO_CONSUMER_CHECK
    "${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/check_package.py")
  add_test(NAME sdk_package_build_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case build-static)
  add_test(NAME sdk_package_build_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case build-shared)
  add_test(NAME sdk_package_consumers_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case consumers-static --sound-reference "${GLUEYNEO_SOUND_REFERENCE}")
  add_test(NAME sdk_package_consumers_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case consumers-shared --sound-reference "${GLUEYNEO_SOUND_REFERENCE}")
  set_tests_properties(sdk_package_consumers_static sdk_package_consumers_shared
    PROPERTIES FIXTURES_REQUIRED sdk_sound_reference)
  add_test(NAME sdk_example_continuation_static
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_continuation_install.py
            --variant static --mode process)
  add_test(NAME sdk_example_continuation_shared
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_continuation_install.py
            --variant shared --mode process)
  set_tests_properties(sdk_example_continuation_static sdk_example_continuation_shared
    PROPERTIES LABELS "sdk-example-continuation" TIMEOUT 600)
  add_test(NAME sdk_example_persistence_static
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_persistence_install.py
            --variant static --mode full)
  add_test(NAME sdk_example_persistence_shared
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_persistence_install.py
            --variant shared --mode full)
  add_test(NAME sdk_example_persistence_faults
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_persistence_install.py
            --variant static --mode faults)
  set_tests_properties(sdk_example_persistence_static sdk_example_persistence_shared
    sdk_example_persistence_faults
    PROPERTIES LABELS "sdk-example-persistence" TIMEOUT 900)
  add_test(NAME sdk_package_docs_static
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-static)
  add_test(NAME sdk_package_docs_shared
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-shared)
  add_test(NAME sdk_package_docs_readme
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case docs-readme)
  add_test(NAME sdk_example_docs
    COMMAND ${Python3_EXECUTABLE}
            ${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_example_docs.py
            --mode commands)
  add_test(NAME sdk_package_capabilities
    COMMAND ${Python3_EXECUTABLE} "${GLUEYNEO_CONSUMER_CHECK}"
            --case capabilities)
  set_tests_properties(sdk_package_build_static sdk_package_build_shared
    PROPERTIES LABELS "sdk-package-build" TIMEOUT 360)
  set_tests_properties(sdk_package_consumers_static sdk_package_consumers_shared
    PROPERTIES LABELS "sdk-package-consumers" TIMEOUT 360)
  set_tests_properties(sdk_package_docs_static sdk_package_docs_shared sdk_package_docs_readme
    PROPERTIES LABELS "sdk-package-docs" TIMEOUT 600)
  set_tests_properties(sdk_example_docs
    PROPERTIES LABELS "sdk-package-docs" TIMEOUT 900)
  set_tests_properties(sdk_package_capabilities
    PROPERTIES LABELS "sdk-package-capabilities" TIMEOUT 180)

  # Qualification tooling regressions (redaction, sink scans, evidence gate)
  # run in every local CTest and in the clean qualification's full CTest lane.
  add_test(NAME qualification_private_paths
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_private_paths.py")
  add_test(NAME qualification_runner
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_verify_playable.py")
  # G6WR-01: the allowlist pins are self-attested, so the freshness and history
  # check is the verifier. It needs the full pre-ship branch history and refuses
  # on a squashed or shallow checkout, including main after the squash merge, so
  # it is opt-in here; CI runs it on every pull request to which it applies
  # (docs/testing.md).
  if(GLUEYNEO_PRE_SHIP_HISTORY_CHECK)
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.git"
       OR NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/docs/history-allowlist.json")
      message(FATAL_ERROR "GLUEYNEO_PRE_SHIP_HISTORY_CHECK needs a Git checkout that tracks docs/history-allowlist.json")
    endif()
    add_test(NAME qualification_history_allowlist
      COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tools/verify_playable.py"
              --history-allowlist check --base "${GLUEYNEO_HISTORY_BASE}")
    set_tests_properties(qualification_history_allowlist
      PROPERTIES LABELS "qualification-tools" TIMEOUT 120)
  endif()
  add_test(NAME qualification_independent_review
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_independent_review.py")
  add_test(NAME qualification_check_package
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/consumers/test_check_package.py")
  add_test(NAME qualification_frontend_smoke
    COMMAND ${Python3_EXECUTABLE} -m unittest discover
            -s "${CMAKE_CURRENT_SOURCE_DIR}/tests/libretro" -p test_retroarch_smoke.py)
  set_property(TEST qualification_frontend_smoke APPEND PROPERTY ENVIRONMENT
    "GLUEYNEO_MVS_OBSERVATION_TEST=$<TARGET_FILE:mvs_observations_test>")
  add_test(NAME libretro_frontend_registration
    COMMAND ${Python3_EXECUTABLE} -B
            "${CMAKE_CURRENT_SOURCE_DIR}/tests/libretro/test_frontend_registration.py"
            --build-dir "${CMAKE_CURRENT_BINARY_DIR}" --mode registration)
  set_tests_properties(libretro_frontend_registration PROPERTIES
    LABELS "libretro;qualification-tools" TIMEOUT 120)
  add_test(NAME qualification_frontend_replay
    COMMAND ${Python3_EXECUTABLE} -B -m unittest discover
            -s "${CMAKE_CURRENT_SOURCE_DIR}/tests/libretro" -p test_frontend_replay.py)
  set_tests_properties(qualification_frontend_replay PROPERTIES
    LABELS "qualification-tools;libretro" TIMEOUT 30)
  # The register consistency check reads planning state, which a source archive
  # may not carry. An empty GLUEYNEO_PLANNING_WORKSTREAM means auto: the default
  # workstream is checked when its directory exists and silently skipped when it
  # does not. An explicitly set name that does not exist fails configure, so a
  # misconfiguration cannot silently drop the gate. The CTest is a consistency
  # check only; closure is `check_security_register.py --require-closed`
  # (docs/testing.md, "Closure gates"). The mutation suite stays unconditional.
  set(GLUEYNEO_PLANNING_WORKSTREAM "" CACHE STRING
    "Workstream under .planning/workstreams whose security registers planning_security_register_consistency checks (empty: first-playable-game when present)")
  if(GLUEYNEO_PLANNING_WORKSTREAM STREQUAL "")
    set(_glueyneo_workstream "first-playable-game")
  else()
    set(_glueyneo_workstream "${GLUEYNEO_PLANNING_WORKSTREAM}")
    if(NOT EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.planning/workstreams/${_glueyneo_workstream}")
      # CMake word-wraps long messages; the break keeps the phrase on one line.
      message(FATAL_ERROR
        "GLUEYNEO_PLANNING_WORKSTREAM=${_glueyneo_workstream}\n"
        "names no .planning/workstreams directory")
    endif()
  endif()
  if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/.planning/workstreams/${_glueyneo_workstream}")
    add_test(NAME planning_security_register_consistency
      COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/check_security_register.py"
              "${_glueyneo_workstream}")
    set_tests_properties(planning_security_register_consistency
      PROPERTIES LABELS "qualification-tools" TIMEOUT 300)
  else()
    message(STATUS "planning_security_register_consistency not registered: "
      ".planning/workstreams/${_glueyneo_workstream} does not exist")
  endif()
  add_test(NAME planning_security_register_mutations
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_check_security_register.py")
  # The duplicated runtime copies in libretro_callback_test must share no
  # mutable state: reject any writable or zero-initialized runtime symbol.
  set(GLUEYNEO_STORAGE_AUDIT_TARGET glueyneo_runtime_static)
  if(NOT GLUEYNEO_SDK_SANITIZER STREQUAL "NONE")
    # Sanitizers inject writable registration/diagnostic metadata. Keep the
    # strict symbol audit (no symbol allowlist), but inspect the exact same
    # production sources/properties with instrumentation explicitly disabled.
    add_library(glueyneo_storage_audit STATIC ${GLUEYNEO_RUNTIME_SOURCES})
    foreach(property C_STANDARD C_STANDARD_REQUIRED C_EXTENSIONS
        CXX_STANDARD CXX_STANDARD_REQUIRED CXX_EXTENSIONS
        CXX_VISIBILITY_PRESET VISIBILITY_INLINES_HIDDEN
        POSITION_INDEPENDENT_CODE C_VISIBILITY_PRESET INCLUDE_DIRECTORIES
        SYSTEM_INCLUDE_DIRECTORIES COMPILE_DEFINITIONS COMPILE_OPTIONS)
      get_target_property(value glueyneo_runtime_static ${property})
      if(NOT value STREQUAL "value-NOTFOUND")
        set_property(TARGET glueyneo_storage_audit PROPERTY ${property} "${value}")
      endif()
    endforeach()
    target_include_directories(glueyneo_storage_audit SYSTEM PRIVATE
      ${CMAKE_CURRENT_SOURCE_DIR}/third_party/chips
      ${CMAKE_CURRENT_SOURCE_DIR}/third_party/ymfm/src)
    target_compile_options(glueyneo_storage_audit PRIVATE -fno-sanitize=all)
    set(GLUEYNEO_STORAGE_AUDIT_TARGET glueyneo_storage_audit)
    set(GLUEYNEO_STORAGE_AUDIT_ARGS
      --compile-commands "${CMAKE_BINARY_DIR}/compile_commands.json")
  endif()
  add_test(NAME runtime_writable_storage
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/check_runtime_storage.py"
            --nm "${CMAKE_NM}" ${GLUEYNEO_STORAGE_AUDIT_ARGS}
            "$<TARGET_FILE:${GLUEYNEO_STORAGE_AUDIT_TARGET}>")
  add_test(NAME runtime_host_source_audit
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_check_runtime_host.py")
  add_test(NAME runtime_writable_storage_audit
    COMMAND ${Python3_EXECUTABLE} "${CMAKE_CURRENT_SOURCE_DIR}/tests/tools/test_check_runtime_storage.py")
  set_tests_properties(runtime_writable_storage PROPERTIES SKIP_RETURN_CODE 77)
  set_tests_properties(qualification_private_paths qualification_runner qualification_check_package
    qualification_independent_review
    qualification_frontend_smoke
    planning_security_register_mutations runtime_writable_storage runtime_writable_storage_audit
    runtime_host_source_audit
    PROPERTIES LABELS "qualification-tools" TIMEOUT 300)

  # CI builds tests only against a static libglueyneo, where hidden private
  # symbols still link. Reject at configure time any executable that includes
  # the private SDK header while linking the public library, because that
  # combination fails to link once BUILD_SHARED_LIBS=ON. It is deliberately
  # enforced in static builds as the early warning for that shared-build link
  # failure.
  #
  # Limits (best-effort, an accepted residual): it inspects direct .c/.cpp
  # sources only (not headers or transitive sources), top-level targets of this
  # directory only, and ignores links written as generator expressions.
  # libretro_callback_test intentionally links two runtime copies (the core's
  # private copy and the independent native reference); the
  # runtime_writable_storage test is the control proving those copies share no
  # mutable global state, not this guard.
  get_property(_glueyneo_targets DIRECTORY PROPERTY BUILDSYSTEM_TARGETS)
  foreach(_target IN LISTS _glueyneo_targets)
    get_target_property(_type ${_target} TYPE)
    if(NOT _type STREQUAL "EXECUTABLE")
      continue()
    endif()
    get_target_property(_links ${_target} LINK_LIBRARIES)
    if(NOT _links)
      continue()
    endif()
    list(FIND _links glueyneo _plain)
    list(FIND _links Glueyneo::glueyneo _alias)
    if(_plain EQUAL -1 AND _alias EQUAL -1)
      continue()
    endif()
    get_target_property(_sources ${_target} SOURCES)
    foreach(_source IN LISTS _sources)
      if(NOT _source MATCHES "\\.(c|cpp)$")
        continue()
      endif()
      if(NOT IS_ABSOLUTE "${_source}")
        set(_source "${CMAKE_CURRENT_SOURCE_DIR}/${_source}")
      endif()
      file(STRINGS "${_source}" _private_includes REGEX "sdk_private\\.h")
      if(_private_includes)
        message(FATAL_ERROR
          "${_target} includes src/sdk_private.h but links the public "
          "glueyneo library; link glueyneo_runtime_static or glueyneo_test")
      endif()
    endforeach()
  endforeach()
endif()

if(GLUEYNEO_CPU_EXPERIMENT)
  add_subdirectory(experiments/cpu)
endif()
if(GLUEYNEO_OWNED_CPU_EXPERIMENT)
  add_subdirectory(experiments/owned_cpu)
endif()
